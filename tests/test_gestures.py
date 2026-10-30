"""Uji logika gesture dengan landmark buatan (tanpa kamera).

Jalankan:  .venv\\Scripts\\python.exe tests\\test_gestures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gesture_logic import (  # noqa: E402
    NONE,
    NO,
    YES,
    GestureGate,
    arms_crossed_score,
    evaluate,
    thumbs_up_score,
)

ASPECT = 16 / 9


def hand_thumbs_up() -> np.ndarray:
    """Tangan kanan dengan jempol ke atas, 4 jari terlipat."""
    pts = np.zeros((21, 3), dtype=np.float32)
    pts[0] = (0.50, 0.70, 0)          # pergelangan
    # MCP jari (telapak)
    palm_x = {"index": 0.47, "middle": 0.50, "ring": 0.53, "pinky": 0.56}
    order = ["index", "middle", "ring", "pinky"]
    for i, name in enumerate(order):
        mcp = 5 + i * 4
        pts[mcp] = (palm_x[name], 0.62, 0)
        pts[mcp + 1] = (palm_x[name], 0.565, 0)   # PIP terangkat
        pts[mcp + 2] = (palm_x[name] + 0.005, 0.615, 0)
        pts[mcp + 3] = (palm_x[name] + 0.005, 0.655, 0)  # ujung jari masuk telapak
    # Jempol: MCP -> IP -> ujung, mengarah ke atas
    pts[1] = (0.455, 0.655, 0)
    pts[2] = (0.445, 0.640, 0)
    pts[3] = (0.438, 0.575, 0)
    pts[4] = (0.432, 0.500, 0)
    return pts


def hand_relaxed() -> np.ndarray:
    """Tangan terbuka lebar (bukan jempol)."""
    pts = hand_thumbs_up()
    for i, name in enumerate(["index", "middle", "ring", "pinky"]):
        mcp = 5 + i * 4
        x = pts[mcp, 0]
        pts[mcp + 1] = (x, 0.555, 0)
        pts[mcp + 2] = (x + 0.004, 0.520, 0)
        pts[mcp + 3] = (x + 0.006, 0.485, 0)
    pts[3] = (0.400, 0.600, 0)
    pts[4] = (0.360, 0.640, 0)
    return pts


def pose_crossed() -> np.ndarray:
    pts = np.zeros((33, 4), dtype=np.float32)
    pts[:, 3] = 1.0
    pts[0] = (0.50, 0.25, 0, 1)          # hidung
    pts[11] = (0.42, 0.35, 0, 1)         # bahu kiri
    pts[12] = (0.58, 0.35, 0, 1)         # bahu kanan
    pts[13] = (0.36, 0.55, 0, 1)         # siku kiri
    pts[14] = (0.64, 0.55, 0, 1)         # siku kanan
    pts[15] = (0.56, 0.52, 0, 1)         # pergelangan kiri (menyilang ke kanan)
    pts[16] = (0.48, 0.50, 0, 1)         # pergelangan kanan (menyilang ke kiri)
    pts[23] = (0.44, 0.72, 0, 1)
    pts[24] = (0.56, 0.72, 0, 1)
    return pts


def pose_hands_down() -> np.ndarray:
    pts = pose_crossed()
    pts[13] = (0.39, 0.55, 0, 1)
    pts[14] = (0.61, 0.55, 0, 1)
    pts[15] = (0.34, 0.80, 0, 1)
    pts[16] = (0.66, 0.80, 0, 1)
    return pts


def pose_hands_clasped() -> np.ndarray:
    """Kedua tangan dikatupkan di depan dada (bukan menyilang)."""
    pts = pose_crossed()
    pts[15] = (0.46, 0.52, 0, 1)
    pts[16] = (0.54, 0.52, 0, 1)
    return pts


def test_thumbs_up() -> None:
    assert thumbs_up_score(hand_thumbs_up(), ASPECT) == 1.0, "jempol ke atas harus terdeteksi"
    assert thumbs_up_score(hand_relaxed(), ASPECT) == 0.0, "tangan terbuka bukan jempol"
    print("OK  jempol ke atas terdeteksi, tangan terbuka tidak")


def test_arms_crossed() -> None:
    score, checks, metrics = arms_crossed_score(pose_crossed(), ASPECT)
    assert score >= 0.9, f"tangan menyilang harus skor tinggi: {score} {checks}"
    score_down, checks_down, _ = arms_crossed_score(pose_hands_down(), ASPECT)
    assert score_down < 0.5, f"tangan di bawah bukan silang: {score_down} {checks_down}"
    score_clasped, _, _ = arms_crossed_score(pose_hands_clasped(), ASPECT)
    assert score_clasped == 0.0, f"tangan dikatupkan bukan silang: {score_clasped}"
    print(f"OK  menyilang {score:.2f}, tangan turun {score_down:.2f}, dikatupkan {score_clasped:.2f}")


def test_evaluate() -> None:
    gesture, _, _, _, _ = evaluate([hand_thumbs_up()], pose_hands_down(), ASPECT)
    assert gesture == YES, f"harus YA, dapat {gesture}"
    gesture, _, _, _, _ = evaluate([], pose_crossed(), ASPECT)
    assert gesture == NO, f"harus TIDAK, dapat {gesture}"
    gesture, _, _, _, _ = evaluate([], pose_hands_down(), ASPECT)
    assert gesture == NONE, f"harus NETRAL, dapat {gesture}"
    print("OK  evaluate: YA / TIDAK / NETRAL")


def test_gate() -> None:
    gate = GestureGate()
    gate.reset()
    for _ in range(3):
        assert gate.update(YES, 0.2) is None
    assert gate.update(YES, 0.2) == YES, "setelah ditahan 0.8 detik harus memicu"

    # setelah memicu, wajib netral dulu
    assert gate.update(YES, 0.2) is None, "tidak boleh memicu dua kali"
    for _ in range(5):
        assert gate.update(NONE, 0.2) is None
    for _ in range(3):
        assert gate.update(YES, 0.2) is None
    assert gate.update(YES, 0.2) == YES, "setelah netral harus bisa memicu lagi"
    print("OK  GestureGate: hold 0.8 detik, tidak dobel, wajib netral")


if __name__ == "__main__":
    test_thumbs_up()
    test_arms_crossed()
    test_evaluate()
    test_gate()
    print("\nSemua uji logika gesture lulus.")
