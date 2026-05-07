import cv2
import numpy as np
import mss
import pygetwindow as gw

class BlockBlastVision:
    def __init__(self, window_title=None):
        self.sct = mss.mss()
        self.window_title = window_title
        self.grid_coords = None
        self.cell_size = 0

    def set_window(self, title):
        self.window_title = title
        self.grid_coords = None

    def _get_window_region(self):
        if not self.window_title: return None
        try:
            wins = gw.getWindowsWithTitle(self.window_title)
            if not wins: return None
            w = wins[0]
            if w.width <= 10 or w.height <= 10: return None
            # DPI scaling'e karsi koruma
            return {"top": max(0, w.top), "left": max(0, w.left),
                    "width": max(10, w.width), "height": max(10, w.height)}
        except Exception:
            return None

    def capture_screen(self):
        # 1. Tum ekrani yakala (siyah ekran sorununa karsi en guvenli yol)
        screen_img = np.array(self.sct.grab(self.sct.monitors[1]))
        
        region = self._get_window_region()
        if region:
            x, y = region["left"], region["top"]
            w, h = region["width"], region["height"]
            
            max_h, max_w = screen_img.shape[:2]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(max_w, x + w), min(max_h, y + h)
            
            if x2 > x1 and y2 > y1:
                return screen_img[y1:y2, x1:x2]
                
        return screen_img

    def find_grid(self, frame):
        if frame.size == 0: return None
        
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR) if frame.shape[2] == 4 else frame.copy()
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 30, 100)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        # Sadece dış konturlar yerine hepsine bak (tahtanın içi daha belirgin olabilir)
        contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        best = None
        max_a = 0
        min_area = 20000 # En az 140x140 pixel (önceki yüzdelik sistem hatalı alan seçiyordu)
        
        for cnt in contours:
            a = cv2.contourArea(cnt)
            if a < min_area: continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            ratio = float(w) / max(h, 1)
            
            # Tahta 8x8 bir kare olmalı
            if 0.85 <= ratio <= 1.15:
                if a > max_a:
                    max_a = a
                    best = (x, y, w, h)
                    
        if best:
            self.grid_coords = best
            self.cell_size = best[2] // 8
        return best

    def get_board_matrix(self, frame):
        if not self.grid_coords or self.cell_size == 0 or frame.size == 0:
            return None
            
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR) if frame.shape[2] == 4 else frame.copy()
        x, y, w, h = self.grid_coords
        roi = bgr[y:y+h, x:x+w]
        
        # Tema Bağımsız Boş Zemin Rengi Tahmini
        # Oyun tahtasının arka planı daima "mat" (düşük doygunluk) ve "koyu" (düşük parlaklık) olur.
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]
        
        # Tahtanın en soluk ve en karanlık %10'luk kısmı kesinlikle BOŞ ZEMİN referansıdır
        bg_s_ref = np.percentile(s_channel, 10)
        bg_v_ref = np.percentile(v_channel, 10)
        
        matrix = np.zeros((8, 8), dtype=int)
        cell = self.cell_size
        mg = max(3, cell // 4) # Hücre sınırlarını ve grid çizgilerini yoksay, sadece hücre merkezine odaklan
        
        for r in range(8):
            for c in range(8):
                r0, r1 = r * cell + mg, min((r + 1) * cell - mg, roi.shape[0])
                c0, c1 = c * cell + mg, min((c + 1) * cell - mg, roi.shape[1])
                if r1 <= r0 or c1 <= c0: continue
                
                cell_s = s_channel[r0:r1, c0:c1]
                cell_v = v_channel[r0:r1, c0:c1]
                
                mean_s = np.mean(cell_s)
                mean_v = np.mean(cell_v)
                std_v = np.std(cell_v) # Hücre içindeki parlaklık değişimi (Doku/Zar delikleri/Gölgeler)
                
                # KURAL 1: Hücrenin rengi zeminden 40 birim daha CANLIYSA doludur (Yeşil, Kırmızı, Mavi bloklar)
                # KURAL 2: Hücre zeminden 40 birim daha PARLAKSA doludur (Açık ahşap veya Buz bloklar)
                # KURAL 3: Hücrenin içinde PÜRÜZ (Varyans > 12) varsa doludur (Zar delikleri, eğimli blok kenarları)
                # Boş zemin her zaman düz mat bir renktir (std_v < 5).
                if (mean_s > bg_s_ref + 40) or (mean_v > bg_v_ref + 40) or (std_v > 12):
                    matrix[r, c] = 1
                    
        return matrix

    def get_blocks(self, frame):
        if not self.grid_coords or frame.size == 0: return []
        
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR) if frame.shape[2] == 4 else frame.copy()
        gx, gy, gw, gh = self.grid_coords
        
        by = gy + gh + int(gh * 0.05)
        bh = min(int(gh * 0.45), bgr.shape[0] - by)
        if bh < 20: return []
        
        sw = gw // 3
        slot_data = []
        for i in range(3):
            sx = gx + i * sw
            slot = bgr[by:by+bh, sx:sx+sw]
            bbox, mask = self._get_bbox_and_mask(slot)
            if bbox:
                slot_data.append({"i": i, "bbox": bbox, "mask": mask, "sx": sx})
                
        blocks = [ {"shape": None, "coords": (gx + i*sw, by, sw, bh)} for i in range(3) ]
        if not slot_data: 
            return blocks
            
        # ── Her Slot İçin Bağımsız "Unit Size" ve "Padding" Analizi (Shadow-Proof) ──
        # Blokların sağındaki ve altındaki gölgeler (padding) en-boy oranını bozar. 
        # Gölge miktarını denklemden çıkarmak için Fark Teoremi (S = |W - H| / |c - r|) kullanıyoruz.
        
        valid_pairs = [
            (1, 1), (2, 1), (3, 1), (4, 1), (5, 1),
            (1, 2), (1, 3), (1, 4), (1, 5),
            (2, 2), (3, 2), (2, 3),
            (3, 3)
        ]
        
        for sd in slot_data:
            x, y, w, h = sd["bbox"]
            mask = sd["mask"]
            
            best_pair = None
            best_score = float('inf')
            best_unit = self.cell_size * 0.45
            
            for c, r in valid_pairs:
                if c == r:
                    # Kare şekiller için gölge oranını sabit %25 varsayarak S'i tahmin ediyoruz.
                    S = w / (c + 0.25)
                    P_w = w - c * S
                    P_h = h - r * S
                else:
                    # Dikdörtgen şekiller için gölge (P) fark alma yöntemiyle tamamen yok edilir:
                    S = abs(w - h) / abs(c - r)
                    P_w = w - c * S
                    P_h = h - r * S
                    
                if S <= 0: continue
                
                p_ratio_w = P_w / S
                p_ratio_h = P_h / S
                
                # Gölge eksi değerlere inmemeli (Anti-aliasing payı olan -0.15'e kadar esneme payı)
                if p_ratio_w < -0.15 or p_ratio_h < -0.15:
                    continue
                # Gölge oranı bloğun %60'ından büyük olamaz
                if p_ratio_w > 0.60 or p_ratio_h > 0.60:
                    continue
                    
                # S (Gerçek hücre boyutu) mantıklı bir aralıkta olmalı (%20 ile %90 arası)
                if not (0.20 * self.cell_size < S < 0.90 * self.cell_size):
                    continue
                    
                # SKORLAMA SİSTEMİ
                # 1. P_w ve P_h birbirine eşit olmalıdır (gölge her yönde aynıdır)
                padding_diff = abs(P_w - P_h) / S
                
                # 2. Beklenen ideal gölge oranı ~%20'dir
                expected_p = 0.20
                p_penalty = abs(p_ratio_w - expected_p) + abs(p_ratio_h - expected_p)
                
                # 3. İdeal alt hücre boyutuna (S) uzaklık
                dist_ideal = abs(S - self.cell_size * 0.45) / (self.cell_size * 0.45)
                
                # Formül: Kesin eşleşmeyi vurgulamak için padding_diff'e büyük ağırlık veriyoruz
                score = (padding_diff * 5) + (p_penalty * 2) + dist_ideal
                
                if score < best_score:
                    best_score = score
                    best_pair = (c, r)
                    best_unit = S
                    
            if not best_pair:
                # Güvenlik ağı
                best_pair = (max(1, round(w / (self.cell_size * 0.45))), 
                             max(1, round(h / (self.cell_size * 0.45))))
                             
            cols, rows = best_pair
            cols = max(1, min(5, cols))
            rows = max(1, min(5, rows))
            
            mat = np.zeros((rows, cols), dtype=int)
            for r in range(rows):
                for c in range(cols):
                    # Maskenin tam ortasından nokta atışı örnekleme yapıyoruz
                    cx = x + int((c + 0.5) * (w / cols))
                    cy = y + int((r + 0.5) * (h / rows))
                    if cy < mask.shape[0] and cx < mask.shape[1] and mask[cy, cx] > 127:
                        mat[r, c] = 1
                        
            blocks[sd["i"]]["shape"] = mat.tolist() if np.any(mat) else None
            
        return blocks

    def _get_bbox_and_mask(self, slot_img):
        if slot_img.size == 0 or self.cell_size == 0: return None, None
        
        gray = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 30, 100)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None, None
        
        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < (self.cell_size * self.cell_size * 0.15): 
            return None, None
            
        x, y, w, h = cv2.boundingRect(cnt)
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [cnt], -1, 255, -1)
        
        return (x, y, w, h), mask
