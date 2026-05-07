"""
main.py — Terminalde hızlı test/debug modu.
GUI için ui.py'yi çalıştırın.
"""
import cv2
import time
import numpy as np
from vision import BlockBlastVision
from solver import BlockBlastAI

def main():
    window_name = "LetsView [Cast]"
    print("Block Blast! Bot — Debug Modu")
    print("(GUI için: python ui.py)")
    print("------------------------------")

    vision    = BlockBlastVision(window_title=window_name)
    ai_engine = BlockBlastAI()
    start_t   = time.time()

    while True:
        key   = cv2.waitKey(1) & 0xFF
        frame = vision.capture_screen()
        grid  = vision.find_grid(frame)

        t     = time.time() - start_t
        pulse = (np.sin(t * 10) + 1) / 2

        if grid:
            x, y, w, h = grid
            cell_size   = w // 8
            matrix      = vision.get_board_matrix(frame)
            blocks_data = vision.get_blocks(frame)

            if matrix is not None:
                fullness   = int(np.sum(matrix))
                risk_color = (0, 200, 80)
                if fullness > 35: risk_color = (0, 200, 200)
                if fullness > 50: risk_color = (0, 60, 220)

                # Risk barı
                cv2.rectangle(frame, (x, y-50), (x+w, y-38), (40, 40, 40), -1)
                bar_w = int((fullness / 64) * w)
                cv2.rectangle(frame, (x, y-50), (x+bar_w, y-38), risk_color, -1)
                cv2.putText(frame, f"RISK: {int((fullness/64)*100)}%",
                            (x+w+8, y-38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, risk_color, 2)

                if fullness > 45:
                    alpha   = 0.3 + 0.5 * pulse
                    overlay = frame.copy()
                    cv2.putText(overlay, "!!! KRITIK !!!", (x+w//4, y+h//2),
                                cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 60, 220), 3)
                    cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)

                # Dolu hücreleri işaretle
                for r in range(8):
                    for c in range(8):
                        if matrix[r, c] == 1:
                            cx_ = x + c*cell_size + cell_size//2
                            cy_ = y + r*cell_size + cell_size//2
                            cv2.circle(frame, (cx_, cy_), 4, (0, 220, 100), -1)

            shapes       = [b["shape"] for b in blocks_data]
            valid_indices = [i for i, b in enumerate(blocks_data) if b["shape"] is not None]

            if shapes and any(s is not None for s in shapes):
                result = ai_engine.find_best_sequence(matrix, shapes)

                if result:
                    seq = result["sequence"]
                    if seq:
                        m0         = seq[0]
                        actual_idx = valid_indices[m0["block_idx"]] if m0["block_idx"] < len(valid_indices) else 0
                        target_r, target_c = m0["r"], m0["c"]

                        # Bloğu vurgula
                        bx, by, bw_, bh_ = blocks_data[actual_idx]["coords"]
                        cv2.rectangle(frame, (bx, by), (bx+bw_, by+bh_), (255, 220, 0), 4)

                        block_shape = np.array(shapes[m0["block_idx"]])
                        for br in range(block_shape.shape[0]):
                            for bc in range(block_shape.shape[1]):
                                if block_shape[br, bc] == 1:
                                    tx = x + (target_c+bc)*cell_size
                                    ty = y + (target_r+br)*cell_size
                                    ov = frame.copy()
                                    cv2.rectangle(ov, (tx+2, ty+2),
                                                  (tx+cell_size-2, ty+cell_size-2),
                                                  (0, 220, 220), -1)
                                    cv2.addWeighted(ov, 0.3+0.3*pulse,
                                                    frame, 0.7-0.3*pulse, 0, frame)
                                    cv2.rectangle(frame, (tx+2, ty+2),
                                                  (tx+cell_size-2, ty+cell_size-2),
                                                  (0, 220, 220), 2)

                        ax_s = (bx+bw_//2, by)
                        ax_e = (x + target_c*cell_size + block_shape.shape[1]*cell_size//2,
                                y + target_r*cell_size + block_shape.shape[0]*cell_size//2)
                        cv2.arrowedLine(frame, ax_s, ax_e, (255,255,255), 4, tipLength=0.1)

                        # Sıra bilgisi
                        for step_i, step_m in enumerate(seq):
                            txt = f"{'1.' if step_i==0 else '2.' if step_i==1 else '3.'} Blok {step_m['block_idx']+1} → ({step_m['r']+1},{step_m['c']+1})"
                            cv2.putText(frame, txt, (x+w+10, y + 20 + step_i*22),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220,220,220), 1)

        disp = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        cv2.imshow("Block Blast! Debug", disp)

        if key == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
