"""Logika penilaian gesture: jempol (YA) dan tangan menyilang (TIDAK)."""

from __future__ import annotations

import math

import numpy as np

import config as C

YES = "YA"
NO = "TIDAK"
NONE = "NETRAL"


def _to_pts(landmarks: np.ndarray, aspect: float) -> np.ndarray:
    """Ubah koordinat ternormalisasi (0..1) ke ruang yang proporsional.

    Tanpa koreksi aspect, sudut & jarak jadi melar karena frame 16:9.
    """
    pts = np.empty((len(landmarks), 2), dtype=np.float32)
    pts[:, 0] = landmarks[:, 0] * aspect
    pts[:, 1] = landmarks[:, 1]
    return pts


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Sudut ABC dalam derajat."""
    v1 = a - b
    v2 = c - b
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    cos_a = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(cos_a))


def thumbs_up_score(hand: np.ndarray | None, aspect: float) -> float:
    """1.0 kalau tangan membentuk jempol ke atas, 0.0 kalau tidak."""
    if hand is None or len(hand) < 21:
        return 0.0

    p = _to_pts(hand, aspect)
    wrist = p[0]
    hand_scale = float(np.linalg.norm(p[9] - wrist))
    if hand_scale < 1e-5:
        return 0.0

    thumb_tip, thumb_ip, thumb_mcp = p[4], p[3], p[2]

    # 1. jempol mengarah ke atas (bukan ke samping)
    v = thumb_tip - wrist
    norm = float(np.linalg.norm(v))
    if norm < 1e-5:
        return 0.0
    v /= norm
    if v[1] > -C.THUMB_MIN_VERTICAL:
        return 0.0
    if abs(v[0]) > C.THUMB_MAX_TILT * abs(v[1]):
        return 0.0

    # 2. jempol terentang: ujung di atas sendi IP, dan IP di atas MCP
    if not (thumb_tip[1] < thumb_ip[1] and thumb_ip[1] < thumb_mcp[1]):
        return 0.0

    # 3. ujung jempol cukup jauh dari pangkal telunjuk (bukan menggenggam)
    if float(np.linalg.norm(thumb_tip - p[5])) < C.THUMB_MIN_EXTENSION * hand_scale:
        return 0.0

    # 4. empat jari lain terlipat ke telapak
    folded = 0
    for pip_idx, tip_idx in ((6, 8), (10, 12), (14, 16), (18, 20)):
        tip_dist = float(np.linalg.norm(p[tip_idx] - wrist))
        pip_dist = float(np.linalg.norm(p[pip_idx] - wrist))
        if tip_dist < pip_dist * C.THUMB_FINGER_FOLD_RATIO:
            folded += 1
    if folded < C.THUMB_MIN_FOLDED_FINGERS:
        return 0.0

    return 1.0


def thumbs_up_score_both_hands(hands: list[np.ndarray], aspect: float) -> float:
    return max((thumbs_up_score(h, aspect) for h in hands), default=0.0)


def arms_crossed_score(pose: np.ndarray | None, aspect: float) -> tuple[float, dict[str, bool], dict[str, float]]:
    """Skor 0..1 untuk pose tangan menyilang di depan dada.

    Beberapa kondisi diberi nilai sebagian supaya pose yang hampir benar tetap
    bisa lolos, dan tetap aman karena harus ditahan 1 detik.
    """
    checks = {
        "landmark terlihat": False,
        "pergelangan menyilang": False,
        "pergelangan berdekatan": False,
        "setinggi dada": False,
        "siku menekuk": False,
        "lengan mendatar": False,
    }
    metrics: dict[str, float] = {}
    score = 0.0

    if pose is None or len(pose) < 25:
        return score, checks, metrics

    x = pose[:, 0].astype(np.float32) * aspect
    y = pose[:, 1].astype(np.float32)
    vis = pose[:, 3].astype(np.float32) if pose.shape[1] > 3 else np.ones(len(pose))

    LS, RS, LE, RE, LW, RW = 11, 12, 13, 14, 15, 16
    core = (LS, RS, LE, RE, LW, RW)
    visible = vis[list(core)] >= C.CROSS_MIN_VISIBILITY
    metrics["terlihat"] = float(visible.sum())
    if int(visible.sum()) < 5:
        return score, checks, metrics
    checks["landmark terlihat"] = True

    shoulder_w = abs(float(x[LS] - x[RS]))
    metrics["lebar_bahu"] = shoulder_w
    if shoulder_w < 0.06:
        return score, checks, metrics

    # A. urutan kiri-kanan pergelangan terbalik dari bahu => menyilang
    inverted = bool(
        np.sign(x[LS] - x[RS]) != np.sign(x[LW] - x[RW])
        and abs(x[LW] - x[RW]) > 1e-4
    )
    metrics["terbalik"] = float(inverted)
    if inverted:
        score += 0.35
        checks["pergelangan menyilang"] = True

    # B. kedua pergelangan cukup dekat (menumpuk di depan dada)
    gap_ratio = abs(float(x[LW] - x[RW])) / shoulder_w
    metrics["jarak_pergelangan"] = gap_ratio
    if gap_ratio <= C.CROSS_MAX_WRIST_GAP:
        score += 0.20
        checks["pergelangan berdekatan"] = True

    # C. pergelangan setinggi dada, bukan di perut atau atas kepala
    chest_top = min(float(y[LS]), float(y[RS])) - 0.45 * shoulder_w
    hips_visible = vis[23] >= C.CROSS_MIN_VISIBILITY and vis[24] >= C.CROSS_MIN_VISIBILITY
    if hips_visible:
        chest_bottom = max(float(y[23]), float(y[24]))
    else:
        chest_bottom = max(float(y[LS]), float(y[RS])) + 1.5 * shoulder_w
    wrist_y = (float(y[LW]) + float(y[RW])) * 0.5
    metrics["tinggi_pergelangan"] = wrist_y
    metrics["batas_atas_dada"] = chest_top
    metrics["batas_bawah_dada"] = chest_bottom
    if chest_top < wrist_y < chest_bottom:
        score += 0.20
        checks["setinggi dada"] = True

    # D & E. siku menekuk + lengan bawah mendatar
    if bool(np.all(visible[2:])):
        elbow_angles = []
        slopes = []
        for elbow, shoulder, wrist in ((LE, LS, LW), (RE, RS, RW)):
            elbow_angles.append(_angle(
                np.array([x[shoulder], y[shoulder]]),
                np.array([x[elbow], y[elbow]]),
                np.array([x[wrist], y[wrist]]),
            ))
            dx = abs(float(x[wrist] - x[elbow]))
            dy = abs(float(y[wrist] - y[elbow]))
            slopes.append(999.0 if dx < 1e-4 else dy / dx)
        metrics["sudut_siku_min"] = min(elbow_angles)
        metrics["sudut_siku_max"] = max(elbow_angles)
        metrics["kemiringan_lengan_max"] = max(slopes)

        if all(C.CROSS_MIN_ELBOW_ANGLE <= a <= C.CROSS_MAX_ELBOW_ANGLE for a in elbow_angles):
            score += 0.15
            checks["siku menekuk"] = True
        if all(s <= C.CROSS_MAX_FOREARM_SLOPE for s in slopes):
            score += 0.10
            checks["lengan mendatar"] = True

    # Urutan menyilang adalah bukti terkuat: tanpa ini pose lain (mis. tangan
    # dikatupkan di dada) tidak boleh dianggap "TIDAK".
    if not inverted:
        score = 0.0

    return round(score, 3), checks, metrics


def evaluate(hands: list[np.ndarray], pose: np.ndarray | None,
             aspect: float) -> tuple[str, float, float, dict[str, bool], dict[str, float]]:
    """Tentukan satu jawaban dari hasil deteksi satu frame."""
    yes_score = thumbs_up_score_both_hands(hands, aspect)
    cross_score, checks, metrics = arms_crossed_score(pose, aspect)
    if yes_score >= 0.5:
        return YES, yes_score, cross_score, checks, metrics
    if cross_score >= C.CROSS_MIN_SCORE:
        return NO, yes_score, cross_score, checks, metrics
    return NONE, yes_score, cross_score, checks, metrics


class ScoreSmoother:
    """Ratakan skor antar frame supaya pose yang sempat goyah tidak langsung hilang."""

    def __init__(self, alpha: float | None = None) -> None:
        self.alpha = C.GESTURE_SMOOTHING if alpha is None else alpha
        self.value: float | None = None

    def update(self, score: float) -> float:
        if self.value is None:
            self.value = score
        else:
            self.value += self.alpha * (score - self.value)
        return self.value

    def reset(self) -> None:
        self.value = None


class GestureGate:
    """Pastikan gesture ditahan cukup lama dan tidak memicu dua kali."""

    def __init__(self) -> None:
        self.gesture = NONE
        self.held = 0.0
        self.progress = 0.0
        self.armed = True
        self._neutral_time = 0.0
        self._cooldown = 0.0

    def reset(self) -> None:
        self.gesture = NONE
        self.held = 0.0
        self.progress = 0.0
        self.armed = True
        self._neutral_time = 0.0
        self._cooldown = 0.0

    def disarm(self) -> None:
        """Minta pengguna kembali netral dulu sebelum jawaban berikutnya."""
        self.gesture = NONE
        self.held = 0.0
        self.progress = 0.0
        self.armed = False
        self._neutral_time = 0.0

    def update(self, gesture: str, dt: float) -> str | None:
        dt = max(0.0, min(dt, 0.25))  # hindari lompatan besar saat frame tersendat
        self._cooldown = max(0.0, self._cooldown - dt)

        if not self.armed:
            if gesture == NONE:
                self._neutral_time += dt
            else:
                self._neutral_time = 0.0
            if self._neutral_time >= C.NEUTRAL_SECONDS:
                self.armed = True
                self._neutral_time = 0.0
            self.gesture = NONE
            self.held = 0.0
            self.progress = 0.0
            return None

        if gesture == NONE:
            self.gesture = NONE
            # Toleransi: pose sempat hilang 1-2 frame tidak menghapus progres.
            self.held = max(0.0, self.held - C.GATE_DECAY * dt)
            self.progress = min(1.0, self.held / max(1e-6, C.HOLD_SECONDS))
            return None

        if gesture != self.gesture:
            self.gesture = gesture
            self.held = 0.0

        self.held += dt
        self.progress = min(1.0, self.held / max(1e-6, C.HOLD_SECONDS))

        if self.held >= C.HOLD_SECONDS and self._cooldown <= 0.0:
            self._cooldown = C.COOLDOWN_SECONDS
            self.disarm()
            return gesture
        return None
