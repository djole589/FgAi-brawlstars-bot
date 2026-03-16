import cv2
import numpy as np
from PIL import Image
import onnxruntime as ort
from ultralytics.utils.nms import non_max_suppression
import torch
from utils import load_toml_as_dict


class Detect:
    def __init__(self, model_path, ignore_classes=None, classes=None, input_size=(640, 640)):
        self.preferred_device = load_toml_as_dict("cfg/general_config.toml")['cpu_or_gpu']
        self.model_path      = model_path
        self.classes         = classes
        self.ignore_classes  = set(ignore_classes) if ignore_classes else set()
        self.input_size      = input_size

        # ── Pre-allocate reusable buffers (avoids GC pressure every frame) ───
        self._pad_buf = np.full(
            (input_size[0], input_size[1], 3), 128, dtype=np.uint8)
        self._inp_buf = np.empty(
            (1, 3, input_size[0], input_size[1]), dtype=np.float32)

        self.model, self.device = self._load_model()

        # Cache input name so we don't look it up every inference
        self._input_name = self.model.get_inputs()[0].name

    # ── Model loader ──────────────────────────────────────────────────────────
    def _load_model(self):
        avail = ort.get_available_providers()
        pref  = self.preferred_device

        if pref in ("gpu", "auto"):
            if "CUDAExecutionProvider" in avail:
                provider = "CUDAExecutionProvider"
                print(f"[Detect] Using CUDA GPU  ({self.model_path})")
            elif "DmlExecutionProvider" in avail:
                provider = "DmlExecutionProvider"
                print(f"[Detect] Using DirectML GPU  ({self.model_path})")
            else:
                provider = "CPUExecutionProvider"
                print(f"[Detect] No GPU found, using CPU  ({self.model_path})")
        else:
            provider = "CPUExecutionProvider"
            print(f"[Detect] Using CPU  ({self.model_path})")

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Allow ONNX to use multiple CPU threads for post-processing
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 2

        model = ort.InferenceSession(
            self.model_path, sess_options=opts, providers=[provider])
        return model, provider

    # ── Preprocessing ─────────────────────────────────────────────────────────
    def _preprocess(self, img: np.ndarray):
        """
        img: BGR numpy array (H, W, 3) uint8
        Returns: (input_tensor float32 (1,3,H,W), resized_w, resized_h)
        Uses pre-allocated buffers — zero heap allocation per frame.
        """
        h, w = img.shape[:2]
        scale  = min(self.input_size[0] / h, self.input_size[1] / w)
        new_w  = int(w * scale)
        new_h  = int(h * scale)

        # Resize into pre-allocated pad buffer
        self._pad_buf[:] = 128
        cv2.resize(img, (new_w, new_h),
                   dst=self._pad_buf[:new_h, :new_w],
                   interpolation=cv2.INTER_LINEAR)

        # BGR → RGB, uint8 → float32, HWC → CHW, add batch dim
        # All in one shot using numpy views — no extra copies
        rgb = cv2.cvtColor(self._pad_buf, cv2.COLOR_BGR2RGB)
        np.divide(rgb.transpose(2, 0, 1)[np.newaxis],
                  255.0,
                  out=self._inp_buf,
                  casting='unsafe')

        return self._inp_buf, new_w, new_h

    # ── Postprocessing ────────────────────────────────────────────────────────
    def _postprocess(self, raw_output, orig_h, orig_w, new_w, new_h, conf_thresh):
        preds = non_max_suppression(
            torch.from_numpy(raw_output),
            conf_thres=conf_thresh,
            iou_thres=0.6,
            classes=None,
            agnostic=False,
        )

        scale_w = orig_w / new_w
        scale_h = orig_h / new_h

        results = {}
        for pred in preds:
            if not len(pred):
                continue
            arr = pred.cpu().numpy()
            arr[:, 0] *= scale_w
            arr[:, 1] *= scale_h
            arr[:, 2] *= scale_w
            arr[:, 3] *= scale_h

            for *xyxy, conf, cls in arr:
                cls_id   = int(cls)
                cls_name = self.classes[cls_id]
                if cls_id in self.ignore_classes or cls_name in self.ignore_classes:
                    continue
                if cls_name not in results:
                    results[cls_name] = []
                results[cls_name].append([int(xyxy[0]), int(xyxy[1]),
                                          int(xyxy[2]), int(xyxy[3])])
        return results

    # ── Public API ────────────────────────────────────────────────────────────
    def detect_objects(self, img, conf_tresh=0.6):
        """
        img: PIL Image OR numpy array (BGR or RGB)
        Returns: dict {class_name: [[x1,y1,x2,y2], ...]}
        """
        # Convert to BGR numpy once — no double conversions
        if isinstance(img, Image.Image):
            bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        elif isinstance(img, np.ndarray):
            bgr = img if img.shape[2] == 3 else cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            raise TypeError(f"Unsupported image type: {type(img)}")

        orig_h, orig_w = bgr.shape[:2]

        inp, new_w, new_h = self._preprocess(bgr)

        # Run inference — pass numpy directly, skip torch round-trip
        raw = self.model.run(None, {self._input_name: inp})[0]

        return self._postprocess(raw, orig_h, orig_w, new_w, new_h, conf_tresh)
