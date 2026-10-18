"""Decode source videos/photos for the energetic clip.

Outputs:
  assets/src/<name>.npy   uint8 (N, 640, 640, 3) BGR @ 30 fps
  assets/photos/<name>.png  square 900x900 crops
  assets/beats.json       beat grid
"""
from __future__ import annotations

import json
import os
import subprocess

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVE = os.path.join(HERE, "..", "google_drive")
ASSETS = os.path.join(HERE, "assets")
SRC = os.path.join(ASSETS, "src")
PHOTOS = os.path.join(ASSETS, "photos")
FF = subprocess.run(["python3", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True).stdout.strip()

SIZE = 640
FPS = 30

VIDEOS = {
    "office": "VID_20261018_233753_206.mp4",
    "wash": "VID_20261018_233757_889.mp4",
    "fire": "VID_20261018_233802_792.mp4",
    "gas": "VID_20261018_233806_819.mp4",
    "storm": "VID_20261018_233808_787.mp4",
    "game": "VID_20261018_233812_540.mp4",
    "night": "VID_20261018_233818_692.mp4",
}
PHOTO_FILES = {
    "portrait": "IMG_20261018_233750_886.jpg",
    "messy": "IMG_20261018_233826_431.jpg",
}


def decode_video(name, path):
    out = os.path.join(SRC, name + ".npy")
    if os.path.exists(out):
        arr = np.load(out, mmap_mode="r")
        print(f"  {name}: cached {arr.shape}")
        return
    cmd = [FF, "-v", "error", "-i", path, "-vf", f"fps={FPS},scale={SIZE}:{SIZE}:flags=lanczos",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, SIZE, SIZE, 3)
    np.save(out, frames)
    print(f"  {name}: {frames.shape[0]} frames")


def crop_square(img, size=900):
    h, w = img.shape[:2]
    s = min(h, w)
    y0 = (h - s) // 2
    x0 = (w - s) // 2
    # bias towards the face: top third
    y0 = int(y0 * 0.55)
    y0 = max(0, min(h - s, y0))
    crop = img[y0:y0 + s, x0:x0 + s]
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_CUBIC)


def main():
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(PHOTOS, exist_ok=True)
    for name, fn in VIDEOS.items():
        decode_video(name, os.path.join(DRIVE, fn))
    for name, fn in PHOTO_FILES.items():
        img = cv2.imread(os.path.join(DRIVE, fn))
        sq = crop_square(img)
        cv2.imwrite(os.path.join(PHOTOS, name + ".png"), sq)
        print(f"  photo {name}: {sq.shape}")
    print("beats:", len(json.load(open(os.path.join(ASSETS, "beats.json")))["beats"]))


if __name__ == "__main__":
    main()
