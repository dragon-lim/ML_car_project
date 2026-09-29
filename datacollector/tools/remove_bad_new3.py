"""
apply_audit.py의 dataset_new3(8/12 촬영분) 전용 파생 버전.
로직은 apply_audit.py와 동일하며, 이 배치에서 육안으로 확인된 삭제 대상
번호만 다르다(하늘/건물/신발 등이 찍힌 21장).
"""
import os
import re
import shutil

RAW_DELETE_INDICES = """
126,127,164,172,177,182,183,191,192,259,270,276,333,584,609,845,853,854,1007,1012,1185
"""

text = re.sub(r"\s*~\s*", "~", RAW_DELETE_INDICES)
text = re.sub(r"[^\d~]+", ",", text)
tokens = [t for t in text.split(",") if t]

DELETE_INDICES = set()
for tok in tokens:
    if "~" in tok:
        lo, hi = tok.split("~")
        DELETE_INDICES.update(range(int(lo), int(hi) + 1))
    else:
        DELETE_INDICES.add(int(tok))

print(f"삭제 대상 인덱스 개수: {len(DELETE_INDICES)}")

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
    if idx in DELETE_INDICES:
        shutil.move(fname, os.path.join(remove_dir, fname))
        removed += 1
    else:
        kept += 1

print(f"유지: {kept}장 / 이동(삭제 대상): {removed}장 / 파일 없음: {missing}장")
