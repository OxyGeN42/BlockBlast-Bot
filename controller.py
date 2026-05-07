import pyautogui
import time

class BlockBlastController:
    def __init__(self, move_duration=0.3, pause_between=0.5):
        """
        move_duration  : Sürükleme hareketi süresi (saniye)
        pause_between  : Hamleler arası bekleme (saniye) — tahta güncellensin diye
        """
        pyautogui.PAUSE = 0.05
        self.move_duration = move_duration
        self.pause_between = pause_between

    # ─────────────────────────────────────────────────────────
    #  TEK HAMLE
    # ─────────────────────────────────────────────────────────

    def drag_block(self, from_pos, to_pos):
        """Bir blok parçasını from_pos → to_pos'a sürükler."""
        fx, fy = from_pos
        tx, ty = to_pos
        pyautogui.moveTo(fx, fy, duration=0.1)
        pyautogui.mouseDown()
        pyautogui.moveTo(tx, ty, duration=self.move_duration)
        pyautogui.mouseUp()

    def execute_move(self, move_info, grid_info, blocks_data):
        """
        Tek bir hamleyi ekran üzerinde gerçekleştirir.

        move_info   : {"block_idx": int, "r": int, "c": int, ...}
        grid_info   : (gx, gy, gw, gh, cell_size)
        blocks_data : [{"shape": ..., "coords": (bx, by, bw, bh)}, ...]
        """
        block_idx = move_info["block_idx"]
        target_r = move_info["r"]
        target_c = move_info["c"]

        bx, by, bw, bh = blocks_data[block_idx]["coords"]
        from_x = bx + bw // 2
        from_y = by + bh // 2

        gx, gy, gw, gh, cell_size = grid_info
        to_x = gx + target_c * cell_size + cell_size // 2
        to_y = gy + target_r * cell_size + cell_size // 2

        self.drag_block((from_x, from_y), (to_x, to_y))

    # ─────────────────────────────────────────────────────────
    #  TAM SIRALAMA (YENİ)
    # ─────────────────────────────────────────────────────────

    def execute_sequence(self, sequence, grid_info, blocks_data, on_step=None):
        """
        Solver'dan gelen tam sırayı yürütür.

        sequence   : [{"block_idx": int, "r": int, "c": int, ...}, ...]
        on_step    : Her hamleden SONRA çağrılacak callback (isteğe bağlı)
                     İmza: on_step(step_index, move_info)
        """
        for step_idx, move_info in enumerate(sequence):
            self.execute_move(move_info, grid_info, blocks_data)
            if on_step:
                on_step(step_idx, move_info)
            # Tahta güncellenmesi için bekle
            time.sleep(self.pause_between)
