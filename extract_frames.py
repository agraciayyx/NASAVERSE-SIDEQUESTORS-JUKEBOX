
import cv2
import numpy as np
import csv
import os
import math

# ==========================================
# 1. SETTINGS
# ==========================================

video_path = "iss_lightning_sphere_07312023_60p4k.mp4"
output_file = "lightning_dataset.csv"

# Image processing resolution
PROCESS_WIDTH = 960

# Lightning colour range
LOWER_YELLOW = np.array([15, 100, 150])
UPPER_YELLOW = np.array([40, 255, 255])

# Minimum connected region size (at resized resolution)
MIN_AREA = 4

# Tracking settings (at resized resolution)
MAX_DISTANCE = 15
MEMORY_SECONDS = 0.5

# Phase boundaries
PHASE_2_START = 20
PHASE_3_START = 70

# Sampling
PHASE_2_FPS = 30
PHASE_3_FPS = 5

# Periodic saving
SAVE_INTERVAL = 5


# ==========================================
# 2. LIGHTNING DETECTION
# ==========================================

def detect_lightning(frame):

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(
        hsv,
        LOWER_YELLOW,
        UPPER_YELLOW
    )

    kernel = np.ones((3, 3), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.dilate(
        mask,
        kernel,
        iterations=1
    )

    num_labels, labels, stats, centroids = (
        cv2.connectedComponentsWithStats(mask)
    )

    detections = []

    for i in range(1, num_labels):

        area = stats[i, cv2.CC_STAT_AREA]

        if area < MIN_AREA:
            continue

        x, y = centroids[i]

        detections.append({
            "x": float(x),
            "y": float(y),
            "area": int(area)
        })

    return detections


# ==========================================
# 3. CLASSIFY LATITUDE ZONE
# ==========================================

def get_latitude_zone(y, height):

    if y < height / 3:
        return "Northern"

    elif y < 2 * height / 3:
        return "Equatorial"

    return "Southern"


# ==========================================
# 4. SAVE CSV
# ==========================================

csv_columns = [
    "Timestamp",
    "Event ID",
    "X",
    "Y",
    "Pan",
    "Latitude zone",
    "Phase",
    "Detection Count"
]


def save_csv(records):

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=csv_columns
        )

        writer.writeheader()
        writer.writerows(records)


# ==========================================
# 5. LOAD VIDEO
# ==========================================

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    raise FileNotFoundError(
        f"Unable to open video: {video_path}"
    )

FPS = cap.get(cv2.CAP_PROP_FPS)

total_frames = int(
    cap.get(cv2.CAP_PROP_FRAME_COUNT)
)

frame_width = int(
    cap.get(cv2.CAP_PROP_FRAME_WIDTH)
)

frame_height = int(
    cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
)

# Calculate resized dimensions
scale = PROCESS_WIDTH / frame_width

process_height = int(
    frame_height * scale
)

print("========== VIDEO INFORMATION ==========")
print(f"Original resolution: {frame_width} x {frame_height}")
print(f"Processing resolution: {PROCESS_WIDTH} x {process_height}")
print(f"Original FPS: {FPS}")
print(f"Video duration: {total_frames / FPS:.2f} seconds")


# ==========================================
# 6. SAMPLING INTERVALS
# ==========================================

PHASE_2_STEP = max(
    1,
    round(FPS / PHASE_2_FPS)
)

PHASE_3_STEP = max(
    1,
    round(FPS / PHASE_3_FPS)
)

print(f"Phase 2 sampling: every {PHASE_2_STEP} frames")
print(f"Phase 3 sampling: every {PHASE_3_STEP} frames")


# ==========================================
# 7. INITIALISE DATA
# ==========================================

frame_number = 0

output_records = []

next_event_id = 1

# Recent lightning positions
recent_tracks = []

next_save_time = PHASE_2_START + SAVE_INTERVAL
next_progress_time = 10

# Convert original coordinates back from resized image
x_scale = frame_width / PROCESS_WIDTH
y_scale = frame_height / process_height


# ==========================================
# 8. PROCESS VIDEO
# ==========================================

try:

    while True:

        success, frame = cap.read()

        if not success:
            break

        timestamp = frame_number / FPS

        # ----------------------------------
        # PHASE 1: 0-20 SECONDS
        # ----------------------------------

        if timestamp < PHASE_2_START:

            frame_number += 1
            continue


        # ==================================
        # PHASE 2: 20-70 SECONDS
        # INDIVIDUAL LIGHTNING
        # ==================================

        if timestamp < PHASE_3_START:

            # Process approximately 30 FPS
            if frame_number % PHASE_2_STEP != 0:

                frame_number += 1
                continue

            # Resize before image processing
            small_frame = cv2.resize(
                frame,
                (PROCESS_WIDTH, process_height),
                interpolation=cv2.INTER_AREA
            )

            detections = detect_lightning(small_frame)

            # Remove old position memories
            recent_tracks = [
                track for track in recent_tracks
                if timestamp - track["last_seen"] <= MEMORY_SECONDS
            ]

            # Find possible matches
            possible_matches = []

            for track_index, track in enumerate(recent_tracks):

                for detection_index, detection in enumerate(detections):

                    distance = math.hypot(
                        detection["x"] - track["x"],
                        detection["y"] - track["y"]
                    )

                    if distance <= MAX_DISTANCE:

                        possible_matches.append((
                            distance,
                            track_index,
                            detection_index
                        ))

            # Match closest pairs first
            possible_matches.sort(key=lambda x: x[0])

            matched_tracks = set()
            matched_detections = set()

            for distance, track_index, detection_index in possible_matches:

                if track_index in matched_tracks:
                    continue

                if detection_index in matched_detections:
                    continue

                track = recent_tracks[track_index]
                detection = detections[detection_index]

                # Update existing lightning position
                track["x"] = detection["x"]
                track["y"] = detection["y"]
                track["last_seen"] = timestamp

                matched_tracks.add(track_index)
                matched_detections.add(detection_index)

            # Unmatched detections = new appearances
            for detection_index, detection in enumerate(detections):

                if detection_index in matched_detections:
                    continue

                x_original = detection["x"] * x_scale
                y_original = detection["y"] * y_scale

                pan = (
                    detection["x"] / (PROCESS_WIDTH - 1)
                ) * 2 - 1

                latitude_zone = get_latitude_zone(
                    detection["y"],
                    process_height
                )

                output_records.append({

                    "Timestamp": round(timestamp, 3),

                    "Event ID": next_event_id,

                    "X": round(x_original, 2),

                    "Y": round(y_original, 2),

                    "Pan": round(pan, 3),

                    "Latitude zone": latitude_zone,

                    "Phase": "Individual",

                    "Detection Count": 1
                })

                # Remember this new flash
                recent_tracks.append({

                    "event_id": next_event_id,

                    "x": detection["x"],
                    "y": detection["y"],

                    "last_seen": timestamp
                })

                next_event_id += 1


        # ==================================
        # PHASE 3: 70 SECONDS ONWARDS
        # REGIONAL LIGHTNING ACTIVITY
        # ==================================

        else:

            # Process approximately 5 FPS
            if frame_number % PHASE_3_STEP != 0:

                frame_number += 1
                continue

            small_frame = cv2.resize(
                frame,
                (PROCESS_WIDTH, process_height),
                interpolation=cv2.INTER_AREA
            )

            detections = detect_lightning(small_frame)

            zones = {
                "Northern": [],
                "Equatorial": [],
                "Southern": []
            }

            for detection in detections:

                zone = get_latitude_zone(
                    detection["y"],
                    process_height
                )

                zones[zone].append(detection)

            # Record regional activity
            for zone, zone_detections in zones.items():

                if not zone_detections:
                    continue

                avg_x = np.mean([
                    d["x"] for d in zone_detections
                ])

                avg_y = np.mean([
                    d["y"] for d in zone_detections
                ])

                output_records.append({

                    "Timestamp": round(timestamp, 3),

                    "Event ID": "",

                    "X": round(avg_x * x_scale, 2),

                    "Y": round(avg_y * y_scale, 2),

                    "Pan": round(
                        (avg_x / (PROCESS_WIDTH - 1)) * 2 - 1,
                        3
                    ),

                    "Latitude zone": zone,

                    "Phase": "Regional",

                    "Detection Count": len(zone_detections)
                })


        # ==================================
        # 9. PERIODIC SAVING
        # ==================================

        if timestamp >= next_save_time:

            save_csv(output_records)

            print(
                f"Saved checkpoint at {timestamp:.1f}s | "
                f"Individual events: "
                f"{sum(r['Phase'] == 'Individual' for r in output_records)}"
            )

            next_save_time += SAVE_INTERVAL


        # ==================================
        # 10. PROGRESS
        # ==================================

        if timestamp >= next_progress_time:

            progress = (
                frame_number / total_frames
            ) * 100

            individual_count = sum(
                r["Phase"] == "Individual"
                for r in output_records
            )

            regional_count = sum(
                r["Phase"] == "Regional"
                for r in output_records
            )

            print(
                f"Processing: {timestamp:.1f}s | "
                f"{progress:.1f}% | "
                f"Individual events: {individual_count} | "
                f"Regional records: {regional_count}"
            )

            next_progress_time += 10

        frame_number += 1


except KeyboardInterrupt:

    print("\nProcessing interrupted by user.")
    print("Saving collected data...")


finally:

    cap.release()

    # Always save collected records
    save_csv(output_records)


# ==========================================
# 11. PROCESSING SUMMARY
# ==========================================

individual_count = sum(
    r["Phase"] == "Individual"
    for r in output_records
)

regional_count = sum(
    r["Phase"] == "Regional"
    for r in output_records
)

print("\n========== PROCESSING COMPLETE ==========")

print(f"Total video frames: {total_frames}")

print(f"Individual lightning events: {individual_count}")

print(f"Regional activity records: {regional_count}")

print(f"Total CSV records: {len(output_records)}")

print(f"\nCSV saved to: {os.path.abspath(output_file)}")
