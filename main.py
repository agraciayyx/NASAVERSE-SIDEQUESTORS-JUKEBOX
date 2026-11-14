# Earth Jukebox: turns NASA GISTEMP zonal temperatures into a 30 s soundtrack
# for the SVS 5209 video (https://svs.gsfc.nasa.gov/5209).

# - 8 latitude bands -> 8 notes on the A minor pentatonic scale (warmer = higher)
# - global temperature -> heartbeat, brighter tone, volume swell, drone

# tweak the settings then run >  python main.py > to get output at output/zonal_pentatonic.wav


import csv
import math
import os
import struct
import wave

CSV_PATH = "data/gistemp_zonal.csv"
OUT_WAV = "output/zonal_pentatonic.wav"
BANDS = ["64N-90N", "44N-64N", "24N-44N", "EQU-24N", "24S-EQU", "44S-24S", "64S-44S", "90S-64S"]

# video timing
FIRST_YEAR, LAST_YEAR = 1880, 2023
LAST_YEAR_AT = 28.0        # seconds when 2023 appears
VIDEO_LENGTH = 30.0        # seconds
SECONDS_PER_YEAR = LAST_YEAR_AT / (LAST_YEAR - FIRST_YEAR)
SAMPLE_RATE = 44100

# A minor pentatonic, A2 to A5 (MIDI note numbers)
SCALE = [45 + step + 12 * octave for octave in range(3) for step in [0, 3, 5, 7, 10]] + [81]

# settings
NOTE_VOLUME = 0.15
DEAD_ZONE = 0.3            # higher = band notes change less often

WARMTH_SMOOTH_YEARS = 5    # average temperature over this many years
WARMTH_CURVE = 1.5         # >1 = intensity builds later, <1 = earlier

HEARTBEAT_BPM = (55, 140)        # (coolest, warmest)
HEARTBEAT_VOLUME = (0.10, 0.55)  # (coolest, warmest)
BRIGHTNESS = 1.0                 # how harsh the notes get by 2023 (0 = never)
SWELL = (0.55, 1.0)              # note volume multiplier (coolest, warmest)
DRONE_STARTS_AT = 0.3            # deg C global anomaly when the drone fades in
DRONE_VOLUME = 0.22


def blend(pair, x):
    # Go from pair[0] (x=0) to pair[1] (x=1).
    return pair[0] + (pair[1] - pair[0]) * x


def load_data():
    bands, glob = [], []
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if FIRST_YEAR <= int(row["Year"]) <= LAST_YEAR:
                bands.append([float(row[b]) for b in BANDS])
                glob.append(float(row["Glob"]))
    return bands, glob

# build intensity but gradually, so the music doesn't jump around too much
def smooth(values, size):
    half = size // 2
    result = []
    for i in range(len(values)):
        window = values[max(0, i - half): i + half + 1]
        result.append(sum(window) / len(window))
    return result

# smoothed global anomaly (deg C) at time t seconds in the video.
def global_temp_at(t, glob):
    year_index = min(int(t / SECONDS_PER_YEAR), len(glob) - 1)
    return glob[year_index]

# 0 = coolest point in the video, 1 = warmest
def warmth_at(t, glob):
    x = (global_temp_at(t, glob) - min(glob)) / (max(glob) - min(glob))
    return x ** WARMTH_CURVE

# map one band yearly value to scale steps - only change note when past deadzone 
def to_note_steps(values, low, high):
    steps = []
    current = round((values[0] - low) / (high - low) * (len(SCALE) - 1))
    for v in values:
        position = (v - low) / (high - low) * (len(SCALE) - 1)
        if abs(position - current) > 0.5 + DEAD_ZONE:
            current = round(position)
        steps.append(current)
    return steps



def add_note(left, right, midi, start, length, volume, pan, brightness):
    freq = 440 * 2 ** ((midi - 69) / 12)
    first = int(start * SAMPLE_RATE)
    hold = int(length * SAMPLE_RATE)
    release = int(0.25 * SAMPLE_RATE)
    for i in range(min(hold + release, len(left) - first)):
        t = i / SAMPLE_RATE
        env = min(1, t / 0.01) * (0.3 + 0.7 * math.exp(-t / 0.4))
        if i > hold:
            env *= 1 - (i - hold) / release
        w = 2 * math.pi * freq * t
        tone = math.sin(w) + 0.3 * math.sin(2 * w) + brightness * (0.35 * math.sin(3 * w) + 0.25 * math.sin(4 * w))
        s = tone * env * volume / (1.3 + 0.6 * brightness)
        left[first + i] += s * (1 - pan)
        right[first + i] += s * pan

# more warm = faster heartbeat, louder, more intense
def add_heartbeat(left, right, glob):
    t = 0.0
    while t < VIDEO_LENGTH - 0.3:
        w = warmth_at(t, glob)
        volume = blend(HEARTBEAT_VOLUME, w)
        for offset, strength in [(0.0, 1.0), (0.14, 0.6)]:      # lub, dub
            first = int((t + offset) * SAMPLE_RATE)
            for i in range(int(0.18 * SAMPLE_RATE)):
                x = i / SAMPLE_RATE
                pitch = 55 * (1 + 1.5 * math.exp(-x / 0.02))
                s = math.sin(2 * math.pi * pitch * x) * math.exp(-x / 0.05) * volume * strength
                left[first + i] += s
                right[first + i] += s
        t += 60 / blend(HEARTBEAT_BPM, w)

# low wobbly hum that fades in once the global anomaly passes DRONE_STARTS_AT
def add_drone(left, right, glob):
    for i in range(len(left)):
        t = i / SAMPLE_RATE
        temp = global_temp_at(t, glob)
        if temp > DRONE_STARTS_AT:
            level = DRONE_VOLUME * (temp - DRONE_STARTS_AT) / (max(glob) - DRONE_STARTS_AT)
            s = (math.sin(2 * math.pi * 55 * t) + 0.6 * math.sin(2 * math.pi * 55.8 * t)) / 1.6
            left[i] += s * level
            right[i] += s * level


def write_wav(left, right):
    os.makedirs("output", exist_ok=True)
    peak = max(max(map(abs, left)), max(map(abs, right)))
    with wave.open(OUT_WAV, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        for l, r in zip(left, right):
            f.writeframes(struct.pack("<hh", int(l / peak * 29000), int(r / peak * 29000)))


def main():
    bands, glob = load_data()
    glob = smooth(glob, WARMTH_SMOOTH_YEARS)
    low = min(min(year) for year in bands)
    high = max(max(year) for year in bands)

    total = int(VIDEO_LENGTH * SAMPLE_RATE)
    left, right = [0.0] * total, [0.0] * total

    # 8 band notes: strike a note only when the band's pitch changes
    for b in range(len(BANDS)):
        steps = to_note_steps([year[b] for year in bands], low, high)
        pan = 0.1 + 0.8 * b / (len(BANDS) - 1)              # Arctic left, Antarctic right
        i = 0
        while i < len(steps):
            j = i
            while j + 1 < len(steps) and steps[j + 1] == steps[i]:
                j += 1
            start = i * SECONDS_PER_YEAR
            end = (j + 1) * SECONDS_PER_YEAR if j + 1 < len(steps) else VIDEO_LENGTH
            w = warmth_at(start, glob)
            add_note(left, right, SCALE[steps[i]], start, end - start,
                     NOTE_VOLUME * blend(SWELL, w), pan, BRIGHTNESS * w)
            i = j + 1

    add_heartbeat(left, right, glob)
    add_drone(left, right, glob)

    # fade out over the last second
    for i in range(SAMPLE_RATE):
        left[total - SAMPLE_RATE + i] *= 1 - i / SAMPLE_RATE
        right[total - SAMPLE_RATE + i] *= 1 - i / SAMPLE_RATE

    write_wav(left, right)
    print("Wrote", OUT_WAV)


if __name__ == "__main__":
    main()
