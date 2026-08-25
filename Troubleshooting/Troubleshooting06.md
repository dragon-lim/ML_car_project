현재 가지고 있는 데이터셋(프레임 약 7000장)의 scv 의 label 값이 정확한 정답인지 아닌지 알 수 없어서
이미지를 스크립트로 정확한 label을 추려낼지 Ai에게 교육하는 방식으로 할지 고민중

<진행 단계>
1단계: 규칙 기반 코드로 약 2000장의 "계산된 각도"를 구함
2단계: "계산된 각도 vs 실제 라벨" 차이가 큰 순서로 정렬
3단계: 차이가 큰 것 150장(비정상 후보) + 차이가 작은 것 150장(정상 후보)을 뽑음
4단계: 사람이 이 300장을 눈으로 최종 확인해서 "적합/부적합" 진짜 정답을 매김
5단계: 이 300장(정답 있음)으로 "적합/부적합 판별 AI"를 학습
6단계: 이 판별 AI로 나머지 7000장 이상을 자동 판별


우선은 규칙 기반으로 이미지를 전처리
# 데이터 정리 & 라벨 검증 도구 모음

`datacollector/dataset/` 에서 촬영한 원본 사진을 학습 가능한 상태로 만들기까지 사용한
스크립트들을 정리한 문서입니다. 크게 두 단계로 나뉩니다.

- **1단계 (품질 정리)**: 화질/구도 문제가 있는 사진을 걸러내는 도구 — `clean_dataset.py`,
  `preview.py`, `audit.py`, `apply_audit.py`
- **2단계 (라벨 검증)**: 사진과 라벨(조향각)이 실제로 일치하는지 검증하고 수정하는 도구 —
  `label_check_v3.py`, `filter_high_confidence.py`, `relabel_high_confidence.py`
- **공통 유틸리티**: `make_csv.py`, `remove_bad_new3.py`

전체 흐름은 문서 맨 아래 "전체 파이프라인" 참고.

---

## 1단계: 품질 정리

### `clean_dataset.py`

블러(흐림), 노출 이상, 단색/빈 화면을 자동으로 검출해 걸러내는 1차 필터.

- 라플라시안 분산(`cv2.Laplacian(...).var()`)으로 흐림 정도를 판정 (`BLUR_THRESHOLD`)
- 평균 밝기로 과다 노출/저노출 판정 (`BRIGHT_MIN`, `BRIGHT_MAX`)
- RGB 채널 표준편차로 단색에 가까운(차선이 안 보이는) 사진 판정 (`PINK_STD_THRESHOLD`)
- 문제로 판정된 사진은 삭제하지 않고 `_rejected/` 폴더로 이동

```python
import os
import shutil
import cv2

dataset_dir = "."
reject_dir = "_rejected"
os.makedirs(reject_dir, exist_ok=True)

BLUR_THRESHOLD = 15.0   # 촬영 환경(역광/글레어 유무)에 따라 조정 필요
BRIGHT_MIN = 20
BRIGHT_MAX = 235
PINK_STD_THRESHOLD = 15

def check_image(path):
    img = cv2.imread(path)
    if img is None:
        return "read_fail", None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        return "blurry", blur_score

    mean_bright = gray.mean()
    if mean_bright < BRIGHT_MIN or mean_bright > BRIGHT_MAX:
        return "bad_exposure", mean_bright

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

print("\n=== 요약 ===")
for k, v in results.items():
    print(f"{k}: {v}")
```

**주의**: 역광/글레어가 있는 촬영 환경에서는 정상 사진까지 blurry로 오판하는 경우가 많았다.
threshold를 낮추기 전에 `preview.py`로 실제 오탐 여부를 먼저 확인할 것.

---

### `preview.py`

`clean_dataset.py`의 필터링이 제대로 작동했는지 **랜덤 샘플로 빠르게 검증**하는 도구.
`ok`(통과)와 `_rejected`(걸러짐) 각각에서 16장씩 뽑아 4x4 그리드 이미지로 저장한다.

```python
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
```

---

### `audit.py`

`preview.py`가 랜덤 샘플만 보여주는 것과 달리, **전체 사진을 번호 매겨 그리드로 전수 검사**할
때 사용. 20장씩 페이지로 나눠 `audit_page0.png ~ pageN.png`를 생성하고, 번호-파일명 매핑을
`audit_index.txt`에 저장한다.

```python
import os
import cv2
import numpy as np

def make_labeled_grid(folder, out_prefix, per_page=20, cols=5):
    files = sorted([f for f in os.listdir(folder) if f.lower().endswith(".png")])
    n_pages = (len(files) + per_page - 1) // per_page

    for page in range(n_pages):
        chunk = files[page*per_page : (page+1)*per_page]
        rows = (len(chunk) + cols - 1) // cols
        cell_w, cell_h = 220, 150
        grid = np.zeros((rows*cell_h, cols*cell_w, 3), dtype=np.uint8)

        for i, f in enumerate(chunk):
            img = cv2.imread(os.path.join(folder, f))
            img = cv2.resize(img, (200, 120))
            r, c = i // cols, i % cols
            grid[r*cell_h:r*cell_h+120, c*cell_w:c*cell_w+200] = img
            cv2.putText(grid, f"[{page*per_page+i}]", (c*cell_w+5, r*cell_h+135),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        out_name = f"{out_prefix}_page{page}.png"
        cv2.imwrite(out_name, grid)
        print(f"저장됨: {out_name}")

    with open(f"{out_prefix}_index.txt", "w", encoding="utf-8") as f:
        for i, name in enumerate(files):
            f.write(f"[{i}] {name}\n")

make_labeled_grid(".", "audit")
```

사람이 그리드를 눈으로 보면서 "천장/난간/신발이 찍힌 사진", "차선이 안 보이는 사진" 등의
번호를 골라내면, 그 번호 목록을 `apply_audit.py`에 입력해 실제로 처리한다.

---

### `apply_audit.py`

`audit.py`로 사람이 확인한 **번호 목록을 실제 파일 이동(삭제)으로 실행**하는 스크립트.
"이 번호들만 남기고 나머지 삭제" 또는 "이 번호들만 삭제" 두 방식 모두 가능하도록, 범위
표기(`14~28,34,41` 등)를 파싱해서 처리한다.

```python
import os
import re
import shutil

# 예시: 살릴 번호 범위 (사람이 audit 그리드를 보고 확정한 목록)
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
```

### `remove_bad_new3.py`

`apply_audit.py`의 특정 데이터 배치(`dataset_new3`, 8/12 촬영분) 전용 파생 버전. 로직은
동일하며, 그 배치에서 확인된 삭제 대상 번호만 다르다. 여러 배치를 각각 오디트할 때는 이런
식으로 대상 폴더별 파생 스크립트를 만들어 사용했다.

---

## 2단계: 라벨 검증 (사진-각도 일치 여부 확인)

1단계가 "사진 자체의 품질"을 본다면, 2단계는 **"사진 내용과 저장된 라벨(조향각)이 실제로
일치하는가"**를 검증한다.

<img width="640" height="480" alt="preview" src="https://github.com/user-attachments/assets/48ebcb01-5632-4897-9211-0e7df697e551" />
<img width="640" height="480" alt="preview (1)" src="https://github.com/user-attachments/assets/ff15f4ee-8f94-494c-b1e1-39aeecaa91d9" />
<img width="640" height="480" alt="preview (2)" src="https://github.com/user-attachments/assets/75d66c5b-814c-40cb-8fd4-5e800898f3cb" />



### `label_check_v3.py`

이미지에서 초록/노란 테이프 색상을 검출하고, 화면 상/하단 픽셀 분포로 기울기(편차)를
계산해 라벨과 비교한다. 동일 장면이 여러 프레임 중복 촬영된 경우 하나의 사건(cluster)으로
묶고, 화면에 두 색이 모두 검출되는 교차로 의심 장면(`mixed_scene`)은 별도로 낮은 신뢰도로
분류한다.

```python
import os
import re
import cv2
import numpy as np

FOLDER = "."
THRESHOLD = 20
MIXED_SCENE_MIN_RATIO = 0.15

def label_to_group(angle):
    if angle in (30, 60):
        return "left"
    elif angle == 90:
        return "center"
    elif angle in (120, 150):
        return "right"
    else:
        return "invalid"

def analyze_image(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 30, 30]); upper_green = np.array([90, 255, 255])
    lower_yellow = np.array([10, 20, 100]); upper_yellow = np.array([30, 255, 255])

    mask_g = cv2.inRange(hsv, lower_green, upper_green)
    mask_y = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask = cv2.bitwise_or(mask_g, mask_y)

    g_count, y_count = cv2.countNonZero(mask_g), cv2.countNonZero(mask_y)
    total_color = g_count + y_count
    scene_type = "single_scene"
    if total_color > 0 and min(g_count, y_count) / total_color >= MIXED_SCENE_MIN_RATIO:
        scene_type = "mixed_scene"

    ys, xs = np.where(mask > 0)
    if len(xs) < 50:
        return None, scene_type

    h = img.shape[0]
    top_half, bottom_half = ys < h // 2, ys >= h // 2
    if top_half.sum() < 20 or bottom_half.sum() < 20:
        return None, scene_type

    dx = xs[top_half].mean() - xs[bottom_half].mean()
    dy = ys[bottom_half].mean() - ys[top_half].mean()
    return np.degrees(np.arctan2(dx, dy)), scene_type

# 전체 파일 순회, 라벨 비교, 클러스터링, CSV 저장 로직은
# label_check_v3.py 전체 소스 참고 (분류 결과: single_scene 우선 확인 / mixed_scene 참고용)
```

### `filter_high_confidence.py`

`label_check_v3.py` 결과 중, 실제 검증(표본 12건, 적중률 92%)으로 확인된 신뢰도 높은
조건만 걸러낸다.

```python
def is_high_confidence(label_angle, dev):
    if label_angle == 90:
        return abs(dev) >= 30
    if label_angle in (120, 150):
        return dev <= 20
    if label_angle in (30, 60):
        return dev >= -20
    return False
```

### `relabel_high_confidence.py`

확신도 높은 오류로 확인된 클러스터의 편차값을 새로운 표준 각도로 매핑하여, 해당 클러스터에
속한 모든 프레임의 파일명(`angleXX` 부분)을 일괄 변경한다. 실행 전 원본은
`_before_relabel_backup/`에 자동 백업한다.

```python
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
```

**검증 결과**: 서로 다른 3개 촬영 배치에 적용한 결과 모두 단일 장면(single_scene) 기준
MISMATCH가 79~85% 감소하는 효과를 재현 확인했다.

---

## 공통 유틸리티

### `make_csv.py`

정리·검증이 끝난 최종 사진들로 학습용 라벨 CSV(`data_labels_updated.csv`)를 생성한다.
파일명의 `angleXX_speedYY` 패턴을 정규식으로 파싱해 `image_path, servo_angle` 두 컬럼으로
저장한다.

```python
import os
import re
import pandas as pd

dataset_dir = "."
rows = []
pattern = re.compile(r"angle(\d+)_speed(\d+)")

for fname in os.listdir(dataset_dir):
    if not fname.lower().endswith(".png"):
        continue
    match = pattern.search(fname)
    if not match:
        continue
    angle = int(match.group(1))
    rows.append({"image_path": fname, "servo_angle": angle})

df = pd.DataFrame(rows)
df.to_csv("data_labels_updated.csv", index=False)

print(f"총 {len(df)}개 이미지 처리 완료")
print(df["servo_angle"].value_counts().sort_index())
```

---

## 전체 파이프라인

```
촬영 (img-collector.py, Jetson)
  │
  ▼
clean_dataset.py   ─ 블러/노출/단색 자동 필터
  │
  ▼
preview.py         ─ 필터 결과 랜덤 샘플 검증 (오탐 확인)
  │
  ▼
audit.py           ─ 전수 검사용 그리드 생성
  │
  ▼
apply_audit.py /   ─ 사람이 확인한 문제 사진 제거
remove_bad_new3.py   (배치별 파생 스크립트)
  │
  ▼
label_check_v3.py  ─ 사진-라벨 일치 여부 검증 (색상 기반 기하 계산)
  │
  ▼
filter_high_confidence.py ─ 신뢰도 높은 오류만 필터링
  │
  ▼
relabel_high_confidence.py ─ 자동 라벨 재수정 (파일명 변경)
  │
  ▼
make_csv.py        ─ 최종 학습용 라벨 CSV 생성
  │
  ▼
학습 (training/train_pilotnet.py)
```

## 사용상 주의사항

- 여러 배치의 데이터를 병합할 때는 파일명이 촬영 시각 기반이라 서로 다른 배치 간에도
  우연히 겹칠 수 있다. 병합 전 반드시 파일명 중복 여부를 확인할 것 (`Compare-Object` 등).
- `relabel_high_confidence.py`, `apply_audit.py`류는 파일을 직접 변경/이동하므로, 실행 전
  전체 폴더를 별도로 백업해두는 것을 권장
- 라벨 검증(2단계) 방법론은 완벽하지 않다. 순환 논리, 표본 검증의 한계 등 자세한 내용은
  `docs/라벨검증_트러블슈팅.md`를 참고하시길!!
