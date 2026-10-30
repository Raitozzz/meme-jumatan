"""Tampilan pygame: kamera fullscreen, panel gambar, teks besar, ring progres."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pygame

import config as C

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (118, 226, 132)
RED = (255, 110, 110)
YELLOW = (255, 214, 92)
SOFT = (232, 236, 240)


class UI:
    def __init__(self, fullscreen: bool = True) -> None:
        pygame.init()
        pygame.display.set_caption("GA JUMATAN KAH?")
        flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
        size = (0, 0) if fullscreen else (1280, 720)
        self.screen = pygame.display.set_mode(size, flags)
        self.w, self.h = self.screen.get_size()
        self.s = self.h / 1080.0

        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._text_cache: dict[tuple, pygame.Surface] = {}
        self._image_cache: dict[tuple, pygame.Surface] = {}
        self._dim_cache: dict[int, pygame.Surface] = {}
        # Arial Black paling mirip panel meme dan tidak butuh synthetic bold
        # (Impact + bold=True rusak di SDL_ttf, glyph-nya tumpang tindih).
        self._font_path = None
        for family in ("arialblack", "segoeuiblack", "impact", "segoeui"):
            path = pygame.font.match_font(family)
            if path:
                self._font_path = path
                break

        if C.HIDE_CURSOR:
            pygame.mouse.set_visible(False)

    # ------------------------------------------------------------ utilitas --
    def _font(self, px: float, bold: bool = False) -> pygame.font.Font:
        size = max(8, int(round(px)))
        key = (size, bold)
        font = self._fonts.get(key)
        if font is None:
            if self._font_path:
                font = pygame.font.Font(self._font_path, size)
            else:
                font = pygame.font.SysFont("segoeui", size, bold=bold)
            font.set_bold(bold and "impact" not in str(self._font_path).lower())
            self._fonts[key] = font
        return font

    def _label(self, text: str, px: float, color=WHITE, outline: float = 0.0) -> pygame.Surface:
        """Render teks (dengan cache) plus outline hitam opsional."""
        key = (text, int(px), color, int(outline))
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached

        font = self._font(px)
        base = font.render(text, True, color)
        pad = int(outline) * 2 + 2
        surf = pygame.Surface((base.get_width() + pad * 2, base.get_height() + pad * 2), pygame.SRCALPHA)
        if outline > 0:
            dark = font.render(text, True, BLACK)
            for angle in range(0, 360, 30):
                dx = int(round(math.cos(math.radians(angle)) * outline))
                dy = int(round(math.sin(math.radians(angle)) * outline))
                surf.blit(dark, (pad + dx, pad + dy))
        surf.blit(base, (pad, pad))
        if len(self._text_cache) > 400:
            self._text_cache.clear()
        self._text_cache[key] = surf
        return surf

    def blit_text(self, text: str, cx: float, cy: float, px: float, color=WHITE,
                  outline: float = 0.0) -> pygame.Rect:
        surf = self._label(text, px, color, outline)
        rect = surf.get_rect(center=(int(cx), int(cy)))
        self.screen.blit(surf, rect)
        return rect

    def panel(self, path: Path, max_w: float, max_h: float) -> pygame.Surface | None:
        key = (str(path), int(max_w), int(max_h))
        cached = self._image_cache.get(key)
        if cached is not None:
            return cached
        if not Path(path).is_file():
            return None
        image = pygame.image.load(str(path)).convert_alpha()
        iw, ih = image.get_size()
        scale = min(max_w / iw, max_h / ih)
        size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
        scaled = pygame.transform.smoothscale(image, size)
        self._image_cache[key] = scaled
        return scaled

    def dim(self, alpha: int) -> None:
        if alpha <= 0:
            return
        overlay = self._dim_cache.get(alpha)
        if overlay is None:
            overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            overlay.fill((8, 10, 14, alpha))
            self._dim_cache[alpha] = overlay
        self.screen.blit(overlay, (0, 0))

    def box(self, rect: pygame.Rect, color=(10, 12, 18), alpha: int = 165, radius: int = 26) -> None:
        surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (*color, alpha), surf.get_rect(), border_radius=radius)
        self.screen.blit(surf, rect.topleft)

    # ------------------------------------------------------------- kamera ---
    def draw_camera(self, rgb: np.ndarray, dim_alpha: int = 110) -> None:
        height, width = rgb.shape[:2]
        surface = pygame.image.frombuffer(np.ascontiguousarray(rgb).tobytes(), (width, height), "RGB")
        scale = max(self.w / width, self.h / height)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        scaled = pygame.transform.smoothscale(surface, new_size)
        self.screen.fill(BLACK)
        self.screen.blit(scaled, ((self.w - new_size[0]) // 2, (self.h - new_size[1]) // 2))
        self.dim(dim_alpha)

    # -------------------------------------------------------------- panel ---
    def draw_panel(self, path: Path, center_y: float, max_w_frac: float = 0.52,
                   max_h_frac: float = 0.42, lift: float = 1.0) -> pygame.Rect | None:
        image = self.panel(path, self.w * max_w_frac, self.h * max_h_frac)
        if image is None:
            return None

        rect = image.get_rect(center=(self.w // 2, int(self.h * center_y)))
        # bayangan + bingkai putih ala panel meme
        shadow = pygame.Surface((rect.w + 28, rect.h + 28), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=18)
        self.screen.blit(shadow, (rect.x - 14, rect.y - 6))
        frame = pygame.Surface((rect.w + 12, rect.h + 12), pygame.SRCALPHA)
        pygame.draw.rect(frame, (250, 250, 250, 235), frame.get_rect(), border_radius=14)
        self.screen.blit(frame, (rect.x - 6, rect.y - 6))
        self.screen.blit(image, rect)
        return rect

    # --------------------------------------------------------------- teks ---
    def draw_question(self, text: str, center_y: float, size_frac: float = 0.105,
                      max_width_frac: float = 0.90) -> None:
        px = self.h * size_frac
        while True:
            label = self._label(text, px, WHITE, outline=max(2.0, px * 0.055))
            if label.get_width() <= self.w * max_width_frac or px <= 12:
                break
            px *= 0.94

        rect = label.get_rect(center=(self.w // 2, int(self.h * center_y)))
        pad_x = int(self.h * 0.03)
        pad_y = int(self.h * 0.012)
        band = pygame.Rect(rect.x - pad_x, rect.y - pad_y, rect.w + pad_x * 2, rect.h + pad_y * 2)
        self.box(band, alpha=135, radius=int(self.h * 0.02))
        self.screen.blit(label, rect)

    def draw_hints(self, center_y: float) -> None:
        px = self.h * 0.026
        gap = self.w * 0.06
        yes = self._label(C.TEXT_HINT_YES, px, SOFT)
        no = self._label(C.TEXT_HINT_NO, px, SOFT)
        total = yes.get_width() + no.get_width() + gap
        x = self.w / 2 - total / 2
        cy = int(self.h * center_y)

        for offset, surf, color, icon in ((x, yes, GREEN, "thumb"), (x + yes.get_width() + gap, no, RED, "cross")):
            icon_center = (int(offset - px * 1.1), cy)
            if icon == "thumb":
                pygame.draw.circle(self.screen, color, icon_center, int(px * 0.42))
                pygame.draw.circle(self.screen, (15, 20, 15), icon_center, int(px * 0.42), 3)
            else:
                r = int(px * 0.34)
                pygame.draw.line(self.screen, color, (icon_center[0] - r, icon_center[1] - r),
                                 (icon_center[0] + r, icon_center[1] + r), 4)
                pygame.draw.line(self.screen, color, (icon_center[0] + r, icon_center[1] - r),
                                 (icon_center[0] - r, icon_center[1] + r), 4)
            self.screen.blit(surf, surf.get_rect(center=(int(offset + surf.get_width() / 2), cy)))

    def draw_ring(self, progress: float, gesture: str, center_y: float = 0.885) -> None:
        center = (self.w // 2, int(self.h * center_y))
        radius = int(self.h * 0.036)
        width = max(6, int(self.h * 0.010))

        pygame.draw.circle(self.screen, (255, 255, 255, 60), center, radius, width)
        if progress > 0:
            color = GREEN if gesture == "YA" else RED
            rect = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
            start = math.pi / 2
            end = start - 2 * math.pi * max(0.001, min(1.0, progress))
            pygame.draw.arc(self.screen, color, rect, end, start, width)
        label = self._label(f"{int(progress * 100)}%", self.h * 0.024, SOFT)
        self.screen.blit(label, label.get_rect(center=center))

        if progress > 0.02:
            hint = self._label(C.TEXT_HOLD, self.h * 0.022, (210, 214, 220))
            self.screen.blit(hint, hint.get_rect(midtop=(center[0], center[1] + radius + int(self.h * 0.012))))

    def draw_footer(self, text: str, y_frac: float = 0.965) -> None:
        label = self._label(text, self.h * 0.019, (180, 188, 196))
        self.screen.blit(label, label.get_rect(center=(self.w // 2, int(self.h * y_frac))))

    def draw_debug(self, lines: list[str]) -> None:
        px = self.h * 0.019
        pad = int(px * 0.6)
        surfaces = [self._label(line, px, YELLOW) for line in lines]
        width = max(s.get_width() for s in surfaces) + pad * 2
        height = sum(s.get_height() for s in surfaces) + pad * 2
        box = pygame.Rect(int(self.w * 0.012), int(self.h * 0.015), width, height)
        self.box(box, alpha=170, radius=10)
        y = box.y + pad
        for surf in surfaces:
            self.screen.blit(surf, (box.x + pad, y))
            y += surf.get_height()

    # ------------------------------------------------------------ layar inti -
    def show_question(self, rgb, panel_path: Path, question: str, progress: float, gesture: str,
                      panel_y: float = 0.285, question_y: float = 0.655) -> None:
        self.draw_camera(rgb)
        self.draw_panel(panel_path, panel_y, max_w_frac=0.46, max_h_frac=0.40)
        self.draw_question(question, question_y)
        self.draw_hints(0.795)
        self.draw_ring(progress, gesture)
        self.draw_footer("ESC = keluar     F1 = mode debug")

    def show_reminder(self, rgb, seconds_left: float) -> None:
        self.draw_camera(rgb, dim_alpha=165)
        self.draw_panel(C.ASSET_REMINDER, 0.475, max_w_frac=0.46, max_h_frac=0.70)
        self.draw_footer(f"{C.TEXT_REMINDER_SUB}  ({max(0.0, seconds_left):.1f} detik)", 0.945)

    def show_message(self, rgb, title: str, subtitle: str) -> None:
        self.draw_camera(rgb, dim_alpha=200)
        self.draw_question(title, 0.47, size_frac=0.105)
        if subtitle:
            label = self._label(subtitle, self.h * 0.034, SOFT, outline=self.h * 0.002)
            self.screen.blit(label, label.get_rect(center=(self.w // 2, int(self.h * 0.62))))
        self.draw_footer("ESC = keluar")

    def flash(self, color, alpha: int) -> None:
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        surf.fill((*color, alpha))
        self.screen.blit(surf, (0, 0))

    def present(self) -> None:
        pygame.display.flip()

    def close(self) -> None:
        pygame.quit()
