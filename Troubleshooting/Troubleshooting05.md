# 데이터 증강 & 학습 방법 개선 트러블슈팅

## 배경

오디트(데이터 정제)를 통해 데이터 품질은 개선했지만, 절대적인 데이터 양(1,944장)이
여전히 적어 test_acc가 44~49% 사이에서 정체되는 문제가 있었다. 
날씨 등 외부 조건, 과제 마감 기간(8월 안)을 생각하여 촬영을 추가로 하지 않고
데이터를 늘리는 방법(증강, augmentation)과 학습 방식 자체를 개선해 이 문제를 해결한 과정을 정리한다.

---

## 1. 파인튜닝 시도 — 실패 사례 (중요한 반면교사)

### 시도한 것
기존에 44.40% 성능을 낸 체크포인트(`.pth`)를 불러온 뒤, 새로 촬영한 데이터(30/120도 위주)만
가지고 낮은 learning rate(1e-5)로 추가 학습(fine-tuning)을 시도했다.

### 결과
- 전체 각도가 섞인 새 데이터로 파인튜닝: test_acc **23.57%**로 붕괴
- 30/120도 위주 + 나머지 각도 소량 포함 데이터로 재시도: test_acc **31.40%**로 여전히 붕괴

두 시도 모두 원본 체크포인트(44.40%)보다 크게 낮은 성능이 나왔다.

### 원인 분석
- 기존 체크포인트 자체가 아직 정확도 40%대의 불안정한 상태였고, 이런 얕은 기반 위에서는
  파인튜닝 시 조금만 건드려도 기존 지식이 쉽게 무너지는 **파국적 망각(catastrophic forgetting)** 이 발생함
- Epoch 1부터 이미 성능이 크게 떨어진 채로 시작하는 것으로 보아, learning rate를 낮춰도
  첫 배치 학습만으로 급격히 흔들리는 것을 확인함

### 결론
**"기반 모델이 이미 충분히 좋을 때(예: test_acc 80% 이상)만 파인튜닝이 유효하다.**
지금처럼 기반 모델 자체가 불안정한 단계에서는, 전체 데이터를 합쳐 처음부터
다시 학습하는 것이 안전하다.

---

## 2. 온라인 데이터 증강 (Data Augmentation) 적용

### 배경
프로젝트 코드에 이미 `RCAugmentor` 클래스가 준비되어 있었으나, `train_pilotnet.py`에서
`augmentor=None`으로 설정되어 실제로 한 번도 적용되지 않고 있었다.

### 적용 1 — 기존 기능 활성화 (hflip / 밝기 / 블러)

`RCAugmentor`는 좌우 반전 시 라벨(조향각)도 함께 대칭 변환하는 `flip_map`이 이미 구현되어 있어 안전하게 사용 가능했다.

```python
self.flip_map = {30: 150, 60: 120, 90: 90, 120: 60, 150: 30}
```

`train_pilotnet.py`에서 한 줄만 수정:

```python
train_dataset = RCDataset(
    ...
    augmentor=augment,   # 기존 None → augment 로 변경
    ...
)
```

(단, `test_dataset`은 검증 정확도를 왜곡하지 않도록 `augmentor=None`을 그대로 유지)

**결과**: Best test_acc는 소폭 하락(49.83% → 47.69%)했지만, train_acc와 test_acc의 격차가
**12.1%p → 4.2%p로 크게 감소**했다. 이는 모델이 학습 데이터를 "암기"하기보다 일반화된
패턴을 학습하고 있다는 신호로 판단, 실주행 강건성 측면에서 긍정적으로 평가했다.

### 적용 2 — 이동(Shift) / 회전(Rotation) 증강 추가

`RCAugmentor.py`에 이동과 회전을 추가했다. 회전은 각도가 크면 실제 차선의 기울기가
왜곡되어 라벨(조향각)과 불일치할 위험이 있으므로 **최대 ±5도로 제한**했다.

```python
def __init__(self, hflip_prob=0.5, brightness_delta=0.2, blur_prob=0.3,
             shift_prob=0.5, max_shift_ratio=0.08,
             rotate_prob=0.5, max_rotate_deg=5):
    ...

def __call__(self, img_bgr, angle):
    h, w = img_bgr.shape[:2]

    if random.random() < self.hflip_prob:
        img_bgr = cv2.flip(img_bgr, 1)
        angle = self.flip_map.get(angle, angle)

    # 이동: 카메라가 살짝 다른 위치에서 찍힌 것처럼 효과
    if random.random() < self.shift_prob:
        max_dx = int(w * self.max_shift_ratio)
        max_dy = int(h * self.max_shift_ratio)
        dx = random.randint(-max_dx, max_dx)
        dy = random.randint(-max_dy, max_dy)
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        img_bgr = cv2.warpAffine(img_bgr, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # 회전: 각도 왜곡 방지를 위해 미세하게만 적용
    if random.random() < self.rotate_prob:
        deg = random.uniform(-self.max_rotate_deg, self.max_rotate_deg)
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, deg, 1.0)
        img_bgr = cv2.warpAffine(img_bgr, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    if self.brightness_delta > 0:
        alpha = 1.0 + random.uniform(-self.brightness_delta, self.brightness_delta)
        img_bgr = np.clip(img_bgr.astype(np.float32) * alpha, 0, 255).astype(np.uint8)

    if random.random() < self.blur_prob:
        img_bgr = cv2.GaussianBlur(img_bgr, (3, 3), 0)

    return img_bgr, angle
```

**중요**: 온라인 증강은 디스크의 실제 파일 개수를 늘리지 않는다. 매 epoch마다
동일 파일을 메모리 상에서 랜덤하게 변형해 보여주는 방식으로, 학습 시 모델이
접하는 이미지의 다양성만 늘어난다.

---

## 3. 오프라인 데이터 증강 (실제 파일 수 증량)

온라인 증강만으로는 "질적 다양성"만 늘어날 뿐 실제 데이터 양은 그대로였다.
이를 보완하기 위해 원본 각 이미지에 대해 4가지 버전(원본/좌우반전/밝게/어둡게)을
실제 파일로 생성하여 데이터셋 자체를 물리적으로 4배 증량했다.

### 스크립트 (`expand_dataset.py`)

```python
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

for fname in files:
    match = pattern.search(fname)
    if not match:
        continue
    angle = int(match.group(1))

    img = cv2.imread(os.path.join(SRC_DIR, fname))
    if img is None:
        continue

    base_name = fname.rsplit(".png", 1)[0]

    # 원본
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_orig.png"), img)

    # 좌우반전 (라벨도 flip_map으로 변경하여 파일명에 반영)
    flipped = cv2.flip(img, 1)
    flipped_angle = FLIP_MAP.get(angle, angle)
    flipped_name = f"{base_name.replace(f'angle{angle}_', f'angle{flipped_angle}_')}_flip.png"
    cv2.imwrite(os.path.join(OUT_DIR, flipped_name), flipped)

    # 밝게 / 어둡게
    bright = np.clip(img.astype(np.float32) * 1.2, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_bright.png"), bright)

    dark = np.clip(img.astype(np.float32) * 0.8, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT_DIR, f"{base_name}_dark.png"), dark)
```

**결과**: 1,944장 → **7,776장**으로 증량.

---

## 4. 최종 결과 — 오프라인 증강(4배) + 온라인 증강(이동/회전 포함) + 50 epoch

| 시도 | 데이터 규모 | Best test_acc | train-test 격차 |
|---|---|---|---|
| 오디트만 적용 (증강 없음) | 1,944장 | 49.83%(주: 오디트 이전 데이터 기준 최고치) / 46.41%(오디트 후) | 12.1%p |
| 온라인 증강만(hflip+밝기+블러) | 1,944장 | 47.69% | 4.2%p |
| **온라인 증강(+이동/회전) + 오프라인 4배 증량** | **7,776장** | **61.76%** | **약 1.4%p** |

마지막 조합에서 test_acc가 처음으로 60%를 돌파했고, train_acc와 test_acc 격차가 거의 없어
과적합 없이 안정적으로 학습됐음을 확인했다. Epoch 49까지 계속 최고 기록을 갱신하고 있어
추가 학습 여지도 남아있는 것으로 판단된다.

---

## 5. 교훈 정리

1. **파인튜닝은 만능이 아니다.** 기반 모델이 충분히 안정적이지 않은 상태에서는
   처음부터 재학습하는 것이 더 안전하다.
2. **온라인 증강(실시간 변형)만으로는 데이터 양 자체가 늘지 않는다.** 과적합 완화에는
   도움이 되지만, 절대적인 정확도 향상을 위해서는 오프라인 증강(실제 파일 생성)이 필요했다.
3. **라벨과 연동된 증강(좌우 반전 시 각도 매핑)** 이 이 프로젝트처럼 좌우 비대칭
   라벨 구조에서는 특히 중요하다. `flip_map`이 없었다면 반전 증강 자체가 잘못된
   라벨을 양산했을 것이다.
4. **회전 등 기하학적 변형은 각도를 작게 제한**해야 한다. 조향각 라벨과 실제 화면
   속 차선 기울기가 어긋나지 않는 범위 내에서만 적용해야 한다.
5. **train/test 정확도 격차를 함께 모니터링**하는 것이 단일 정확도 수치보다
   실전(실주행) 성능을 더 잘 예측하는 지표였다.

---

## 다음 단계

- 이 모델(test_acc 61.76%)을 opset 13으로 재export → Jetson TensorRT 재변환 → 실주행 테스트
- 여유가 되면 epoch을 70~80으로 늘려 추가 개선 여지 확인
- 실주행에서 이전 모델들의 고질적 문제였던 "차선 이탈 시 특정 각도로 고정 예측"되는
  현상이 실제로 개선되었는지 확인 필요
