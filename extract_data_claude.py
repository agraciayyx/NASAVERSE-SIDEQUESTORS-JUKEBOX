import cv2
import numpy as np
import csv
import os
import math
from collections import defaultdict

# ==========================================
# 1. SETTINGS
# ==========================================

video_path = "iss_lightning_sphere_07312023_60p4k.mp4"
output_file = "lightning_master_dataset.csv"

# HSV range for yellow/orange-yellow lightning
LOWER_YELLOW = np.array([15, 100, 150])
UPPER_YELLOW = np.array([40, 255, 255])
V_MIN = int(LOWER_YELLOW[2])      # used to stretch brightness to 0-1

MIN_AREA = 2                      # minimum real (undilated) pixels
OPEN_KERNEL = 3                   # noise removal size. Set to 1 to disable
                                  # (opening with 3 deletes blobs under ~3x3 px)

# Event tracking
MAX_DISTANCE = 30
MAX_GAP_FRAMES = 3

# Phase boundaries (seconds)
PHASE_2_START = 20
PHASE_3_START = 70

# Phase 3 grouping
WINDOW_SEC = 0.2

# Optional: save mask/overlay images at these times (seconds) to tune thresholds
DEBUG_TIMES = []                  # e.g. [30.0, 80.0]

LAT_ZONES = ["Northern", "Equatorial", "Southern"]
LON_ZONES = ["Left", "Centre", "Right"]


# ==========================================
# 2. HELPERS
# ==========================================

def lat_zone(y, h):
    if y < h / 3:
        return "Northern"
    if y < 2 * h / 3:
        return "Equatorial"
    return "Southern"


def lon_zone(x, w):
    if x < w / 3:
        return "Left"
    if x < 2 * w / 3:
        return "Centre"
    return "Right"


def detect_lightning(frame):
    """Return list of detections with position, real size and brightness."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    core = cv2.inRange(hsv, LOWER_YELLOW, UPPER_YELLOW)

    if OPEN_KERNEL > 1:
        core = cv2.morphologyEx(
            core, cv2.MORPH_OPEN,
            np.ones((OPEN_KERNEL, OPEN_KERNEL), np.uint8)
        )

    # Dilate only to merge nearby pixels into one flash
    merged = cv2.dilate(core, np.ones((3, 3), np.uint8), iterations=1)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(merged)
    v_channel = hsv[:, :, 2]

    detections = []
    for i in range(1, num):
        x0 = stats[i, cv2.CC_STAT_LEFT]
        y0 = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        in_label = labels[y0:y0 + h, x0:x0 + w] == i
        core_px = in_label & (core[y0:y0 + h, x0:x0 + w] > 0)
        area = int(core_px.sum())
        if area < MIN_AREA:
            continue

        v_vals = v_channel[y0:y0 + h, x0:x0 + w][core_px]
        peak = (float(v_vals.max()) - V_MIN) / (255 - V_MIN)
        mean = (float(v_vals.mean()) - V_MIN) / (255 - V_MIN)

        detections.append({
            "x": float(centroids[i][0]),
            "y": float(centroids[i][1]),
            "area": area,
            "peak": max(0.0, min(1.0, peak)),
            "mean": max(0.0, min(1.0, mean)),
        })
    return detections


def save_debug(frame, detections, t):
    small = cv2.resize(frame, None, fx=0.4, fy=0.4)
    for d in detections:
        cv2.circle(small, (int(d["x"] * 0.4), int(d["y"] * 0.4)),
                   8, (0, 255, 0), 1)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_YELLOW, UPPER_YELLOW)
    cv2.imwrite(f"debug_{t:.1f}s_overlay.png", small)
    cv2.imwrite(f"debug_{t:.1f}s_mask.png",
                cv2.resize(mask, None, fx=0.4, fy=0.4))


# ==========================================
# 3. LOAD VIDEO
# ==========================================

cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    raise FileNotFoundError(f"Unable to open video: {video_path}")

FPS = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration = total_frames / FPS

print(f"Video: {frame_width}x{frame_height} @ {FPS:.2f} fps, "
      f"{duration:.1f}s, {total_frames} frames")

# Skip Phase 1 entirely (no events recorded there)
start_frame = int(PHASE_2_START * FPS)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
frame_number = start_frame

output_records = []      # Individual rows (Phase 2)
regional_events = []     # Finished events that start in Phase 3
active_events = []
next_event_id = 1
debug_frames = {int(t * FPS) for t in DEBUG_TIMES}


# ==========================================
# 4. EVENT FINALISATION
# ==========================================

def finalise_event(ev):
    avg_x = float(np.mean(ev["xs"]))
    avg_y = float(np.mean(ev["ys"]))
    event = {
        "id": ev["id"],
        "start": ev["start_ts"],
        "x": avg_x,
        "y": avg_y,
        "peak": ev["peak"],
        "mean": ev["mean_sum"] / ev["n"],
        "size": ev["max_area"],
        "duration": (ev["last_frame"] - ev["start_frame"] + 1) / FPS,
    }

    if ev["start_ts"] < PHASE_3_START:
        output_records.append({
            "Timestamp": round(event["start"], 3),
            "Event ID": event["id"],
            "X": round(avg_x, 2),
            "Y": round(avg_y, 2),
            "X_norm": round(avg_x / frame_width, 4),
            "Y_norm": round(avg_y / frame_height, 4),
            "Pan": round(avg_x / frame_width * 2 - 1, 4),
            "Pitch_Norm": round(1 - avg_y / frame_height, 4),
            "Latitude zone": lat_zone(avg_y, frame_height),
            "Longitude zone": lon_zone(avg_x, frame_width),
            "Phase": "Individual",
            "Duration_sec": round(event["duration"], 3),
            "Peak_Brightness": round(event["peak"], 3),
            "Mean_Brightness": round(event["mean"], 3),
            "Size_px": event["size"],
            "Flash_Count": 1,
        })
    else:
        regional_events.append(event)


# ==========================================
# 5. PROCESS VIDEO (tracker runs on every frame, Phase 2 and 3)
# ==========================================

while True:
    success, frame = cap.read()
    if not success:
        break

    timestamp = frame_number / FPS
    detections = detect_lightning(frame)

    if frame_number in debug_frames:
        save_debug(frame, detections, timestamp)

    # Expire old events
    remaining = []
    for ev in active_events:
        if frame_number - ev["last_frame"] > MAX_GAP_FRAMES:
            finalise_event(ev)
        else:
            remaining.append(ev)
    active_events = remaining

    # Match detections to events
    matched = set()
    for det in detections:
        best, best_dist = None, MAX_DISTANCE
        for ev in active_events:
            if ev["id"] in matched:
                continue
            dist = math.hypot(det["x"] - ev["last_x"], det["y"] - ev["last_y"])
            if dist <= best_dist:
                best, best_dist = ev, dist

        if best is not None:
            best["last_frame"] = frame_number
            best["last_x"], best["last_y"] = det["x"], det["y"]
            best["xs"].append(det["x"])
            best["ys"].append(det["y"])
            best["peak"] = max(best["peak"], det["peak"])
            best["mean_sum"] += det["mean"]
            best["n"] += 1
            best["max_area"] = max(best["max_area"], det["area"])
            matched.add(best["id"])
        else:
            active_events.append({
                "id": next_event_id,
                "start_ts": timestamp,
                "start_frame": frame_number,
                "last_frame": frame_number,
                "last_x": det["x"], "last_y": det["y"],
                "xs": [det["x"]], "ys": [det["y"]],
                "peak": det["peak"],
                "mean_sum": det["mean"], "n": 1,
                "max_area": det["area"],
            })
            matched.add(next_event_id)
            next_event_id += 1

    if frame_number % 300 == 0:
        print(f"Processing: {frame_number}/{total_frames} "
              f"({frame_number / total_frames * 100:.1f}%)")

    frame_number += 1

for ev in active_events:
    finalise_event(ev)

cap.release()


# ==========================================
# 6. PHASE 3: BIN EVENTS INTO WINDOWS x 3x3 REGIONS
# ==========================================

bins = defaultdict(list)
max_window = int(math.ceil((duration - PHASE_3_START) / WINDOW_SEC))

for e in regional_events:
    w = int((e["start"] - PHASE_3_START) // WINDOW_SEC)
    key = (w, lat_zone(e["y"], frame_height), lon_zone(e["x"], frame_width))
    bins[key].append(e)
    max_window = max(max_window, w + 1)

cell_counts = [len(v) for v in bins.values()] or [1]
max_cell = max(cell_counts)

global_counts = defaultdict(int)
for (w, _, _), evs in bins.items():
    global_counts[w] += len(evs)
max_global = max(global_counts.values()) if global_counts else 1

regional_rows = []
for w in range(max_window):
    ts = round(PHASE_3_START + w * WINDOW_SEC, 3)
    for lat in LAT_ZONES:
        for lon in LON_ZONES:
            evs = bins.get((w, lat, lon), [])
            count = len(evs)
            total_b = sum(e["peak"] for e in evs)

            if count:
                weights = [e["peak"] + 1e-6 for e in evs]
                x = float(np.average([e["x"] for e in evs], weights=weights))
                y = float(np.average([e["y"] for e in evs], weights=weights))
                row_x, row_y = round(x, 2), round(y, 2)
                x_norm, y_norm = x / frame_width, y / frame_height
                pan, pitch = x_norm * 2 - 1, 1 - y_norm
                x_norm, y_norm = round(x_norm, 4), round(y_norm, 4)
                pan, pitch = round(pan, 4), round(pitch, 4)
                peak = round(max(e["peak"] for e in evs), 3)
                size = sum(e["size"] for e in evs)
            else:
                row_x = row_y = x_norm = y_norm = pan = pitch = None
                peak = size = None

            regional_rows.append({
                "Timestamp": ts,
                "Event ID": next_event_id,
                "X": row_x,
                "Y": row_y,
                "X_norm": x_norm,
                "Y_norm": y_norm,
                "Pan": pan,
                "Pitch_Norm": pitch,
                "Latitude zone": lat,
                "Longitude zone": lon,
                "Phase": "Regional",
                "Peak_Brightness": peak,
                "Size_px": size,
                "Flash_Count": count,
                "Total_Brightness": round(total_b, 3),
                "Activity_Level": round(count / max_cell, 4),
                "Global_Activity": round(global_counts[w] / max_global, 4),
            })
            next_event_id += 1

output_records.extend(regional_rows)
output_records.sort(key=lambda r: (r["Timestamp"], r["Event ID"]))


# ==========================================
# 7. EXPORT
# ==========================================

csv_columns = [
    "Timestamp", "Event ID", "X", "Y", "X_norm", "Y_norm", "Pan",
    "Pitch_Norm", "Latitude zone", "Longitude zone", "Phase",
    "Duration_sec", "Peak_Brightness", "Mean_Brightness", "Size_px",
    "Flash_Count", "Total_Brightness", "Activity_Level", "Global_Activity",
]

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns)
    writer.writeheader()
    writer.writerows(output_records)


# ==========================================
# 8. SUMMARY
# ==========================================

individual = sum(1 for r in output_records if r["Phase"] == "Individual")
regional = sum(1 for r in output_records if r["Phase"] == "Regional")
active_cells = sum(1 for r in regional_rows if r["Flash_Count"] > 0)

print("\n========== PROCESSING COMPLETE ==========")
print(f"Individual lightning events: {individual}")
print(f"Regional rows: {regional} ({active_cells} with activity)")
print(f"Phase 3 flashes counted: {len(regional_events)}")
print(f"Total CSV records: {len(output_records)}")
print(f"\nCSV saved to: {os.path.abspath(output_file)}")
