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
외부 환경에서 진행하여 IP가 통하지 않았다

**원인 분석**
Jetson과 노트북이 같은 Wi-Fi에 있어도, 다수의 기관용 AP는
**AP isolation(단말 간 통신 차단)** 이 설정되어 있어 SSH가 통하지 않는다.

**해결**
폰 핫스팟으로 두 기기를 묶었다. 이 방식은 실외 수집 시에도 그대로 쓸 수 있어
결과적으로 최종 운용 방식과 동일해졌다.

```bash
# 핫스팟 연결 후 IP 재확인 → 변경됨
```

> **교훈:** 핫스팟 재연결 시 IP가 바뀐다.
> 모니터가 없는 실외에서는 **폰의 "연결된 기기" 목록**에서 IP를 확인하는 것이 유일한 수단

---


## 2. 실행 중 발생한 문제

### 🔴 문제 2 — `Device '/dev/video0' is busy`

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



## 3. 속도 제어 시도

### 🔴 문제 3 — 주행 속도 과다로 조종 불가

**상황**
기본 속도로 주행 시 표면이 매끄럽지 않아 앞으로 나아가지 못했다
앞으로 나아갈 수 있도록 기본 속도 70 -> 90, 100으로 조정하였으나 너무 빠른 속도로, 트랙 내에서 세밀한 제어가 불가능.
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


## 5. 오늘의 결론 — 트랙 변경

저속(기존 70에서) 구동이 불가능하고 최저 주행 속도(커브길에도 나아가기 위해서는 100)가 고정된 상황에서,
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
