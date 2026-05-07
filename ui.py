import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import cv2
import numpy as np
import pygetwindow as gw
import webbrowser

from vision import BlockBlastVision
from solver import BlockBlastAI
from controller import BlockBlastController

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT  = "#E53935" # Modern vibrant red
SUCCESS = "#43A047"
WARNING = "#FB8C00"
DANGER  = "#D32F2F"
BG_DARK  = "#120909" # Deep red-black
BG_CARD  = "#1c0d0d"
BG_PANEL = "#160a0a"

MIRROR_KEYWORDS = ["letsview", "iphone", "ipad", "ios", "airplay",
                   "reflector", "lonelyscreen", "5kplayer", "apowermirror",
                   "mirror", "phone", "cast"]

def draw_block_shape(canvas, shape, cell=13, color=ACCENT):
    canvas.delete("all")
    if shape is None:
        canvas.create_text(45, 45, text="—", fill="#444", font=("Consolas", 16))
        return
    arr = np.array(shape)
    rows, cols = arr.shape
    ox = (90 - cols * cell) // 2
    oy = (90 - rows * cell) // 2
    for r in range(rows):
        for c in range(cols):
            if arr[r, c] == 1:
                x0 = ox + c * cell + 1
                y0 = oy + r * cell + 1
                canvas.create_rectangle(x0, y0, x0+cell-2, y0+cell-2,
                                        fill=color, outline="#000")


class BlockBlastUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Block Blast! Bot — Control Center v2.0 | Developed by SukaRyn")
        self.geometry("1150x760")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARK)

        self.running    = False
        self.auto_play  = tk.BooleanVar(value=False)
        self.speed_var  = tk.DoubleVar(value=0.6)
        self._lock      = threading.Lock()
        self._last_frame = None
        self._result     = None
        self._stats      = {"cleared": 0, "moves": 0}

        self.vision     = None
        self.ai         = BlockBlastAI()
        self.controller = BlockBlastController()

        self._build_ui()
        self._refresh_windows()
        self._auto_detect()

    # ─────────────────────────────────────────────────────────
    #  ANA LAYOUT
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()

    # ── Sol Panel ────────────────────────────────────────────
    def _build_left(self):
        left = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=16)
        left.grid(row=0, column=0, padx=(12,6), pady=12, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(12,4))
        ctk.CTkLabel(hdr, text="📷  Canlı Önizleme",
                     font=ctk.CTkFont("Inter", 13, "bold"),
                     text_color=ACCENT).pack(side="left")
        self.lbl_status = ctk.CTkLabel(hdr, text="● DURDURULDU",
                                       font=ctk.CTkFont("Inter", 12),
                                       text_color=DANGER)
        self.lbl_status.pack(side="right")

        self.preview_canvas = tk.Canvas(left, bg="#0a0505", highlightthickness=0)
        self.preview_canvas.grid(row=1, column=0, padx=10, pady=(4,6), sticky="nsew")

        card_row = ctk.CTkFrame(left, fg_color="transparent")
        card_row.grid(row=2, column=0, padx=10, pady=(0,10), sticky="ew")
        card_row.grid_columnconfigure((0,1,2), weight=1)

        self.block_cards = [self._make_card(card_row, i) for i in range(3)]
        for i, c in enumerate(self.block_cards):
            c.grid(row=0, column=i, padx=4, sticky="nsew")

    def _make_card(self, parent, idx):
        medals = ["🥇", "🥈", "🥉"]
        colors = [SUCCESS, ACCENT, WARNING]
        f = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        ctk.CTkLabel(f, text=f"{medals[idx]}  Blok {idx+1}",
                     font=ctk.CTkFont("Inter", 12, "bold"),
                     text_color=colors[idx]).pack(pady=(8,3), padx=8)
        cv = tk.Canvas(f, width=90, height=90, bg=BG_DARK, highlightthickness=0)
        cv.pack()
        lo = ctk.CTkLabel(f, text="—", font=ctk.CTkFont("Inter", 11), text_color="#aaa")
        lo.pack()
        lp = ctk.CTkLabel(f, text="—", font=ctk.CTkFont("Inter", 11, "bold"), text_color="#fff")
        lp.pack(pady=(0,3))
        ls = ctk.CTkLabel(f, text="", font=ctk.CTkFont("Inter", 10), text_color="#666")
        ls.pack(pady=(0,8))
        f._canvas = cv; f._lo = lo; f._lp = lp; f._ls = ls; f._color = colors[idx]
        return f

    # ── Sağ Panel: Sabit Üst + Scrollable + Sabit Alt Butonlar ──
    def _build_right(self):
        right = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=16)
        right.grid(row=0, column=1, padx=(6,12), pady=12, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)   # scroll alanı genişler
        right.grid_rowconfigure(2, weight=0)   # butonlar sabit

        # ── Sabit Başlık ────────────────────────────────────
        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=14, pady=(14,0), sticky="ew")
        ctk.CTkLabel(hdr, text="🎮  Block Blast! Bot",
                     font=ctk.CTkFont("Inter", 16, "bold"),
                     text_color="#fff").pack(anchor="w")
        ctk.CTkLabel(hdr, text="Control Center  v2.0  •  Created by SukaRyn",
                     font=ctk.CTkFont("Inter", 10), text_color=ACCENT).pack(anchor="w")
        ctk.CTkFrame(right, height=1, fg_color="#252830").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(60, 0))

        # ── Kaydırılabilir İçerik ───────────────────────────
        scroll = ctk.CTkScrollableFrame(right, fg_color="transparent",
                                        scrollbar_button_color="#361a1a",
                                        scrollbar_button_hover_color="#4a2424")
        scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        self._fill_scroll(scroll)

        # ── Sabit Alt Butonlar ──────────────────────────────
        btn_frame = ctk.CTkFrame(right, fg_color="#0d0707", corner_radius=0)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        btn_frame.grid_columnconfigure((0,1), weight=1)

        self.btn_start = ctk.CTkButton(
            btn_frame, text="▶  Başlat", height=46,
            fg_color=SUCCESS, hover_color="#1faf82", text_color="#000",
            font=ctk.CTkFont("Inter", 14, "bold"),
            command=self._start_bot)
        self.btn_start.grid(row=0, column=0, padx=(12,4), pady=10, sticky="ew")

        self.btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  Durdur", height=46,
            fg_color=DANGER, hover_color="#c94545", text_color="#fff",
            font=ctk.CTkFont("Inter", 14, "bold"),
            state="disabled", command=self._stop_bot)
        self.btn_stop.grid(row=0, column=1, padx=(4,12), pady=10, sticky="ew")

    def _fill_scroll(self, parent):
        """Scroll alanı içindeki tüm paneller."""
        def card(title):
            f = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
            f.grid(sticky="ew", padx=8, pady=4)
            f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont("Inter", 12, "bold"),
                         text_color="#ccc").grid(row=0, column=0, padx=12,
                                                 pady=(10,6), sticky="w")
            return f

        # iOS Paneli
        ios = ctk.CTkFrame(parent, fg_color="#170c0c", corner_radius=10,
                           border_width=1, border_color="#3d1e1e")
        ios.grid(sticky="ew", padx=8, pady=4)
        ios.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ios, text="📱  iOS Ekran Yansıtma",
                     font=ctk.CTkFont("Inter", 12, "bold"),
                     text_color=ACCENT).grid(row=0, column=0, padx=12, pady=(10,4), sticky="w")
        self.lbl_scrcpy = ctk.CTkLabel(ios, text="🔍 Aranıyor...",
                                       font=ctk.CTkFont("Inter", 10), text_color="#666")
        self.lbl_scrcpy.grid(row=1, column=0, padx=12, sticky="w")
        ctk.CTkButton(ios, text="🔍 LetsView / AirPlay Penceresini Otomatik Bul",
                      height=30, fg_color="#0d2040", hover_color="#143060",
                      font=ctk.CTkFont("Inter", 10),
                      command=self._auto_detect).grid(row=2, column=0, padx=10,
                                                      pady=(6,4), sticky="ew")
        note = ctk.CTkFrame(ios, fg_color="#1a1200", corner_radius=6)
        note.grid(row=3, column=0, padx=10, pady=(2,10), sticky="ew")
        ctk.CTkLabel(note, text="ℹ️  iOS'ta otomatik dokunuş mümkün değil.\n"
                                "   Bot rehberlik eder, siz dokunursunuz.",
                     font=ctk.CTkFont("Inter", 9), text_color="#aaa",
                     justify="left").pack(padx=8, pady=5, anchor="w")

        # Pencere Seçici
        wf = card("🖥️  Oyun Penceresi")
        wr = ctk.CTkFrame(wf, fg_color="transparent")
        wr.grid(row=1, column=0, padx=10, pady=(0,10), sticky="ew")
        wr.grid_columnconfigure(0, weight=1)
        self.window_combo = ctk.CTkComboBox(wr, values=[], fg_color="#0F1117",
                                             border_color="#333", button_color=ACCENT)
        self.window_combo.grid(row=0, column=0, padx=(0,4), sticky="ew")
        ctk.CTkButton(wr, text="🔄", width=36, height=32, fg_color="#1a1d27",
                      hover_color="#252836",
                      command=self._refresh_windows).grid(row=0, column=1)

        # Tahta Durumu
        rf = card("📊  Tahta Durumu")
        self.risk_bar = ctk.CTkProgressBar(rf, height=14, corner_radius=7,
                                           fg_color="#222", progress_color=SUCCESS)
        self.risk_bar.grid(row=1, column=0, padx=12, sticky="ew")
        self.risk_bar.set(0)
        self.lbl_risk = ctk.CTkLabel(rf, text="Risk: %0  |  Dolu: 0/64",
                                     font=ctk.CTkFont("Inter", 10), text_color="#aaa")
        self.lbl_risk.grid(row=2, column=0, padx=12, pady=(4,2), sticky="w")
        self.lbl_safety = ctk.CTkLabel(rf, text="Güvenlik: —",
                                       font=ctk.CTkFont("Inter", 10), text_color="#aaa")
        self.lbl_safety.grid(row=3, column=0, padx=12, pady=(0,10), sticky="w")

        # İstatistik
        sf = card("🏆  İstatistik")
        sf.grid_columnconfigure((0,1), weight=1)
        self.lbl_cleared = ctk.CTkLabel(sf, text="Temizlenen\n—",
                                        font=ctk.CTkFont("Inter", 12),
                                        text_color=SUCCESS, justify="center")
        self.lbl_cleared.grid(row=1, column=0, pady=(0,10))
        self.lbl_moves = ctk.CTkLabel(sf, text="Hamle\n—",
                                      font=ctk.CTkFont("Inter", 12),
                                      text_color=ACCENT, justify="center")
        self.lbl_moves.grid(row=1, column=1, pady=(0,10))

        # Ayarlar
        af = card("⚙️  Ayarlar")
        ar = ctk.CTkFrame(af, fg_color="transparent")
        ar.grid(row=1, column=0, padx=12, pady=(0,4), sticky="ew")
        ctk.CTkSwitch(ar, text="Tam Otomatik (Android only)",
                      variable=self.auto_play, fg_color="#222",
                      progress_color=SUCCESS, font=ctk.CTkFont("Inter", 11),
                      state="disabled").pack(side="left")
        ctk.CTkLabel(ar, text="  iOS desteklemez",
                     font=ctk.CTkFont("Inter", 9), text_color=DANGER).pack(side="left")
        ctk.CTkLabel(af, text="Hamle Hızı:", font=ctk.CTkFont("Inter", 10),
                     text_color="#aaa").grid(row=2, column=0, padx=12, sticky="w")
        self.speed_slider = ctk.CTkSlider(af, from_=0.2, to=2.0, variable=self.speed_var,
                                          progress_color=ACCENT, fg_color="#222")
        self.speed_slider.grid(row=3, column=0, padx=12, pady=(2,4), sticky="ew")
        self.lbl_speed = ctk.CTkLabel(af, text="0.60 sn", font=ctk.CTkFont("Inter", 10),
                                      text_color="#555")
        self.lbl_speed.grid(row=4, column=0, padx=12, pady=(0,10), sticky="w")
        self.speed_slider.configure(command=lambda v:
            self.lbl_speed.configure(text=f"{float(v):.2f} sn"))

        # Sıfırla
        ctk.CTkButton(parent, text="🔄  İstatistiği Sıfırla", height=30,
                      fg_color="#111", hover_color="#1a1d27", text_color="#555",
                      font=ctk.CTkFont("Inter", 10),
                      command=lambda: self._stats.update({"cleared":0,"moves":0})
                      ).grid(sticky="ew", padx=8, pady=(0,4))

    # ─────────────────────────────────────────────────────────
    #  YARDIMCI
    # ─────────────────────────────────────────────────────────
    def _refresh_windows(self):
        titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
        self.window_combo.configure(values=titles)

    def _auto_detect(self):
        for w in gw.getAllWindows():
            t = w.title.strip()
            if t and any(k in t.lower() for k in MIRROR_KEYWORDS):
                self.window_combo.set(t)
                self.lbl_scrcpy.configure(text=f"✅ Bulundu: {t}", text_color=SUCCESS)
                return
        self.lbl_scrcpy.configure(text="❌ Bulunamadı — LetsView açık olsun",
                                   text_color=DANGER)

    # ─────────────────────────────────────────────────────────
    #  BOT
    # ─────────────────────────────────────────────────────────
    def _start_bot(self):
        win = self.window_combo.get().strip()
        self.vision = BlockBlastVision(window_title=win if win else None)
        self.running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="● ÇALIŞIYOR", text_color=SUCCESS)
        threading.Thread(target=self._bot_loop, daemon=True).start()
        self._ui_loop()

    def _stop_bot(self):
        self.running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="● DURDURULDU", text_color=DANGER)

    def _bot_loop(self):
        while self.running:
            try:
                frame = self.vision.capture_screen()
                grid  = self.vision.find_grid(frame)
                result = None
                blocks_data = []
                
                if grid:
                    matrix = self.vision.get_board_matrix(frame)
                    blocks_data = self.vision.get_blocks(frame)
                    shapes = [b["shape"] for b in blocks_data]
                    
                    if matrix is not None and any(s is not None for s in shapes):
                        result = self.ai.find_best_sequence(matrix, shapes)
                        
                        if result and self.auto_play.get():
                            gx, gy, gw_, gh = grid
                            gi = (gx, gy, gw_, gh, gw_//8)
                            self.controller.pause_between = self.speed_var.get()
                            for mv in result["sequence"]:
                                if not self.running: break
                                self.controller.execute_move(mv, gi, blocks_data)
                                self._stats["moves"]   += 1
                                self._stats["cleared"] += mv.get("cleared", 0)
                                time.sleep(self.speed_var.get())
                                
                with self._lock:
                    self._last_frame = frame.copy()
                    self._result = result
                    self._last_blocks = blocks_data
                    
            except Exception as e:
                print(f"[Bot] {e}")
                time.sleep(0.5)
            time.sleep(0.05)

    def _ui_loop(self):
        if not self.running:
            return
        with self._lock:
            frame  = self._last_frame
            result = self._result
            blocks = getattr(self, '_last_blocks', [])
            
        if frame is not None:
            self._draw_preview(frame, result, blocks)
            self._update_cards(result, blocks)
            self._update_stats(frame, result)
            
        self.after(50, self._ui_loop)

    def _draw_preview(self, frame, result, blocks):
        try:
            img = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB if frame.shape[2]==4 else cv2.COLOR_BGR2RGB)
            
            crop_y1, crop_y2, crop_x1, crop_x2 = 0, img.shape[0], 0, img.shape[1]
            
            if self.vision and self.vision.grid_coords:
                gx, gy, gw, gh = self.vision.grid_coords
                cell = gw // 8
                
                # Tahtayı belirginleştiren hafif çizgiler çiz
                overlay = img.copy()
                for i in range(9):
                    cv2.line(overlay, (gx, gy + i*cell), (gx + gw, gy + i*cell), (255,255,255), 1)
                    cv2.line(overlay, (gx + i*cell, gy), (gx + i*cell, gy + gh), (255,255,255), 1)
                cv2.addWeighted(overlay, 0.15, img, 0.85, 0, img)
                
                # Hedef hamleyi (TAM ŞEKLİYLE) çiz
                seq = result.get("sequence", []) if result else []
                if seq and blocks:
                    mv = seq[0]
                    bidx = mv["block_idx"]
                    tr, tc = mv["r"], mv["c"]
                    
                    if bidx < len(blocks) and blocks[bidx]["shape"]:
                        shape = np.array(blocks[bidx]["shape"])
                        
                        b_overlay = img.copy()
                        for r in range(shape.shape[0]):
                            for c in range(shape.shape[1]):
                                if shape[r, c] == 1:
                                    px = gx + (tc + c) * cell
                                    py = gy + (tr + r) * cell
                                    cv2.rectangle(b_overlay, (px+2, py+2), (px+cell-2, py+cell-2), (45, 212, 160), -1)
                        cv2.addWeighted(b_overlay, 0.5, img, 0.5, 0, img)
                        
                        for r in range(shape.shape[0]):
                            for c in range(shape.shape[1]):
                                if shape[r, c] == 1:
                                    px = gx + (tc + c) * cell
                                    py = gy + (tr + r) * cell
                                    cv2.rectangle(img, (px+2, py+2), (px+cell-2, py+cell-2), (45, 212, 160), 3)

                # Sadece oyun alanına zoom yap
                crop_y1 = max(0, gy - 20)
                crop_y2 = min(img.shape[0], int(gy + gh + gh * 0.55))
                crop_x1 = max(0, gx - 20)
                crop_x2 = min(img.shape[1], gx + gw + 20)
                
                img = img[crop_y1:crop_y2, crop_x1:crop_x2]
                
            cw = max(self.preview_canvas.winfo_width(), 10)
            ch = max(self.preview_canvas.winfo_height(), 10)
            h, w = img.shape[:2]
            sc = min(cw/w, ch/h)
            nw, nh = int(w*sc), int(h*sc)
            tk_img = ImageTk.PhotoImage(Image.fromarray(cv2.resize(img,(nw,nh))))
            self.preview_canvas._tk_img = tk_img
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image((cw-nw)//2, (ch-nh)//2, anchor="nw", image=tk_img)
        except Exception as e:
            print(f"[Preview] Error: {e}")
            pass

    def _update_cards(self, result, blocks):
        for card in self.block_cards:
            draw_block_shape(card._canvas, None)
            card._lo.configure(text="—", text_color="#555")
            card._lp.configure(text="—")
            card._ls.configure(text="")
        if not result:
            return
        seq  = result.get("sequence", [])
        alts = result.get("alternatives", {})
        labels = ["1. Oyna ▶","2. Oyna ▶","3. Oyna ▶"]
        colors = [SUCCESS, ACCENT, WARNING]
        for si, mv in enumerate(seq):
            bidx = mv["block_idx"]
            card = self.block_cards[bidx]
            tops = alts.get(bidx, [])
            
            shape_to_draw = blocks[bidx]["shape"] if blocks and bidx < len(blocks) else None
            draw_block_shape(card._canvas, shape_to_draw, color=card._color)
            
            card._lo.configure(text=labels[si] if si<3 else "Bekle",
                               text_color=colors[si] if si<3 else "#555")
            card._lp.configure(text=f"Satır {mv['r']+1}, Sütun {mv['c']+1}")
            txt = f"+{mv['cleared']} satır" if mv["cleared"]>0 else ""
            if len(tops)>1:
                txt += f"  | Alt fark: {int(abs(tops[0]['score']-tops[1]['score']))}"
            card._ls.configure(text=txt)

    def _update_stats(self, frame, result):
        try:
            if self.vision and self.vision.grid_coords:
                matrix = self.vision.get_board_matrix(frame)
                if matrix is not None:
                    full = int(np.sum(matrix))
                    ratio = full/64
                    self.risk_bar.set(ratio)
                    col = SUCCESS if ratio<=0.55 else (WARNING if ratio<=0.75 else DANGER)
                    self.risk_bar.configure(progress_color=col)
                    self.lbl_risk.configure(text=f"Risk: %{int(ratio*100)}  |  Dolu: {full}/64")
                    s = self.ai.get_safety_score(matrix)
                    self.lbl_safety.configure(
                        text=f"Güvenlik: {'✅ İYİ' if s>=0 else '⚠️ KRİTİK'}",
                        text_color=SUCCESS if s>=0 else DANGER)
        except Exception:
            pass
        self.lbl_cleared.configure(text=f"Temizlenen\n{self._stats['cleared']} satır")
        self.lbl_moves.configure(text=f"Hamle\n{self._stats['moves']}")


if __name__ == "__main__":
    app = BlockBlastUI()
    app.mainloop()
