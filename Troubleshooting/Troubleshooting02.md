# 원격 데이터 수집 환경 구축 — 시행착오 기록

> Jetson Nano 기반 자율주행 RC카의 **실외 데이터 수집**을 위해
> 모니터·유선 전원 없이 노트북 SSH만으로 차량을 제어하는 환경을 구축한 과정.
> 발생한 문제와 실제로 사용한 해결 명령어를 순서대로 기록한다.
>
> **베이스 코드:** [gsc-lab/course-autodrive](https://github.com/gsc-lab/course-autodrive)

---

## 0. 출발점

이전 단계에서 하드웨어 구동(서보 + 모터)까지 확인 완료.
이번 목표는 **실외 트랙에서 주행 데이터를 수집**하는 것.

문제는 실외에는 **모니터도, 벽 전원도 없다**는 점이었다.
`img-collector.py`는 키보드로 차량을 조종하면서 그 조향각을 라벨로 저장하는 구조이므로,
**조종 없이는 라벨이 생성되지 않는다.** 따라서 원격 제어 환경이 필수 전제였다.

---

## 1. SSH 원격 제어 환경 구축

### 1-1. SSH 서버 설치

```bash
sudo apt install -y openssh-server
sudo systemctl status ssh        # active (running) 확인
```

### 1-2. IP 확인

```bash
hostname -I
# 또는
ifconfig                          # wlan0 항목의 inet 값을 사용
```

> `hostname -I`은 `192.168.0.2 172.17.0.1`처럼 여러 개를 반환한다.
> 뒤쪽 `172.17.x.x`는 Docker 가상 인터페이스이므로, **`wlan0`의 주소를 써야 한다.**

### 1-3. 클라이언트

노트북에 **MobaXterm** 설치 → `Session > SSH` → Remote host에 Jetson IP, username `lsy`.

---

### 🔴 문제 1 — 네트워크 타임아웃

**상황**
교실 Wi-Fi에서 Jetson IP(`192.168.0.115`)로 접속 시 연결이 되지 않고 타임아웃.

**원인 분석**
Jetson과 노트북이 같은 Wi-Fi에 있어도, 다수의 기관용 AP는
**AP isolation(단말 간 통신 차단)** 이 설정되어 있어 SSH가 통하지 않는다.

**해결**
폰 핫스팟으로 두 기기를 묶었다. 이 방식은 실외 수집 시에도 그대로 쓸 수 있어
결과적으로 최종 운용 방식과 동일해졌다.

```bash
# 핫스팟 연결 후 IP 재확인 → 172.20.10.2 로 변경됨
hostname -I
```

> **교훈:** 핫스팟 재연결 시 IP가 바뀐다.
> 모니터가 없는 실외에서는 **폰의 "연결된 기기" 목록**에서 IP를 확인하는 것이 유일한 수단이다.

---

### 🔴 문제 2 — Access denied

**상황**
```
lsy@172.20.10.2's password:
Access denied
```

**원인**
IP·계정은 정상이므로 비밀번호 불일치. 한/영 입력 상태 또는 Caps Lock이 주원인.

**해결**
입력 상태 확인 후 재입력. (SSH 비밀번호 입력은 화면에 아무 표시도 되지 않는 것이 정상)

---

## 2. 실행 준비 단계에서의 오류

### 🔴 문제 3 — `nvmodel: command not found`

**상황**
성능 모드 진입 시도 중 명령어를 찾을 수 없음.

```bash
sudo nvmodel -m 0        # ❌ 오타
```

**해결**
정확한 명령은 `nv**p**model`이다.

```bash
sudo nvpmodel -m 0       # ✅ 최대 성능 모드
sudo jetson_clocks       # 클럭 고정
```

---

### 🔴 문제 4 — 경로 오타 반복

**상황**
```bash
cd ~/course-autodrive/data-collector/hw_control/   # ❌ 실제 폴더명은 datacollector
cd ~/course-autodrvie/datacollector/               # ❌ autodrive 철자 오류
ls /dataset | head -20                             # ❌ 절대경로 → 최상위 /dataset 을 가리킴
```

**해결**
파일 위치를 추측하지 않고 직접 탐색.

```bash
find ~/course-autodrive -name "drive.py"
# → /home/lsy/course-autodrive/datacollector/hw_control/drive.py
```

상대경로로 수정하고, 이후로는 **Tab 자동완성**을 사용해 오타를 원천 차단했다.

```bash
ls dataset | head -20
ls dataset/*.png | wc -l
```

---

## 3. 실행 중 발생한 문제

### 🔴 문제 5 — `Device '/dev/video0' is busy`

**상황**
`img-collector.py` 재실행 시 카메라 초기화 실패.

```
GStreamer warning: Embedded video playback halted;
module v4l2src0 reported: Device '/dev/video0' is busy
```

**원인**
이전 실행을 `Ctrl+C` / `Ctrl+Z`로 강제 종료해서,
프로세스가 **카메라 디바이스와 GPIO를 점유한 채 남아 있었다.**
동반해서 나타난 `NameError: name 'open' is not defined`(Jetson.GPIO 소멸자 오류)도
비정상 종료 시 자원 해제가 실패하며 발생한 잔여 메시지였다.

**해결**

```bash
sudo pkill -f img-collector
sudo pkill -f drive.py

sudo fuser /dev/video0        # 점유 프로세스 확인 (출력 없으면 해제 완료)
sudo fuser -k /dev/video0     # 강제 해제
```

일시정지(`Ctrl+Z`)로 남은 작업은 별도로 정리해야 한다.

```bash
jobs
kill %1
```

> **재발 방지:** 종료는 반드시 **ESC**로 한다.
> `Ctrl+C`/`Ctrl+Z`는 카메라·GPIO 자원을 반납하지 않아 다음 실행을 실패시킨다.

---

### 🔴 문제 6 — 주행 중 ENA 핀 이탈

**상황**
조향(← →)은 정상 동작하지만 **전후진(↑ ↓)만 동작하지 않음.**

**원인**
L298N의 **ENA(Jetson BOARD 33번, 모터 속도 제어)** 점퍼선이 빠져 있었다.
방향 신호(IN1/IN2)는 살아 있어 프로그램은 정상 동작하지만,
Enable 신호가 없으면 모터 출력이 나가지 않는다.

주행 진동으로 점퍼가 이탈한 것으로, **같은 증상이 두 번 재발**했다.

**해결**
33번 ↔ ENA 재연결. 이후 주행 전 배선 점검을 루틴에 포함.

| Jetson 핀 | L298N | 기능 |
|---|---|---|
| 33 | ENA | 속도 제어 |
| 31 | IN1 | 방향 1 |
| 29 | IN2 | 방향 2 |
| GND | GND | 공통 접지 |

> **교훈:** "조향은 되는데 구동만 안 된다"는 증상은
> 소프트웨어가 아니라 **ENA 계통 단선**을 먼저 의심해야 한다.

---

### 🔴 문제 7 — CONTROL MODE가 표시되지 않음

**상황**
프로그램을 실행했으나 조작 안내가 뜨지 않고 아무 반응이 없음.

**원인**
`drive.py`는 시작 시 PWM 레지스터 설정(`activate_jetson_pwm`)을 위해
**비밀번호를 한 번 더 요구**한다.

```python
sudo_pw = getpass.getpass("Enter sudo password: ")
```

이 입력은 화면에 아무것도 표시되지 않아 "멈춘 것"처럼 보이지만,
실제로는 입력 대기 상태이며 여기서 진행하지 않으면 PWM이 활성화되지 않는다.

**해결**
비밀번호가 **두 번** 요구된다는 점을 인지하고 모두 입력.

```
[sudo] password for lsy:     ← 1차 (sudo 실행 권한)
Enter sudo password:         ← 2차 (PWM 레지스터 설정) ⭐
```

---

## 4. 속도 제어 시도

### 🔴 문제 8 — 주행 속도 과다로 조종 불가

**상황**
기본 속도로 주행 시 너무 빨라 트랙 내에서 조향 제어가 불가능.
급조작이 그대로 잘못된 라벨로 기록되어 **데이터 품질을 훼손**하는 문제로 이어졌다.

**시도한 해결 — 상수 조정**

`drive.py`의 속도 관련 상수를 수정:

```python
motor_speed  = 50    # 기본 모터 속도 (0~100)
MOTOR_STEP   = 0     # 0으로 두면 A/Z 키로도 속도가 변하지 않아 사실상 고정
```

```bash
nano ~/course-autodrive/datacollector/hw_control/drive.py
grep -E "motor_speed|MOTOR_STEP" ~/course-autodrive/datacollector/hw_control/drive.py
```

---

### 🔴 문제 9 — nano 저장 실패 및 파일명 오염

**상황**
MobaXterm이 `Ctrl+O`(Write Out)를 가로채 저장이 되지 않음.
`Ctrl+X` → `Y` 흐름에서 **`Y`가 파일명 입력란에 입력**되어
`drive.py`가 `drive.pyy`로 저장될 뻔했다.

**해결**
파일명 확인 후 `Backspace`로 수정하여 저장.
이후 편집기 의존을 줄이기 위해 **`sed`로 직접 치환**하는 방식으로 전환했다.

```bash
sed -i 's/^motor_speed.*= 60/motor_speed     = 50/' \
  ~/course-autodrive/datacollector/hw_control/drive.py

sed -i 's/^MOTOR_STEP.*= 10/MOTOR_STEP      = 0/' \
  ~/course-autodrive/datacollector/hw_control/drive.py

# 검증
grep -E "motor_speed|MOTOR_STEP" ~/course-autodrive/datacollector/hw_control/drive.py
```

잘못 생성된 파일은 제거.

```bash
rm ~/course-autodrive/datacollector/hw_control/drive.pyy
```

---

### 🔴 문제 10 — 저속 구동 불가 (미해결)

**상황**
상수를 낮춰도 **PWM 듀티 100 부근에서만 모터가 회전**하고,
그 이하에서는 아예 구동되지 않았다.

즉 **"제어 가능한 속도"와 "구동 가능한 속도" 구간이 겹치지 않는 상태**다.

**원인 후보**
- 배터리 전압 부족 (부하 시 강하)
- L298N 자체 전압 강하 (약 2V)
- 구동계 기계적 저항 (기어·베어링)

**검토했으나 기각한 대안**
> 차량을 손으로 밀며 이미지만 수집하는 방법을 검토했으나 **기각**했다.
> `img-collector.py`는 이미지와 **당시 서보 각도**를 한 쌍으로 저장한다.
> 손으로 밀 경우 서보는 중앙(90°)에 머무르므로,
> 커브 구간 이미지에도 전부 "직진" 라벨이 붙는다.
> 이는 데이터 증가가 아니라 **라벨 오염**이며, 학습 시 모델은 직진만 출력하게 된다.

---

## 5. 오늘의 결론 — 트랙 변경

저속 구동이 불가능하고 최저 주행 속도가 고정된 상황에서,
**현재 트랙은 차량의 최소 회전 반경과 속도에 비해 규모가 작다**는 결론에 도달했다.

이는 단순한 조작 미숙이 아니라 **차량 물리 특성과 트랙 설계의 불일치** 문제다.

### 다음 단계

- **트랙 재설계** — 곡률 반경을 키워, 고정된 최저 속도에서도 조향이 성립하도록 함
- 트랙 확장 시에도 **조향각 클래스 균형**을 유지할 것
  (직선 구간 최소화, 곡선 구간 위주, 시계/반시계 양방향 주행)
- 병행 과제: 저속 구동 불가 원인 규명 (배터리 부하 전압 측정, 구동계 저항 점검)

---

## 부록 — 최종 실행 절차

```bash
# 1) 접속 (MobaXterm → SSH → Jetson IP, user: lsy)

# 2) 성능 모드
sudo nvpmodel -m 0
sudo jetson_clocks

# 3) 이전 세션 잔여 프로세스 정리
sudo pkill -f img-collector
sudo pkill -f drive.py
sudo fuser /dev/video0          # 출력 없어야 정상

# 4) PWM 레지스터 활성화 (재부팅 시 초기화되므로 필요할 때 수동 실행)
sudo busybox devmem 0x700031fc 32 0x45
sudo busybox devmem 0x6000d504 32 0x2
sudo busybox devmem 0x70003248 32 0x46
sudo busybox devmem 0x6000d100 32 0x00

# 5) 데이터 수집 실행 (비밀번호 2회 입력)
cd ~/course-autodrive/datacollector/
sudo python3 img-collector.py

# 6) 수집량 및 클래스 분포 확인
ls dataset/*.png | wc -l
awk -F',' 'NR>1 {print $2}' dataset/*.csv | sort | uniq -c
```

**조작키**

| 키 | 동작 |
|---|---|
| ↑ / ↓ | 전진 / 후진 |
| ← / → | 조향 |
| S | 중앙 정렬 (90°) |
| A / Z | 속도 증가 / 감소 |
| T | 감속 정지 |
| **ESC** | **정상 종료 (필수)** |

---

## 오늘 얻은 것

- 모니터·유선 전원 없이 **노트북 SSH만으로 차량을 원격 제어**하는 환경 확보
- 실패를 소프트웨어 / 배선 / 전원 / 물리 특성 계층으로 **분리해 진단하는 절차** 정립
- 데이터 수집에서 **양보다 라벨 정확도가 우선**이라는 판단 기준 확립
- 수집 실패 원인을 조작 문제가 아닌 **트랙 설계 문제로 재정의**
