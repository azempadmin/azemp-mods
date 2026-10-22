"""
AzeMP Installer
Assetto Corsa modlarını yükləyib avtomatik düzgün qovluğa quraşdıran tətbiq.
"""

import base64
import ctypes
import io
import json
import os
import queue
import re
import ssl
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import zipfile
from tkinter import filedialog

import customtkinter as ctk
from azemp_assets import LOGO_B64, MARK_B64
from PIL import Image, ImageColor, ImageDraw, ImageOps, ImageTk

APP_NAME = "AzeMP Installer"

# ----------------------------------------------------------------------------
# MOD SİYAHISI (GitHub-dakı mods.json)
# ----------------------------------------------------------------------------
MODS_URL = "https://raw.githubusercontent.com/azempadmin/azemp-mods/main/mods.json"

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".azemp_installer.json")
USER_AGENT = "AzeMP-Installer/2.0"


def make_ssl_context():
    """Windows-un sertifikatlarına əlavə olaraq tətbiqin öz sertifikat siyahısını (certifi) da istifadə et."""
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    return ctx


SSL_CTX = make_ssl_context()

# ----------------------------------------------------------------------------
# RƏNGLƏR (qara + magenta + bənövşəyi)
# ----------------------------------------------------------------------------
BG = "#07050b"
SURFACE = "#110d18"
SURFACE2 = "#1a1426"
BORDER = "#2b2040"
MAGENTA = "#d91fd0"
MAGENTA_HOVER = "#b816af"
PURPLE = "#6d28d9"
TEXT = "#f5f0ff"
MUTED = "#9d90b5"
GREEN = "#4ade80"
ORANGE = "#fbbf24"
RED = "#fb7185"

# ----------------------------------------------------------------------------
# QURAŞDIRMA YERLƏRİ
# ----------------------------------------------------------------------------
TYPE_DIRS = {
    "car": "content/cars",
    "track": "content/tracks",
    "skin": "content/cars",
    "app": "apps/python",
    "font": "content/fonts",
    "root": "",
}

# Ana ekrandakı kateqoriyalar: (açar, başlıq, qradiyent rəngləri)
CATEGORIES = [
    ("car", "Avtomobil modları", (MAGENTA, PURPLE)),
    ("track", "Xəritə modları", (PURPLE, "#3730a3")),
    ("tool", "Vasitəçi alətlər", ("#a21caf", "#4c1d95")),
]


def category_of(mod):
    typ = str(mod.get("type", "")).lower()
    if typ in ("car", "skin"):
        return "car"
    if typ == "track":
        return "track"
    return "tool"


# Zip-in içində bu qovluqlardan biri varsa, fayllar birbaşa Assetto Corsa
# qovluğuna açılır (Content Manager kimi).
ROOT_MARKERS = {"content", "apps", "system", "extension"}

# ----------------------------------------------------------------------------
# LOQO ŞƏKİLLƏRİ azemp_assets.py faylındadır
# ----------------------------------------------------------------------------


def _img(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ----------------------------------------------------------------------------
# ŞƏKİL KÖMƏKÇİLƏRİ
# ----------------------------------------------------------------------------
def lighten(hex_color, amount):
    r, g, b = ImageColor.getrgb(hex_color)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return (r, g, b)


def gradient_rgba(w, h, c1, c2):
    """Soldan sağa c1 -> c2 qradiyent."""
    g = Image.linear_gradient("L").rotate(90, expand=True)  # sol qara, sağ ağ
    g = g.resize((w, h), Image.BILINEAR)
    rgb = ImageOps.colorize(g, black=c1, white=c2)
    return rgb.convert("RGBA")


def rounded_mask(w, h, radius, inset=0):
    ss = 3
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [inset * ss, inset * ss, w * ss - 1 - inset * ss, h * ss - 1 - inset * ss],
        radius=max(1, (radius - inset)) * ss,
        fill=255,
    )
    return m.resize((w, h), Image.LANCZOS)


def hexlight(hex_color, amount):
    r, g, b = lighten(hex_color, amount)
    return "#%02x%02x%02x" % (r, g, b)


_NORM = str.maketrans({
    "ə": "e", "Ə": "e", "ı": "i", "İ": "i", "ö": "o", "Ö": "o",
    "ü": "u", "Ü": "u", "ç": "c", "Ç": "c", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
})


def norm(s):
    """Axtarış üçün: Azərbaycan hərflərini sadələşdir (ə->e, ı->i ...) və kiçilt."""
    return str(s).translate(_NORM).lower()


def tile_image(w, h, hover, mark, radius, colors):
    mask = rounded_mask(w, h, radius)
    c1 = lighten(colors[0], 0.10 if hover else 0.0)
    c2 = lighten(colors[1], 0.14 if hover else 0.0)
    base = gradient_rgba(w, h, c1, c2)
    if mark is not None:
        mh = int(h * 0.95)
        mw = int(mark.width * mh / mark.height)
        m = mark.resize((mw, mh), Image.LANCZOS)
        a = m.getchannel("A").point(lambda v: int(v * 0.16))
        m.putalpha(a)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(m, (w - int(mw * 0.95), (h - mh) // 2 + int(h * 0.08)))
        base = Image.alpha_composite(base, layer)
    base.putalpha(mask)
    return base


def card_image(w, h, border, fill, radius):
    mask = rounded_mask(w, h, radius)
    base = Image.new("RGBA", (w, h), border)
    inner = rounded_mask(w, h, radius, inset=2)
    base.paste(Image.new("RGBA", (w, h), fill), (0, 0), inner)
    base.putalpha(mask)
    return base


def make_ico(path):
    """Tətbiq ikonu: magenta-bənövşəyi yuvarlaq kvadrat + loqo işarəsi."""
    size = 256
    base = gradient_rgba(size, size, lighten(MAGENTA, 0.0), PURPLE)
    mark = _img(MARK_B64)
    mh = int(size * 0.56)
    mw = int(mark.width * mh / mark.height)
    m = mark.resize((mw, mh), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(m, ((size - mw) // 2, (size - mh) // 2))
    base = Image.alpha_composite(base, layer)
    base.putalpha(rounded_mask(size, size, 60))
    base.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


# ----------------------------------------------------------------------------
# ŞRİFT
# ----------------------------------------------------------------------------
def load_private_fonts():
    if os.name != "nt":
        return
    folder = resource_path("fonts")
    if not os.path.isdir(folder):
        return
    for fn in os.listdir(folder):
        if fn.lower().endswith((".ttf", ".otf")):
            try:
                ctypes.windll.gdi32.AddFontResourceExW(os.path.join(folder, fn), 0x10, 0)
            except Exception:
                pass


def pick_font(root):
    fams = set(tkfont.families(root))
    for f in ("Inter", "Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI", "Arial"):
        if f in fams:
            return f
    return "Arial"


# ----------------------------------------------------------------------------
# ASSETTO CORSA QOVLUĞUNU TAP
# ----------------------------------------------------------------------------
AC_SUB = os.path.join("steamapps", "common", "assettocorsa")


def is_ac_dir(p):
    if not p or not os.path.isdir(p):
        return False
    has_exe = os.path.isfile(os.path.join(p, "AssettoCorsa.exe")) or os.path.isfile(os.path.join(p, "acs.exe"))
    return has_exe and os.path.isdir(os.path.join(p, "content"))


def steam_roots():
    roots = []
    if os.name == "nt":
        try:
            import winreg

            for hive, key, val in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        v, _ = winreg.QueryValueEx(k, val)
                        roots.append(os.path.normpath(v))
                except OSError:
                    pass
        except ImportError:
            pass
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if base:
            roots.append(os.path.join(base, "Steam"))
    return roots


def find_ac():
    libs = []
    for root in steam_roots():
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                libs.append(os.path.normpath(m.group(1).replace("\\\\", "\\")))
        except OSError:
            pass
    if os.name == "nt":
        for d in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            for sub in ("SteamLibrary", "Steam", r"Games\Steam", r"Games\SteamLibrary",
                        r"Program Files (x86)\Steam", r"Program Files\Steam"):
                libs.append(d + ":\\" + sub)
    seen = set()
    for lib in libs:
        key = os.path.normcase(lib)
        if key in seen:
            continue
        seen.add(key)
        p = os.path.join(lib, AC_SUB)
        if is_ac_dir(p):
            return p
    return ""


def shorten(path, n=64):
    if len(path) <= n:
        return path
    keep = (n - 3) // 2
    return path[:keep] + "..." + path[-keep:]


# ----------------------------------------------------------------------------
# AYARLAR VƏ SİYAHI
# ----------------------------------------------------------------------------
class InstallError(Exception):
    """Artıq istifadəçiyə göstərilməyə hazır mesaj daşıyır."""


class Cancelled(Exception):
    pass


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("ac_dir", "")
    data.setdefault("installed", {})
    return data


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def parse_mods(data):
    items = data.get("mods", []) if isinstance(data, dict) else data
    out = []
    for m in items:
        if isinstance(m, dict) and m.get("url"):
            m.setdefault("id", m.get("name", m["url"]))
            out.append(m)
    return out


# ----------------------------------------------------------------------------
# KATEQORİYA PƏNCƏRƏSİ (CANVAS)
# ----------------------------------------------------------------------------
class CategoryTile(tk.Canvas):
    def __init__(self, master, base_height, family, command, mark, colors):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.s = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self.h = int(base_height * self.s)
        self.configure(height=self.h)
        self.family = family
        self.command = command
        self.mark = mark
        self.colors = colors
        self.w = 0
        self.hover = False
        self.count = ""
        self.title = ""
        self.sub = ""
        self.cta = ""
        self._cache = {}
        self._cw = 0
        self._photo = None
        self.bind("<Configure>", self._on_conf)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.command())

    def set_text(self, count, title, sub, cta):
        self.count, self.title, self.sub, self.cta = count, title, sub, cta
        self.redraw()

    def _on_conf(self, e):
        self.w = e.width
        self.redraw()

    def _set_hover(self, v):
        self.hover = v
        self.redraw()

    def _pill(self, x0, y0, x1, y1, color):
        r = (y1 - y0) / 2
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=color, outline="")
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=color, outline="")
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline="")

    def redraw(self):
        if self.w < 60:
            return
        if self._cw != self.w:
            self._cache = {}
            self._cw = self.w
        photo = self._cache.get(self.hover)
        if photo is None:
            img = tile_image(self.w, self.h, self.hover, self.mark, int(22 * self.s), self.colors)
            photo = ImageTk.PhotoImage(img)
            self._cache[self.hover] = photo
        self._photo = photo
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=photo)

        s, F, h = self.s, self.family, self.h
        pad = int(26 * s)
        self.create_text(pad, h * 0.21, text=self.count, anchor="w", fill="#ffffff", font=(F, 40, "bold"))
        self.create_text(pad, h * 0.36, text=self.sub, anchor="w", fill="#f3e3ff", font=(F, 11))
        self.create_text(pad, h * 0.47, text=self.title, anchor="nw", fill="#ffffff",
                         font=(F, 19, "bold"), width=self.w - 2 * pad)
        pw, ph = int(112 * s), int(38 * s)
        y0 = h - int(26 * s) - ph
        self._pill(pad, y0, pad + pw, y0 + ph, "#ffffff")
        self.create_text(pad + pw / 2, y0 + ph / 2, text=self.cta, fill="#2a0a3a", font=(F, 12, "bold"))


# ----------------------------------------------------------------------------
# MOD KARTI (kvadrat, çərçivəli)
# ----------------------------------------------------------------------------
GREEN_FILL = "#0c2a1a"
GREEN_FILL_HOVER = "#12402a"
FILL_BY_STATE = {"installed": (GREEN_FILL, GREEN_FILL_HOVER)}
BORDER_BY_STATE = {"idle": MAGENTA, "installed": GREEN, "update": ORANGE, "busy": "#a78bfa"}
STATUS_BY_STATE = {
    "idle": ("Yüklə", "#e9a8f5"),
    "installed": ("Quraşdırılıb", GREEN),
    "update": ("Yeniləmə var", ORANGE),
    "busy": ("Yüklənir...", "#c4b5fd"),
}
ICON_BY_STATE = {
    "idle": ("↓", MAGENTA, "#ffffff"),
    "installed": ("✓", GREEN, "#06210f"),
    "update": ("↑", ORANGE, "#2b1a00"),
    "busy": ("…", "#7c3aed", "#ffffff"),
}


class ModCard(tk.Canvas):
    cache = {}

    def __init__(self, master, app, mod, family, scale):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.app = app
        self.mod = mod
        self.family = family
        self.s = scale
        self.w = 0
        self.h = 0
        self.state = "idle"
        self.hover = False
        self.progress = 0.0
        self._photo = None
        self.name = str(mod.get("name", "?"))
        self.search_key = norm(self.name)
        meta = []
        if mod.get("version"):
            meta.append("v" + str(mod["version"]))
        if mod.get("size_mb"):
            meta.append(f"{mod['size_mb']} MB")
        self.meta = "  •  ".join(meta)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.app.on_card_click(self.mod))

    def set_size(self, w, h):
        self.w, self.h = w, h
        self.configure(width=w, height=h)
        self.redraw()

    def set_state(self, state):
        self.state = state
        self.progress = 0.0
        self.redraw()

    def set_progress(self, p):
        self.progress = p
        self._draw_progress()

    def _set_hover(self, v):
        self.hover = v
        self.redraw()

    def redraw(self):
        if self.w < 40:
            return
        border = BORDER_BY_STATE[self.state]
        normal, hov = FILL_BY_STATE.get(self.state, (SURFACE, SURFACE2))
        fill = hov if self.hover else normal
        if self.hover:
            border = hexlight(border, 0.25)
        key = (self.w, self.h, border, fill)
        photo = ModCard.cache.get(key)
        if photo is None:
            if len(ModCard.cache) > 60:
                ModCard.cache.clear()
            photo = ImageTk.PhotoImage(card_image(self.w, self.h, border, fill, int(18 * self.s)))
            ModCard.cache[key] = photo
        self._photo = photo
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=photo)

        s, F = self.s, self.family
        pad = int(16 * s)
        name_id = self.create_text(pad, pad, text=self.name, anchor="nw", fill=TEXT,
                                   font=(F, 13, "bold"), width=self.w - 2 * pad)
        if self.meta:
            bb = self.bbox(name_id)
            self.create_text(pad, bb[3] + int(4 * s), text=self.meta, anchor="nw", fill=MUTED, font=(F, 9))

        txt, col = STATUS_BY_STATE[self.state]
        icon, icol, tcol = ICON_BY_STATE[self.state]
        d = int(34 * s)
        cx = self.w - pad - d
        cy = self.h - pad - d
        self.create_oval(cx, cy, cx + d, cy + d, fill=icol, outline="")
        self.create_text(cx + d / 2, cy + d / 2, text=icon, fill=tcol, font=(F, 14, "bold"))
        self.create_text(pad, cy + d / 2, text=txt, anchor="w", fill=col, font=(F, 11, "bold"))
        self._draw_progress()

    def _draw_progress(self):
        self.delete("prog")
        if self.state != "busy" or self.w < 40:
            return
        s = self.s
        x0 = int(16 * s)
        x1 = self.w - int(16 * s)
        y = self.h - int(8 * s) - 2
        self.create_rectangle(x0, y, x1, y + 3, fill=SURFACE2, outline="", tags="prog")
        fx = x0 + (x1 - x0) * max(0.0, min(1.0, self.progress))
        if fx > x0:
            self.create_rectangle(x0, y, fx, y + 3, fill=MAGENTA, outline="", tags="prog")


# ----------------------------------------------------------------------------
# ƏSAS TƏTBİQ
# ----------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.font_family = pick_font(self)
        self.s = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self.title(APP_NAME)
        self.geometry("1060x760")
        self.minsize(880, 660)
        self.configure(fg_color=BG)

        self.cfg = load_config()
        self.ac_dir = self.cfg["ac_dir"] if is_ac_dir(self.cfg["ac_dir"]) else ""
        self.mods = []
        self.list_state = "loading"
        self.current = "car"
        self.busy = False
        self.cancel_flag = False
        self.active_id = None
        self.cards = []
        self.cards_by_id = {}
        self.visible = []
        self._layout_key = None
        self._reflow_job = None
        self._search_job = None
        self.q = queue.Queue()

        self.logo_img = _img(LOGO_B64)
        self.mark_img = _img(MARK_B64)

        self._build_ui()
        self._set_icon()
        self.after(50, self._poll)

        self._update_ac_ui(searching=not self.ac_dir)
        if not self.ac_dir:
            threading.Thread(target=self._find_ac_worker, daemon=True).start()
        self.reload_lists()

    # ---------- yardımçılar ----------
    def F(self, size, weight="normal"):
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)

    def ui(self, fn, *args):
        self.q.put((fn, args))

    def _poll(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _set_icon(self):
        try:
            path = os.path.join(tempfile.gettempdir(), "azemp_icon.ico")
            make_ico(path)
            self.after(300, lambda: self.iconbitmap(path))
        except Exception:
            pass

    # ---------- interfeys ----------
    def _build_ui(self):
        # Başlıq
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(22, 6))
        lh = 34
        lw = int(self.logo_img.width * lh / self.logo_img.height)
        logo = ctk.CTkImage(light_image=self.logo_img, dark_image=self.logo_img, size=(lw, lh))
        ctk.CTkLabel(header, image=logo, text="").pack(side="left")
        self.refresh_btn = ctk.CTkButton(
            header, text="Yenilə", width=96, height=36, corner_radius=12,
            fg_color=SURFACE, hover_color=SURFACE2, border_width=1, border_color=BORDER,
            font=self.F(13), command=self.reload_lists,
        )
        self.refresh_btn.pack(side="right")

        # Assetto Corsa zolağı
        bar = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        bar.pack(fill="x", padx=30, pady=(8, 10))
        self.ac_dot = ctk.CTkLabel(bar, text="●", text_color=MUTED, font=self.F(14))
        self.ac_dot.pack(side="left", padx=(16, 8), pady=12)
        self.ac_text = ctk.CTkLabel(bar, text="", anchor="w", font=self.F(13), text_color=TEXT)
        self.ac_text.pack(side="left", fill="x", expand=True)
        self.ac_btn = ctk.CTkButton(
            bar, text="Dəyiş", width=100, height=32, corner_radius=10,
            fg_color=SURFACE2, hover_color="#251b38", font=self.F(12, "bold"), command=self.choose_ac,
        )
        self.ac_btn.pack(side="right", padx=12, pady=10)

        # Alt panel (proqres)
        bottom = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=16, border_width=1, border_color=BORDER)
        bottom.pack(side="bottom", fill="x", padx=30, pady=(8, 24))
        self.progress = ctk.CTkProgressBar(
            bottom, height=8, corner_radius=4, fg_color=SURFACE2, progress_color=MAGENTA
        )
        self.progress.set(0)
        self.progress.pack(fill="x", padx=18, pady=(16, 8))
        srow = ctk.CTkFrame(bottom, fg_color="transparent")
        srow.pack(fill="x", padx=18, pady=(0, 14))
        self.status = ctk.CTkLabel(srow, text="Hazır", text_color=MUTED, anchor="w", font=self.F(13))
        self.status.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            srow, text="Ləğv et", width=90, height=30, corner_radius=10,
            fg_color="#3a1a28", hover_color="#4f2234", text_color=RED, font=self.F(12, "bold"),
            state="disabled", command=self.cancel,
        )
        self.cancel_btn.pack(side="right")

        # Səhifələr
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=30)

        # --- Ana səhifə: 3 kateqoriya ---
        self.home = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkLabel(self.home, text="Kateqoriya seç", anchor="w", text_color=MUTED,
                     font=self.F(15)).pack(fill="x", pady=(8, 10))
        row = ctk.CTkFrame(self.home, fg_color="transparent")
        row.pack(fill="x")
        for i in range(len(CATEGORIES)):
            row.grid_columnconfigure(i, weight=1, uniform="cat")
        self.cat_tiles = {}
        for i, (key, _title, colors) in enumerate(CATEGORIES):
            tile = CategoryTile(row, 290, self.font_family, lambda k=key: self.open_category(k),
                                self.mark_img, colors)
            left = 0 if i == 0 else 8
            right = 0 if i == len(CATEGORIES) - 1 else 8
            tile.grid(row=0, column=i, sticky="ew", padx=(left, right))
            self.cat_tiles[key] = tile

        # --- Siyahı səhifəsi ---
        self.listpage = ctk.CTkFrame(self.container, fg_color="transparent")
        top = ctk.CTkFrame(self.listpage, fg_color="transparent")
        top.pack(fill="x", pady=(4, 8))
        self.back_btn = ctk.CTkButton(
            top, text="←  Geri", width=96, height=36, corner_radius=12,
            fg_color=SURFACE, hover_color=SURFACE2, border_width=1, border_color=BORDER,
            font=self.F(13, "bold"), command=self.show_home,
        )
        self.back_btn.pack(side="left")
        self.all_btn = ctk.CTkButton(
            top, text="⬇  Hamısını yüklə", width=170, height=36, corner_radius=12,
            fg_color=MAGENTA, hover_color=MAGENTA_HOVER, text_color="#ffffff",
            text_color_disabled="#c9b6d6", font=self.F(13, "bold"), command=self.install_all,
        )
        self.all_btn.pack(side="left", padx=(10, 0))
        self.list_title = ctk.CTkLabel(top, text="", font=self.F(22, "bold"), text_color=TEXT)
        self.list_title.pack(side="left", padx=16)
        self.count_lbl = ctk.CTkLabel(top, text="", font=self.F(13), text_color=MUTED)
        self.count_lbl.pack(side="right")

        self.search = ctk.CTkEntry(
            self.listpage, height=42, corner_radius=14, fg_color=SURFACE,
            border_color="#3a2a55", border_width=1, text_color=TEXT, font=self.F(14),
            placeholder_text="Modun adını yaz və axtar...", placeholder_text_color=MUTED,
        )
        self.search.pack(fill="x", pady=(0, 10))
        self.search.bind("<KeyRelease>", self._on_search_key)

        self.list_frame = ctk.CTkScrollableFrame(
            self.listpage, fg_color="transparent",
            scrollbar_button_color=SURFACE2, scrollbar_button_hover_color=MAGENTA,
        )
        self.list_frame.pack(fill="both", expand=True)
        self.empty_lbl = ctk.CTkLabel(self.list_frame, text="", text_color=MUTED, font=self.F(14))
        self.listpage.bind("<Configure>", self._on_list_conf, add="+")

        self.show_home()

    # ---------- səhifələr ----------
    def show_home(self):
        self.listpage.pack_forget()
        self.home.pack(fill="both", expand=True)
        self._update_home()

    def open_category(self, key):
        self.current = key
        title = next(t for k, t, _c in CATEGORIES if k == key)
        self.list_title.configure(text=title)
        self.search.delete(0, "end")
        self.home.pack_forget()
        self.listpage.pack(fill="both", expand=True)
        self.build_cards()
        self.after(80, lambda: self.reflow(True))

    def _counts(self):
        counts = {k: 0 for k, _t, _c in CATEGORIES}
        for m in self.mods:
            counts[category_of(m)] += 1
        return counts

    def _update_home(self):
        counts = self._counts()
        for key, title, _colors in CATEGORIES:
            n = counts[key]
            if self.list_state == "loading":
                cnt, sub = "…", "Yüklənir..."
            elif self.list_state == "error":
                cnt, sub = "!", "Siyahı yüklənə bilmədi"
            elif n == 0:
                cnt, sub = "0", "Hələlik mod yoxdur"
            else:
                cnt, sub = str(n), "mod mövcuddur"
            self.cat_tiles[key].set_text(cnt, title, sub, "Bax  →")

    # ---------- kartlar, axtarış, düzülüş ----------
    def _state_for(self, mod):
        inst = self.cfg["installed"].get(str(mod.get("id")))
        if inst is None:
            return "idle"
        if inst == str(mod.get("version", "")):
            return "installed"
        return "update"

    def build_cards(self):
        for c in self.cards:
            c.destroy()
        self.cards, self.visible, self.cards_by_id = [], [], {}
        mods = [m for m in self.mods if category_of(m) == self.current]
        mods.sort(key=lambda m: norm(m.get("name", "")))
        for mod in mods:
            card = ModCard(self.list_frame, self, mod, self.font_family, self.s)
            card.state = self._state_for(mod)
            self.cards.append(card)
            self.cards_by_id[str(mod["id"])] = card
        self._update_all_btn()
        self.apply_filter()

    def _on_search_key(self, _e=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(120, self.apply_filter)

    def apply_filter(self):
        q = norm(self.search.get().strip())
        self.visible = [c for c in self.cards if q in c.search_key]
        total = len(self.cards)
        if q:
            self.count_lbl.configure(text=f"{len(self.visible)} / {total} mod")
        else:
            self.count_lbl.configure(text=f"{total} mod")
        try:
            self.list_frame._parent_canvas.yview_moveto(0)
        except Exception:
            pass
        self.reflow(True)

    def _on_list_conf(self, _e=None):
        if self._reflow_job:
            self.after_cancel(self._reflow_job)
        self._reflow_job = self.after(120, self.reflow)

    def _empty_text(self):
        if self.list_state == "loading":
            return "Yüklənir..."
        if self.list_state == "error":
            return "Siyahı yüklənə bilmədi."
        if not self.cards:
            return "Bu kateqoriyada hələlik mod yoxdur."
        return "Heç nə tapılmadı."

    def reflow(self, force=False):
        if not self.listpage.winfo_ismapped():
            return
        avail = self.listpage.winfo_width() - int(56 * self.s)
        if avail < 240:
            return
        key = (avail, tuple(id(c) for c in self.visible))
        if not force and key == self._layout_key:
            return
        self._layout_key = key

        gap = int(12 * self.s)
        min_w = int(190 * self.s)
        cols = max(2, (avail + gap) // (min_w + gap))
        w = (avail - gap * (cols - 1)) // cols
        h = int(w * 0.8)

        for c in self.cards:
            c.grid_forget()
        if not self.visible:
            self.empty_lbl.configure(text=self._empty_text())
            self.empty_lbl.grid(row=0, column=0, pady=50)
            return
        self.empty_lbl.grid_forget()
        for i, c in enumerate(self.visible):
            if c.w != w or c.h != h:
                c.set_size(w, h)
            col = i % cols
            c.grid(row=i // cols, column=col, padx=(0, gap if col != cols - 1 else 0), pady=(0, gap))

    def refresh_card_states(self):
        for c in self.cards:
            c.set_state(self._state_for(c.mod))
        self._update_all_btn()

    def _pending_mods(self):
        """Cari kateqoriyada hələ yüklənməyən və ya yeniləməsi olan modlar."""
        return [c.mod for c in self.cards if self._state_for(c.mod) != "installed"]

    def _update_all_btn(self):
        if not hasattr(self, "all_btn"):
            return
        if self.busy:
            self.all_btn.configure(state="disabled")
            return
        n = len(self._pending_mods())
        if not self.cards:
            self.all_btn.configure(text="⬇  Hamısını yüklə", state="disabled",
                                   fg_color=SURFACE2)
        elif n == 0:
            self.all_btn.configure(text="✓  Hamısı yüklənib", state="disabled",
                                   fg_color="#14532d")
        else:
            self.all_btn.configure(text=f"⬇  Hamısını yüklə ({n})", state="normal",
                                   fg_color=MAGENTA)

    # ---------- status ----------
    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def set_progress(self, v):
        v = max(0.0, min(1.0, v))
        self.progress.set(v)
        card = self.cards_by_id.get(self.active_id) if self.active_id else None
        if card is not None:
            card.set_progress(v)

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.refresh_btn.configure(state=state)
        self.ac_btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if busy else "disabled")
        self.back_btn.configure(state=state)
        self._update_all_btn()

    def cancel(self):
        self.cancel_flag = True
        self.set_status("Ləğv edilir...", ORANGE)

    # ---------- Assetto Corsa qovluğu ----------
    def _update_ac_ui(self, searching=False):
        if searching:
            self.ac_dot.configure(text_color=ORANGE)
            self.ac_text.configure(text="Assetto Corsa axtarılır...", text_color=MUTED)
            self.ac_btn.configure(text="Özüm seçim")
        elif self.ac_dir:
            self.ac_dot.configure(text_color=GREEN)
            self.ac_text.configure(text="Assetto Corsa tapıldı   " + shorten(self.ac_dir), text_color=TEXT)
            self.ac_btn.configure(text="Dəyiş")
        else:
            self.ac_dot.configure(text_color=RED)
            self.ac_text.configure(text="Assetto Corsa avtomatik tapılmadı. Qovluğu özün seç.", text_color=TEXT)
            self.ac_btn.configure(text="Qovluğu seç")

    def _find_ac_worker(self):
        path = find_ac()
        self.ui(self._ac_found, path)

    def _ac_found(self, path):
        if path and not self.ac_dir:
            self.ac_dir = path
            self.cfg["ac_dir"] = path
            save_config(self.cfg)
        self._update_ac_ui()

    def choose_ac(self):
        folder = filedialog.askdirectory(title="Assetto Corsa qovluğunu seç (içində AssettoCorsa.exe olan)")
        if not folder:
            return
        folder = os.path.normpath(folder)
        if not is_ac_dir(folder):
            self.set_status("Bu qovluqda Assetto Corsa tapılmadı. İçində AssettoCorsa.exe olan qovluğu seç.", RED)
            return
        self.ac_dir = folder
        self.cfg["ac_dir"] = folder
        save_config(self.cfg)
        self._update_ac_ui()
        self.set_status("Assetto Corsa qovluğu yadda saxlandı.", GREEN)

    # ---------- siyahı ----------
    def reload_lists(self):
        if self.busy:
            return
        self.list_state = "loading"
        self._update_home()
        self.set_status("Siyahı yüklənir...")
        threading.Thread(target=self._load_list, daemon=True).start()

    def _load_list(self):
        try:
            res = parse_mods(fetch_json(MODS_URL))
        except Exception:
            res = "error"
        self.ui(self._list_loaded, res)

    def _list_loaded(self, res):
        if res == "error":
            self.mods, self.list_state = [], "error"
            self.set_status("Siyahı yüklənə bilmədi. İnternet bağlantını yoxla.", RED)
        else:
            self.mods, self.list_state = res, "ok"
            self.set_status("Hazır")
        self._update_home()
        if self.listpage.winfo_ismapped():
            self.build_cards()

    # ---------- quraşdırma ----------
    def on_card_click(self, mod):
        if self.busy:
            self.set_status("Başqa mod yüklənir, bitməsini gözlə.", ORANGE)
            return
        self.install(mod)

    def install(self, mod):
        if self.busy:
            return
        if not self.ac_dir or not is_ac_dir(self.ac_dir):
            self.set_status("Əvvəlcə Assetto Corsa qovluğunu seç (yuxarıdakı zolaqda).", RED)
            return
        self.cancel_flag = False
        self.active_id = str(mod["id"])
        card = self.cards_by_id.get(self.active_id)
        if card is not None:
            card.set_state("busy")
        self.set_busy(True)
        self.progress.set(0)
        threading.Thread(target=self._install_worker, args=(mod, self.ac_dir), daemon=True).start()

    def _resolve_dest(self, mod, zip_path, ac):
        ac_real = os.path.realpath(ac)
        target = mod.get("target")
        if target:
            p = os.path.realpath(os.path.join(ac_real, *[x for x in re.split(r"[\\/]", target) if x]))
            if p != ac_real and not p.startswith(ac_real + os.sep):
                raise Exception("Modun 'target' yolu düzgün deyil.")
            return p
        with zipfile.ZipFile(zip_path) as zf:
            tops = {n.replace("\\", "/").split("/")[0].lower() for n in zf.namelist() if n.strip("/\\")}
        if tops & ROOT_MARKERS:
            return ac_real
        sub = TYPE_DIRS.get(str(mod.get("type", "")).lower())
        if sub is None:
            raise Exception("Bu mod üçün quraşdırma yeri müəyyən edilə bilmədi (mods.json-da 'type' yoxdur).")
        parts = [x for x in sub.split("/") if x]
        return os.path.join(ac_real, *parts) if parts else ac_real

    def _install_one(self, mod, ac):
        """Bir modu endirir və quraşdırır. Xəta olsa Cancelled / InstallError / Exception atır."""
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="azemp_")
            os.close(fd)
            self._download(mod["url"], tmp_path, mod.get("name", "mod"))
            dest = self._resolve_dest(mod, tmp_path, ac)
            os.makedirs(dest, exist_ok=True)
            self._extract(tmp_path, dest)
            self.cfg["installed"][str(mod["id"])] = str(mod.get("version", ""))
            save_config(self.cfg)
        except zipfile.BadZipFile:
            raise InstallError(self._bad_zip_message(tmp_path))
        except PermissionError:
            raise InstallError(
                "Qovluğa yazmaq mümkün olmadı. Tətbiqi 'Administrator kimi işə sal' ilə aç.")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _install_worker(self, mod, ac):
        try:
            self._install_one(mod, ac)
            self.ui(self._install_done, mod)
        except Cancelled:
            self.ui(self._install_stopped, "Ləğv edildi.", ORANGE)
        except InstallError as e:
            self.ui(self._install_stopped, str(e), RED)
        except Exception as e:
            self.ui(self._install_stopped, f"Xəta: {e}", RED)

    # ---------- hamısını yüklə ----------
    def install_all(self):
        if self.busy:
            return
        if not self.ac_dir or not is_ac_dir(self.ac_dir):
            self.set_status("Əvvəlcə Assetto Corsa qovluğunu seç (yuxarıdakı zolaqda).", RED)
            return
        mods = self._pending_mods()
        if not mods:
            self.set_status("Bu kateqoriyada hamısı artıq yüklənib.", GREEN)
            return
        self.cancel_flag = False
        self.set_busy(True)
        self.progress.set(0)
        threading.Thread(target=self._install_all_worker, args=(mods, self.ac_dir),
                         daemon=True).start()

    def _install_all_worker(self, mods, ac):
        total = len(mods)
        ok, failed, cancelled = 0, [], False
        for i, mod in enumerate(mods, 1):
            if self.cancel_flag:
                cancelled = True
                break
            self.ui(self._batch_item_start, mod, i, total)
            try:
                self._install_one(mod, ac)
                ok += 1
                self.ui(self._batch_item_done, mod)
            except Cancelled:
                cancelled = True
                self.ui(self._batch_item_done, mod)
                break
            except InstallError as e:
                failed.append((mod.get("name", "?"), str(e)))
                self.ui(self._batch_item_done, mod)
            except Exception as e:
                failed.append((mod.get("name", "?"), str(e)))
                self.ui(self._batch_item_done, mod)
        self.ui(self._batch_finished, ok, failed, cancelled, total)

    def _batch_item_start(self, mod, i, total):
        self.active_id = str(mod["id"])
        card = self.cards_by_id.get(self.active_id)
        if card is not None:
            card.set_state("busy")
        self.progress.set(0)
        self.set_status(f"({i}/{total})  {mod.get('name', 'mod')} yüklənir...", MUTED)

    def _batch_item_done(self, mod):
        card = self.cards_by_id.get(str(mod["id"]))
        if card is not None:
            card.set_state(self._state_for(mod))  # uğurlu olduqda yaşıl olur
        self.active_id = None

    def _batch_finished(self, ok, failed, cancelled, total):
        self._finish()
        self.progress.set(1 if ok and not failed and not cancelled else 0)
        if cancelled:
            self.set_status(f"Ləğv edildi. {ok} / {total} mod yükləndi.", ORANGE)
        elif failed:
            names = ", ".join(n for n, _m in failed[:3]) + ("..." if len(failed) > 3 else "")
            self.set_status(f"{ok} mod yükləndi, {len(failed)} xəta: {names}", ORANGE)
        else:
            self.set_status(f"✓ Hamısı quraşdırıldı! ({ok} mod)", GREEN)

    def _bad_zip_message(self, path):
        try:
            with open(path, "rb") as f:
                head = f.read(16)
        except Exception:
            head = b""
        if head.startswith(b"Rar!"):
            return "Bu fayl RAR formatındadır. Onu ZIP formatında yenidən yarat və yüklə."
        if head.startswith(b"7z"):
            return "Bu fayl 7z formatındadır. Onu ZIP formatında yenidən yarat və yüklə."
        if head.lstrip().startswith(b"<"):
            return "Link yanlışdır: zip əvəzinə veb-səhifə yüklənir. Release-dəki zip-in düzgün linkini kopyala."
        if len(head) == 0:
            return "Fayl boş yüklənib. Linki yoxla."
        return "Yüklənən fayl düzgün zip deyil (zədəli ola bilər). Zip-i yenidən yarat."

    def _download(self, url, out_path, name):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp, open(out_path, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if self.cancel_flag:
                    raise Cancelled()
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    self.ui(self.set_progress, done / total)
                    self.ui(self.set_status,
                            f"{name} yüklənir...   {done / 1048576:.1f} / {total / 1048576:.1f} MB", MUTED)
                else:
                    self.ui(self.set_status, f"{name} yüklənir...   {done / 1048576:.1f} MB", MUTED)

    def _extract(self, zip_path, dest):
        dest_real = os.path.realpath(dest)
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.infolist()
            n = len(members) or 1
            for i, m in enumerate(members, 1):
                if self.cancel_flag:
                    raise Cancelled()
                target = os.path.realpath(os.path.join(dest_real, m.filename))
                if target != dest_real and not target.startswith(dest_real + os.sep):
                    raise Exception("Zip daxilində təhlükəli fayl yolu tapıldı.")
                zf.extract(m, dest_real)
                self.ui(self.set_progress, i / n)
                self.ui(self.set_status, f"Quraşdırılır...   {i}/{n}", MUTED)

    def _finish(self):
        self.active_id = None
        self.set_busy(False)
        self.refresh_card_states()

    def _install_done(self, mod):
        self._finish()
        self.progress.set(1)
        self.set_status(f"✓ {mod.get('name', 'Mod')} uğurla quraşdırıldı!", GREEN)

    def _install_stopped(self, msg, color):
        self._finish()
        self.progress.set(0)
        self.set_status(msg, color)


def main():
    load_private_fonts()
    App().mainloop()


if __name__ == "__main__":
    main()
