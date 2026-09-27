import torch
from training.model import PilotNet

# 학습 완료 후 생성된 .pth 경로를 매번 갱신해서 사용
PTH_PATH = "models/pilotnet_steering_YYYYMMDD_HHMMSS.pth"
ONNX_OUT_PATH = "models/pilotnet_steering_opset13.onnx"

model = PilotNet(num_classes=5, input_shape=(3, 66, 200))
model.load_state_dict(torch.load(PTH_PATH, map_location="cpu"))
model.eval()

dummy_input = torch.randn(1, 3, 66, 200, dtype=torch.float32)

torch.onnx.export(
    model,
    dummy_input,
    ONNX_OUT_PATH,
    opset_version=13,
    export_params=True,
    do_constant_folding=True,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes=None,
    dynamo=False,  # legacy exporter 강제 (opset 자동 승격/다운그레이드 실패 회피)
)

print("[INFO] Export 완료 →", ONNX_OUT_PATH)
