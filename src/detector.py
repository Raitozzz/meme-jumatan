"""Wrapper MediaPipe Tasks: deteksi tangan (jempol) dan pose (tangan menyilang)."""

from __future__ import annotations

import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

import config as C

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
POSE_MODEL_URLS = {
    "lite": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "full": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_full/float16/1/pose_landmarker_full.task",
    "heavy": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
}


@dataclass
class Detection:
    hands: list[np.ndarray] = field(default_factory=list)  # (21, 3) x, y, z
    pose: np.ndarray | None = None                        # (33, 4) x, y, z, visibility
    frame_size: tuple[int, int] = (0, 0)


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[model] mengunduh {target.name} ...", flush=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(target)
    print(f"[model] selesai: {target}", flush=True)


def ensure_models() -> tuple[Path, Path]:
    hand = C.MODELS_DIR / "hand_landmarker.task"
    pose = C.MODELS_DIR / f"pose_landmarker_{C.POSE_MODEL}.task"
    pose_url = POSE_MODEL_URLS.get(C.POSE_MODEL, POSE_MODEL_URLS["full"])
    try:
        if not hand.is_file():
            _download(HAND_MODEL_URL, hand)
        if not pose.is_file():
            _download(pose_url, pose)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Gagal mengunduh model MediaPipe. Pastikan internet aktif, lalu jalankan ulang.\n"
            f"Detail: {exc}"
        ) from exc
    return hand, pose


class Detector:
    def __init__(self) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "MediaPipe belum terpasang. Jalankan run.bat atau:\n"
                "  .venv\\Scripts\\pip install -r requirements.txt"
            ) from exc

        self._mp = mp
        self._mp_python = mp_python
        self._mp_vision = mp_vision
        self._start = time.monotonic()
        self._last_ts = -1

        hand_path, pose_path = ensure_models()

        hand_opts = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(hand_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=C.HAND_MAX_HANDS,
            min_hand_detection_confidence=0.45,
            min_hand_presence_confidence=0.45,
            min_tracking_confidence=0.45,
        )
        pose_opts = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(pose_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.35,
            min_pose_presence_confidence=0.35,
            min_tracking_confidence=0.35,
            output_segmentation_masks=False,
        )
        self._hands = mp_vision.HandLandmarker.create_from_options(hand_opts)
        self._pose = mp_vision.PoseLandmarker.create_from_options(pose_opts)

    def process(self, frame_bgr: np.ndarray) -> Detection:
        rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

        ts = int((time.monotonic() - self._start) * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts

        hands_result = self._hands.detect_for_video(image, ts)
        pose_result = self._pose.detect_for_video(image, ts)

        hands: list[np.ndarray] = []
        for landmarks in getattr(hands_result, "hand_landmarks", []) or []:
            hands.append(np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32))

        pose = None
        pose_landmarks = getattr(pose_result, "pose_landmarks", None) or []
        if pose_landmarks:
            pose = np.array(
                [[lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0)] for lm in pose_landmarks[0]],
                dtype=np.float32,
            )

        h, w = frame_bgr.shape[:2]
        return Detection(hands=hands, pose=pose, frame_size=(w, h))

    def close(self) -> None:
        for obj in (getattr(self, "_hands", None), getattr(self, "_pose", None)):
            try:
                if obj is not None:
                    obj.close()
            except Exception:  # noqa: BLE001
                pass
        sys.stdout.flush()
