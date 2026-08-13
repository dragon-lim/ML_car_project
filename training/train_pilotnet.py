# 기존 코드에서 변경된 점

# 시드 고정 — 재현 가능하게
# class weight 상한 3.0으로 clip — 극단적 가중치로 인한 붕괴 방지
# 그레이디언트 클리핑 — 학습 폭주 방지
# best model 저장 — 마지막 epoch이 아니라, 학습 중 test_acc가 가장 높았던 시점의 모델을 최종 저장 (중간에 성능 좋았다가 나빠져도 안전)
# epoch 20 -> 40 -> 30으로 변경

import os
import time
import numpy as np
import torch
from torch.utils.data import DataLoader
from torch import nn, optim

from training.RCDataset import RCDataset
from preprocessor.RCPreprocessor import RCPreprocessor
from preprocessor.RCAugmentor import RCAugmentor
from training.model import PilotNet

# 고정 입력 크기에서 cuDNN 최적화
torch.backends.cudnn.benchmark = True

# 재현성을 위한 시드 고정 (실행마다 결과가 크게 달라지는 것 방지)
torch.manual_seed(42)
np.random.seed(42)


def train():
    # 학습 설정
    csv_filename = "data_labels_updated.csv"
    dataset_root = "datacollector/dataset"
    num_epochs = 30
    batch_size = 128
    learning_rate = 5e-4
    weight_decay = 1e-4
    split_ratio = 0.8

    # 학습 장치 선택
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] device = {device}")

    # PilotNet 입력 크기로 전처리
    preproc = RCPreprocessor(
        out_size=(200, 66),
        crop_top_ratio=0.4,
        crop_bottom_ratio=1.0
    )

    augment = RCAugmentor(
        hflip_prob=0.5,
        brightness_delta=0.2,
        blur_prob=0.3
    )

    train_dataset = RCDataset(
        csv_filename=csv_filename,
        root=dataset_root,
        preprocessor=preproc,
        augmentor=None,
        split="train",
        split_ratio=split_ratio
    )

    test_dataset = RCDataset(
        csv_filename=csv_filename,
        root=dataset_root,
        preprocessor=preproc,
        augmentor=None,
        split="test",
        split_ratio=split_ratio
    )

    num_classes = len(train_dataset.angles)
    print(f"[INFO] classes = {num_classes}")
    print(f"[INFO] train samples = {len(train_dataset)}")
    print(f"[INFO] test  samples = {len(test_dataset)}")

    # 클래스 불균형 보정용 weight 계산 (극단값 방지를 위해 상한 clip)
    class_counts = train_dataset.df["servo_angle"].value_counts().sort_index()
    class_counts = class_counts.reindex(train_dataset.angles)
    class_weights = 1.0 / class_counts.values
    class_weights = class_weights / class_weights.sum() * num_classes
    class_weights = np.clip(class_weights, a_min=None, a_max=3.0)
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)
    print(f"[INFO] class_weights = {class_weights_tensor.tolist()}")

    pin_memory = (device.type == "cuda")
    num_workers = 12 if device.type == "cuda" else 4

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=True,
        prefetch_factor=4,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=True,
        prefetch_factor=4,
    )

    model = PilotNet(num_classes=num_classes, input_shape=(3, 66, 200)).to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor, label_smoothing=0.1)
    optimizer = optim.Adam(model.parameters(),
                           lr=learning_rate,
                           weight_decay=weight_decay)

    train_start = time.time()

    best_test_acc = 0.0
    best_state_dict = None

    for epoch in range(1, num_epochs + 1):
        model.train()

        train_loss = 0.0
        train_correct = 0
        train_total = 0

        epoch_start = time.time()
        data_move_time = 0.0
        compute_time = 0.0

        for images, labels in train_loader:
            t0 = time.time()
            images = images.to(device, non_blocking=True)
            labels = labels.to(device)
            t1 = time.time()
            data_move_time += (t1 - t0)

            optimizer.zero_grad()

            t2 = time.time()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            # 그레이디언트 폭주 방지
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            t3 = time.time()
            compute_time += (t3 - t2)

            train_loss += loss.item() * images.size(0)

            _, predicted = outputs.max(1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()

        epoch_train_loss = train_loss / train_total
        epoch_train_acc = train_correct / train_total * 100.0

        model.eval()

        test_loss = 0.0
        test_correct = 0
        test_total = 0

        with torch.no_grad():
            for images, labels in test_loader:
                images = images.to(device, non_blocking=True)
                labels = labels.to(device)

                outputs = model(images)
                loss = criterion(outputs, labels)

                test_loss += loss.item() * images.size(0)

                _, predicted = outputs.max(1)
                test_total += labels.size(0)
                test_correct += (predicted == labels).sum().item()

        epoch_test_loss = test_loss / test_total
        epoch_test_acc = test_correct / test_total * 100.0

        epoch_time = time.time() - epoch_start

        # 지금까지 중 가장 좋은 test_acc 모델을 별도 저장
        is_best = ""
        if epoch_test_acc > best_test_acc:
            best_test_acc = epoch_test_acc
            best_state_dict = {k: v.clone() for k, v in model.state_dict().items()}
            is_best = "  <- best"

        print(
            f"[Epoch {epoch:02d}] "
            f"train_loss={epoch_train_loss:.4f}, train_acc={epoch_train_acc:.2f}% | "
            f"test_loss={epoch_test_loss:.4f}, test_acc={epoch_test_acc:.2f}% | "
            f"time={epoch_time:.2f}s "
            f"(data={data_move_time:.2f}s, compute={compute_time:.2f}s){is_best}"
        )

    print(f"Total train time={time.time()-train_start:.2f}s")
    print(f"[INFO] Best test_acc = {best_test_acc:.2f}%")

    # best 모델을 최종 모델로 사용
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)

    os.makedirs("models", exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    pth_path = f"models/pilotnet_steering_{timestamp}.pth"
    torch.save(model.state_dict(), pth_path)
    print(f"[INFO] Saved PTH (best) → {pth_path}")

    onnx_path = f"models/pilotnet_steering_{timestamp}.onnx"
    dummy_input = torch.randn(1, 3, 66, 200, dtype=torch.float32).to(device)

    model.eval()
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        opset_version=11,
        export_params=True,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=None,
    )

    print(f"[INFO] Saved ONNX → {onnx_path}")


if __name__ == "__main__":
    train()
