import os
import cv2
import numpy as np

def make_labeled_grid(folder, out_prefix, per_page=20, cols=5):
    files = sorted([f for f in os.listdir(folder) if f.lower().endswith(".png")])
    n_pages = (len(files) + per_page - 1) // per_page

    for page in range(n_pages):
        chunk = files[page*per_page : (page+1)*per_page]
        rows = (len(chunk) + cols - 1) // cols
        cell_w, cell_h = 220, 150
        grid = np.zeros((rows*cell_h, cols*cell_w, 3), dtype=np.uint8)

        for i, f in enumerate(chunk):
            img = cv2.imread(os.path.join(folder, f))
            img = cv2.resize(img, (200, 120))
            r, c = i // cols, i % cols
            grid[r*cell_h:r*cell_h+120, c*cell_w:c*cell_w+200] = img
            # 파일명에서 번호만 짧게 표시 (전체 파일명은 콘솔에 따로 출력)
            cv2.putText(grid, f"[{page*per_page+i}]", (c*cell_w+5, r*cell_h+135),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        out_name = f"{out_prefix}_page{page}.png"
        cv2.imwrite(out_name, grid)
        print(f"저장됨: {out_name}")

    # 인덱스-파일명 매핑을 텍스트로도 저장 (나중에 삭제할 때 참조용)
    with open(f"{out_prefix}_index.txt", "w", encoding="utf-8") as f:
        for i, name in enumerate(files):
            f.write(f"[{i}] {name}\n")

make_labeled_grid(".", "audit")