# Test: Extract a sample frame at 30 seconds
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

video_path = "iss_lightning_sphere_07312023_60p4k.mp4"

cap = cv2.VideoCapture(video_path)

cap.set(cv2.CAP_PROP_POS_MSEC, 30000)

success, frame = cap.read()
cap.release()

# Create folder if it doesn't already exist
output_folder = "test_extracted_frames"
os.makedirs(output_folder, exist_ok=True)

if success:
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    output_path = os.path.join(output_folder, "frame_30s.jpg")
    cv2.imwrite(output_path, frame)
    print("Frame saved to:", output_path)

    plt.figure(figsize=(12, 7))
    plt.imshow(frame_rgb)
    plt.title("NASA Lightning Visualisation - 30 Seconds")
    plt.axis("off")
    plt.show()
else:
    print("Could not read frame")


# Test: Detect the lightning visually
import cv2
import numpy as np
import matplotlib.pyplot as plt

frame = cv2.imread("test_extracted_frames/frame_30s.jpg")
if frame is None:
    raise FileNotFoundError("Frame not found. Check your file path.")

frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Identify pixels with brightness above 200
threshold = 200

# Detect bright pixels
_, bright_mask = cv2.threshold(
    gray,
    threshold,
    255,
    cv2.THRESH_BINARY
)

# Display results
plt.figure(figsize=(14, 6))

plt.subplot(1, 2, 1)
plt.imshow(frame_rgb)
plt.title("Original Frame")
plt.axis("off")

plt.subplot(1, 2, 2)
plt.imshow(bright_mask, cmap="gray")
plt.title("Detected Bright Pixels")
plt.axis("off")

plt.tight_layout()
plt.show()



# # ==========================================
# # TEST: EXTRACT ONE SAMPLE FRAME
# # ==========================================

# import cv2
# import numpy as np
# import csv
# import os

# # ==========================================
# # SETTINGS - frames per second, brightness threshold (detect lightning)
# # ==========================================
# video_path = "iss_lightning_sphere_07312023_60p4k.mp4"

# FPS = 30
# THRESHOLD = 200
# MIN_AREA = 2

# ## Adjust the values to pick up the lightning color more accurately.
# LOWER_YELLOW = np.array([15, 100, 150])   # H, S, V minimums
# UPPER_YELLOW = np.array([40, 255, 255])   # H, S, V maximums
# MIN_AREA = 2

# # Phase 2 event tracking
# MAX_DISTANCE = 30
# MAX_GAP_FRAMES = 3


# # ==========================================
# # LOAD VIDEO
# # ==========================================

# cap = cv2.VideoCapture(video_path)

# fps = cap.get(cv2.CAP_PROP_FPS)
# total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# print("FPS:", fps)
# print("Total frames:", total_frames)
# print("Duration:", total_frames / fps, "seconds")

# sample_time = 30  # seconds

# # Move video to the selected timestamp
# cap.set(cv2.CAP_PROP_POS_MSEC, sample_time * 1000)

# success, frame = cap.read()

# if success:

#     print("Sample frame extracted successfully!")

#     # Save original frame
#     cv2.imwrite("sample_frame.jpg", frame)

# else:

#     print("Unable to extract sample frame.")


# def detect_lightning(frame):

#     hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

#     # Keep only yellow-ish, saturated, bright pixels
#     mask = cv2.inRange(hsv, LOWER_YELLOW, UPPER_YELLOW)

#     # Optional: remove single-pixel noise and merge nearby glow pixels
#     kernel = np.ones((3, 3), np.uint8)
#     mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
#     mask = cv2.dilate(mask, kernel, iterations=1)

#     num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)

#     detections = []

#     for i in range(1, num_labels):
#         x, y = centroids[i]
#         area = stats[i, cv2.CC_STAT_AREA]

#         if area >= MIN_AREA:
#             detections.append({
#                 "x": float(x),
#                 "y": float(y),
#                 "area": int(area)
#             })

#     return detections
# # ==========================================
# # TEST: DETECT LIGHTNING
# # ==========================================

# if success:

#     detections = detect_lightning(frame)

#     print("\nLightning detections:", len(detections))

#     for i, detection in enumerate(detections):

#         print(f"Lightning {i+1}:")
#         print("X:", detection["x"])
#         print("Y:", detection["y"])
#         print("Area:", detection["area"])