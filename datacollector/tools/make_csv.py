import os
import re
import pandas as pd

# 이 스크립트를 dataset 폴더 안에서 실행한다고 가정
dataset_dir = "."

rows = []
pattern = re.compile(r"angle(\d+)_speed(\d+)")

for fname in os.listdir(dataset_dir):
    if not fname.lower().endswith(".png"):
        continue

    match = pattern.search(fname)
    if not match:
        print(f"[SKIP] 패턴 안 맞음: {fname}")
        continue

    angle = int(match.group(1))
    rows.append({
        "image_path": fname,
        "servo_angle": angle
    })

df = pd.DataFrame(rows)
df.to_csv("data_labels_updated.csv", index=False)

print(f"총 {len(df)}개 이미지 처리 완료")
print(df["servo_angle"].value_counts().sort_index())