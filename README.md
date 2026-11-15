# Earth Jukebox · NASAVERSE Sidequestors

Our entry for the **NASA Space Apps Challenge 2026: The Earth Information Jukebox**.

Meet the Team: 

Yuting: The World After Dark, twelve years of Earth’s night lights, and the first version of the jukebox interface
Ryan: A Planet With a Fever, 144 years of temperature from pole to pole
Agracia: The Planet Breathing, the land absorbing and releasing CO₂, plus the narrated Play Story mode and the final interface
Angela: The Storm Gathers, six years of lightning seen from the International Space Station

Together, the four tracks tell one story: a brighter, warmer planet whose land is struggling to keep breathing, and whose skies are full of storms.

Earth Jukebox turns four NASA visualizations into music you can hear, styled as a digital jukebox. Each track plays its own piece of music in step with the NASA video or images it was made from. A narrator explains what you are hearing and describes the visual, with captions. **Play Story** plays all four tracks in order as one narrated climate story.

| # | Track | NASA data | Audio file |
|---|---|---|---|
| A | The World After Dark | Earth's night lights, 2012–2023 | `nightlight/nightlights_output/nightlights.wav` |
| B | A Planet With a Fever | Temperature anomalies in 8 latitude bands, 1880–2023 (GISTEMP) | `zonal/output/zonal_down.wav` |
| C | The Planet Breathing | Net ecosystem exchange of CO₂ on land, 2003–2017 | `nee/output/nee.wav` |
| D | The Storm Gathers | Lightning seen from the International Space Station, 2017–2023 | `lightning/output/final_soundscape.wav` |

---

## How to run it

You need **Python 3** (only to start a small local web server) and a modern browser (Chrome, Edge, Firefox or Safari). Nothing needs to be installed or built.

1. **Get the code**
   ```bash
   git clone https://github.com/agraciayyx/NASAVERSE-SIDEQUESTORS-JUKEBOX.git
   cd NASAVERSE-SIDEQUESTORS-JUKEBOX
   ```

2. **Start a local server from the repository root** (the folder with this README)
   ```bash
   python -m http.server 8000
   ```
   On Windows, if `python` isn't found, use `py -m http.server 8000`.

3. **Open http://localhost:8000** in your browser. It goes straight to the jukebox.

4. When you're done, press `Ctrl + C` in the terminal to stop the server.

> **Why a server?** Opening `index.html` by double-clicking it won't work. Browsers block pages opened as files from loading the audio, video and caption files, so the tracks won't play.

### Using the jukebox
- **Home page:** use the arrows or the dial to pick a track, then press **Play** to open it.
- **Track page:** play, pause and seek. The NASA video or images move in step with the music.
- **▶ LISTEN** buttons: the narrator reads "What you are hearing" or "Describe this visual". The music dips while they speak.
- **Play Story:** the narrator introduces each track with one line of the story, then the track plays, from A to D. Captions appear under the visual. Press **Home** to leave the story.

---

## Project structure

```
NASAVERSE-SIDEQUESTORS-JUKEBOX/
├── index.html              # redirects to homepageUI/
├── homepageUI/             # the jukebox website
│   ├── index.html, app.js, styles.css
│   ├── tracks.js           # track names, text, audio, video and cover for each track
│   ├── assets/             # cover images, night-lights frames, narration MP3s + captions.json
│   └── narration/make_narration.py   # records the narrator clips
├── nightlight/             # Track A: frames/ (NASA images), sonify_nightlights.py, nightlights_output/
├── zonal/                  # Track B: data/, main/main.py, output/
├── nee/                    # Track C: data/, main/, output/
└── lightning/              # Track D: data/, main/, output/
```

Each track folder follows the same pattern: `data/` holds the NASA source and extracted numbers, `main/` holds the scripts, and `output/` holds the finished audio.

---

## Re-making the audio (optional)

The finished audio is already in the repo, so you only need this if you change a track. Run the commands from the repository root unless a step says otherwise.

**Track A: The World After Dark**
```bash
pip install numpy pillow
python nightlight/sonify_nightlights.py --no-preview
```
Reads `nightlight/frames/` and writes `nightlight/nightlights_output/nightlights.wav`. Leave out `--no-preview` to see a contact sheet of the frames first.

**Track B: A Planet With a Fever** (standard library only, so there's nothing to install)
```bash
cd zonal
python main/main.py
```
Reads `data/gistemp_zonal.csv` and writes `output/zonal_down.wav`. It must be run from inside `zonal/`.

**Track C: The Planet Breathing**
```bash
pip install opencv-python numpy mido
python nee/main/extract_features.py
python nee/main/compose_midi.py
```
This writes `nee/data/nee_features.csv`, then the score `nee/output/nee.mid`. Open the MIDI in MuseScore 4 (Muse Sounds) and export it as `nee/output/nee.wav`.

**Track D: The Storm Gathers**
1. Download the 4K video `iss_lightning_sphere_07312023_60p4k.mp4` (414 MB) from [NASA SVS 5011](https://svs.gsfc.nasa.gov/5011/) into `lightning/data/`. The scripts measure positions at 4K, so the smaller copy won't give the same result.
2. Run:
   ```bash
   pip install opencv-python numpy pandas soundfile scipy
   python lightning/main/extract_frames.py
   python lightning/main/main_soundification.py
   ```
   This writes `lightning/data/lightning_dataset.csv`, then `lightning/output/final_soundscape.wav`.

**Narrator voice**

The narrator is Kokoro, an open text-to-speech model. Edit the scripts in `homepageUI/narration/make_narration.py`, then:
```bash
pip install kokoro-onnx soundfile numpy
python homepageUI/narration/make_narration.py
```
You also need `ffmpeg` on your PATH, plus `kokoro-v1.0.onnx` and `voices-v1.0.bin` next to the script, from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0). Keep the model files out of git because they're large. Add `intro`, `hearing` or `visual` to the command to re-record only those clips.

### Changing a track's name or text
Edit `homepageUI/tracks.js`. Each track has its name (`subtitle`), card line (`description`), "What you are hearing" text (`hearing`, `mapping`), "Describe this visual" text (`visualDescription`), and its `src` (audio), `video` and `cover` paths. Refresh the browser to see changes.

---

## Working on the repo together

- `main` is protected, so nobody pushes to it directly. Work on your own branch, e.g. `yourname/task`:
  ```bash
  git checkout main
  git pull
  git checkout -b yourname/task
  ```
- Commit and push to your branch, then open a **Pull Request** into `main` on GitHub.
- Files over 100 MB can't go on GitHub. The original NASA lightning videos are listed in `.gitignore` for this reason.

---

## Data sources and credits

All visualizations are by **NASA's Scientific Visualization Studio (SVS)**.

- Track A: Earth at night, 2012–2023: [svs.gsfc.nasa.gov/5276](https://svs.gsfc.nasa.gov/5276/) (Kel Elkins)
- Track B: GISTEMP zonal temperature anomalies, 1880–2023: [svs.gsfc.nasa.gov/5209](https://svs.gsfc.nasa.gov/5209)
- Track C: Net ecosystem exchange of CO₂: [svs.gsfc.nasa.gov/5047](https://svs.gsfc.nasa.gov/5047)
- Track D: Lightning events detected from the ISS, 2017–2023: [svs.gsfc.nasa.gov/5011](https://svs.gsfc.nasa.gov/5011/)

Our scripts read the colours and brightness of NASA's *rendered* images and videos, not the raw scientific datasets. The music shows the patterns in the visuals; it isn't a precise measurement.
