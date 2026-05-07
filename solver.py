import numpy as np
from itertools import permutations

class BlockBlastAI:
    def __init__(self):
        # AI Ağırlıkları (Research-based optimal weights)
        self.weights = {
            "cleared_lines": 1000,
            "height": -5,
            "holes": -15,
            "bumpiness": -4,
            "safety": 50
        }

        # En tehlikeli bloklar (bu bloklar her zaman sığabilmeli)
        self.danger_blocks = [
            [[1, 1, 1], [1, 1, 1], [1, 1, 1]],  # 3x3 Kare
            [[1, 1, 1, 1, 1]],                    # 5'li Yatay
            [[1], [1], [1], [1], [1]]             # 5'li Dikey
        ]

    # ─────────────────────────────────────────────────────────
    #  TEMEL YARDIMCI FONKSİYONLAR
    # ─────────────────────────────────────────────────────────

    def can_place(self, board, block, r, c):
        block = np.array(block)
        rows, cols = block.shape
        if r + rows > 8 or c + cols > 8:
            return False
        return not np.any(np.logical_and(block == 1, board[r:r+rows, c:c+cols] == 1))

    def simulate_move(self, board, block, r, c):
        """Hamleyi simüle eder; temizlenen satır/sütun sayısını ve yeni tahtayı döndürür."""
        temp_board = board.copy()
        block = np.array(block)
        rows, cols = block.shape
        temp_board[r:r+rows, c:c+cols] = np.logical_or(
            temp_board[r:r+rows, c:c+cols], block
        ).astype(int)

        rows_to_clear = np.all(temp_board == 1, axis=1)
        cols_to_clear = np.all(temp_board == 1, axis=0)
        cleared = int(np.sum(rows_to_clear) + np.sum(cols_to_clear))

        temp_board[rows_to_clear, :] = 0
        temp_board[:, cols_to_clear] = 0
        return cleared, temp_board

    # ─────────────────────────────────────────────────────────
    #  TAHTA DEĞERLENDİRME
    # ─────────────────────────────────────────────────────────

    def get_safety_score(self, board):
        """Tahtanın tehlikeli blokları hâlâ barındırabildiğini ölçer."""
        score = 0
        for db in self.danger_blocks:
            db = np.array(db)
            rows, cols = db.shape
            found = False
            for r in range(9 - rows):
                for c in range(9 - cols):
                    if self.can_place(board, db, r, c):
                        score += 1
                        found = True
                        break
                if found:
                    break
            if not found:
                score -= 100  # KRİTİK: 3x3 sığmıyorsa büyük ceza
        return score

    def evaluate_board(self, board):
        fullness = np.sum(board)

        current_weights = self.weights.copy()
        if fullness > 40:
            current_weights["holes"] *= 2
            current_weights["safety"] *= 3
            current_weights["height"] *= 1.5

        heights = [8 - np.argmax(np.append(board[:, c], 1)) for c in range(8)]
        bumpiness = sum(abs(heights[i] - heights[i + 1]) for i in range(7))

        holes = 0
        for c in range(8):
            block_found = False
            for r in range(8):
                if board[r, c] == 1:
                    block_found = True
                elif block_found and board[r, c] == 0:
                    holes += 1

        safety = self.get_safety_score(board)

        return (
            fullness * current_weights["height"]
            + bumpiness * current_weights["bumpiness"]
            + holes * current_weights["holes"]
            + safety * current_weights["safety"]
        )

    # ─────────────────────────────────────────────────────────
    #  ALTERNATİF KONUM ANALİZİ (YENİ)
    # ─────────────────────────────────────────────────────────

    def get_top_positions(self, board, block, top_n=3):
        """
        Bir blok için en iyi N konumu ve skorlarını döndürür.

        Dönüş: [
            {"r": int, "c": int, "score": float, "cleared": int},
            ...
        ]
        Skorlar normalize edilmiş değil; karşılaştırma içindir.
        """
        if block is None:
            return []

        block = np.array(block)
        candidates = []

        for r in range(8):
            for c in range(8):
                if self.can_place(board, block, r, c):
                    cleared, next_board = self.simulate_move(board, block, r, c)
                    score = (cleared * self.weights["cleared_lines"]) + self.evaluate_board(next_board)
                    candidates.append({
                        "r": r,
                        "c": c,
                        "score": score,
                        "cleared": cleared
                    })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_n]

    # ─────────────────────────────────────────────────────────
    #  SIRALAMA — "Hangisini önce koymalıyım?" (YENİ)
    # ─────────────────────────────────────────────────────────

    def find_best_sequence(self, board, blocks):
        """
        3 blok için en iyi yerleştirme SIRALAMASI ve konumlarını bulur.

        Dönüş:
        {
            "sequence": [
                {"block_idx": int, "r": int, "c": int, "cleared": int, "score": float},
                ...
            ],
            "alternatives": {
                block_idx: [{"r": int, "c": int, "score": float, "cleared": int}, ...]
            },
            "total_score": float
        }
        None döner sadece hiçbir hamle yoksa.
        """
        available_indices = [i for i, b in enumerate(blocks) if b is not None]
        if not available_indices:
            return None

        best_result = None
        best_total_score = -9_999_999

        # Derinlik öncelikli: önce 3'lü, sonra 2'li, sonra 1'li dene
        for depth in range(min(3, len(available_indices)), 0, -1):
            for seq in permutations(available_indices, depth):
                current_board = board.copy()
                path = []
                valid = True

                for idx in seq:
                    best_sub_score = -9_999_999
                    best_sub_move = None

                    for r in range(8):
                        for c in range(8):
                            if self.can_place(current_board, blocks[idx], r, c):
                                cleared, next_board = self.simulate_move(current_board, blocks[idx], r, c)
                                score = (
                                    cleared * self.weights["cleared_lines"]
                                ) + self.evaluate_board(next_board)

                                if score > best_sub_score:
                                    best_sub_score = score
                                    best_sub_move = (r, c, cleared, next_board)

                    if best_sub_move:
                        r, c, cleared, current_board = best_sub_move
                        path.append({
                            "block_idx": idx,
                            "r": r,
                            "c": c,
                            "cleared": cleared,
                            "score": best_sub_score
                        })
                    else:
                        valid = False
                        break

                if valid:
                    final_score = self.evaluate_board(current_board)
                    if final_score > best_total_score:
                        best_total_score = final_score
                        best_result = {
                            "sequence": path,
                            "total_score": final_score
                        }

            if best_result:
                break

        if best_result is None:
            return None

        # Her blok için alternatif konumları hesapla (sadece ilk tahtayla)
        alternatives = {}
        for idx in available_indices:
            alternatives[idx] = self.get_top_positions(board, blocks[idx], top_n=3)

        best_result["alternatives"] = alternatives
        return best_result
