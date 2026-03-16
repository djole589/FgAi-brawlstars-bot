"""
FgAi ESP Overlay
================
- Always visible as soon as bot starts (no F2 needed to show)
- F2 toggles it OFF/ON if you want
- Only GREEN boxes for all detections
- Class name drawn next to each box (right side)
- Zero startup delay — shows immediately
- Smooth 60fps render loop
- Reads bot frame dimensions directly for pixel-perfect accuracy
"""

import threading
import time
import tkinter as tk
import win32gui
import warnings
from typing import Optional

# Suppress harmless tkinter GC warning from non-main thread
warnings.filterwarnings("ignore", category=RuntimeWarning, module="tkinter")
try:
    import keyboard
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False
    print("[Overlay] 'keyboard' module niet gevonden. Run: pip install keyboard")

# ── Shared state ──────────────────────────────────────────────────────────────
_lock   = threading.Lock()
_latest: dict = {}
_enabled       = True          # ON by default — no need to press anything
_thread: Optional[threading.Thread] = None
_root:   Optional[tk.Tk]            = None

# ── Single color for all boxes ────────────────────────────────────────────────
ESP_COLOR   = "#00FF88"        # bright green
SHADOW      = "#003322"        # dark shadow for text readability
BG_KEY      = "gray1"          # transparentcolor key (near-black, not used elsewhere)

# ── Emulator window titles to search ─────────────────────────────────────────
_EMU_TITLES = ["LDPlayer", "LDPlayer4", "LDPlayer9", "雷电模拟器",
               "LD Player", "BlueStacks", "BlueStacks App Player", "MEmu"]

# ── Class label names ─────────────────────────────────────────────────────────
_LABELS = {
    "enemy":    "ENEMY",
    "player":   "PLAYER",
    "teammate": "TEAMMATE",
    "wall":     "WALL",
    "bush":     "BUSH",
    "tile":     "WALL",
}


# ── Public API ────────────────────────────────────────────────────────────────

def push(detections: dict, walls: list = None):
    """Called by play.py every detection frame. Thread-safe."""
    data = {}
    if detections:
        for k, v in detections.items():
            if v:
                data[k] = v
    if walls:
        data["wall"] = walls
    with _lock:
        _latest.clear()
        _latest.update(data)


def start():
    """Start overlay thread. Call once at bot init."""
    global _thread, _enabled
    if _thread and _thread.is_alive():
        return
    _enabled = True
    _thread = threading.Thread(target=_run, daemon=True, name="FgAiESP")
    _thread.start()


def stop():
    global _enabled
    _enabled = False


def is_enabled():
    return _enabled


# ── Window finder ─────────────────────────────────────────────────────────────

def _find_emulator():
    """Returns (x, y, w, h) of emulator window or None."""
    found = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        for t in _EMU_TITLES:
            if t.lower() in title.lower():
                try:
                    x, y, x2, y2 = win32gui.GetWindowRect(hwnd)
                    w, h = x2 - x, y2 - y
                    if w > 200 and h > 200:
                        found.append((x, y, w, h))
                except Exception:
                    pass

    win32gui.EnumWindows(_cb, None)
    return found[0] if found else None


# ── Main overlay thread ───────────────────────────────────────────────────────

def _run():
    global _root, _enabled

    root = tk.Tk()
    _root = root

    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", BG_KEY)
    root.attributes("-alpha", 1.0)
    root.configure(bg=BG_KEY)

    cv = tk.Canvas(root, bg=BG_KEY, highlightthickness=0, cursor="none")
    cv.pack(fill="both", expand=True)

    # Global F toggle — polling thread, works even when game has focus
    def _toggle():
        global _enabled
        _enabled = not _enabled
        if not _enabled:
            cv.delete("all")

    def _hotkey_poller():
        was_pressed = False
        while True:
            try:
                if _HAS_KEYBOARD:
                    pressed = keyboard.is_pressed("f")
                    if pressed and not was_pressed:
                        _toggle()
                    was_pressed = pressed
                time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

    threading.Thread(target=_hotkey_poller, daemon=True, name="HotkeyF").start()

    # Cache emulator position — re-check every 30 frames to avoid lag
    _emu_cache   = [None]
    _emu_counter = [0]
    _fps_times   = []

    def _render():
        t0 = time.perf_counter()

        # Re-find emulator window periodically
        _emu_counter[0] += 1
        if _emu_counter[0] >= 30 or _emu_cache[0] is None:
            _emu_cache[0] = _find_emulator()
            _emu_counter[0] = 0

        emu = _emu_cache[0]

        if emu is None:
            root.after(16, _render)
            return

        ex, ey, ew, eh = emu

        # Reposition overlay window over emulator (only if moved)
        cur_geo = f"{ew}x{eh}+{ex}+{ey}"
        try:
            if root.winfo_width() != ew or root.winfo_height() != eh \
               or root.winfo_x() != ex or root.winfo_y() != ey:
                root.geometry(cur_geo)
                cv.config(width=ew, height=eh)
        except Exception:
            root.geometry(cur_geo)

        root.deiconify()
        cv.delete("all")

        if not _enabled:
            root.after(16, _render)
            return

        # ── Grab latest data ──────────────────────────────────────────────────
        with _lock:
            data = {k: list(v) for k, v in _latest.items() if v}

        # ── Scale factor ──────────────────────────────────────────────────────
        # Bot detections are in scrcpy native frame coords (same as emulator window)
        # So 1:1 mapping — no scaling needed, boxes already match pixel positions
        sx = 1.0
        sy = 1.0

        # ── Draw boxes ────────────────────────────────────────────────────────
        for cls, boxes in data.items():
            label = _LABELS.get(cls, cls.upper())

            for box in boxes:
                if len(box) < 4:
                    continue

                x1 = int(box[0] * sx)
                y1 = int(box[1] * sy)
                x2 = int(box[2] * sx)
                y2 = int(box[3] * sy)

                bw = x2 - x1
                bh = y2 - y1
                if bw < 2 or bh < 2:
                    continue

                # Full rectangle box (clean, no gaps)
                cv.create_rectangle(x1, y1, x2, y2,
                                    outline=ESP_COLOR, width=2, fill="")

                # Label: right side of box, vertically centered
                lx = x2 + 4
                ly = y1 + bh // 2

                # Shadow
                cv.create_text(lx + 1, ly + 1, text=label,
                               fill=SHADOW,
                               font=("Consolas", 9, "bold"),
                               anchor="w")
                # Label
                cv.create_text(lx, ly, text=label,
                               fill=ESP_COLOR,
                               font=("Consolas", 9, "bold"),
                               anchor="w")

        # ── FPS counter top-left ──────────────────────────────────────────────
        _fps_times.append(t0)
        while _fps_times and t0 - _fps_times[0] > 1.0:
            _fps_times.pop(0)
        fps = len(_fps_times)

        total = sum(len(v) for v in data.values())
        hud = f"FgAi ESP  {fps}fps  [{total} obj]  F=toggle(global)"

        cv.create_text(9, 9, text=hud, fill=SHADOW,
                       font=("Consolas", 10, "bold"), anchor="nw")
        cv.create_text(8, 8, text=hud, fill=ESP_COLOR,
                       font=("Consolas", 10, "bold"), anchor="nw")

        # ── Schedule next frame (~60fps) ──────────────────────────────────────
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        delay = max(1, 16 - elapsed_ms)   # target 60fps
        root.after(delay, _render)

    # Start immediately — no initial delay
    root.after(1, _render)
    root.mainloop()
