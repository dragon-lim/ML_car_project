# Jetson Environment Setup & Verification Commands

## 1. Check environment
```bash
dpkg-query --show nvidia-l4t-core   # Check L4T (Jetson OS) version
nvcc --version                       # Check CUDA version
```

## 2. Switch to max performance mode (required before running)
```bash
sudo nvpmodel -q        # Check current mode
sudo nvpmodel -m 0      # Switch to max performance mode
sudo jetson_clocks      # Lock clocks at max frequency
```

## 3. Standalone test for drive control
```bash
cd course-autodrive/datacollector/hw_control/
sudo python3 drive.py
```

## 4. Verify GPIO module works
```bash
sudo python3 - << 'EOF'
import Jetson.GPIO as GPIO
print("GPIO module OK")
EOF
```

## 5. Convert ONNX to TensorRT
```bash
/usr/src/tensorrt/bin/trtexec \
  --onnx=pilotnet_steering_[training_date]_[training_time].onnx \
  --saveEngine=pilotnet_steering.trt \
  --explicitBatch \
  --fp16 \
  --workspace=1024 \
  --verbose
```


dpkg-query --show nvidia-l4t-core
nvcc --version
sudo nvpmodel -q
sudo nvpmodel -m 0
sudo jetson_clocks
cd course-autodrive/data-collector/hw_control/
sudo python3 drive.py
sudo python3 - << 'EOF'
import Jetson.GPIO as GPIO
print("GPIO module OK")
EOF
/usr/src/tensorrt/bin/trtexec \
  --onnx=pilotnet_steering_[訓練日]_[訓練時間].onnx \
  --saveEngine=pilotnet_steering.trt \
  --explicitBatch \
  --fp16 \
  --workspace=1024 \
  --verbose
