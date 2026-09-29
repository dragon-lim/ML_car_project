import os
import random

TARGET_ANGLE = 90
KEEP_COUNT = 500

files = [f for f in os.listdir(".") if f.endswith(".png") and f"angle{TARGET_ANGLE}_" in f]
print(f"현재 {TARGET_ANGLE}도: {len(files)}장")

if len(files) > KEEP_COUNT:
    random.shuffle(files)
    to_remove = files[KEEP_COUNT:]
    os.makedirs("_reduced", exist_ok=True)
    for f in to_remove:
        os.replace(f, os.path.join("_reduced", f))
    print(f"{len(to_remove)}장을 _reduced 폴더로 이동, {KEEP_COUNT}장 남김")
else:
    print("이미 목표치 이하라 줄일 필요 없음")