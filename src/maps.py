"""Membuka Google Maps di Google Chrome."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import config as C


def find_chrome() -> str | None:
    """Cari chrome.exe di lokasi yang umum."""
    candidates = list(C.CHROME_CANDIDATES)
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    for path in candidates:
        if Path(path).is_file():
            return path
    return None


def open_maps(url: str = C.MAPS_URL) -> tuple[bool, str]:
    """Buka URL di Chrome. Mengembalikan (berhasil, pesan)."""
    chrome = find_chrome()
    try:
        if chrome:
            subprocess.Popen(
                [chrome, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            )
            return True, "Chrome"
        if sys.platform == "win32":
            os.startfile(url)  # type: ignore[attr-defined]
            return True, "browser default"
        return False, "Chrome tidak ditemukan"
    except Exception as exc:  # noqa: BLE001
        return False, f"Gagal membuka browser: {exc}"
