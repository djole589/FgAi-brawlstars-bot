import json
import tkinter as tk
from math import ceil

import customtkinter as ctk
import pyautogui
from PIL import Image, ImageDraw
from customtkinter import CTkImage
from utils import load_toml_as_dict, update_toml_file, save_brawler_icon, get_dpi_scale
from tkinter import filedialog

debug = load_toml_as_dict("cfg/general_config.toml")['super_debug'] == "yes"
orig_w, orig_h = 1920, 1080
sw, sh = pyautogui.size()
scale_factor = min(sw / orig_w, sh / orig_h) * (96 / get_dpi_scale())
ver = load_toml_as_dict("./cfg/general_config.toml")['pyla_version']

def S(v): return int(v * scale_factor)

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#0A0A10"
SURF    = "#10101A"
CARD    = "#14141F"
CARD_HOV = "#1C1C2C"
CARD_S  = "#1A1A2E"   # selected
BORDER  = "#222236"
BORD_H  = "#FF6B00"
ACC     = "#FF6B00"
ACC2    = "#E05500"
TEXT    = "#EEEEF5"
SUB     = "#666688"
GREEN   = "#00FF88"
RED     = "#FF3355"
INP     = "#0C0C18"
STRIPE  = "#FF6B00"

COLS     = 10
ICON_SZ  = S(64)
CARD_W   = ICON_SZ + S(14)
CARD_HEIGHT  = ICON_SZ + S(20)
GAP      = S(4)


class SelectBrawler:

    def __init__(self, data_setter, brawlers):
        ctk.set_appearance_mode("dark")

        self.brawlers      = brawlers
        self.data_setter   = data_setter
        self.images        = []
        self.queue         = []     # list of configured brawler dicts
        self._sel          = set()  # selected brawler names
        self.farm_type     = "trophies"

        # ── Load icons ────────────────────────────────────────────────────────
        for b in brawlers:
            p = f"./api/assets/brawler_icons/{b}.png"
            try:
                img = Image.open(p)
            except FileNotFoundError:
                save_brawler_icon(b)
                img = Image.open(p)
            self.images.append((b, CTkImage(img, size=(ICON_SZ, ICON_SZ))))

        # ── Window ────────────────────────────────────────────────────────────
        n_rows  = ceil(len(brawlers) / COLS)
        grid_w  = COLS * CARD_W + (COLS + 1) * GAP
        win_w   = max(grid_w + S(32), S(900))
        grid_h  = n_rows * CARD_HEIGHT + (n_rows + 1) * GAP
        win_h   = S(88) + S(48) + grid_h + S(48) + S(24)

        ox = max(0, (sw - win_w) // 2)
        oy = max(0, (sh - win_h) // 2 - 30)

        self.app = ctk.CTk()
        self.app.configure(fg_color=BG)
        self.app.title(f"FgAi Bot  v{ver}")
        self.app.geometry(f"{win_w}x{win_h}+{ox}+{oy}")
        self.app.resizable(False, False)

        self._build(win_w, win_h)
        self.app.mainloop()

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self, win_w, win_h):

        # Orange top stripe
        tk.Frame(self.app, bg=STRIPE, height=S(3)).pack(fill="x")

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self.app, fg_color=SURF, height=S(85), corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left: logo
        logo = ctk.CTkFrame(hdr, fg_color="transparent")
        logo.place(x=S(22), rely=0.5, anchor="w")

        ctk.CTkLabel(logo, text="Fg", font=("Impact", S(36)),
                     text_color=ACC).pack(side="left")
        ctk.CTkLabel(logo, text="Ai", font=("Impact", S(36)),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="  BRAWLSTARS BOT",
                     font=("Segoe UI", S(12), "bold"),
                     text_color=SUB).pack(side="left", pady=(S(14), 0))

        # Right: queue badge
        self._q_var = tk.StringVar(value="0 queued")
        q_frame = ctk.CTkFrame(hdr,
                               fg_color=CARD, corner_radius=S(8),
                               border_color=BORDER, border_width=1)
        q_frame.place(relx=1.0, x=-S(22), rely=0.5, anchor="e")

        ctk.CTkLabel(q_frame, text="QUEUE",
                     font=("Segoe UI", S(9), "bold"),
                     text_color=SUB).pack(padx=S(14), pady=(S(6), 0))
        ctk.CTkLabel(q_frame, textvariable=self._q_var,
                     font=("Impact", S(22)),
                     text_color=ACC).pack(padx=S(14), pady=(0, S(6)))

        # ── Toolbar ───────────────────────────────────────────────────────────
        tb = ctk.CTkFrame(self.app, fg_color=CARD, height=S(46), corner_radius=0)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        # Search
        self.fv = tk.StringVar()
        ctk.CTkEntry(tb, textvariable=self.fv,
                     placeholder_text="🔍  Search brawler...",
                     font=("Segoe UI", S(12)),
                     width=S(190), height=S(30),
                     fg_color=INP, border_color=BORDER, border_width=1,
                     text_color=TEXT, corner_radius=S(6)
                     ).pack(side="left", padx=(S(12), S(8)), pady=S(8))
        self.fv.trace_add("write", lambda *_: self._redraw(self.fv.get()))

        # Divider
        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y",
                                               padx=S(4), pady=S(8))

        # Timer
        ctk.CTkLabel(tb, text="Run", font=("Segoe UI", S(11)),
                     text_color=SUB).pack(side="left", padx=(S(8), S(4)))
        self.tv = tk.StringVar(value=str(
            load_toml_as_dict("cfg/general_config.toml")["run_for_minutes"]))
        ctk.CTkEntry(tb, textvariable=self.tv,
                     placeholder_text="∞",
                     font=("Consolas", S(12)),
                     width=S(52), height=S(30),
                     fg_color=INP, border_color=BORDER, border_width=1,
                     text_color=ACC, corner_radius=S(6), justify="center"
                     ).pack(side="left")
        ctk.CTkLabel(tb, text=" min",
                     font=("Segoe UI", S(11)), text_color=SUB).pack(side="left")
        self.tv.trace_add("write", lambda *_: self._save_timer())

        # Load config
        ctk.CTkButton(tb, text="📂  Config",
                      command=self._load_cfg,
                      fg_color=CARD_HOV, hover_color=SURF,
                      border_color=BORDER, border_width=1,
                      text_color=TEXT, font=("Segoe UI", S(11), "bold"),
                      corner_radius=S(6), width=S(100), height=S(30)
                      ).pack(side="left", padx=S(10))

        # START (right)
        ctk.CTkButton(tb, text="▶  START",
                      command=self._start,
                      fg_color=ACC, hover_color=ACC2,
                      text_color="#fff",
                      font=("Segoe UI Black", S(12), "bold"),
                      corner_radius=S(6), width=S(110), height=S(32)
                      ).pack(side="right", padx=S(12), pady=S(7))

        # Clear queue
        ctk.CTkButton(tb, text="✖  Clear",
                      command=self._clear_queue,
                      fg_color="transparent", hover_color=CARD_HOV,
                      border_color=BORDER, border_width=1,
                      text_color=RED, font=("Segoe UI", S(10), "bold"),
                      corner_radius=S(6), width=S(72), height=S(28)
                      ).pack(side="right", padx=(0, S(4)))

        # ── Grid ──────────────────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self.app, fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACC,
            corner_radius=0)
        self._scroll.pack(fill="both", expand=True,
                          padx=S(12), pady=(S(6), S(2)))

        self._grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid.pack(anchor="nw")
        self._redraw("")

        # ── Status bar ────────────────────────────────────────────────────────
        sb = ctk.CTkFrame(self.app, fg_color=SURF, height=S(22), corner_radius=0)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._sv = tk.StringVar(value="Click a brawler to configure it")
        ctk.CTkLabel(sb, textvariable=self._sv,
                     font=("Segoe UI", S(9)), text_color=SUB
                     ).pack(side="left", padx=S(10))

    # ── Grid render ───────────────────────────────────────────────────────────
    def _redraw(self, flt=""):
        for w in self._grid.winfo_children():
            w.destroy()

        row = col = 0
        for brawler, img in self.images:
            if flt and not brawler.lower().startswith(flt.lower()):
                continue

            sel = brawler in self._sel
            card = ctk.CTkFrame(
                self._grid,
                fg_color=CARD_S if sel else CARD,
                border_color=ACC if sel else BORDER,
                border_width=S(1) if sel else 1,
                corner_radius=S(7),
                width=CARD_W, height=CARD_HEIGHT)
            card.grid(row=row, column=col, padx=GAP//2, pady=GAP//2)
            card.grid_propagate(False)

            il = ctk.CTkLabel(card, image=img, text="", cursor="hand2")
            il.place(relx=0.5, rely=0.42, anchor="center")

            nl = ctk.CTkLabel(card, text=brawler[:9],
                              font=("Segoe UI", S(7)),
                              text_color=ACC if sel else SUB)
            nl.place(relx=0.5, rely=0.90, anchor="center")

            # Tiny checkmark if selected
            if sel:
                ctk.CTkLabel(card, text="✔",
                             font=("Segoe UI", S(8), "bold"),
                             text_color=GREEN,
                             fg_color=CARD_S
                             ).place(relx=0.88, rely=0.08, anchor="center")

            def _e(e, c=card, b=brawler):
                if b not in self._sel:
                    c.configure(fg_color=CARD_HOV, border_color=BORD_H)

            def _l(e, c=card, b=brawler):
                if b not in self._sel:
                    c.configure(fg_color=CARD, border_color=BORDER)

            def _c(e, b=brawler):
                self._open(b)

            for w in [card, il, nl]:
                w.bind("<Enter>", _e)
                w.bind("<Leave>", _l)
                w.bind("<Button-1>", _c)

            col += 1
            if col >= COLS:
                col = 0
                row += 1

    # ── Config popup ─────────────────────────────────────────────────────────
    def _open(self, brawler):
        top = ctk.CTkToplevel(self.app)
        top.configure(fg_color=BG)
        top.title(f"{brawler}")
        top.geometry(f"{S(360)}x{S(510)}+{S(300)}+{S(180)}")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.lift(); top.focus_force()

        tk.Frame(top, bg=STRIPE, height=S(3)).place(x=0, y=0, relwidth=1)

        # Header
        h = ctk.CTkFrame(top, fg_color=SURF, height=S(48), corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(h, text=f"  ⚙  {brawler.upper()}",
                     font=("Impact", S(20)),
                     text_color=ACC).pack(side="left", pady=S(10))

        body = ctk.CTkFrame(top, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=S(20), pady=S(6))

        # Farm type
        ctk.CTkLabel(body, text="FARM TYPE",
                     font=("Segoe UI", S(9), "bold"),
                     text_color=SUB, anchor="w").pack(fill="x", pady=(S(6), S(3)))

        tf = ctk.CTkFrame(body, fg_color=CARD, corner_radius=S(7))
        tf.pack(fill="x")

        _bt = [None, None]

        def _ft(t):
            self.farm_type = t
            _bt[0].configure(
                fg_color=ACC if t == "trophies" else "transparent",
                text_color="#fff" if t == "trophies" else SUB)
            _bt[1].configure(
                fg_color=ACC if t == "wins" else "transparent",
                text_color="#fff" if t == "wins" else SUB)

        _bt[0] = ctk.CTkButton(tf, text="🏆 Trophies",
                                command=lambda: _ft("trophies"),
                                fg_color=ACC if self.farm_type == "trophies" else "transparent",
                                hover_color=ACC2,
                                text_color="#fff" if self.farm_type == "trophies" else SUB,
                                font=("Segoe UI", S(11), "bold"),
                                corner_radius=S(6), width=S(148), height=S(32))
        _bt[0].pack(side="left", padx=S(3), pady=S(3))

        _bt[1] = ctk.CTkButton(tf, text="🥊 Wins",
                                command=lambda: _ft("wins"),
                                fg_color=ACC if self.farm_type == "wins" else "transparent",
                                hover_color=ACC2,
                                text_color="#fff" if self.farm_type == "wins" else SUB,
                                font=("Segoe UI", S(11), "bold"),
                                corner_radius=S(6), width=S(148), height=S(32))
        _bt[1].pack(side="left", padx=S(3), pady=S(3))

        def _inp(lbl, ph, var):
            ctk.CTkLabel(body, text=lbl,
                         font=("Segoe UI", S(9), "bold"),
                         text_color=SUB, anchor="w"
                         ).pack(fill="x", pady=(S(8), S(2)))
            ctk.CTkEntry(body, textvariable=var,
                         placeholder_text=ph,
                         font=("Consolas", S(12)),
                         fg_color=INP, border_color=BORDER, border_width=1,
                         text_color=TEXT, corner_radius=S(6), height=S(33)
                         ).pack(fill="x")

        pv = tk.StringVar(); tv2 = tk.StringVar()
        wv = tk.StringVar(); sv  = tk.StringVar(value="0")
        av = tk.BooleanVar(value=True)

        _inp("TARGET AMOUNT",    "e.g. 500",  pv)
        _inp("CURRENT TROPHIES", "e.g. 300",  tv2)
        _inp("CURRENT WINS",     "e.g. 0",    wv)
        _inp("WIN STREAK",       "0",         sv)

        ctk.CTkCheckBox(body, text="Auto-select brawler",
                        variable=av,
                        font=("Segoe UI", S(11)),
                        text_color=TEXT, fg_color=ACC,
                        hover_color=ACC2, border_color=BORDER,
                        checkmark_color="#fff", corner_radius=S(3)
                        ).pack(anchor="w", pady=(S(10), S(3)))

        tk.Frame(top, bg=BORDER, height=1).pack(fill="x", padx=S(20), pady=(S(3), 0))

        def _add():
            pu = pv.get().strip();  pu = int(pu) if pu.isdigit() else ""
            tr = tv2.get().strip(); tr = int(tr) if tr.isdigit() else 0
            wi = wv.get().strip();  wi = int(wi) if wi.isdigit() else ""
            sk = sv.get().strip();  sk = int(sk) if sk.isdigit() else 0
            if self.farm_type == "trophies" and wi == "": wi = 0
            d = {"brawler": brawler, "push_until": pu,
                 "trophies": tr, "wins": wi,
                 "type": self.farm_type or "trophies",
                 "automatically_pick": av.get(), "win_streak": sk}
            self.queue = [x for x in self.queue if x["brawler"] != brawler]
            self.queue.append(d)
            self._sel.add(brawler)
            self._q_var.set(f"{len(self.queue)} queued")
            self._sv.set(f"✔  {brawler} added  •  {len(self.queue)} total")
            self._redraw(self.fv.get())
            if debug: print("Queue:", self.queue)
            top.destroy()

        ctk.CTkButton(top, text="✔  ADD TO QUEUE",
                      command=_add,
                      fg_color=ACC, hover_color=ACC2,
                      text_color="#fff",
                      font=("Segoe UI Black", S(12), "bold"),
                      corner_radius=S(7), height=S(40)
                      ).pack(fill="x", padx=S(20), pady=S(10))

    # ── Actions ───────────────────────────────────────────────────────────────
    def _start(self):
        if not self.queue:
            self._sv.set("⚠  Add at least one brawler first!")
            return
        self.data_setter(self.queue)
        self.app.destroy()

    def _clear_queue(self):
        self.queue.clear()
        self._sel.clear()
        self._q_var.set("0 queued")
        self._sv.set("Queue cleared")
        self._redraw(self.fv.get())

    def _load_cfg(self):
        path = filedialog.askopenfilename(
            title="Load Brawler Config",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            data = [d for d in data if not (d["push_until"] <= d[d["type"]])]
            self.queue = data
            self._sel  = {d["brawler"] for d in data}
            self._q_var.set(f"{len(data)} queued")
            self._sv.set(f"✔  Loaded {len(data)} brawler(s)")
            self._redraw(self.fv.get())
        except Exception as e:
            self._sv.set(f"✖  {e}")

    def _save_timer(self):
        try:
            cfg = load_toml_as_dict("cfg/general_config.toml")
            cfg["run_for_minutes"] = int(self.tv.get())
            update_toml_file("cfg/general_config.toml", cfg)
        except ValueError:
            pass

    # legacy compat
    def set_farm_type(self, v): self.farm_type = v
    def update_timer(self, v): self._save_timer()


def dummy_data_setter(d): print("Data:", d)
