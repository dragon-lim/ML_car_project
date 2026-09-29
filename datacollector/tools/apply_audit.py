"""
audit.py로 사람이 확인한 번호 목록을 실제 파일 이동(삭제)으로 실행하는 스크립트.
RAW_KEEP_RANGES에 "살릴 번호" 범위를 적으면, 그 외의 사진들은 _removed_audit로 이동한다.
(반대로 "지울 번호" 목록을 쓰고 싶으면 로직을 KEEP -> DELETE 기준으로 바꿔서 사용)

각 데이터 배치(폴더)마다 삭제 대상 번호가 다르므로, 배치별로 이 스크립트를 복사해
RAW_KEEP_RANGES만 교체해서 사용한다. (예: remove_bad_new3.py는 이 템플릿의
dataset_new3 배치 전용 버전)
"""
import os
import re
import shutil

# 예시: 사람이 audit 그리드를 보고 확정한, 살릴 번호 범위
RAW_KEEP_RANGES = """
14~28,34~38,41,42,44~67,69~80,82~131
"""

text = re.sub(r"\s*~\s*", "~", RAW_KEEP_RANGES)
text = re.sub(r"[^\d~]+", ",", text)
tokens = [t for t in text.split(",") if t]

KEEP_INDICES = set()
for tok in tokens:
    if "~" in tok:
        lo, hi = tok.split("~")
        KEEP_INDICES.update(range(int(lo), int(hi) + 1))
    else:
        KEEP_INDICES.add(int(tok))

print(f"유지 대상 인덱스 개수: {len(KEEP_INDICES)}")

index_map = {}
with open("audit_index.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        idx_str, fname = line.split("]", 1)
        index_map[int(idx_str.strip("["))] = fname.strip()

remove_dir = "_removed_audit"
os.makedirs(remove_dir, exist_ok=True)

kept, removed, missing = 0, 0, 0
for idx, fname in index_map.items():
    if not os.path.exists(fname):
        missing += 1
        continue
    if idx in KEEP_INDICES:
        kept += 1
    else:
        shutil.move(fname, os.path.join(remove_dir, fname))
        removed += 1

print(f"유지: {kept}장 / 이동(삭제 대상): {removed}장 / 파일 없음: {missing}장")
