# Earth Jukebox - Track 04 "The planet breathing"
# Step 1 of 2: read the frames of NASA SVS 5047 (Net Ecosystem Exchange of CO2,
# https://svs.gsfc.nasa.gov/5047) and measure, frame by frame, how much land is
# ABSORBING CO2 (green) vs RELEASING it (magenta).
#
# Colour bar in the video: bright green = -10, black = 0, bright magenta = +10
# (kg of CO2 per 100 square metres per month). We turn each pixel's colour back
# into that scale, so the numbers follow the real legend, not just "how green".
#
# run  >  python nee/main/extract_features.py
# needs > pip install opencv-python numpy
# in   >  data/co2_nee_5.webm   (download the .webm from the SVS page above)
# out  >  data/nee_features.csv   one row per frame

import csv
import os

import cv2
import numpy as np

NEE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the nee/ folder
VIDEO_PATH = os.path.join(NEE_DIR, "data", "co2_nee_5.webm")
OUT_CSV = os.path.join(NEE_DIR, "data", "nee_features.csv")

# first month shown in the video (check the label in the bottom-left corner of frame 1)
START_YEAR, START_MONTH = 2003, 1

ANALYSIS_WIDTH = 480        # frames are shrunk to this width before measuring (4K is overkill)
LON_BANDS = 8               # west -> east slices of the map, used for left/right panning
FLUX_MAX = 10.0             # value at the ends of the colour bar
# from 2004 on, video compression (VP8) adds a faint blocky magenta tint to flat areas
# (ocean, Antarctica, deserts), worth up to ~0.75 on the colour bar. Values below this are ignored.
DEAD_ZONE = 1.0

# where things sit on screen, as fractions of the frame (x0, y0, x1, y1)
MAP_BOX = (0.015, 0.07, 0.99, 0.95)
EQUATOR_Y = 0.51            # the map's equator, as a fraction of the frame height
IGNORE_BOXES = [
    (0.00, 0.84, 0.13, 1.00),   # month / year label, bottom-left
    (0.85, 0.86, 1.00, 1.00),   # colour bar, bottom-right
    (0.25, 0.00, 0.75, 0.08),   # title
]
# only land counts: land = pixels brighter than the ocean in the first frames (2003 has no tint)
LAND_MASK_FRAMES = 120      # the first year
LAND_MIN_BRIGHTNESS = 28    # ocean is ~16, grey land ~45
ANTARCTICA_Y = 0.86         # below this line is Antarctica (no ecosystem data), left out

# a new month starts when a frame differs from the previous one by this many times the usual change
MONTH_CHANGE_FACTOR = 4.0
# the video crossfades between months, so detection can miss them. If it doesn't find
# EXPECTED_MONTHS, fall back to fixed months (checked against the label: 10 frames each)
EXPECTED_MONTHS = 180       # Jan 2003 -> Dec 2017
FRAMES_PER_MONTH = 10


def shrink(frame):
    h0, w0 = frame.shape[:2]
    return cv2.resize(frame, (ANALYSIS_WIDTH, round(ANALYSIS_WIDTH * h0 / w0)), interpolation=cv2.INTER_AREA)


def find_land():
    # brightest value each pixel reaches in the first frames: land is grey or coloured, ocean stays dark
    cap = cv2.VideoCapture(VIDEO_PATH)
    brightest = None
    for _ in range(LAND_MASK_FRAMES):
        ok, frame = cap.read()
        if not ok:
            break
        b = shrink(frame).max(axis=2)
        brightest = b if brightest is None else np.maximum(brightest, b)
    cap.release()
    return brightest > LAND_MIN_BRIGHTNESS


def build_masks(land):
    # boolean masks for: the land on the map, northern half, southern half, and each longitude band
    h, w = land.shape
    ys, xs = np.mgrid[0:h, 0:w]
    fx, fy = xs / w, ys / h
    x0, y0, x1, y1 = MAP_BOX
    on_map = land & (fx >= x0) & (fx <= x1) & (fy >= y0) & (fy <= min(y1, ANTARCTICA_Y))
    for bx0, by0, bx1, by1 in IGNORE_BOXES:
        on_map &= ~((fx >= bx0) & (fx <= bx1) & (fy >= by0) & (fy <= by1))
    north = on_map & (fy < EQUATOR_Y)
    south = on_map & (fy >= EQUATOR_Y)
    band_edges = np.linspace(x0, x1, LON_BANDS + 1)
    bands = [on_map & (fx >= band_edges[i]) & (fx < band_edges[i + 1]) for i in range(LON_BANDS)]
    return on_map, north, south, bands


def colour_to_flux(frame_bgr):
    # per-pixel absorb (green) and release (magenta) strength, in colour-bar units (0..FLUX_MAX)
    f = frame_bgr.astype(np.float32) / 255.0
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    absorb = np.clip(g - np.maximum(r, b), 0, 1) * FLUX_MAX     # green beats red and blue
    release = np.clip(np.minimum(r, b) - g, 0, 1) * FLUX_MAX    # red and blue both beat green
    absorb[absorb < DEAD_ZONE] = 0
    release[release < DEAD_ZONE] = 0
    return absorb, release


def mean_in(values, mask):
    return float(values[mask].mean()) if mask.any() else 0.0


def main():
    if not os.path.exists(VIDEO_PATH):
        raise SystemExit(f"Video not found: {VIDEO_PATH}. Download co2_nee_5.webm from https://svs.gsfc.nasa.gov/5047")

    cap = cv2.VideoCapture(VIDEO_PATH)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    on_map, north, south, bands = build_masks(find_land())
    rows, prev_small = [], None

    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = shrink(frame)
        absorb, release = colour_to_flux(small)
        change = 0.0 if prev_small is None else float(np.abs(small.astype(np.int16) - prev_small).mean())
        prev_small = small.astype(np.int16)

        row = {
            "frame": index,
            "time_s": round(index / fps, 4),
            "absorb": mean_in(absorb, on_map),
            "release": mean_in(release, on_map),
            "north_absorb": mean_in(absorb, north),
            "north_release": mean_in(release, north),
            "south_absorb": mean_in(absorb, south),
            "south_release": mean_in(release, south),
            "change": change,
        }
        for i, band in enumerate(bands):
            row[f"absorb_band{i}"] = mean_in(absorb, band)
            row[f"release_band{i}"] = mean_in(release, band)
        rows.append(row)
        index += 1
        if index % 300 == 0:
            print(f"  {index} frames read...")
    cap.release()

    if not rows:
        raise SystemExit("No frames could be read from the video.")

    # find where each new month starts: frames that change much more than usual
    changes = np.array([r["change"] for r in rows[1:]])
    usual = float(np.median(changes)) if len(changes) else 0.0
    starts = [0] + [i + 1 for i, c in enumerate(changes) if c > max(usual * MONTH_CHANGE_FACTOR, 0.5)]
    months_detected = len(starts)
    month_mode = "detected"
    if months_detected != EXPECTED_MONTHS:
        print(f"Detected {months_detected} months, expected {EXPECTED_MONTHS}: using fixed {FRAMES_PER_MONTH} frames per month")
        starts = list(range(0, len(rows), FRAMES_PER_MONTH))
        month_mode = "fixed"

    month_of_frame = np.searchsorted(starts, np.arange(len(rows)), side="right") - 1
    for r, m in zip(rows, month_of_frame):
        total = START_MONTH - 1 + int(m)
        r["year"] = START_YEAR + total // 12
        r["month"] = total % 12 + 1

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = ["frame", "time_s", "year", "month", "absorb", "release", "north_absorb", "north_release",
              "south_absorb", "south_release", "change"] + \
             [f"absorb_band{i}" for i in range(LON_BANDS)] + [f"release_band{i}" for i in range(LON_BANDS)]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})

    last = rows[-1]
    meta = {
        "video": VIDEO_PATH,
        "fps": fps,
        "frames": len(rows),
        "video_length_s": round(len(rows) / fps, 4),
        "months_detected": months_detected,
        "month_mode": month_mode,
        "months": len(starts),
        "first_month": f"{START_YEAR}-{START_MONTH:02d}",
        "last_month": f"{last['year']}-{last['month']:02d}",
        "land_pixels": int(on_map.sum()),
        "dead_zone": DEAD_ZONE,
        "month_start_frames": starts,
    }
    print(f"Wrote {OUT_CSV}: {len(rows)} frames, {meta['video_length_s']} s")
    print(f"{len(starts)} months ({month_mode}): {meta['first_month']} to {meta['last_month']}")
    print("Check these dates against the label in the video; fix START_YEAR/START_MONTH if needed.")


if __name__ == "__main__":
    main()
