
import os
import cv2
import pandas as pd
import numpy as np
import soundfile as sf

from scipy.signal import butter, sosfilt


# ==========================================================
# 1. SETTINGS
# ==========================================================

# Paths are relative to this script: lightning/main/ -> lightning/data, lightning/output
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_PATH = os.path.join(BASE_DIR, "..", "data", "lightning_dataset.csv")

VIDEO_PATH = os.path.join(BASE_DIR, "..", "data", "iss_lightning_sphere_07312023_60p4k.mp4")

OUTPUT_PATH = os.path.join(BASE_DIR, "..", "output", "final_soundscape.wav")

SR = 44100

PHASE_1_END = 20.0
PHASE_2_END = 70.0

RISER_DURATION = 4.0
DROP_DURATION = 4.0

RNG = np.random.default_rng(42)


# ==========================================================
# 2. GET ORIGINAL VIDEO DURATION
# ==========================================================

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise FileNotFoundError(
        f"Cannot open video: {VIDEO_PATH}"
    )

fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

if fps <= 0 or frame_count <= 0:
    cap.release()
    raise ValueError("Unable to determine video duration.")

VIDEO_DURATION = frame_count / fps

cap.release()

print(f"Video duration: {VIDEO_DURATION:.2f} seconds")

if VIDEO_DURATION <= PHASE_2_END + RISER_DURATION + DROP_DURATION:
    raise ValueError(
        "Video must be longer than 78 seconds "
        "to accommodate the planned phases."
    )

# # Final 8 seconds are reserved for the cinematic ending
# RISER_START = VIDEO_DURATION - RISER_DURATION - DROP_DURATION

# DROP_START = VIDEO_DURATION - DROP_DURATION

# STORM_END = RISER_START

# STORM_DURATION = STORM_END - PHASE_2_END

STORM_END = VIDEO_DURATION
STORM_DURATION = STORM_END - PHASE_2_END

print(f"Phase 1: 0 - {PHASE_1_END}s")
print(f"Phase 2: {PHASE_1_END} - {PHASE_2_END}s")
print(f"Phase 3: {PHASE_2_END} - {STORM_END:.2f}s")
# print(f"Riser: {RISER_START:.2f} - {DROP_START:.2f}s")
# print(f"Drop: {DROP_START:.2f} - {VIDEO_DURATION:.2f}s")



# ==========================================================
# 3. LOAD AND CLEAN CSV
# ==========================================================

df = pd.read_csv(CSV_PATH)

df.columns = (
    df.columns
    .str.replace("\ufeff", "", regex=False)
    .str.strip()
)

required_columns = [
    "Timestamp",
    "X",
    "Y",
    "Pan",
    "Latitude zone",
    "Phase",
    "Detection Count"
]

missing = [
    col for col in required_columns
    if col not in df.columns
]

if missing:
    raise ValueError(
        f"Missing CSV columns: {missing}\n"
        f"Available columns: {df.columns.tolist()}"
    )

# Convert numeric columns
for col in [
    "Timestamp",
    "X",
    "Y",
    "Pan",
    "Detection Count"
]:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

df = df.dropna(
    subset=[
        "Timestamp",
        "X",
        "Y",
        "Pan",
        "Latitude zone",
        "Phase"
    ]
)

# Keep timestamps within video duration
df = df[
    (df["Timestamp"] >= 0) &
    (df["Timestamp"] < VIDEO_DURATION)
].copy()

# Separate individual lightning and regional activity
individual_df = df[
    df["Phase"].str.strip().str.lower() == "individual"
].copy()

regional_df = df[
    df["Phase"].str.strip().str.lower() == "regional"
].copy()

# Derive pitch from vertical screen position.
# Upper screen = higher notes.
# Lower screen = lower notes.
individual_df["Pitch_Norm"] = (
    1 - individual_df["Y"] / frame_height
).clip(0, 1)

# Keep stereo panning within valid range
individual_df["Pan"] = individual_df["Pan"].clip(-1, 1)

# Keep regional activity counts non-negative
regional_df["Detection Count"] = (
    regional_df["Detection Count"].fillna(0).clip(lower=0)
)

individual_df = individual_df.sort_values(
    "Timestamp"
).reset_index(drop=True)

regional_df = regional_df.sort_values(
    "Timestamp"
).reset_index(drop=True)

print("\nCSV successfully loaded.")

print("Individual lightning events:", len(individual_df))
print("Regional activity records:", len(regional_df))

print("\nIndividual latitude distribution:")
print(individual_df["Latitude zone"].value_counts())



# ==========================================================
# 4. AUDIO MIXING FUNCTIONS
# ==========================================================

TOTAL_SAMPLES = int(VIDEO_DURATION * SR)

audio = np.zeros(
    (TOTAL_SAMPLES, 2),
    dtype=np.float32
)


def add_sound(sound, start_time, pan=0.0, volume=1.0):

    """Add a mono sound to the stereo timeline."""

    start = int(start_time * SR)

    if start >= TOTAL_SAMPLES or start < 0:
        return

    end = min(
        start + len(sound),
        TOTAL_SAMPLES
    )

    length = end - start

    if length <= 0:
        return

    pan = np.clip(pan, -1, 1)

    left_gain = np.sqrt((1 - pan) / 2)
    right_gain = np.sqrt((1 + pan) / 2)

    section = sound[:length] * volume

    audio[start:end, 0] += section * left_gain
    audio[start:end, 1] += section * right_gain


def filtered_noise(duration, low=None, high=None):

    """Generate filtered atmospheric noise."""

    samples = int(duration * SR)

    noise = RNG.normal(0, 1, samples)

    nyquist = SR / 2

    if low is not None and high is not None:

        sos = butter(
            4,
            [low / nyquist, high / nyquist],
            btype="bandpass",
            output="sos"
        )

    elif low is not None:

        sos = butter(
            4,
            low / nyquist,
            btype="highpass",
            output="sos"
        )

    else:

        sos = butter(
            4,
            high / nyquist,
            btype="lowpass",
            output="sos"
        )

    return sosfilt(
        sos,
        noise
    ).astype(np.float32)


def smooth_noise(n, div):

    """Generate slowly changing noise for ambience."""

    lr = RNG.standard_normal(n // div + 2)

    return np.interp(
        np.arange(n) / div,
        np.arange(len(lr)),
        lr
    ).astype(np.float32)


# ==========================================================
# 5. MUSICAL PITCH AND LATITUDE MAPPING
# ==========================================================

A_MINOR = [0, 2, 3, 5, 7, 8, 10]


def get_zone(latitude):

    latitude = str(latitude).strip().lower()

    if "north" in latitude:
        return "N"

    elif "south" in latitude:
        return "S"

    else:
        return "E"


def get_frequency(pitch_norm, latitude):

    """
    Map Pitch_Norm to an A minor scale.

    Latitude determines the instrument's octave.
    """

    zone = get_zone(latitude)

    pitch_norm = np.clip(
        float(pitch_norm),
        0,
        1
    )

    degree_index = int(
        round(
            pitch_norm * (len(A_MINOR) - 1)
        )
    )

    degree = A_MINOR[degree_index]

    if zone == "N":
        octave = 4

    elif zone == "E":
        octave = 2

    else:
        octave = 0.5

    return (
        220.0
        * octave
        * (2 ** (degree / 12))
    )


# ==========================================================
# 6. CLAUDE-INSPIRED MUSICAL INSTRUMENTS
# ==========================================================

def pluck(f, dur=1.0, harmonics=8, decay=5.0):

    """Warm plucked string sound."""

    t = np.arange(
        int(dur * SR)
    ) / SR

    out = np.zeros_like(t)

    for k in range(1, harmonics + 1):

        if f * k > 9000:
            break

        out += (
            np.sin(2 * np.pi * f * k * t)
            / k ** 1.1
            * np.exp(
                -t * decay * (1 + 0.6 * k)
            )
        )

    return (
        out * np.minimum(1, t / 0.002)
    ).astype(np.float32)


def glass(f, dur=1.6):

    """Celesta / glass-like instrument."""

    t = np.arange(
        int(dur * SR)
    ) / SR

    out = np.zeros_like(t)

    harmonics = [
        (1, 1, 2.5),
        (2.0, 0.5, 3.5),
        (2.76, 0.4, 4.5),
        (5.4, 0.2, 7),
        (8.9, 0.1, 9)
    ]

    for ratio, amplitude, decay in harmonics:

        if f * ratio < 12000:

            out += (
                amplitude
                * np.sin(
                    2 * np.pi * f * ratio * t
                )
                * np.exp(-t * decay)
            )

    return (
        out * np.minimum(1, t / 0.002)
    ).astype(np.float32)


def cello_pizz(f, dur=1.0):

    """Low cello-like pizzicato."""

    t = np.arange(
        int(dur * SR)
    ) / SR

    body = pluck(
        f,
        dur,
        harmonics=6,
        decay=3.5
    )

    thud = (
        np.sin(2 * np.pi * f * 0.5 * t)
        * np.exp(-t * 18)
        * 0.6
    )

    return (
        body + thud
    ).astype(np.float32)


def generate_lightning_crack(dur=0.07):

    """Short, soft electrical transient."""

    n = int(dur * SR)

    t = np.arange(n) / SR

    noise = np.tanh(
        np.diff(
            RNG.standard_normal(n + 1)
        ) * 1.5
    )

    return (
        noise * np.exp(-t * 100)
    ).astype(np.float32)


def generate_lightning_sound(latitude, pitch_norm):

    """Select an instrument based on latitude."""

    zone = get_zone(latitude)

    frequency = get_frequency(
        pitch_norm,
        latitude
    )

    if zone == "N":

        sound = glass(frequency)

    elif zone == "E":

        sound = pluck(
            frequency,
            dur=1.0,
            harmonics=8,
            decay=5.0
        )

    else:

        sound = cello_pizz(frequency)

    return sound


# ==========================================================
# 7. CINEMATIC STRING AND DRUM FUNCTIONS
# ==========================================================

def string_pad(
    freqs,
    dur,
    trem_hz=6.5,
    glide=0.0
):

    """Layered string pad with tremolo and detuning."""

    n = int(dur * SR)

    t = np.arange(n) / SR

    out = np.zeros(n)

    for f0 in freqs:

        for det in (-0.004, 0.0, 0.004):

            f = (
                f0
                * (1 + det)
                * (1 + glide * t / dur)
            )

            ph = (
                2 * np.pi
                * np.cumsum(f)
                / SR
            )

            for k in (1, 2, 3, 4):

                out += (
                    np.sin(ph * k)
                    / k ** 1.3
                )

    trem = (
        0.65
        + 0.35
        * np.sin(2 * np.pi * trem_hz * t)
    )

    return (
        out * trem * 0.04
    ).astype(np.float32)


def taiko(strength=1.0):

    """Generate a cinematic low Taiko drum."""

    t = np.arange(
        int(0.7 * SR)
    ) / SR

    f = (
        50
        + 70 * np.exp(-t * 30)
    )

    body = (
        np.sin(
            2 * np.pi * np.cumsum(f) / SR
        )
        * np.exp(-t * 6)
    )

    skin = (
        RNG.standard_normal(len(t))
        * np.exp(-t * 60)
        * 0.25
    )

    return (
        (body + skin) * strength
    ).astype(np.float32)


def generate_thunder(dur=3.0, strength=1.0):

    """Generate a distant, rolling thunder sound."""

    n = int(dur * SR)

    t = np.arange(n) / SR

    # Slowly changing low-frequency noise
    rumble = (
        smooth_noise(n, 90)
        + 0.6 * smooth_noise(n, 40)
    )

    envelope = (
        np.minimum(1, t / 0.15)
        * np.exp(-t * 2.2 / dur * 1.6)
    )

    return (
        rumble * envelope * strength
    ).astype(np.float32)



# ==========================================================
# 8. PHASE 1: THE PLANET (0–70 SECONDS)
# ==========================================================

print("\nGenerating Phase 1: The Planet...")

# Extend atmospheric ambience until 70 seconds
phase_duration = PHASE_2_END

t = np.arange(
    int(phase_duration * SR)
) / SR

# --------------------------------------
# A. Atmospheric fade envelope
# --------------------------------------

# Gradual fade-in during first 5 seconds
fade_in = np.clip(t / 5, 0, 1)

# Gradual fade-out from 65 to 70 seconds
fade_out = np.clip(
    (PHASE_2_END - t) / 5,
    0,
    1
)

ambient_envelope = fade_in * fade_out


# --------------------------------------
# B. Deep sub-bass drone
# --------------------------------------

sub_bass = (
    np.sin(2 * np.pi * 55 * t)
    + 0.6 * np.sin(2 * np.pi * 82.4 * t)
    + 0.4 * np.sin(2 * np.pi * 110 * t)
)

sub_bass *= (
    1 + 0.2 * np.sin(2 * np.pi * 0.08 * t)
)

sub_bass *= ambient_envelope

add_sound(
    sub_bass.astype(np.float32),
    0,
    pan=0,
    volume=0.10
)


# --------------------------------------
# C. Soft atmospheric wind
# --------------------------------------

wind = smooth_noise(
    len(t),
    120
)

wind *= ambient_envelope

add_sound(
    wind,
    0,
    pan=0,
    volume=0.04
)


# --------------------------------------
# D. High-frequency shimmer
# --------------------------------------

shimmer = np.zeros(len(t))

for f in (1320, 1760, 1975.5, 2637):

    shimmer += (
        np.sin(
            2 * np.pi * f * t
            + RNG.uniform(0, 6)
        )
        * (
            0.5
            + 0.5 * np.sin(
                2 * np.pi
                * RNG.uniform(0.05, 0.2)
                * t
                + RNG.uniform(0, 6)
            )
        )
    )

shimmer *= ambient_envelope

add_sound(
    shimmer.astype(np.float32),
    0,
    pan=0,
    volume=0.015
)


# --------------------------------------
# E. Slow planetary pulses
# --------------------------------------

# Subtle pulses every 8 seconds
pulse_times = np.arange(
    2,
    PHASE_2_END,
    8
)

for pulse_time in pulse_times:

    pulse_duration = 1.2

    pulse_samples = int(
        pulse_duration * SR
    )

    pulse_t = np.arange(
        pulse_samples
    ) / SR

    pulse = (
        np.sin(2 * np.pi * 55 * pulse_t)
        * np.exp(-2.5 * pulse_t)
    )

    # Follow the overall atmospheric fade
    pulse_fade = np.clip(
        (PHASE_2_END - pulse_time - pulse_t) / 5,
        0,
        1
    )

    pulse *= pulse_fade

    add_sound(
        pulse.astype(np.float32),
        pulse_time,
        pan=0,
        volume=0.07
    )

print("Atmospheric ambience generated: 0–70 seconds")


# ==========================================================
# 9. PHASE 2: INDIVIDUAL LIGHTNING (20–70 SECONDS)
# ==========================================================

print("\nGenerating Phase 2: Individual Lightning...")

phase2 = individual_df[
    (individual_df["Timestamp"] >= PHASE_1_END) &
    (individual_df["Timestamp"] < PHASE_2_END)
]

LIGHTNING_SOUND_DURATION = 0.5

for _, event in phase2.iterrows():

    timestamp = event["Timestamp"]

    latitude = event["Latitude zone"]

    pan = event["Pan"]

    pitch_norm = event["Pitch_Norm"]

    # Generate the selected musical instrument
    note = generate_lightning_sound(
        latitude,
        pitch_norm
    )

    # Ensure every lightning sound has the same duration
    note = note[:int(LIGHTNING_SOUND_DURATION * SR)].copy()

    fade_samples = min(
    int(0.04 * SR),
    len(note)
    )

    note[-fade_samples:] *= np.linspace(
        1,
        0,
        fade_samples
    )

    # Generate short electrical crack
    crack = generate_lightning_crack()

    add_sound(
        crack,
        timestamp,
        pan=pan,
        volume=0.025
    )

    # Musical note follows the crack slightly
    add_sound(
        note,
        timestamp + 0.035,
        pan=pan,
        volume=0.16
    )

print("Phase 2 individual lightning events:", len(phase2))


# ==========================================================
# 10. PHASE 3: THE STORM (70 SECONDS ONWARDS)
# ==========================================================

print("\nGenerating Phase 3: The Storm...")

storm_duration = STORM_DURATION

if storm_duration > 1:

    storm_samples = int(
        storm_duration * SR
    )

    storm_t = np.arange(
        storm_samples
    ) / SR


    # --------------------------------------
    # A. FIRST CINEMATIC STRING LAYER
    # --------------------------------------

    print("Generating first string layer...")

    sw = string_pad(
        [220, 261.63, 329.63, 440],
        storm_duration,
        trem_hz=6.5
    )

    swell = np.interp(
        np.arange(len(sw)) / SR,
        [
            0,
            storm_duration * 0.5,
            storm_duration
        ],
        [0, 0.5, 1.0]
    )

    add_sound(
        (sw * swell).astype(np.float32),
        PHASE_2_END,
        pan=-0.3,
        volume=1.0
    )


    # --------------------------------------
    # B. SECOND RISING STRING LAYER
    # --------------------------------------

    print("Generating second string layer...")

    sw2 = string_pad(
        [659.25, 783.99, 880],
        storm_duration,
        trem_hz=7.5,
        glide=0.35
    )

    sw2_envelope = np.interp(
        np.arange(len(sw2)) / SR,
        [
            0,
            storm_duration * 0.65,
            storm_duration
        ],
        [0, 0.6, 1.0]
    )

    add_sound(
        (sw2 * sw2_envelope).astype(np.float32),
        PHASE_2_END,
        pan=0.3,
        volume=0.8
    )


   
    # --------------------------------------
    # C. DATA-DRIVEN REGIONAL STORM ACTIVITY
    # --------------------------------------

    print("Calculating regional storm intensity...")

    storm_regions = regional_df[
        (regional_df["Timestamp"] >= PHASE_2_END) &
        (regional_df["Timestamp"] < STORM_END)
    ].copy()

    # Combine all three latitude zones into 1-second windows
    storm_regions["Activity Window"] = (
        np.floor(storm_regions["Timestamp"]).astype(int)
    )

    activity_by_second = (
        storm_regions.groupby("Activity Window")["Detection Count"]
        .sum()
        .to_dict()
    )

    # Normalise activity using the 90th percentile
    if activity_by_second:

        activity_reference = max(
            1,
            np.percentile(
                list(activity_by_second.values()),
                90
            )
        )

    else:

        activity_reference = 1

    print("Regional activity windows:", len(activity_by_second))



    
    # --------------------------------------
    # D. ACCELERATING DATA-DRIVEN TAIKO DRUMS
    # --------------------------------------

    print("Generating Taiko drums...")

    drum_time = PHASE_2_END

    interval = 1.2

    while drum_time < STORM_END:

        progress = (
            drum_time - PHASE_2_END
        ) / max(storm_duration, 1)

        # Look up regional activity around this drum hit
        activity_window = int(drum_time)

        detection_count = activity_by_second.get(
            activity_window,
            0
        )

        activity_level = min(
            detection_count / activity_reference,
            1.0
        )

        # Combine cinematic build-up with actual regional activity
        drum_strength = (
            0.23
            + 0.30 * progress
            + 0.27 * activity_level
        )
        # drum_strength = (
        #     0.35
        #     + 0.45 * progress
        #     + 0.40 * activity_level
        # )


        drum = taiko(
            strength=drum_strength
        )

        add_sound(
            drum,
            drum_time,
            pan=RNG.uniform(-0.15, 0.15),
            volume=0.65
            # volume = 0.9
        )

        # Gradually accelerate the rhythm
        interval = max(
            0.18,
            interval * 0.93
        )

        drum_time += interval


    # --------------------------------------
    # E. FIVE DISTANT THUNDER ROLLS
    # --------------------------------------

    print("Generating thunder rolls...")

    for i in range(5):

        thunder_position = (
            PHASE_2_END
            + storm_duration * (i + 1) / 6
        )

        thunder = generate_thunder(
            dur=3.5,
            strength=1.0
        )

        add_sound(
            thunder,
            thunder_position,
            pan=RNG.uniform(-0.4, 0.4),
            volume=0.18
        )

# ==========================================================
# GENTLE ENDING
# ==========================================================

fade_duration = 8.0
fade_start = max(0, VIDEO_DURATION - fade_duration)

fade_start_sample = int(fade_start * SR)
fade_end_sample = int(VIDEO_DURATION * SR)

fade_length = fade_end_sample - fade_start_sample

fade_curve = np.linspace(1.0, 0.0, fade_length)

audio[fade_start_sample:fade_end_sample] *= fade_curve[:, None]

# # ==========================================================
# # 11. PHASE 4: THE CINEMATIC RISER (FINAL 8 SECONDS)
# # ==========================================================

# print("\nGenerating the cinematic riser...")

# riser_duration = DROP_START - RISER_START

# riser_samples = int(
#     riser_duration * SR
# )

# riser_t = np.arange(
#     riser_samples
# ) / SR


# # --------------------------------------
# # A. Rising noise sweep
# # --------------------------------------

# riser_noise = filtered_noise(
#     riser_duration,
#     low=500,
#     high=10000
# )

# riser_envelope = (
#     np.linspace(0, 1, riser_samples) ** 2
# )

# riser_noise *= riser_envelope

# add_sound(
#     riser_noise.astype(np.float32),
#     RISER_START,
#     pan=0,
#     volume=0.12
# )


# # --------------------------------------
# # B. Rising tonal sweep
# # --------------------------------------

# riser_frequency = np.linspace(
#     200,
#     200 * 12,
#     riser_samples
# )

# riser_phase = (
#     2 * np.pi
#     * np.cumsum(riser_frequency)
#     / SR
# )

# riser_tone = np.sin(riser_phase)

# riser_tone *= riser_envelope

# add_sound(
#     riser_tone.astype(np.float32),
#     RISER_START,
#     pan=0,
#     volume=0.09
# )


# # ==========================================================
# # 12. PHASE 5: THE DROP (FINAL 4 SECONDS)
# # ==========================================================

# print("\nGenerating the final drop...")

# # Clear all sounds after the drop begins
# drop_sample = int(
#     DROP_START * SR
# )

# audio[drop_sample:, :] = 0

# # Brief silence before the final rumble
# impact_time = DROP_START + 0.65

# impact_duration = 2.5

# impact_samples = int(
#     impact_duration * SR
# )

# impact_t = np.arange(
#     impact_samples
# ) / SR


# # --------------------------------------
# # A. Deep cinematic impact
# # --------------------------------------

# impact_frequency = (
#     65 - 35 * (
#         impact_t / impact_duration
#     )
# )

# impact_phase = (
#     2 * np.pi
#     * np.cumsum(impact_frequency)
#     / SR
# )

# impact = np.sin(impact_phase)

# impact *= np.exp(-2.2 * impact_t)


# # --------------------------------------
# # B. Low-frequency rumble
# # --------------------------------------

# rumble = filtered_noise(
#     impact_duration,
#     low=25,
#     high=100
# )

# rumble *= np.exp(-1.2 * impact_t)

# impact += rumble * 0.7

# add_sound(
#     impact.astype(np.float32),
#     impact_time,
#     pan=0,
#     volume=0.65
# )


# ==========================================================
# 13. FINAL MIX AND EXPORT
# ==========================================================

print("\nMixing audio...")

# Gentle fade at the very end
fade_length = int(
    1.5 * SR
)

fade_start = max(
    0,
    TOTAL_SAMPLES - fade_length
)

fade = np.linspace(
    1,
    0,
    TOTAL_SAMPLES - fade_start
)

audio[fade_start:, 0] *= fade
audio[fade_start:, 1] *= fade


# --------------------------------------
# Prevent clipping
# --------------------------------------

peak = np.max(
    np.abs(audio)
)

if peak > 0:

    audio *= 0.90 / peak


# --------------------------------------
# Export stereo WAV
# --------------------------------------

sf.write(
    OUTPUT_PATH,
    audio,
    SR,
    subtype="PCM_16"
)


# ==========================================================
# 14. COMPLETION SUMMARY
# ==========================================================

print("\n===================================")
print("SOUNDIFICATION COMPLETED!")
print("===================================")

print("Output:", OUTPUT_PATH)

print(
    "Duration:",
    round(VIDEO_DURATION, 2),
    "seconds"
)

print("Sample rate:", SR)

print("Audio channels: Stereo")

print("Individual lightning events:", len(individual_df))
print("Regional activity records:", len(regional_df))

print(
    "Phase 2 events:",
    len(phase2)
)

print(
    "Storm events:",
    len(
        df[
            (df["Timestamp"] >= PHASE_2_END) &
            (df["Timestamp"] < STORM_END)
        ]
    )
)

print("===================================")
