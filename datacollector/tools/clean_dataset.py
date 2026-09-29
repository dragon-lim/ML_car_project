import os
import shutil
import cv2
import numpy as np

dataset_dir = "."
reject_dir = "_rejected"
os.makedirs(reject_dir, exist_ok=True)

# 기준값 (필요하면 조정)
BLUR_THRESHOLD = 15.0      # 이 값보다 낮으면 초점 나감(흐림)으로 판단
BRIGHT_MIN = 20             # 너무 어두운 사진(평균 밝기) 기준
BRIGHT_MAX = 235            # 너무 밝은/날아간 사진 기준
PINK_STD_THRESHOLD = 15     # 채널별 표준편차가 낮으면 단색으로 날아간 것으로 판단

def check_image(path):
    img = cv2.imread(path)
    if img is None:
        return "read_fail", None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1) 흐림 판정 (라플라시안 분산)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        return "blurry", blur_score

    # 2) 밝기 이상 판정 (너무 어둡거나 날아감)
    mean_bright = gray.mean()
    if mean_bright < BRIGHT_MIN or mean_bright > BRIGHT_MAX:
        return "bad_exposure", mean_bright

    # 3) 단색으로 날아간 사진 판정 (예: 스샷의 분홍색 사진)
    b, g, r = cv2.split(img)
    std_total = (b.std() + g.std() + r.std()) / 3
    if std_total < PINK_STD_THRESHOLD:
        return "flat_color", std_total

    return "ok", None


results = {"ok": 0, "blurry": 0, "bad_exposure": 0, "flat_color": 0, "read_fail": 0}

for fname in os.listdir(dataset_dir):
    if not fname.lower().endswith(".png"):
        continue

    path = os.path.join(dataset_dir, fname)
    status, score = check_image(path)
    results[status] += 1

    if status != "ok":
        shutil.move(path, os.path.join(reject_dir, fname))
        print(f"[{status}] {fname} (score={score})")

print("\n=== 요약 ===")
for k, v in results.items():
    print(f"{k}: {v}")