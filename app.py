"""GA JUMATAN KAH? - program tanya-jawab pakai gesture tangan lewat webcam."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pygame

import config as C
from src import maps
from src.detector import Detector
from src.gesture_logic import NONE, NO, YES, GestureGate, ScoreSmoother, evaluate
from src.ui import UI

STATE_Q1 = "tanya_1"
STATE_Q2 = "tanya_2"
STATE_REMINDER = "pengingat"
STATE_MAPS = "maps"
STATE_HATI = "hati_hati"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def open_capture(source: int) -> cv2.VideoCapture | None:
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(source, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, C.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, C.CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, 30)
            return cap
        cap.release()
    return None


class FileSource:
    """Sumber gambar/video pengganti kamera, dipakai untuk uji tampilan."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.image = None
        self.cap = None
        if path.suffix.lower() in IMAGE_SUFFIXES:
            self.image = cv2.imread(str(path))
            if self.image is None:
                raise SystemExit(f"Tidak bisa membaca gambar: {path}")
        else:
            self.cap = cv2.VideoCapture(str(path))
            if not self.cap.isOpened():
                raise SystemExit(f"Tidak bisa membaca video: {path}")

    def read(self) -> np.ndarray | None:
        if self.image is not None:
            return self.image.copy()
        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()


class App:
    def __init__(self, fullscreen: bool = True, debug: bool = False, source: str | None = None,
                 initial_state: str | None = None) -> None:
        self.ui = UI(fullscreen)
        self.detector = Detector()
        self.gate = GestureGate()
        self.yes_smoother = ScoreSmoother()
        self.cross_smoother = ScoreSmoother()
        self.debug = debug
        self.state = STATE_Q1
        self.state_time = 0.0
        self.frame: np.ndarray | None = None
        self.gesture = NONE
        self.progress = 0.0
        self.cross_checks: dict[str, bool] = {}
        self.metrics: dict[str, float] = {}
        self.yes_score = 0.0
        self.cross_score = 0.0
        self.yes_smooth = 0.0
        self.cross_smooth = 0.0
        self.fps = 0.0
        self.frame_count = 0
        self.maps_ok = True
        self.maps_note = ""
        self.running = True
        self._log_file = None
        self._log_writer = None
        self._log_count = 0

        self.file_source: FileSource | None = None
        self.cap: cv2.VideoCapture | None = None
        if source:
            self.file_source = FileSource(Path(source))
        else:
            self.cap = open_capture(C.CAMERA_INDEX)
            if self.cap is None:
                raise SystemExit(
                    "Kamera tidak bisa dibuka. Cek izin kamera Windows, atau pakai --source <gambar/video> "
                    "untuk uji tampilan."
                )

        self._enter(STATE_Q1)
        if initial_state:
            self._enter(initial_state)

    # ------------------------------------------------------------ state ----
    def _enter(self, state: str) -> None:
        self.state = state
        self.state_time = 0.0
        self.progress = 0.0
        self.gate.disarm()
        self.yes_smoother.reset()
        self.cross_smoother.reset()
        if state == STATE_MAPS:
            ok, note = maps.open_maps()
            self.maps_ok = ok
            self.maps_note = note
            print(f"[maps] {'berhasil' if ok else 'gagal'} - {note}", flush=True)

    def _back_to_start(self) -> None:
        self._enter(STATE_Q1)

    def _answer(self, gesture: str) -> None:
        print(f"[jawaban] {self.state}: {gesture}", flush=True)
        if self.state == STATE_Q1:
            self._enter(STATE_Q2 if gesture == YES else STATE_REMINDER)
        elif self.state == STATE_Q2:
            self._enter(STATE_MAPS if gesture == YES else STATE_HATI)

    # ------------------------------------------------------------- frame ----
    def _grab(self) -> np.ndarray | None:
        if self.file_source is not None:
            frame = self.file_source.read()
        else:
            ok, frame = self.cap.read()
            frame = frame if ok else None
        if frame is None:
            return None
        return cv2.flip(frame, 1) if C.MIRROR else frame

    def _detect(self, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        if width > C.DETECT_WIDTH:
            scaled = cv2.resize(frame, (C.DETECT_WIDTH, int(C.DETECT_WIDTH * height / width)),
                               interpolation=cv2.INTER_AREA)
        else:
            scaled = frame
        detection = self.detector.process(scaled)
        aspect = scaled.shape[1] / scaled.shape[0]
        _, yes_score, cross_score, checks, metrics = evaluate(detection.hands, detection.pose, aspect)

        # Skor diratakan antar frame lalu dibandingkan dengan ambang, supaya pose
        # yang sempat goyah 1-2 frame tidak membatalkan jawaban.
        yes_smooth = self.yes_smoother.update(yes_score)
        cross_smooth = self.cross_smoother.update(cross_score)
        if yes_smooth >= 0.55:
            gesture = YES
        elif cross_smooth >= C.CROSS_MIN_SCORE:
            gesture = NO
        else:
            gesture = NONE

        self.gesture = gesture
        self.yes_score = yes_score
        self.cross_score = cross_score
        self.yes_smooth = yes_smooth
        self.cross_smooth = cross_smooth
        self.cross_checks = checks
        self.metrics = metrics
        if self.debug:
            self._draw_landmarks(frame, detection)
        self._log_gesture()

    def _log_gesture(self) -> None:
        """Catat skor gesture ke logs\\gesture.csv untuk diagnosa."""
        if not C.LOG_GESTURES:
            return
        self._log_count += 1
        if self._log_count % max(1, C.LOG_EVERY_N_FRAMES):
            return
        try:
            if self._log_file is None:
                C.LOG_DIR.mkdir(parents=True, exist_ok=True)
                path = C.LOG_DIR / "gesture.csv"
                baru = not path.is_file()
                self._log_file = open(path, "a", newline="", encoding="utf-8")
                self._log_writer = csv.writer(self._log_file)
                if baru:
                    self._log_writer.writerow([
                        "waktu", "state", "gesture", "jempol", "silang", "silang_halus", "terlihat",
                        "terbalik", "jarak", "tinggi", "batas_atas", "batas_bawah",
                        "siku_min", "siku_max", "miring",
                    ])
            m = self.metrics
            self._log_writer.writerow([
                time.strftime("%H:%M:%S"), self.state, self.gesture,
                f"{self.yes_score:.2f}", f"{self.cross_score:.2f}", f"{self.cross_smooth:.2f}",
                m.get("terlihat", ""), m.get("terbalik", ""),
                f"{m['jarak_pergelangan']:.2f}" if "jarak_pergelangan" in m else "",
                f"{m['tinggi_pergelangan']:.2f}" if "tinggi_pergelangan" in m else "",
                f"{m['batas_atas_dada']:.2f}" if "batas_atas_dada" in m else "",
                f"{m['batas_bawah_dada']:.2f}" if "batas_bawah_dada" in m else "",
                f"{m['sudut_siku_min']:.0f}" if "sudut_siku_min" in m else "",
                f"{m['sudut_siku_max']:.0f}" if "sudut_siku_max" in m else "",
                f"{m['kemiringan_lengan_max']:.2f}" if "kemiringan_lengan_max" in m else "",
            ])
            self._log_file.flush()
        except Exception:  # noqa: BLE001
            pass

    def _draw_landmarks(self, frame: np.ndarray, detection) -> None:
        height, width = frame.shape[:2]
        for hand in detection.hands:
            for x, y, _ in hand:
                cv2.circle(frame, (int(x * width), int(y * height)), 4, (90, 240, 120), -1)
        if detection.pose is not None:
            links = ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16))
            for a, b in links:
                ax, ay = detection.pose[a, 0], detection.pose[a, 1]
                bx, by = detection.pose[b, 0], detection.pose[b, 1]
                cv2.line(frame, (int(ax * width), int(ay * height)),
                         (int(bx * width), int(by * height)), (90, 200, 255), 2)
            for idx in (11, 12, 13, 14, 15, 16):
                x, y = detection.pose[idx, 0], detection.pose[idx, 1]
                cv2.circle(frame, (int(x * width), int(y * height)), 4, (255, 170, 90), -1)

    # -------------------------------------------------------------- update --
    def _update(self, dt: float) -> None:
        self.state_time += dt

        if self.state in (STATE_Q1, STATE_Q2):
            triggered = self.gate.update(self.gesture, dt)
            self.progress = self.gate.progress
            if triggered:
                self._answer(triggered)
            return

        self.progress = 0.0
        if self.state == STATE_REMINDER and self.state_time >= C.REMINDER_SECONDS:
            self._back_to_start()
        elif self.state == STATE_MAPS and self.state_time >= C.MAPS_MESSAGE_SECONDS:
            self._back_to_start()
        elif self.state == STATE_HATI and self.state_time >= C.HATI_HATI_SECONDS:
            self._back_to_start()

    # -------------------------------------------------------------- render --
    def _render(self) -> None:
        ui = self.ui
        if self.frame is None:
            ui.screen.fill((12, 14, 20))
            ui.blit_text("MENYIAPKAN KAMERA...", ui.w / 2, ui.h / 2, ui.h * 0.05, outline=ui.h * 0.004)
        else:
            rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
            if self.state == STATE_Q1:
                ui.show_question(rgb, C.ASSET_QUESTION_1, C.TEXT_QUESTION_1, self.progress, self.gesture)
            elif self.state == STATE_Q2:
                ui.show_question(rgb, C.ASSET_QUESTION_1, C.TEXT_QUESTION_2, self.progress, self.gesture,
                                 panel_y=0.255, question_y=0.62)
            elif self.state == STATE_REMINDER:
                ui.show_reminder(rgb, C.REMINDER_SECONDS - self.state_time)
            elif self.state == STATE_MAPS:
                subtitle = C.TEXT_MAPS_SUB if self.maps_ok else f"Gagal membuka browser ({self.maps_note})"
                ui.show_message(rgb, C.TEXT_MAPS_OPENING, subtitle)
            elif self.state == STATE_HATI:
                ui.show_message(rgb, C.TEXT_HATI_HATI, C.TEXT_HATI_HATI_SUB)

        if self.debug:
            checks = " ".join(f"{k}:{'v' if v else 'x'}" for k, v in self.cross_checks.items())
            m = self.metrics
            angka = "  ".join(
                f"{k}={v:.2f}" for k, v in m.items() if k in
                ("jarak_pergelangan", "tinggi_pergelangan", "sudut_siku_min", "kemiringan_lengan_max")
            )
            self.ui.draw_debug([
                f"FPS {self.fps:4.1f}   state={self.state}   gesture={self.gesture}",
                f"jempol={self.yes_score:.2f} (halus {self.yes_smooth:.2f})   "
                f"silang={self.cross_score:.2f} (halus {self.cross_smooth:.2f}, ambang {C.CROSS_MIN_SCORE})",
                angka or "belum ada landmark",
                checks,
                "Y = paksa YA   N = paksa TIDAK   F1 = debug   ESC = keluar",
            ])
        ui.present()

    # ---------------------------------------------------------------- loop --
    def run(self, screenshot: Path | None = None) -> None:
        clock = pygame.time.Clock()
        last = time.perf_counter()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.running = False
                    elif event.key == pygame.K_F1:
                        self.debug = not self.debug
                    elif event.key == pygame.K_y and self.state in (STATE_Q1, STATE_Q2):
                        self._answer(YES)
                    elif event.key == pygame.K_n and self.state in (STATE_Q1, STATE_Q2):
                        self._answer(NO)

            now = time.perf_counter()
            dt = now - last
            last = now
            if dt > 0:
                self.fps = self.fps * 0.9 + (1.0 / dt) * 0.1

            frame = self._grab()
            if frame is not None:
                self.frame = frame
            if self.frame is not None and self.frame_count % max(1, C.DETECT_EVERY_N_FRAMES) == 0:
                self._detect(self.frame)
            self.frame_count += 1

            self._update(dt)
            self._render()

            if screenshot is not None and self.frame_count > 3:
                pygame.image.save(self.ui.screen, str(screenshot))
                print(f"[screenshot] {screenshot}", flush=True)
                self.running = False
                continue

            clock.tick(60)

    def close(self) -> None:
        self.detector.close()
        if self._log_file is not None:
            try:
                self._log_file.close()
            except Exception:  # noqa: BLE001
                pass
        if self.cap is not None:
            self.cap.release()
        if self.file_source is not None:
            self.file_source.release()
        self.ui.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GA JUMATAN KAH? - tanya jawab pakai gesture tangan")
    parser.add_argument("--window", action="store_true", help="jalankan dalam jendela (bukan fullscreen)")
    parser.add_argument("--debug", action="store_true", help="tampilkan landmark & skor deteksi")
    parser.add_argument("--source", help="gambar/video pengganti kamera (untuk uji tampilan)")
    parser.add_argument("--shot", help="simpan satu screenshot lalu keluar (untuk cek layout)")
    parser.add_argument("--state", choices=[STATE_Q1, STATE_Q2, STATE_REMINDER, STATE_MAPS, STATE_HATI],
                        help="paksa mulai di tahap tertentu (untuk uji tampilan)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    fullscreen = C.FULLSCREEN and not args.window and not args.shot
    try:
        app = App(fullscreen=fullscreen, debug=args.debug or bool(args.shot), source=args.source,
                  initial_state=args.state)
    except SystemExit as exc:
        print(exc)
        pygame.init()
        screen = pygame.display.set_mode((1100, 360))
        font = pygame.font.SysFont("segoeui", 26)
        screen.fill((18, 20, 26))
        lines = str(exc).splitlines() or ["Terjadi kesalahan"]
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, (240, 240, 240)), (32, 40 + i * 36))
        pygame.display.flip()
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN):
                    waiting = False
        pygame.quit()
        return 1

    try:
        app.run(Path(args.shot) if args.shot else None)
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
