# 미니 자율주행차 프로젝트 트러블슈팅 정리

## 1. 학습 프레임워크 불일치

**문제**
- 교재 파이프라인(PyTorch)이 아닌 Keras/TensorFlow로 모델을 학습시켜 `.h5` 파일 생성
- 교재 추론 파이프라인은 PyTorch → ONNX → TensorRT 기반이라 호환 불가
- 회귀(MAE 지표)로 학습되어 있었으나, 원래 설계는 5-class 분류(30/60/90/120/150도)

**해결**
- 원본 `training/train_pilotnet.py`(PyTorch, 5-class 분류) 코드로 재학습
- Colab이 아닌 로컬 노트북 환경에서 진행

---

## 2. 환경 세팅 관련 오류

| 증상 | 원인 | 해결 |
|---|---|---|
| `python train_pilotnet.py` 실행 시 `ModuleNotFoundError` | 상대 임포트 구조(`training.xxx`)인데 하위 폴더에서 직접 실행 | 레포 루트에서 `python -m training.train_pilotnet`로 실행 |
| 새로 만든 `.py` 파일을 찾을 수 없음 | 메모장이 `.py.txt`로 저장 | `notepad 파일명.py`로 직접 생성(자동으로 올바른 확장자 저장) |
| `ImportError: DLL load failed ... 애플리케이션 제어 정책에서 이 파일을 차단` (torch, pandas 등) | Windows 11 **Smart App Control**이 서명되지 않은 파이썬 네이티브 모듈(.pyd) 차단 | Windows 보안 → 앱 및 브라우저 컨트롤 → Smart App Control **끄기** (재부팅 필요, 되돌릴 수 없음) |
| venv로 재설치해도 동일 에러 | Smart App Control은 경로와 무관하게 전역 차단 | 위와 동일 |

---

## 3. ONNX Export 관련 오류

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'onnxscript'` | 최신 PyTorch의 ONNX export가 `onnxscript` 의존 | `pip install onnx onnxscript` |
| opset 11 요청했는데 다운그레이드 변환 실패 (`No Adapter From Version 14 for Relu`), 실제로는 opset 18로 저장됨 | PyTorch가 내부적으로 opset 18로 그래프 생성 후 하위 버전 변환 시도 → 실패 시 18로 남음 | `.pth`에서 별도 export 스크립트 작성, `torch.onnx.export(..., opset_version=13, dynamo=False)`로 legacy exporter 강제 사용 |

---

## 4. Jetson Nano 배포 관련 오류

| 증상 | 원인 | 해결 |
|---|---|---|
| `trtexec: command not found` | PATH에 미등록 | 전체 경로로 실행: `/usr/src/tensorrt/bin/trtexec` |
| trtexec 빌드 중 응답 없어 보임 | Jetson Nano 성능상 레이어별 벤치마킹에 수 분~십수 분 소요 (정상 동작) | Ctrl+C로 중단하지 말고 대기 (`PASSED` 로그까지) |
| TensorRT 버전(8.2.1.8, 구버전) | opset 18 미지원 가능성 | opset 13으로 재export 후 정상 변환 성공 |
| `run_inference.py` 실행 시 `SyntaxError: EOL while scanning string literal` | 로컬에서 파일이 수정된 상태(Keras `.h5` 로드하는 다른 버전으로 덮어써짐, 문자열 리터럴 중간에 줄바꿈 포함) | `git status`로 로컬 수정 확인 → `git checkout -- <file>` 로 원본(TensorRT 기반) 복원 (`run_inference.py`, `drive.py` 둘 다 해당) |
| `dataset` 폴더 소유자가 `root`로 되어있어 저장 실패 우려 | 이전 작업이 다른 권한으로 실행됨 | `sudo chown -R lsy:lsy dataset` |
| 추론 실행은 되나 전진이 안 됨 | `run_inference.py`가 조향만 자동, 전진/정지는 키보드 입력(↑/↓) 필요한 반자율 구조 | 완전 자율주행 원할 경우 코드 수정 필요(키 입력 로직 제거, 시작 시 자동 `drive.control_motor("forward")` 호출) — 안전을 위해 비상정지 수단 확보 후 테스트 권장 |

---

## 5. 데이터 품질 문제 (가장 큰 이슈)

### 5-1. 초기 데이터셋(6,210장) 문제
- Blur threshold 100 적용 시 정상 사진까지 대량 탈락 → 40으로 완화
- 눈으로 확인(preview) 결과, `ok` 판정된 사진 중 **천장·난간·벽 등 도로가 아닌 장면**이 다수 포함
- 클래스 불균형 심각: 90도 870장 vs 60도 41장 등

### 5-2. 대응
- 자동 필터(blur/노출/단색)만으로는 "배경이 도로가 아닌 경우"를 못 걸러냄 → **수동 오디트(grid 이미지 + 번호 확인)** 방식 도입
- 1차 정리 결과: 6,210장 → 최종 학습 가능 **180장**까지 축소 (약 3%만 실사용 가능)

### 5-3. 원인 추정
- 카메라 고정이 불안정하여 흔들리며 엉뚱한 장면 촬영
- 특정 배경(난간 등)과 특정 조향각이 우연히 반복 결합 → 모델이 **배경-각도 가짜 상관관계(spurious correlation)** 학습
- 실제 증상: 특정 지점 통과 시 차선과 무관하게 항상 같은 각도(60도)로 고정 예측

### 5-4. 재촬영 (2차)
- 목표: 90도 외 각 각도 300장 이상
- Blur threshold를 15까지 낮췄음에도 여전히 blurry/flat_color 대량 발생
  → 원인은 실제 블러가 아니라 **역광/글레어(강한 햇빛 반사)** 로 인한 대비 저하, 필터 오탐으로 확인
- `_rejected`로 걸러진 사진도 오디트로 재검토하여 쓸만한 것 복구 (1,167장 중 333장 복구)
- 30도/150도(급커브)만 별도로 확인한 결과, 대부분 **차선이 화면에서 벗어난 빈 바닥** → 이는 진짜 결함(오탐 아님), 급커브 시 카메라가 차선을 놓치는 촬영 구도 문제로 판단

### 5-5. 최종 데이터셋 (현재까지)
| 각도 | 1차(구) | 2차(신규) | 합계 |
|---|---|---|---|
| 30 | 17 | 37 | 54 |
| 60 | 12 | 58 | 70 |
| 90 | 139 | 104 | 243 |
| 120 | 1 | 66 | 67 |
| 150 | 11 | 29 | 40 |

→ 여전히 30/60/120/150도 부족, 추가 촬영 예정 (목표 150장/클래스 이상)

---

## 6. 클래스 불균형 대응 (코드 레벨)

- `train_pilotnet.py`의 `nn.CrossEntropyLoss`에 `weight` 파라미터 추가
- 클래스별 샘플 수의 역수 기반으로 가중치 계산 후 정규화하여 적용
- 근본적으로는 데이터 자체의 균형을 맞추는 게 우선이며, class weight는 보조 수단으로 사용

---

## 7. 아직 남은 과제

1. 30/60/120/150도 추가 촬영 (급커브 구간 카메라 구도 개선 필요)
2. 재학습 후 opset 13 재export → Jetson TensorRT 재변환
3. 완전 자율주행(무인 전진) 코드 반영 여부 결정 및 안전장치 마련
4. 실주행 테스트를 통한 반복 개선 (현재 1차 실주행에서 특정 지점 60도 고정 예측 문제 확인됨 → 데이터 개선으로 해결 시도 중)
