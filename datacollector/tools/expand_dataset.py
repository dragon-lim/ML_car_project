"""
오프라인 리샘플링(오버샘플링) 스크립트
원본 이미지 각각에 대해 원본/좌우반전/밝게/어둡게 4가지 버전을 실제 파일로 생성하여
데이터셋 자체를 물리적으로 4배 증량한다.
좌우반전 시 라벨(조향각)도 flip_map에 따라 함께 변경하여 파일명에 반영한다.
"""
import os
import cv2
import numpy as np
import re

SRC_DIR = "."
OUT_DIR = "expanded"
os.makedirs(OUT_DIR, exist_ok=True)

FLIP_MAP = {30: 150, 60: 120, 90: 90, 120: 60, 150: 30}
pattern = re.compile(r"angle(\d+)_speed(\d+)")

files = [f for f in os.listdir(SRC_DIR) if f.lower().endswith(".png")]
print(f"원본 파일 수: {len(files)}")

count = 0
for fname in files:
    match = pattern.search(fname)
    if not match:
        continue
    angle = int(match.group(1))

    img = cv2.imread(os.path.join(SRC_DIR, fname))
    if img is None:
        continue

    base_name = fname.rsplit(".png", 1)[0]

    # 1) 원본 그대로 복사
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_orig.png"), img)
    count += 1

    # 2) 좌우반전 (라벨도 flip_map으로 변경하여 파일명에 반영)
    flipped = cv2.flip(img, 1)
    flipped_angle = FLIP_MAP.get(angle, angle)
    flipped_name = f"{base_name.replace(f'angle{angle}_', f'angle{flipped_angle}_')}_flip.png"
    cv2.imwrite(os.path.join(OUT_DIR, flipped_name), flipped)
    count += 1

    # 3) 밝게
    bright = np.clip(img.astype(np.float32) * 1.2, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_bright.png"), bright)
    count += 1

    # 4) 어둡게
    dark = np.clip(img.astype(np.float32) * 0.8, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_dark.png"), dark)
    count += 1

print(f"총 생성된 파일 수: {count}")
