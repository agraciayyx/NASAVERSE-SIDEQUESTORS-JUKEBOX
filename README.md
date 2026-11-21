# Earth Jukebox · NASAVERSE Sidequestors

Earth Jukebox is a digital climate-music experience created for the **NASA International Space Apps Challenge 2026**. It turns four NASA visualizations into an interactive jukebox with synchronized visuals, captioned narration, and audio.

**Live site:** https://nasaversesidequestorsjukebox.vercel.app/homepageUI/

## The tracks

| Track | Name | NASA visualization |
|---|---|---|
| A | The World After Dark | Earth's night lights, 2012-2023 |
| B | A Planet With a Fever | Zonal temperature anomalies, 1880-2023 |
| C | The Planet Breathing | Land carbon exchange, 2003-2017 |
| D | The Storm Gathers | Lightning observed from the International Space Station, 2017-2023 |

Together, the tracks tell the story of a brighter, warmer planet whose land is struggling to keep breathing and whose skies are full of storms.

**Play Story** plays all four tracks as one narrated climate story.

## Run locally

The project has no build step or package dependencies. You only need Python 3 and a modern browser.

```bash
git clone https://github.com/agraciayyx/NASAVERSE-SIDEQUESTORS-JUKEBOX.git
cd NASAVERSE-SIDEQUESTORS-JUKEBOX
python -m http.server 8000
```

On Windows, use `py -m http.server 8000` if `python` is not available.

Open http://localhost:8000. Press `Ctrl+C` in the terminal when finished.

Opening `index.html` directly is not supported because browsers can block local pages from loading the audio, video, and caption files.

## Using the website

- Choose a track on the home page, then press **Play**.
- Use the track controls to play, pause, and seek.
- Select **LISTEN** to hear the narrator explain the audio or visual.
- Select **Play Story** to listen to the tracks continuously with narrated introductions and captions.
- Select **Home** at any time to leave the story.

The website uses compressed MP3 files for faster loading. Full-quality WAV masters remain alongside them in each track folder.

## Project structure

```text
NASAVERSE-SIDEQUESTORS-JUKEBOX/
├── index.html              # Redirects to homepageUI/
├── homepageUI/             # Jukebox interface
│   ├── assets/             # Covers, images, narration, and captions
│   ├── app.js
│   ├── styles.css
│   └── tracks.js           # Track names, text, and media paths
├── nightlight/             # Track A
├── zonal/                  # Track B
├── nee/                    # Track C
├── lightning/              # Track D
└── .vercelignore           # Files excluded from the Vercel deployment
```

Each track folder contains NASA source material or extracted data, audio-generation scripts, and finished output files.

## Hosting

The jukebox is a static website and can be served by any static web host. It is deployed with Vercel from this repository and does not require a build step.

### Vercel setup

1. Import the repository in Vercel.
2. Set **Framework Preset** to **Other**.
3. Leave **Build Command** empty.
4. Set **Output Directory** to the repository root.
5. Deploy.

Merges into `main` redeploy the site automatically. Pull requests receive preview deployments.

## Rebuilding the audio

The finished audio is already included, so this is optional.

After changing a track, convert its WAV master to MP3 for the website:

```bash
ffmpeg -y -i zonal/output/zonal_down.wav -b:a 192k zonal/output/zonal_down.mp3
```

Use the corresponding WAV and MP3 paths for each track.

### Track A: The World After Dark

```bash
pip install numpy pillow
python nightlight/sonify_nightlights.py --no-preview
```

### Track B: A Planet With a Fever

```bash
cd zonal
python main/main.py
```

Run this from inside `zonal/`. It uses only the Python standard library.

### Track C: The Planet Breathing

```bash
pip install opencv-python numpy mido
python nee/main/extract_features.py
python nee/main/compose_midi.py
```

Open `nee/output/nee.mid` in MuseScore 4 and export it as `nee/output/nee.wav`.

### Track D: The Storm Gathers

Download NASA SVS visualization 5011's 4K source video into `lightning/data/`, then run:

```bash
pip install opencv-python numpy pandas soundfile scipy
python lightning/main/extract_frames.py
python lightning/main/main_soundification.py
```

### Narration

The narrated clips use Kokoro text-to-speech. Install the narration dependencies and provide `kokoro-v1.0.onnx` and `voices-v1.0.bin` beside the script.

```bash
pip install kokoro-onnx soundfile numpy
python homepageUI/narration/make_narration.py
```

FFmpeg must be available on `PATH`.

## Editing track information

Edit `homepageUI/tracks.js` to change a track name, description, narrated text, audio path, video path, or cover image. Refresh the browser to see changes.

## Contributing

`main` is the protected integration branch. Create a feature branch, commit your changes, push the branch, and open a pull request into `main`.

Files over 100 MB cannot be stored on GitHub. Keep large NASA source files out of version control as specified in `.gitignore`.

## Team

- Yuting - The World After Dark
- Ryan - A Planet With a Fever
- Agracia - The Planet Breathing and Play Story
- Angela - The Storm Gathers

## NASA data and credits

The visualizations are provided by **NASA's Scientific Visualization Studio**:

- [Track A: Earth at Night](https://svs.gsfc.nasa.gov/5276/)
- [Track B: GISTEMP Zonal Temperature](https://svs.gsfc.nasa.gov/5209/)
- [Track C: Net Ecosystem Exchange](https://svs.gsfc.nasa.gov/5047/)
- [Track D: Lightning from the ISS](https://svs.gsfc.nasa.gov/5011/)

Tracks A, C, and D sonify patterns in NASA's rendered images and videos. Track B uses the GISTEMP zonal temperature dataset directly, so each note reflects a measured temperature anomaly.
