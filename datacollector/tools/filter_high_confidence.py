"""
label_check_v3.py 결과(clusters_single_scene_priority.csv) 중, 육안 표본 검증
(12건, 적중률 약 92%)으로 확인된 신뢰도 높은 조건만 걸러낸다.

조건:
  - 90도(직진) 라벨인데 편차의 절댓값이 30 이상
  - 120/150도(우회전) 라벨인데 편차가 20 이하 (직진처럼 보이거나 반대 방향)
  - 30/60도(좌회전) 라벨인데 편차가 -20 이상 (직진처럼 보이거나 반대 방향)
"""
import csv

INPUT_CSV = "clusters_single_scene_priority.csv"
OUTPUT_HIGH_CONFIDENCE = "final_high_confidence_errors.csv"


def is_high_confidence(label_angle, dev):
    try:
        dev = float(dev)
    except (ValueError, TypeError):
        return False

    if label_angle == 90:
        return abs(dev) >= 30
    if label_angle in (120, 150):
        return dev <= 20
    if label_angle in (30, 60):
        return dev >= -20
    return False


rows = []
with open(INPUT_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        label_angle = int(row["label_angle"])
        dev = row["estimated_deviation"]
        if is_high_confidence(label_angle, dev):
            rows.append(row)

rows.sort(key=lambda r: -int(r["frame_count"]))

with open(OUTPUT_HIGH_CONFIDENCE, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["representative_file", "frame_count", "label_angle", "estimated_deviation", "result"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

total_frames = sum(int(r["frame_count"]) for r in rows)
print(f"확신도 높은 라벨 오류 후보: {len(rows)}건 (총 {total_frames}프레임)")
print(f"저장 완료: {OUTPUT_HIGH_CONFIDENCE}")
