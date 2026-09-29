"""
filter_high_confidence.py로 확인된 신뢰도 높은 오류 클러스터에 대해,
편차값을 새로운 표준 각도(30/60/90/120/150)로 매핑하여 해당 클러스터에 속한
모든 프레임의 파일명(angleXX 부분)을 일괄 변경한다.
실행 전 원본은 _before_relabel_backup/ 에 자동으로 백업한다.

검증 결과: 서로 다른 3개 촬영 배치에 적용한 결과 모두 단일 장면(single_scene)
기준 MISMATCH가 79~85% 감소하는 효과를 재현 확인했다.
(자세한 내용은 docs/라벨검증_트러블슈팅.md 참고)
"""
import os
import csv
import re
import shutil

INPUT_CSV = "final_high_confidence_errors.csv"
CLUSTER_INDEX_CSV = "label_check_result_v3.csv"
BACKUP_DIR = "_before_relabel_backup"
LOG_FILE = "relabel_log.csv"

os.makedirs(BACKUP_DIR, exist_ok=True)


def dev_to_new_angle(dev):
    if dev < -70:
        return 30
    elif dev < -35:
        return 60
    elif dev <= 35:
        return 90
    elif dev <= 70:
        return 120
    else:
        return 150


target_reps = {}
with open(INPUT_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        target_reps[row["representative_file"]] = row

print(f"재수정 대상 클러스터: {len(target_reps)}건")

all_rows = []
with open(CLUSTER_INDEX_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        all_rows.append(row)


def find_cluster_files(rep_file):
    idx = next((i for i, r in enumerate(all_rows) if r["filename"] == rep_file), None)
    if idx is None:
        return [rep_file]

    rep_row = all_rows[idx]
    try:
        rep_dev = float(rep_row["estimated_deviation"])
    except ValueError:
        return [rep_file]

    label_angle = rep_row["label_angle"]
    files = [rep_file]
    j = idx + 1
    while j < len(all_rows):
        r = all_rows[j]
        try:
            dev_j = float(r["estimated_deviation"])
        except ValueError:
            break
        if r["label_angle"] == label_angle and abs(dev_j - rep_dev) <= 2.0 and "MISMATCH" in r["estimated_group_and_match"]:
            files.append(r["filename"])
            j += 1
        else:
            break
    return files


pattern = re.compile(r"(angle)(\d+)(_speed)")
renamed = 0
skipped_missing = 0
log_rows = []

for rep_file, info in target_reps.items():
    dev = float(info["estimated_deviation"])
    new_angle = dev_to_new_angle(dev)
    old_angle = int(info["label_angle"])

    if new_angle == old_angle:
        continue

    cluster_files = find_cluster_files(rep_file)

    for fname in cluster_files:
        if not os.path.exists(fname):
            skipped_missing += 1
            continue

        new_fname = pattern.sub(rf"\g<1>{new_angle}\g<3>", fname)
        if new_fname == fname:
            continue

        shutil.copy(fname, os.path.join(BACKUP_DIR, fname))
        if os.path.exists(new_fname):
            base, ext = os.path.splitext(new_fname)
            new_fname = f"{base}_relabel{ext}"
        os.rename(fname, new_fname)

        log_rows.append((fname, new_fname, old_angle, new_angle, dev))
        renamed += 1

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("old_filename,new_filename,old_angle,new_angle,deviation\n")
    for row in log_rows:
        f.write(",".join(str(x) for x in row) + "\n")

print(f"\n=== 완료 ===")
print(f"라벨 재수정(파일명 변경)된 파일: {renamed}장")
print(f"찾을 수 없어 건너뜀: {skipped_missing}장")
print(f"백업 위치: {BACKUP_DIR}/")
print(f"변경 로그: {LOG_FILE}")
