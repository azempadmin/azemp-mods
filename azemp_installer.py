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
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import zipfile
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageColor, ImageDraw, ImageOps, ImageTk

APP_NAME = "AzeMP Installer"

# ----------------------------------------------------------------------------
# SİYAHI LİNKLƏRİ
# ----------------------------------------------------------------------------
# "Yeni modlar" pəncərəsinin siyahısı (GitHub-dakı mods.json):
NEW_MODS_URL = "https://raw.githubusercontent.com/azempadmin/azemp-mods/main/mods.json"
# "Bütün modlar" pəncərəsinin siyahısı. Linki bura yaz (dırnaqların arasına):
ALL_MODS_URL = ""

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".azemp_installer.json")
USER_AGENT = "AzeMP-Installer/2.0"

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
TYPE_LABELS = {
    "car": "Avtomobil",
    "track": "Trek",
    "skin": "Skin",
    "app": "Tətbiq",
    "font": "Şrift",
    "root": "Mod",
}
# Zip-in içində bu qovluqlardan biri varsa, fayllar birbaşa Assetto Corsa
# qovluğuna açılır (Content Manager kimi).
ROOT_MARKERS = {"content", "apps", "system", "extension"}

# ----------------------------------------------------------------------------
# LOQO (daxili)
# ----------------------------------------------------------------------------
LOGO_B64 = "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"
MARK_B64 = "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"


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


def tile_image(w, h, style, hover, mark, radius):
    mask = rounded_mask(w, h, radius)
    if style == "hero":
        c1 = lighten(MAGENTA, 0.10 if hover else 0.0)
        c2 = lighten(PURPLE, 0.14 if hover else 0.0)
        base = gradient_rgba(w, h, c1, c2)
        if mark is not None:
            mh = int(h * 1.35)
            mw = int(mark.width * mh / mark.height)
            m = mark.resize((mw, mh), Image.LANCZOS)
            a = m.getchannel("A").point(lambda v: int(v * 0.16))
            m.putalpha(a)
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            layer.paste(m, (w - int(mw * 1.1), (h - mh) // 2))
            base = Image.alpha_composite(base, layer)
    else:
        border = MAGENTA if hover else BORDER
        fill = SURFACE2 if hover else SURFACE
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
    with urllib.request.urlopen(req, timeout=20) as r:
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
# BÖYÜK PƏNCƏRƏ (CANVAS)
# ----------------------------------------------------------------------------
class Tile(tk.Canvas):
    def __init__(self, master, base_height, style, family, command, mark=None):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.s = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self.h = int(base_height * self.s)
        self.configure(height=self.h)
        self.style = style
        self.family = family
        self.command = command
        self.mark = mark
        self.w = 0
        self.hover = False
        self.tag = ""
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

    def set_text(self, tag, title, sub, cta=""):
        self.tag, self.title, self.sub, self.cta = tag, title, sub, cta
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
            img = tile_image(self.w, self.h, self.style, self.hover, self.mark, int(22 * self.s))
            photo = ImageTk.PhotoImage(img)
            self._cache[self.hover] = photo
        self._photo = photo
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=photo)

        s, F, h = self.s, self.family, self.h
        pad = int(34 * s)
        if self.style == "hero":
            self.create_text(pad, h * 0.19, text=self.tag, anchor="w", fill="#ffd6fb", font=(F, 10, "bold"))
            self.create_text(pad, h * 0.40, text=self.title, anchor="w", fill="#ffffff", font=(F, 32, "bold"))
            self.create_text(pad, h * 0.58, text=self.sub, anchor="w", fill="#f3e3ff", font=(F, 13))
            pw, ph = int(132 * s), int(40 * s)
            y0 = h - int(28 * s) - ph
            self._pill(pad, y0, pad + pw, y0 + ph, "#ffffff")
            self.create_text(pad + pw / 2, y0 + ph / 2, text=self.cta, fill="#2a0a3a", font=(F, 12, "bold"))
        else:
            self.create_text(pad, h * 0.38, text=self.title, anchor="w", fill=TEXT, font=(F, 18, "bold"))
            self.create_text(pad, h * 0.66, text=self.sub, anchor="w", fill=MUTED, font=(F, 12))
            d = int(46 * s)
            cx = self.w - pad - d
            cy = (h - d) / 2
            self.create_oval(cx, cy, cx + d, cy + d, fill=MAGENTA if self.hover else SURFACE2, outline="")
            self.create_text(cx + d / 2, cy + d / 2, text="→", fill="#ffffff", font=(F, 16, "bold"))


# ----------------------------------------------------------------------------
# ƏSAS TƏTBİQ
# ----------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.font_family = pick_font(self)
        self.title(APP_NAME)
        self.geometry("1020x740")
        self.minsize(860, 640)
        self.configure(fg_color=BG)

        self.cfg = load_config()
        self.ac_dir = self.cfg["ac_dir"] if is_ac_dir(self.cfg["ac_dir"]) else ""
        self.lists = {"new": [], "all": []}
        self.list_state = {"new": "loading", "all": "loading"}
        self.current = "new"
        self.busy = False
        self.cancel_flag = False
        self.card_buttons = []
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

        # --- Ana səhifə ---
        self.home = ctk.CTkFrame(self.container, fg_color="transparent")
        self.hero = Tile(self.home, 250, "hero", self.font_family, lambda: self.open_list("new"), self.mark_img)
        self.hero.pack(fill="x", pady=(6, 14))
        self.ghost = Tile(self.home, 112, "ghost", self.font_family, lambda: self.open_list("all"))
        self.ghost.pack(fill="x", pady=(0, 6))

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
        self.list_title = ctk.CTkLabel(top, text="", font=self.F(22, "bold"), text_color=TEXT)
        self.list_title.pack(side="left", padx=16)
        self.list_frame = ctk.CTkScrollableFrame(
            self.listpage, fg_color="transparent",
            scrollbar_button_color=SURFACE2, scrollbar_button_hover_color=MAGENTA,
        )
        self.list_frame.pack(fill="both", expand=True)

        self.show_home()

    def show_home(self):
        self.listpage.pack_forget()
        self.home.pack(fill="both", expand=True)
        self._update_home()

    def open_list(self, which):
        if which == "all" and not ALL_MODS_URL:
            self.set_status("Bütün modların siyahısı tezliklə əlavə olunacaq.", ORANGE)
            return
        self.current = which
        self.list_title.configure(text="Yeni modlar" if which == "new" else "Bütün modlar")
        self.home.pack_forget()
        self.listpage.pack(fill="both", expand=True)
        self.render_mods()

    def _update_home(self):
        st = self.list_state["new"]
        n = len(self.lists["new"])
        if st == "loading":
            sub = "Yüklənir..."
        elif st == "error":
            sub = "Siyahı yüklənə bilmədi. Yenilə düyməsinə bas."
        elif n == 0:
            sub = "Hələlik yeni mod yoxdur."
        else:
            sub = f"{n} yeni mod səni gözləyir."
        self.hero.set_text("SON YENİLİKLƏR", "Yeni modlar", sub, "Bax  →")

        if not ALL_MODS_URL:
            gsub = "Tezliklə"
        elif self.list_state["all"] == "ok":
            gsub = f"Əvvəlki bütün modlar  •  {len(self.lists['all'])} mod"
        elif self.list_state["all"] == "error":
            gsub = "Siyahı yüklənə bilmədi"
        else:
            gsub = "Yüklənir..."
        self.ghost.set_text("", "Bütün modlar", gsub)

    # ---------- status ----------
    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def set_progress(self, v):
        self.progress.set(max(0.0, min(1.0, v)))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.refresh_btn.configure(state=state)
        self.ac_btn.configure(state=state)
        for b in self.card_buttons:
            try:
                b.configure(state=state)
            except Exception:
                pass
        self.cancel_btn.configure(state="normal" if busy else "disabled")

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

    # ---------- siyahılar ----------
    def reload_lists(self):
        if self.busy:
            return
        self.list_state = {"new": "loading", "all": "loading" if ALL_MODS_URL else "none"}
        self._update_home()
        self.set_status("Siyahılar yüklənir...")
        threading.Thread(target=self._load_lists, daemon=True).start()

    def _load_lists(self):
        res = {}
        for key, url in (("new", NEW_MODS_URL), ("all", ALL_MODS_URL)):
            if not url:
                res[key] = None
                continue
            try:
                res[key] = parse_mods(fetch_json(url))
            except Exception:
                res[key] = "error"
        self.ui(self._lists_loaded, res)

    def _lists_loaded(self, res):
        for key in ("new", "all"):
            v = res.get(key)
            if v is None:
                self.lists[key], self.list_state[key] = [], "none"
            elif v == "error":
                self.lists[key], self.list_state[key] = [], "error"
            else:
                self.lists[key], self.list_state[key] = v, "ok"
        self._update_home()
        if self.listpage.winfo_ismapped():
            self.render_mods()
        if self.list_state["new"] == "error":
            self.set_status("Siyahı yüklənə bilmədi. İnternet bağlantını yoxla.", RED)
        else:
            self.set_status("Hazır")

    def render_mods(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.card_buttons = []
        mods = self.lists[self.current]
        state = self.list_state[self.current]

        if not mods:
            if state == "error":
                msg = "Siyahı yüklənə bilmədi."
            elif state == "loading":
                msg = "Yüklənir..."
            else:
                msg = "Heç bir mod tapılmadı."
            ctk.CTkLabel(self.list_frame, text=msg, text_color=MUTED, font=self.F(14)).pack(pady=50)
            return

        installed = self.cfg["installed"]
        for mod in mods:
            inst = installed.get(str(mod.get("id")))
            ver = str(mod.get("version", ""))
            if inst is None:
                st_txt, st_col, btn_txt = "Quraşdırılmayıb", MUTED, "Yüklə və quraşdır"
            elif inst == ver:
                st_txt, st_col, btn_txt = "✓ Quraşdırılıb", GREEN, "Yenidən quraşdır"
            else:
                st_txt, st_col, btn_txt = f"Yeniləmə mövcuddur (quraşdırılan: v{inst})", ORANGE, "Yenilə"

            card = ctk.CTkFrame(self.list_frame, fg_color=SURFACE, corner_radius=18,
                                border_width=1, border_color=BORDER)
            card.pack(fill="x", padx=2, pady=7)
            card.grid_columnconfigure(0, weight=1)

            toprow = ctk.CTkFrame(card, fg_color="transparent")
            toprow.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))
            ctk.CTkLabel(toprow, text=mod.get("name", "?"), font=self.F(18, "bold"),
                         text_color=TEXT).pack(side="left")
            t = str(mod.get("type", "")).lower()
            if t in TYPE_LABELS:
                ctk.CTkLabel(
                    toprow, text=TYPE_LABELS[t], fg_color="#2b1346", text_color="#f0b8ff",
                    corner_radius=8, height=24, width=70, font=self.F(11, "bold"),
                ).pack(side="left", padx=(12, 0))

            size = f"{mod['size_mb']} MB" if mod.get("size_mb") else "-"
            ctk.CTkLabel(card, text=f"v{ver or '-'}   •   {size}", anchor="w", text_color=MUTED,
                         font=self.F(12)).grid(row=1, column=0, sticky="w", padx=20, pady=(2, 0))
            if mod.get("description"):
                ctk.CTkLabel(card, text=mod["description"], anchor="w", justify="left", wraplength=620,
                             text_color=TEXT, font=self.F(13)).grid(row=2, column=0, sticky="w", padx=20, pady=(6, 0))
            ctk.CTkLabel(card, text=st_txt, anchor="w", text_color=st_col,
                         font=self.F(12, "bold")).grid(row=3, column=0, sticky="w", padx=20, pady=(6, 16))

            btn = ctk.CTkButton(
                card, text=btn_txt, width=170, height=44, corner_radius=14,
                fg_color=MAGENTA, hover_color=MAGENTA_HOVER, font=self.F(14, "bold"),
                state="disabled" if self.busy else "normal",
                command=lambda m=mod: self.install(m),
            )
            btn.grid(row=0, column=1, rowspan=4, padx=20)
            self.card_buttons.append(btn)

    # ---------- quraşdırma ----------
    def install(self, mod):
        if self.busy:
            return
        if not self.ac_dir or not is_ac_dir(self.ac_dir):
            self.set_status("Əvvəlcə Assetto Corsa qovluğunu seç (yuxarıdakı zolaqda).", RED)
            return
        self.cancel_flag = False
        self.set_busy(True)
        self.set_progress(0)
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

    def _install_worker(self, mod, ac):
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
            self.ui(self._install_done, mod)
        except Cancelled:
            self.ui(self._install_stopped, "Ləğv edildi.", ORANGE)
        except zipfile.BadZipFile:
            self.ui(self._install_stopped, "Yüklənən fayl düzgün zip deyil.", RED)
        except PermissionError:
            self.ui(self._install_stopped,
                    "Qovluğa yazmaq mümkün olmadı. Tətbiqi 'Administrator kimi işə sal' ilə aç.", RED)
        except Exception as e:
            self.ui(self._install_stopped, f"Xəta: {e}", RED)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _download(self, url, out_path, name):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp, open(out_path, "wb") as out:
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

    def _install_done(self, mod):
        self.set_busy(False)
        self.set_progress(1)
        self.set_status(f"✓ {mod.get('name', 'Mod')} uğurla quraşdırıldı!", GREEN)
        if self.listpage.winfo_ismapped():
            self.render_mods()

    def _install_stopped(self, msg, color):
        self.set_busy(False)
        self.set_progress(0)
        self.set_status(msg, color)


def main():
    load_private_fonts()
    App().mainloop()


if __name__ == "__main__":
    main()
