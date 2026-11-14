import csv
import json
import re
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
OUT = ROOT / "nightlights_output"

YEARS = list(range(2012, 2024))
ROWS, COLS = 2, 4

# "relative": pitch represents change since 2012.
# "absolute": pitch represents displayed brightness.
MODE = "relative"

SECONDS_PER_YEAR = 2.0
NOTE_SECONDS = 0.65
SAMPLE_RATE = 44100

# Fixed rectangle excluding the year label.
# Fractions: left, top, right, bottom.
LABEL = (0.42, 0.59, 0.50, 0.66)

SCALE = np.array([
    48, 50, 52, 55, 57,
    60, 62, 64, 67, 69,
    72, 74, 76, 79, 81,
])

EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
ECHO_SECONDS = 0.28


def find_frames():
    found = {}

    for path in sorted(FRAMES.iterdir()):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue

        matches = re.findall(r"(?<!\d)(20\d{2})(?!\d)", path.stem)
        relevant = sorted({int(y) for y in matches if int(y) in YEARS})

        if not relevant:
            continue
        if len(relevant) != 1:
            raise ValueError(f"Ambiguous year in filename: {path.name}")

        year = relevant[0]
        if year in found:
            raise ValueError(
                f"Duplicate images for {year}:\n"
                f"{found[year].name}\n{path.name}\n"
                "Keep only one source image per year in frames."
            )

        found[year] = path

    missing = sorted(set(YEARS) - set(found))
    if missing:
        raise ValueError(f"Missing yearly images: {missing}")

    return {year: found[year] for year in YEARS}


def load_rgb(path):
    with Image.open(path) as source:
        rgba = source.convert("RGBA")

    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def measure(image):
    # Pillow converts RGB into a weighted grayscale brightness.
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape

    valid = np.ones(gray.shape, dtype=bool)
    if LABEL is not None:
        left, top, right, bottom = LABEL
        valid[
            int(top * height):int(bottom * height),
            int(left * width):int(right * width),
        ] = False

    values = []

    for row in range(ROWS):
        for col in range(COLS):
            ys = slice(
                row * height // ROWS,
                (row + 1) * height // ROWS,
            )
            xs = slice(
                col * width // COLS,
                (col + 1) * width // COLS,
            )

            pixels = gray[ys, xs][valid[ys, xs]]
            if pixels.size == 0:
                raise ValueError("A grid cell is completely masked.")

            values.append(float(pixels.mean() / 255.0))

    return values


def make_thumbnail(image, year):
    preview = image.copy()
    preview.thumbnail((480, 270))
    draw = ImageDraw.Draw(preview)
    width, height = preview.size

    for col in range(1, COLS):
        x = col * width // COLS
        draw.line((x, 0, x, height), fill="cyan")

    for row in range(1, ROWS):
        y = row * height // ROWS
        draw.line((0, y, width, y), fill="cyan")

    if LABEL is not None:
        left, top, right, bottom = LABEL
        draw.rectangle(
            (
                int(left * width),
                int(top * height),
                int(right * width),
                int(bottom * height),
            ),
            outline="red",
            width=2,
        )

    draw.text((8, 8), str(year), fill="yellow")
    return preview


def display_contact_sheet(thumbnails):
    columns = 3
    tile_width, tile_height = 480, 300
    sheet_rows = (len(thumbnails) + columns - 1) // columns

    sheet = Image.new(
        "RGB",
        (columns * tile_width, sheet_rows * tile_height),
        "black",
    )

    for index, thumbnail in enumerate(thumbnails):
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        sheet.paste(thumbnail, (x, y))

    # Display a temporary preview instead of saving an output image.
    if "--no-preview" not in sys.argv:
        sheet.show(title="Night-lights frame check: 2012–2023")


def normalize(values):
    # Loudness always represents absolute displayed brightness.
    transformed = np.log1p(values * 255)
    low = float(transformed.min())
    high = float(transformed.max())

    if high > low:
        loudness = (transformed - low) / (high - low)
    else:
        loudness = np.full_like(values, 0.5)

    settings = {
        "loudnessTransform": "log1p(brightness * 255)",
        "loudnessMinimum": low,
        "loudnessMaximum": high,
    }

    if MODE == "relative":
        # Numerical safeguard, far below the dark-cell values.
        # Exactly black baselines have no defined percentage change.
        # This tiny floor allows an artistic pitch mapping for those cells.
        floor = 1e-12
        baseline = values[0]

        relative = (
            np.log2(np.maximum(values, floor))
            - np.log2(np.maximum(baseline, floor))
        )

        limit = float(np.abs(relative).max())
        if limit > 0:
            pitch = 0.5 + relative / (2 * limit)
        else:
            pitch = np.full_like(values, 0.5)

        settings.update({
            "pitchTransform": "log2(current / 2012 baseline)",
            "brightnessFloor": floor,
            "relativeLog2Limit": limit,
            "zeroBaselineCells": np.flatnonzero(baseline == 0).tolist(),
            "interpretation": (
                "Unchanged = middle pitch; increases = higher; "
                "decreases = lower. Range is normalized to this dataset."
            ),
        })

    elif MODE == "absolute":
        pitch = loudness.copy()
        settings["pitchTransform"] = "Same normalization as loudness"

    else:
        raise ValueError('MODE must be "relative" or "absolute".')

    return np.clip(pitch, 0, 1), loudness, settings


def synthesize(values, pitch, loudness):
    number_of_cells = ROWS * COLS
    step = SECONDS_PER_YEAR / number_of_cells
    duration = NOTE_SECONDS

    last_onset = (
        (len(YEARS) - 1) * SECONDS_PER_YEAR
        + (number_of_cells - 1) * step
    )
    total_seconds = last_onset + duration + 2 * ECHO_SECONDS
    audio = np.zeros((int(np.ceil(total_seconds * SAMPLE_RATE)), 2))

    time = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
    envelope = (
        np.minimum(time / 0.012, 1)
        * np.exp(-time / (duration * 0.28))
        * np.minimum((duration - time) / 0.05, 1)
    )

    events = []

    for year_index, year in enumerate(YEARS):
        for cell in range(number_of_cells):
            brightness = float(values[year_index, cell])

            if brightness == 0:
                continue  # Exactly black cells are rests.

            position = float(pitch[year_index, cell])
            scale_index = int(np.floor(position * (len(SCALE) - 1) + 0.5))
            midi = int(SCALE[scale_index])

            velocity = 0.10 + 0.55 * float(loudness[year_index, cell])
            frequency = 440 * 2 ** ((midi - 69) / 12)

            tone = (
                np.sin(2 * np.pi * frequency * time)
                + 0.2 * np.sin(4 * np.pi * frequency * time)
            ) / 1.2
            tone *= envelope * velocity

            pan = (cell % COLS) / max(COLS - 1, 1)
            stereo = np.array([
                np.cos(pan * np.pi / 2),
                np.sin(pan * np.pi / 2),
            ])

            onset = year_index * SECONDS_PER_YEAR + cell * step
            start = round(onset * SAMPLE_RATE)
            audio[start:start + len(time)] += tone[:, None] * stereo

            events.append({
                "timeSeconds": onset,
                "durationSeconds": duration,
                "year": year,
                "imageCell": cell,
                "midiNote": midi,
                "velocity": velocity,
                "pan": pan,
                "displayedBrightness": brightness,
            })

    delay = round(ECHO_SECONDS * SAMPLE_RATE)
    echoed = audio.copy()
    echoed[delay:] += audio[:-delay] * 0.30
    echoed[2 * delay:] += audio[:-2 * delay] * 0.12

    peak = float(np.abs(echoed).max())
    gain = 0.9 / peak if peak > 0 else 1.0

    return echoed * gain, events, gain


def main():
    if ROWS < 1 or COLS < 1:
        raise ValueError("ROWS and COLS must be positive.")
    if SECONDS_PER_YEAR <= 0 or NOTE_SECONDS <= 0:
        raise ValueError("Timing settings must be positive.")
    if LABEL is not None:
        left, top, right, bottom = LABEL
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("Invalid label-mask rectangle.")

    files = find_frames()
    OUT.mkdir(exist_ok=True)

    measurements = []
    thumbnails = []
    expected_size = None
    sources = []

    for year, path in files.items():
        image = load_rgb(path)

        if expected_size is None:
            expected_size = image.size
        elif image.size != expected_size:
            raise ValueError(f"Image size mismatch: {path.name}")

        measurements.append(measure(image))
        thumbnails.append(make_thumbnail(image, year))
        sources.append({"year": year, "filename": path.name})

        print(f"{year}: measured {path.name}", flush=True)
        image.close()

    display_contact_sheet(thumbnails)

    values = np.asarray(measurements, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Measurements contain invalid values.")

    pitch, loudness, mapping = normalize(values)
    audio, events, gain = synthesize(values, pitch, loudness)

    with wave.open(str(OUT / "nightlights.wav"), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes((audio * 32767).astype("<i2").tobytes())

    print("\nBRIGHTNESS MEASUREMENTS (CSV)")
    writer = csv.writer(sys.stdout)
    writer.writerow([
        "year", "image_cell", "row", "column",
        "mean_displayed_brightness_0_1",
    ])

    for yi, year in enumerate(YEARS):
        for cell, value in enumerate(values[yi]):
            writer.writerow([
                year, cell, cell // COLS, cell % COLS, value,
            ])

    metadata = {
        "title": "Global night-lights visual sonification, 2012–2023",
        "sourceFrames": (
            "https://svs.gsfc.nasa.gov/vis/a000000/a005200/a005276/"
            "frames/7680x4320_16x9_3p/nightlights_flat_2012-2023_only_lights/"
        ),
        "referenceVisualization": "https://svs.gsfc.nasa.gov/5313/",
        "credit": "NASA's Scientific Visualization Studio; Kel Elkins",
        "measurement": (
            "Mean Pillow L brightness divided by 255, "
            "after compositing transparency on black. Not calibrated radiance."
        ),
        "sources": sources,
        "imageSize": list(expected_size),
        "grid": [ROWS, COLS],
        "cellOrder": "Top row left to right, then successive rows; zero-based",
        "labelMask": LABEL,
        "mode": MODE,
        "mapping": mapping,
        "midiScale": SCALE.tolist(),
        "secondsPerYear": SECONDS_PER_YEAR,
        "arpeggioStepSeconds": SECONDS_PER_YEAR / (ROWS * COLS),
        "sampleRate": SAMPLE_RATE,
        "synthesis": {
            "fundamentalAmplitude": 1.0,
            "secondHarmonicAmplitude": 0.2,
            "harmonicDivisor": 1.2,
            "attackSeconds": 0.012,
            "decaySeconds": NOTE_SECONDS * 0.28,
            "releaseSeconds": 0.05,
            "panLaw": "equal power; pan 0=left, 1=right",
            "echoSeconds": ECHO_SECONDS,
            "echoGains": [0.30, 0.12],
            "wavMasterGain": gain,
        },
        "events": events,
    }

    print("\nNOTE EVENTS AND SETTINGS (JSON)")
    print(json.dumps(metadata, indent=2, ensure_ascii=True))

    report = [
        "All 12 expected years found: 2012–2023.",
        "No duplicate years; image dimensions match.",
        f"Image dimensions: {expected_size}",
        f"Measurements: {values.size}; notes: {len(events)}",
        f"Pitch mode: {MODE}",
        "Check all year labels and map alignment in the frame preview window.",
        "Matching dimensions alone do not prove matching map alignment.",
        "The red rectangle is excluded from measurement.",
        "Grid cells are image sections, not countries or equal-area regions.",
        "Pitch ranges are normalized to this selected image sequence.",
        "Rendered brightness is affected by NASA's rendering choices.",
        "This is an artistic image-based mapping, not physical radiance.",
    ]

    if MODE == "relative":
        zero_cells = mapping["zeroBaselineCells"]
        if zero_cells:
            report.append(
                f"Black baseline cells: {zero_cells}; "
                "percentage changes are undefined for these cells."
            )

        for cell in range(ROWS * COLS):
            baseline = values[0, cell]
            if baseline > 0:
                changes = (values[:, cell] / baseline - 1) * 100
                report.append(
                    f"Cell {cell}: change vs 2012 ranges from "
                    f"{changes.min():+.2f}% to {changes.max():+.2f}%."
                )

    print("\nVALIDATION")
    print("\n".join(report))

    print(f"\nOnly WAV saved: {OUT / 'nightlights.wav'}")
    print("Measurements, JSON and validation are displayed above, not saved.")


if __name__ == "__main__":
    main()
