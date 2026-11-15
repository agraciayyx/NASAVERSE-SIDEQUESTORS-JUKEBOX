
import cv2
import numpy as np
import csv
import os

# ==========================================
# 1. SETTINGS
# ==========================================

video_path = "iss_lightning_sphere_07312023_60p4k.mp4"

# HSV range for yellow/orange-yellow lightning
LOWER_YELLOW = np.array([15, 100, 150])
UPPER_YELLOW = np.array([40, 255, 255])

MIN_AREA = 2

# Individual event tracking settings
MAX_DISTANCE = 30
MAX_GAP_FRAMES = 3

# Phase boundaries (seconds)
PHASE_2_START = 20
PHASE_3_START = 70

# Output
output_file = "lightning_master_dataset.csv"


# ==========================================
# 2. LIGHTNING DETECTION FUNCTION
# ==========================================

def detect_lightning(frame):

    # Convert BGR image to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Detect yellow/orange-yellow pixels
    mask = cv2.inRange(
        hsv,
        LOWER_YELLOW,
        UPPER_YELLOW
    )

    # Remove small noise
    kernel = np.ones((3, 3), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    # Merge nearby bright regions
    mask = cv2.dilate(
        mask,
        kernel,
        iterations=1
    )

    # Identify connected regions
    num_labels, labels, stats, centroids = (
        cv2.connectedComponentsWithStats(mask)
    )

    detections = []

    for i in range(1, num_labels):

        x, y = centroids[i]

        area = stats[i, cv2.CC_STAT_AREA]

        if area >= MIN_AREA:

            detections.append({
                "x": float(x),
                "y": float(y),
                "area": int(area)
            })

    return detections


# ==========================================
# 3. INDIVIDUAL EVENT FINALISATION
# ==========================================

def finalise_event(event, output_records):

    # Calculate average event position
    avg_x = np.mean(event["x_positions"])
    avg_y = np.mean(event["y_positions"])

    # Classify vertical screen position
    if avg_y < frame_height / 3:
        latitude_zone = "Northern"

    elif avg_y < 2 * frame_height / 3:
        latitude_zone = "Equatorial"

    else:
        latitude_zone = "Southern"

    # Save one row per individual lightning event
    output_records.append({

        "Timestamp": round(
            event["start_timestamp"], 3
        ),

        "Event ID": event["event_id"],

        "X": round(avg_x, 2),

        "Y": round(avg_y, 2),

        "Latitude zone": latitude_zone,

        "Phase": "Individual"
    })


# ==========================================
# 4. LOAD VIDEO
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

frame_number = 0

# Store CSV records
output_records = []

# Store active individual lightning events
active_events = []

# Unique ID counter
next_event_id = 1

# Track whether Phase 2 events have been finalised
phase_2_finalised = False


# ==========================================
# 5. PROCESS VIDEO
# ==========================================

while True:

    success, frame = cap.read()

    if not success:
        break

    timestamp = frame_number / FPS

    # ======================================
    # PHASE 1: 0-20 SECONDS
    # No event recording
    # ======================================

    if timestamp < PHASE_2_START:

        frame_number += 1
        continue


    # ======================================
    # PHASE 2: 20-70 SECONDS
    # INDIVIDUAL LIGHTNING DETECTION
    # Analyse EVERY frame
    # ======================================

    if timestamp < PHASE_3_START:

        detections = detect_lightning(frame)

        # Remove expired events before matching
        remaining_events = []

        for event in active_events:

            gap = frame_number - event["last_frame"]

            if gap > MAX_GAP_FRAMES:

                finalise_event(
                    event,
                    output_records
                )

            else:

                remaining_events.append(event)

        active_events = remaining_events

        # Track detections against existing events
        matched_events = set()

        for detection in detections:

            best_event = None
            best_distance = MAX_DISTANCE

            for event in active_events:

                if event["event_id"] in matched_events:
                    continue

                dx = detection["x"] - event["last_x"]
                dy = detection["y"] - event["last_y"]

                distance = np.sqrt(dx**2 + dy**2)

                if distance <= best_distance:

                    best_distance = distance
                    best_event = event

            # ----------------------------------
            # UPDATE EXISTING LIGHTNING EVENT
            # ----------------------------------

            if best_event is not None:

                best_event["last_frame"] = frame_number

                best_event["last_x"] = detection["x"]
                best_event["last_y"] = detection["y"]

                best_event["x_positions"].append(
                    detection["x"]
                )

                best_event["y_positions"].append(
                    detection["y"]
                )

                matched_events.add(
                    best_event["event_id"]
                )

            # ----------------------------------
            # CREATE NEW LIGHTNING EVENT
            # ----------------------------------

            else:

                new_event = {

                    "event_id": next_event_id,

                    "start_timestamp": timestamp,

                    "last_frame": frame_number,

                    "last_x": detection["x"],
                    "last_y": detection["y"],

                    "x_positions": [
                        detection["x"]
                    ],

                    "y_positions": [
                        detection["y"]
                    ]
                }

                active_events.append(new_event)

                matched_events.add(next_event_id)

                next_event_id += 1


    # ======================================
    # PHASE 3: 70 SECONDS ONWARDS
    # REGIONAL LIGHTNING DETECTION
    # Analyse 5 frames per second
    # ======================================

    else:

        # Finalise all individual events from Phase 2
        if not phase_2_finalised:

            for event in active_events:

                finalise_event(
                    event,
                    output_records
                )

            active_events = []

            phase_2_finalised = True

        # Sample every 6 frames (5 FPS)
        if frame_number % 6 != 0:

            frame_number += 1
            continue

        detections = detect_lightning(frame)

        # Group detections by vertical screen zone
        zones = {

            "Northern": [],
            "Equatorial": [],
            "Southern": []
        }

        for detection in detections:

            y = detection["y"]

            if y < frame_height / 3:

                zone = "Northern"

            elif y < 2 * frame_height / 3:

                zone = "Equatorial"

            else:

                zone = "Southern"

            zones[zone].append(detection)

        # Record regional activity per active zone
        for zone, zone_detections in zones.items():

            if len(zone_detections) == 0:
                continue

            avg_x = np.mean([
                d["x"] for d in zone_detections
            ])

            avg_y = np.mean([
                d["y"] for d in zone_detections
            ])

            output_records.append({

                "Timestamp": round(timestamp, 3),

                "Event ID": next_event_id,

                "X": round(avg_x, 2),

                "Y": round(avg_y, 2),

                "Latitude zone": zone,

                "Phase": "Regional"
            })

            next_event_id += 1


    # ======================================
    # PROGRESS TRACKING
    # ======================================

    if frame_number % 100 == 0:

        progress = (
            frame_number / total_frames
        ) * 100

        print(
            f"Processing: {frame_number}/{total_frames} "
            f"({progress:.1f}%)"
        )

    frame_number += 1


# ==========================================
# 6. FINALISE REMAINING INDIVIDUAL EVENTS
# ==========================================

for event in active_events:

    finalise_event(
        event,
        output_records
    )

cap.release()


# ==========================================
# 7. EXPORT MASTER DATASET TO CSV
# ==========================================

csv_columns = [

    "Timestamp",
    "Event ID",
    "X",
    "Y",
    "Latitude zone",
    "Phase"
]

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

    writer.writerows(output_records)


# ==========================================
# 8. PROCESSING SUMMARY
# ==========================================

individual_count = sum(
    1 for row in output_records
    if row["Phase"] == "Individual"
)

regional_count = sum(
    1 for row in output_records
    if row["Phase"] == "Regional"
)

print("\n========== PROCESSING COMPLETE ==========")

print(f"Total video frames: {total_frames}")

print(f"Individual lightning events: {individual_count}")

print(f"Regional activity records: {regional_count}")

print(f"Total CSV records: {len(output_records)}")

print(
    f"\nCSV saved to: {os.path.abspath(output_file)}"
)
