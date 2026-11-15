import cv2
import os
import numpy as np
import matplotlib.pyplot as plt

## Step 1: Extract frames at regular intervals of 1 second
video_path = "iss_lightning_sphere_07312023_60p4k.mp4"
cap = cv2.VideoCapture(video_path)

# Retrieve video information
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
duration = total_frames / fps

print("FPS:", fps)
print("Duration:", duration, "seconds")

# Create folder to store extracted frames
os.makedirs("extracted_frames", exist_ok=True)

for second in range(0, int(duration), 1):
    cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)

    success, frame = cap.read()

    if success:
        cv2.imwrite(
            f"extracted_frames/frame_{second}.jpg",
            frame
        )

cap.release()

print("Step 3 completed: Frames extracted!")


# # ==========================================
# # STEP 4: DETECT BRIGHT LIGHTNING PIXELS
# # ==========================================

# # Load one extracted frame
# frame = cv2.imread("extracted_frames/frame_10.jpg")

# if frame is None:
#     raise FileNotFoundError("Frame not found. Check your video path and extraction.")

# # Convert image to grayscale
# gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# # Set brightness threshold
# threshold = 200

# # Identify bright pixels
# _, mask = cv2.threshold(
#     gray,
#     threshold,
#     255,
#     cv2.THRESH_BINARY
# )

# # Display original frame and detected pixels
# plt.figure(figsize=(12, 5))

# plt.subplot(1, 2, 1)
# plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
# plt.title("Original Frame")

# plt.subplot(1, 2, 2)
# plt.imshow(mask, cmap="gray")
# plt.title("Bright Pixel Detection")

# plt.show()

# print("Step 4 completed: Bright pixels detected!")


# # ==========================================
# # STEP 5: EXTRACT POSITIONS OF DETECTED EVENTS
# # ==========================================

# # Find connected bright regions
# num_labels, labels, stats, centroids = (
#     cv2.connectedComponentsWithStats(mask)
# )

# events = []

# # Loop through detected regions
# for i in range(1, num_labels):

#     x, y = centroids[i]

#     area = stats[i, cv2.CC_STAT_AREA]

#     # Ignore tiny bright regions
#     if area >= 2:

#         events.append({
#             "x": round(x, 2),
#             "y": round(y, 2),
#             "area": area
#         })

# # Display detected events
# print("\nDetected regions:", len(events))

# for event in events[:10]:
#     print(event)

# print("\nStep 5 completed: Coordinates extracted!")
