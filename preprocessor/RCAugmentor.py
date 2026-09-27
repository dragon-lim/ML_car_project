import cv2
import numpy as np
import random


class RCAugmentor:
    """
    훈련 전용 증강(온라인 리샘플링)
    - 좌우 플립: 각도(라벨)도 flip_map으로 함께 대칭 변환
    - 이동/회전: 라벨은 그대로 유지 (미세 변형이라 조향각과 무관하다고 가정)
    """
    def __init__(self, hflip_prob=0.5, brightness_delta=0.2, blur_prob=0.3,
                 shift_prob=0.5, max_shift_ratio=0.08,
                 rotate_prob=0.5, max_rotate_deg=5):
        self.hflip_prob = hflip_prob
        self.brightness_delta = brightness_delta
        self.blur_prob = blur_prob
        self.shift_prob = shift_prob
        self.max_shift_ratio = max_shift_ratio
        self.rotate_prob = rotate_prob
        self.max_rotate_deg = max_rotate_deg
        self.flip_map = {30: 150, 60: 120, 90: 90, 120: 60, 150: 30}

    def __call__(self, img_bgr: np.ndarray, angle: int):
        h, w = img_bgr.shape[:2]

        # 좌우 플립
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
            img_bgr = cv2.warpAffine(
                img_bgr, M, (w, h),
                borderMode=cv2.BORDER_REPLICATE
            )

        # 회전: 각도 왜곡 방지를 위해 미세하게만 적용
        if random.random() < self.rotate_prob:
            deg = random.uniform(-self.max_rotate_deg, self.max_rotate_deg)
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, deg, 1.0)
            img_bgr = cv2.warpAffine(
                img_bgr, M, (w, h),
                borderMode=cv2.BORDER_REPLICATE
            )

        # 밝기 변화
        if self.brightness_delta > 0:
            alpha = 1.0 + random.uniform(-self.brightness_delta, self.brightness_delta)
            img_bgr = np.clip(img_bgr.astype(np.float32) * alpha, 0, 255).astype(np.uint8)

        # 블러
        if random.random() < self.blur_prob:
            img_bgr = cv2.GaussianBlur(img_bgr, (3, 3), 0)

        return img_bgr, angle
