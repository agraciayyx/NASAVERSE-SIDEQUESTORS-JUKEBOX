# Earth Jukebox UI

Two responsive views matching the reference: a track-selection home and a track player.

## Run

Keep this `homepageUI` folder beside `nightlight` in the repo. From the repository root:

```powershell
py -m http.server 8000
```

Open http://localhost:8000 in your browser. It goes straight to the jukebox home page (the root `index.html` redirects to `homepageUI/`). No npm installation or build is needed.

## Add the remaining tracks

Edit `tracks.js`. Change each track's `title`, `subtitle`, descriptions and `src`.
For example, place a WAV in `homepageUI/assets/climate.wav`, then set `src: 'assets/climate.wav'`.
`null` means that track is still pending. Track A uses the Night Lights WAV, Track B the zonal WAV and Track C the NEE WAV (`../nee/output/nee.wav`).

Play/pause controls real audio. Previous/next select a track and continue playback if it has audio; a pending track stops playback and displays its status. Play Story plays available tracks in list order and skips pending tracks. No narration has been added.

Track A (Night Lights) uses 12 bundled JPEG previews of NASA's rendered yearly night-lights images (2012–2023). The audio clock selects one year every two seconds; pause holds the frame and seeking updates it. The last year holds through the final audio tail. These are rendered images, not a live data feed. The waveform and header equalizer react to the actual audio. Other tracks display an explicitly illustrative placeholder until your teammates supply their visuals. Font loading is optional; local monospace fallbacks work offline.

NASA image source: https://svs.gsfc.nasa.gov/5276/ (linked from https://svs.gsfc.nasa.gov/5313/). Credit: NASA's Scientific Visualization Studio; Kel Elkins.

