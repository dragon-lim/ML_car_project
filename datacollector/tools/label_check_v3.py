"""
사진 내용과 저장된 라벨(조향각)이 실제로 일치하는지 검증하는 도구.

원리:
  1) 초록/노랑 테이프 색상을 HSV 기준으로 검출한다.
  2) 화면 상단/하단의 검출 픽셀 평균 위치로 좌우 기울기(편차, deviation)를 계산한다.
  3) 이 편차가 라벨이 속한 방향 그룹(left/center/right)과 일치하는지 비교한다.

동일 장면이 여러 프레임 중복 촬영된 경우 하나의 사건(cluster)으로 묶어 실제
검토가 필요한 독립 사건 수를 계산한다. 또한 화면에 초록/노랑이 모두 검출되는
경우(교차로·합류 지점일 가능성)를 mixed_scene으로 별도 표시해 판정 신뢰도가
낮은 장면을 구분한다.

주의: 이 방법은 완벽하지 않다. 교차로처럼 여러 테이프가 겹쳐 보이는 장면에서는
계산이 부정확할 수 있으므로, single_scene 결과 위주로 우선 신뢰하고
mixed_scene은 참고용으로만 사용할 것. 자세한 검증 배경은 docs/라벨검증_트러블슈팅.md 참고.
"""
import os
import re
import cv2
import numpy as np

FOLDER = "."
OUTPUT_CSV = "label_check_result_v3.csv"
CLUSTER_HIGH_CSV = "clusters_single_scene_priority.csv"
CLUSTER_LOW_CSV = "clusters_mixed_scene_lowpriority.csv"

THRESHOLD = 20
MIXED_SCENE_MIN_RATIO = 0.15  # 초록/노랑 중 소수색이 전체의 15% 이상이면 "혼합 장면"


def label_to_group(angle):
    if angle in (30, 60):
        return "left"
    elif angle == 90:
        return "center"
    elif angle in (120, 150):
        return "right"
    else:
        return "invalid"  # 정의되지 않은 각도(데이터 오염)


def analyze_image(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_green = np.array([35, 30, 30])
    upper_green = np.array([90, 255, 255])
    # 노란 테이프는 실측 결과 채도가 낮게 나타나 기준을 낮춰 설정함
    lower_yellow = np.array([10, 20, 100])
    upper_yellow = np.array([30, 255, 255])

    mask_g = cv2.inRange(hsv, lower_green, upper_green)
    mask_y = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask = cv2.bitwise_or(mask_g, mask_y)

    g_count = cv2.countNonZero(mask_g)
    y_count = cv2.countNonZero(mask_y)
    total_color = g_count + y_count

    scene_type = "single_scene"
    if total_color > 0:
        minor_ratio = min(g_count, y_count) / total_color
        if minor_ratio >= MIXED_SCENE_MIN_RATIO:
            scene_type = "mixed_scene"

    ys, xs = np.where(mask > 0)
    if len(xs) < 50:
        return None, scene_type

    h = img.shape[0]
    top_half = ys < h // 2
    bottom_half = ys >= h // 2
    if top_half.sum() < 20 or bottom_half.sum() < 20:
        return None, scene_type

    top_x = xs[top_half].mean()
    bottom_x = xs[bottom_half].mean()
    top_y = ys[top_half].mean()
    bottom_y = ys[bottom_half].mean()

    dx = top_x - bottom_x   # 위쪽이 아래쪽보다 오른쪽에 있으면 양수
    dy = bottom_y - top_y

    angle_dev = np.degrees(np.arctan2(dx, dy))
    return angle_dev, scene_type


pattern = re.compile(r"angle(\d+)_speed")
rows = []

files = sorted([f for f in os.listdir(FOLDER) if f.lower().endswith(".png")])
print(f"전체 {len(files)}장 처리 시작...")

for i, fname in enumerate(files):
    match = pattern.search(fname)
    if not match:
        continue
    label_angle = int(match.group(1))
    label_group = label_to_group(label_angle)

    if label_group == "invalid":
        rows.append((fname, label_angle, "INVALID_LABEL", "", "INVALID_LABEL", "n/a"))
        continue

    img = cv2.imread(os.path.join(FOLDER, fname))
    if img is None:
        continue

    dev, scene_type = analyze_image(img)
    if dev is None:
        rows.append((fname, label_angle, label_group, "no_tape_found", "", scene_type))
        continue

    if dev > THRESHOLD:
        est_group = "right"
    elif dev < -THRESHOLD:
        est_group = "left"
    else:
        est_group = "center"

    mismatch = "MISMATCH" if est_group != label_group else "match"
    rows.append((fname, label_angle, label_group, f"{dev:.1f}", est_group + "_" + mismatch, scene_type))

    if (i + 1) % 500 == 0:
        print(f"  {i+1}/{len(files)} 처리됨...")

with open(OUTPUT_CSV, "w", encoding="utf-8") as f:
    f.write("filename,label_angle,label_group,estimated_deviation,estimated_group_and_match,scene_type\n")
    for r in rows:
        f.write(",".join(str(x) for x in r) + "\n")


# ===== 연속 중복 프레임을 하나의 "사건(cluster)"으로 묶기 =====
def build_clusters(target_rows):
    clusters = []
    current = None
    for r in target_rows:
        fname, label_angle, label_group, dev_str, result, scene_type = r
        is_mismatch = "MISMATCH" in result
        try:
            dev_val = float(dev_str)
        except ValueError:
            dev_val = None

        if current is None:
            current = {"start": fname, "count": 1, "label_angle": label_angle,
                       "dev_repr": dev_val, "is_mismatch": is_mismatch,
                       "result": result, "scene_type": scene_type}
            continue

        same = (label_angle == current["label_angle"] and is_mismatch == current["is_mismatch"]
                and dev_val is not None and current["dev_repr"] is not None
                and abs(dev_val - current["dev_repr"]) <= 2.0)

        if same:
            current["count"] += 1
        else:
            clusters.append(current)
            current = {"start": fname, "count": 1, "label_angle": label_angle,
                       "dev_repr": dev_val, "is_mismatch": is_mismatch,
                       "result": result, "scene_type": scene_type}
    if current is not None:
        clusters.append(current)
    return [c for c in clusters if c["is_mismatch"]]


single_rows = [r for r in rows if r[5] == "single_scene"]
mixed_rows = [r for r in rows if r[5] == "mixed_scene"]

single_clusters = build_clusters(single_rows)
mixed_clusters = build_clusters(mixed_rows)

single_clusters.sort(key=lambda c: -c["count"])
mixed_clusters.sort(key=lambda c: -c["count"])

with open(CLUSTER_HIGH_CSV, "w", encoding="utf-8") as f:
    f.write("representative_file,frame_count,label_angle,estimated_deviation,result\n")
    for c in single_clusters:
        f.write(f"{c['start']},{c['count']},{c['label_angle']},{c['dev_repr']},{c['result']}\n")

with open(CLUSTER_LOW_CSV, "w", encoding="utf-8") as f:
    f.write("representative_file,frame_count,label_angle,estimated_deviation,result\n")
    for c in mixed_clusters:
        f.write(f"{c['start']},{c['count']},{c['label_angle']},{c['dev_repr']},{c['result']}\n")

total = len(rows)
mismatch_count = sum(1 for r in rows if "MISMATCH" in r[4])
invalid_count = sum(1 for r in rows if r[2] == "INVALID_LABEL")
no_tape_count = sum(1 for r in rows if r[3] == "no_tape_found")
single_scene_count = len(single_rows)
mixed_scene_count = len(mixed_rows)

print(f"\n=== 결과 요약 ===")
print(f"전체: {total}장")
print(f"단일 장면(single_scene): {single_scene_count}장 -> MISMATCH 클러스터: {len(single_clusters)}건 (우선 확인 대상)")
print(f"혼합 장면(mixed_scene, 교차로 의심): {mixed_scene_count}장 -> MISMATCH 클러스터: {len(mixed_clusters)}건 (참고용, 신뢰도 낮음)")
print(f"비정상 라벨: {invalid_count}장")
print(f"테이프 못 찾음: {no_tape_count}장")
print(f"\n저장 파일:")
print(f"  - 전체 결과: {OUTPUT_CSV}")
print(f"  - 우선 확인 대상: {CLUSTER_HIGH_CSV}")
print(f"  - 참고용(교차로 의심): {CLUSTER_LOW_CSV}")
