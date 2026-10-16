"""
AzeMP Installer - modern arayuz (customtkinter)
Mod listesini internetten ceker, secilen modu indirir ve secilen klasore kurar.
"""

import json
import os
import queue
import tempfile
import threading
import urllib.request
import zipfile
from tkinter import filedialog

import customtkinter as ctk

APP_NAME = "AzeMP Installer"

# >>> BURAYI KENDI mods.json ADRESINLE DEGISTIR <<<
MODS_URL = "https://raw.githubusercontent.com/azempadmin/azemp-mods/main/mods.json"

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".azemp_installer.json")
USER_AGENT = "AzeMP-Installer/1.0"

# Renkler
BG = "#0f1117"
CARD = "#1a1d27"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
MUTED = "#8b93a7"
GREEN = "#4ade80"
ORANGE = "#fb923c"
RED = "#f87171"


class Cancelled(Exception):
    pass


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("install_dir", "")
    data.setdefault("installed", {})
    return data


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_NAME)
        self.geometry("940x640")
        self.minsize(780, 540)
        self.configure(fg_color=BG)

        self.cfg = load_config()
        self.mods = []
        self.busy = False
        self.cancel_flag = False
        self.card_buttons = []
        self.q = queue.Queue()

        self.dir_var = ctk.StringVar(value=self.cfg["install_dir"])

        self._build_ui()
        self.after(50, self._poll)
        self.refresh_mods()

    # ------------------------------------------------ thread -> arayuz kopru
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

    # ------------------------------------------------ arayuz
    def _build_ui(self):
        # Ust bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 8))
        ctk.CTkLabel(
            header, text="AzeMP", font=ctk.CTkFont(size=30, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="  Installer", font=ctk.CTkFont(size=30), text_color=ACCENT
        ).pack(side="left")
        self.refresh_btn = ctk.CTkButton(
            header, text="⟳  Yenile", width=110, height=36, corner_radius=10,
            fg_color=CARD, hover_color="#242836", command=self.refresh_mods,
        )
        self.refresh_btn.pack(side="right")

        ctk.CTkLabel(
            self, text="Oyun modlarını seç, tek tıkla indir ve kur.",
            text_color=MUTED, anchor="w",
        ).pack(fill="x", padx=30, pady=(0, 10))

        # Mod listesi
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=22, pady=4)

        # Alt panel
        bottom = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        bottom.pack(fill="x", padx=28, pady=(8, 24))

        row = ctk.CTkFrame(bottom, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(row, text="Kurulum klasörü", text_color=MUTED).pack(side="left")
        self.browse_btn = ctk.CTkButton(
            row, text="Klasör Seç", width=110, height=34, corner_radius=10,
            command=self.choose_dir,
        )
        self.browse_btn.pack(side="right")
        self.dir_entry = ctk.CTkEntry(
            row, textvariable=self.dir_var, height=34, corner_radius=10,
            placeholder_text="Örn: C:\\Games\\AzeMP",
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=12)

        self.progress = ctk.CTkProgressBar(bottom, height=10, corner_radius=5)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(4, 6))

        status_row = ctk.CTkFrame(bottom, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(0, 14))
        self.status = ctk.CTkLabel(status_row, text="Hazır", text_color=MUTED, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            status_row, text="İptal", width=80, height=30, corner_radius=8,
            fg_color="#3a2326", hover_color="#4d2c30", text_color=RED,
            state="disabled", command=self.cancel,
        )
        self.cancel_btn.pack(side="right")

    # ------------------------------------------------ yardimcilar
    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def set_progress(self, value):
        self.progress.set(max(0.0, min(1.0, value)))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.refresh_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        for b in self.card_buttons:
            try:
                b.configure(state=state)
            except Exception:
                pass
        self.cancel_btn.configure(state="normal" if busy else "disabled")

    def choose_dir(self):
        folder = filedialog.askdirectory(title="Kurulum klasörünü seçin")
        if folder:
            self.dir_var.set(folder)
            self.cfg["install_dir"] = folder
            save_config(self.cfg)

    def cancel(self):
        self.cancel_flag = True
        self.set_status("İptal ediliyor...", ORANGE)

    # ------------------------------------------------ liste
    def refresh_mods(self):
        if self.busy:
            return
        self.set_busy(True)
        self.set_status("Mod listesi alınıyor...")
        threading.Thread(target=self._fetch_mods, daemon=True).start()

    def _fetch_mods(self):
        try:
            req = urllib.request.Request(MODS_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.ui(self._show_mods, data.get("mods", []))
        except Exception as e:
            self.ui(self._fetch_failed, str(e))

    def _fetch_failed(self, err):
        self.mods = []
        self.render_mods()
        self.set_busy(False)
        self.set_status("Liste alınamadı. İnternet bağlantını kontrol et.", RED)

    def _show_mods(self, mods):
        self.mods = mods
        self.render_mods()
        self.set_busy(False)
        self.set_progress(0)
        self.set_status(f"{len(mods)} mod bulundu.")

    def render_mods(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.card_buttons = []

        if not self.mods:
            ctk.CTkLabel(
                self.list_frame, text="Gösterilecek mod yok.", text_color=MUTED
            ).pack(pady=40)
            return

        installed = self.cfg["installed"]
        for mod in self.mods:
            inst_ver = installed.get(mod.get("id"))
            if inst_ver is None:
                state_txt, state_col, btn_txt = "Kurulu değil", MUTED, "İndir ve Kur"
            elif inst_ver == mod.get("version"):
                state_txt, state_col, btn_txt = "✓ Kurulu", GREEN, "Yeniden Kur"
            else:
                state_txt, state_col, btn_txt = f"Güncelleme var (kurulu: v{inst_ver})", ORANGE, "Güncelle"

            card = ctk.CTkFrame(self.list_frame, fg_color=CARD, corner_radius=16)
            card.pack(fill="x", padx=6, pady=7)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card, text=mod.get("name", "?"), anchor="w",
                font=ctk.CTkFont(size=18, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))

            size = f"{mod['size_mb']} MB" if mod.get("size_mb") else "-"
            ctk.CTkLabel(
                card, text=f"v{mod.get('version', '-')}   •   {size}", anchor="w",
                text_color=MUTED,
            ).grid(row=1, column=0, sticky="w", padx=20, pady=(2, 0))

            ctk.CTkLabel(
                card, text=mod.get("description", ""), anchor="w", justify="left",
                wraplength=520,
            ).grid(row=2, column=0, sticky="w", padx=20, pady=(6, 0))

            ctk.CTkLabel(
                card, text=state_txt, anchor="w", text_color=state_col,
            ).grid(row=3, column=0, sticky="w", padx=20, pady=(6, 16))

            btn = ctk.CTkButton(
                card, text=btn_txt, width=140, height=42, corner_radius=12,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda m=mod: self.install(m),
            )
            btn.grid(row=0, column=1, rowspan=4, padx=20)
            self.card_buttons.append(btn)

    # ------------------------------------------------ kurulum
    def install(self, mod):
        if self.busy:
            return
        dest = self.dir_var.get().strip()
        if not dest:
            self.set_status("Önce aşağıdan kurulum klasörünü seç.", RED)
            return
        try:
            os.makedirs(dest, exist_ok=True)
        except Exception as e:
            self.set_status(f"Klasör oluşturulamadı: {e}", RED)
            return
        self.cfg["install_dir"] = dest
        save_config(self.cfg)

        self.cancel_flag = False
        self.set_busy(True)
        self.set_progress(0)
        threading.Thread(target=self._install_worker, args=(mod, dest), daemon=True).start()

    def _install_worker(self, mod, dest):
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="azemp_")
            os.close(fd)
            self._download(mod["url"], tmp_path, mod.get("name", "mod"))
            self._extract(tmp_path, dest)
            self.cfg["installed"][mod["id"]] = mod.get("version", "")
            save_config(self.cfg)
            self.ui(self._install_done, mod)
        except Cancelled:
            self.ui(self._install_stopped, "İşlem iptal edildi.", ORANGE)
        except zipfile.BadZipFile:
            self.ui(self._install_stopped, "İndirilen dosya geçerli bir zip değil.", RED)
        except Exception as e:
            self.ui(self._install_stopped, f"Hata: {e}", RED)
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
                    self.ui(
                        self.set_status,
                        f"{name} indiriliyor...  {done / 1048576:.1f} / {total / 1048576:.1f} MB",
                        MUTED,
                    )
                else:
                    self.ui(self.set_status, f"{name} indiriliyor...  {done / 1048576:.1f} MB", MUTED)

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
                    raise Exception("Zip içinde güvensiz dosya yolu bulundu.")
                zf.extract(m, dest_real)
                self.ui(self.set_progress, i / n)
                self.ui(self.set_status, f"Kuruluyor...  {i}/{n}", MUTED)

    def _install_done(self, mod):
        self.render_mods()
        self.set_busy(False)
        self.set_progress(1)
        self.set_status(f"✓ {mod.get('name', 'Mod')} başarıyla kuruldu!", GREEN)

    def _install_stopped(self, msg, color):
        self.set_busy(False)
        self.set_progress(0)
        self.set_status(msg, color)


if __name__ == "__main__":
    App().mainloop()
