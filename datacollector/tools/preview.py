import os
import cv2
import numpy as np
import random

def make_grid(folder, out_name, n=16, cols=4):
    files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
    if len(files) == 0:
        print(f"[{folder}] 이미지 없음")
        return
    sample = random.sample(files, min(n, len(files)))

    thumbs = []
    for f in sample:
        img = cv2.imread(os.path.join(folder, f))
        img = cv2.resize(img, (200, 120))
        cv2.putText(img, f.split("_angle")[1][:6], (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        thumbs.append(img)

    rows = (len(thumbs) + cols - 1) // cols
    grid = np.zeros((rows * 120, cols * 200, 3), dtype=np.uint8)
    for i, t in enumerate(thumbs):
        r, c = i // cols, i % cols
        grid[r*120:(r+1)*120, c*200:(c+1)*200] = t

    cv2.imwrite(out_name, grid)
    print(f"저장됨: {out_name} ({len(thumbs)}장 샘플)")

make_grid(".", "preview_ok.png", n=16)
make_grid("_rejected", "preview_rejected.png", n=16)