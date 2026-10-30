"""Semua pengaturan program ada di sini.

Ubah nilai di file ini kalau ingin menyesuaikan kamera, teks, durasi,
atau seberapa mudah gesture terbaca.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ROOT_DIR / "assets"
MODELS_DIR = ROOT_DIR / "models"

# ---------------------------------------------------------------- kamera ----
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
MIRROR = True                 # tampilan kamera seperti cermin
DETECT_EVERY_N_FRAMES = 2     # deteksi gesture tiap 2 frame (hemat CPU)

# --------------------------------------------------------------- tampilan ---
FULLSCREEN = True
HIDE_CURSOR = True

# ------------------------------------------------------------------ aset ----
ASSET_QUESTION_1 = ASSETS_DIR / "ga_jumatan.png"
ASSET_REMINDER = ASSETS_DIR / "hanya_mengingatkan.png"

# ------------------------------------------------------------------ teks ----
TEXT_QUESTION_1 = "GA JUMATAN KAH?"
TEXT_QUESTION_2 = "MAU INFO MASJID TERDEKAT?"
TEXT_HATI_HATI = "HATI-HATI DI JALAN"
TEXT_HATI_HATI_SUB = "Semoga Allah mudahkan urusanmu."
TEXT_MAPS_OPENING = "MEMBUKA GOOGLE MAPS..."
TEXT_MAPS_SUB = "Mencari masjid terdekat dari lokasimu"
TEXT_REMINDER_SUB = "Kembali ke awal..."
TEXT_HINT_YES = "JEMPOL = YA"
TEXT_HINT_NO = "TANGAN MENYILANG = TIDAK"
TEXT_HOLD = "Tahan pose sampai lingkaran penuh"

# ------------------------------------------------------------- google maps --
MAPS_URL = "https://www.google.com/maps/search/masjid+terdekat"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\PC\AppData\Local\Google\Chrome\Application\chrome.exe",
]

# ---------------------------------------------------- durasi (dalam detik) ---
HOLD_SECONDS = 0.8        # gesture harus ditahan selama ini sebelum dianggap jawaban
GATE_DECAY = 3.0          # kalau gesture hilang sesaat, progres turun perlahan (per detik)
NEUTRAL_SECONDS = 0.8     # wajib netral dulu sebelum jawaban berikutnya bisa masuk
COOLDOWN_SECONDS = 1.0    # jeda setelah jawaban diterima
GESTURE_SMOOTHING = 0.45  # perataan skor antar frame (0..1, makin besar makin reaktif)
REMINDER_SECONDS = 5.0    # lama panel "hanya mengingatkan" tampil
HATI_HATI_SECONDS = 4.5   # lama pesan "hati-hati di jalan" tampil
MAPS_MESSAGE_SECONDS = 3.5  # lama pesan "membuka google maps" tampil

# ------------------------------------------------------ ambang gesture YA ----
# Jempol harus mengarah ke atas: -dy minimal sebesar ini (0..1)
THUMB_MIN_VERTICAL = 0.55
# Kemiringan jempol maksimum (rasio |dx| / |dy|)
THUMB_MAX_TILT = 0.70
# Jari lain dianggap terlipat kalau ujung jari lebih dekat pergelangan
# daripada sendi tengahnya, dikali faktor ini
THUMB_FINGER_FOLD_RATIO = 0.95
# Minimal jumlah jari (dari 4) yang terlipat
THUMB_MIN_FOLDED_FINGERS = 3
# Jarak minimal ujung jempol dari pangkal telunjuk (rasio ukuran tangan)
THUMB_MIN_EXTENSION = 0.50

# -------------------------------------------------- ambang gesture TIDAK ----
CROSS_MIN_VISIBILITY = 0.35      # landmark harus cukup yakin terlihat
CROSS_MIN_SCORE = 0.55           # skor minimal agar dianggap tangan menyilang
CROSS_MAX_ELBOW_ANGLE = 160.0    # siku harus menekuk (derajat)
CROSS_MIN_ELBOW_ANGLE = 20.0
CROSS_MAX_WRIST_GAP = 1.10       # jarak 2 pergelangan maks (rasio lebar bahu)
CROSS_MAX_FOREARM_SLOPE = 1.60   # |dy| / |dx| lengan bawah, makin kecil makin datar

# --------------------------------------------------------------- logging ----
LOG_DIR = ROOT_DIR / "logs"
LOG_GESTURES = True              # catat skor gesture ke logs\gesture.csv untuk diagnosa
LOG_EVERY_N_FRAMES = 5

# ----------------------------------------------------------------- model ----
DETECT_WIDTH = 960               # frame diperkecil ke lebar ini sebelum dideteksi
POSE_MODEL = "full"              # "lite" (cepat), "full" (lebih akurat), "heavy" (paling akurat)
HAND_MAX_HANDS = 2               # deteksi 2 tangan sekaligus
