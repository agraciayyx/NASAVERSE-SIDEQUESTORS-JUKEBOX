# Earth Jukebox - narrator voice-over for the "What you are hearing" and "Describe this visual" notes.
# An AI voice (Kokoro, an open text-to-speech model) reads each script below into an MP3.
#
# run   >  python homepageUI/narration/make_narration.py            (all clips)
#          python homepageUI/narration/make_narration.py intro      (only the storyline lines; or hearing / visual)
# needs >  pip install kokoro-onnx soundfile numpy, plus ffmpeg on the PATH
#          and two model files next to this script (from github.com/thewh1teagle/kokoro-onnx, release model-files-v1.0):
#          kokoro-v1.0.onnx and voices-v1.0.bin  (large; keep them out of git)
# out   >  homepageUI/assets/narration/<track id>_<intro|hearing|visual>.mp3
#          homepageUI/assets/narration/captions.json  (each clip's sentences with their start and end times, for the captions)
#
# Edit a script, run again, refresh the jukebox. Track ids match tracks.js.

import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "assets", "narration")
VOICE = "bm_george"          # set to the narrator voice you picked
LANG = "en-gb" if VOICE.startswith("b") else "en-us"
SPEED = 0.88                 # a little slower than normal, documentary pace
PAUSE_SECONDS = 0.45         # breath between sentences
# words the voice says wrongly: (how it is written in phonemes, how it should be). "live" as in "people live", not "live music"
PRONUNCIATION_FIXES = [("pˈiːpəl lˈaɪv", "pˈiːpəl lˈɪv")]

SCRIPTS = {
    "a": {  # Night Lights
        # intro: the storyline line the narrator says before the track in Play Story
        "intro": (
            "Our story begins at night. "
            "In just twelve years, the glow of towns and cities has spread across the planet, "
            "tracing where people live and build. "
            "Listen as the light grows and the notes climb."
        ),
        "hearing": (
            "Listen to the planet after dark. "
            "NASA satellites photographed Earth's lights at night, every year from 2012 to 2023. "
            "We divided each image into eight regions, and gave each region a voice. "
            "As a region glows brighter, its note climbs higher. The brighter the lights, the louder it sings. "
            "Twelve years, two seconds each. The chorus of a world that never sleeps."
        ),
        "visual": (
            "This is our world at night, seen from orbit. "
            "Every point of light is a city, a highway, a harbour. A place where people live and work. "
            "From 2012 to 2023, the image moves forward one year at a time, in step with the music. "
            "Watch the lights spread, and listen to them grow."
        ),
    },
    "b": {  # Climate Anomalies (zonal temperatures)
        "intro": (
            "Behind that growing glow is a rising demand for energy. "
            "As greenhouse gases build up, the planet warms. "
            "Listen to a hundred and forty-four years of changing temperature, from pole to pole."
        ),
        "hearing": (
            "For a hundred and forty-four years, scientists have taken the planet's temperature. "
            "Here, eight bands of latitude, from the Arctic to Antarctica, each play a single note. "
            "The warmer a band becomes, the lower its note falls. "
            "Beneath them, a heartbeat quickens as the whole world warms. "
            "And slowly, the harmony begins to fall apart. Notes drift out of tune. They clash. They tremble. "
            "This is the sound of a warming planet."
        ),
        "visual": (
            "This is NASA's temperature record, from 1880 to 2023, divided into eight bands from pole to pole. "
            "Each row is a band of the Earth, and each mark is a year, placed by how much warmer or cooler it was "
            "than the average from 1951 to 1980. "
            "As the decades pass, the newest marks glow red and creep to the right. "
            "By 2023, the Arctic, on the top row, has warmed the most of all."
        ),
    },
    "c": {  # The Planet Breathing (net ecosystem exchange)
        "intro": (
            "Yet the living land fights back, breathing in our carbon every summer. "
            "But when drought takes hold, as it did in 2015 and 2016, its breath begins to falter."
        ),
        "hearing": (
            "Every year, the planet breathes. "
            "In the northern summer, forests and fields draw carbon dioxide from the air. In winter, they let it go. "
            "Here, strings follow that breath, month by month, from 2003 to 2017. "
            "A solo violin climbs as the land breathes in. Cellos and racing violins swell as it breathes out. "
            "Each January, a timpani strikes, louder in the years the land absorbed less. "
            "Listen for 2016 and 2017, when the breath falters."
        ),
        "visual": (
            "This is NASA's map of the living land. "
            "Green marks places absorbing carbon dioxide. Magenta marks places releasing it. "
            "Month by month, the colours follow the seasons. Green sweeps across the north every summer, and fades each winter. "
            "In 2015 and 2016, watch the Amazon turn magenta, as a severe drought grips the rainforest."
        ),
    },
    "d": {  # Lightning (ISS Lightning Imaging Sensor)
        "intro": (
            "And as the planet warms, the air above it holds more heat and more water, the fuel of thunderstorms. "
            "For six years, a sensor on the International Space Station watched lightning flash across the Earth. "
            "Listen as the storm gathers."
        ),
        "hearing": (
            "Listen to lightning, seen from space. "
            "At first, there is only the planet itself: a low hum, the wind, a slow pulse. "
            "Then, single flashes. Each one plays a note. "
            "The higher a flash appears on the screen, the higher its note, and you hear it on the side where it struck. "
            "Flashes in the north ring like glass. Near the equator, they are plucked. In the south, a cello answers. "
            "Then the storm arrives. Strings swell. "
            "Drums quicken, and strike harder whenever more lightning flashes. "
            "And the thunder rolls in."
        ),
        "visual": (
            "This is NASA's view of lightning from the International Space Station. "
            "First, we ride along with the station for a single day, the first of March, 2017. "
            "Each yellow flash is a lightning strike it spotted below. "
            "Then the view pulls back, and six years spin by, to July 2023. "
            "Ten days of strikes are shown at a time, so you can watch the storms follow the seasons. "
            "Watch the flashes gather, and listen to the storm build."
        ),
    },
}


def speak(kokoro, text):
    # one sentence at a time, with a short pause between, so the delivery is calm and measured
    parts, timings, rate, t = [], [], 24000, 0.0
    for sentence in [s.strip() for s in text.replace("? ", "?|").replace(". ", ".|").split("|") if s.strip()]:
        phonemes = kokoro.tokenizer.phonemize(sentence, LANG)
        for wrong, right in PRONUNCIATION_FIXES:
            phonemes = phonemes.replace(wrong, right)
        audio, rate = kokoro.create(phonemes, voice=VOICE, speed=SPEED, lang=LANG, is_phonemes=True)
        timings.append({"start": round(t, 2), "end": round(t + len(audio) / rate, 2), "text": sentence})
        t += len(audio) / rate + PAUSE_SECONDS
        parts += [audio, np.zeros(int(PAUSE_SECONDS * rate), dtype=audio.dtype)]
    return np.concatenate(parts), rate, timings


def main():
    kokoro = Kokoro(os.path.join(HERE, "kokoro-v1.0.onnx"), os.path.join(HERE, "voices-v1.0.bin"))
    os.makedirs(OUT_DIR, exist_ok=True)
    only = set(sys.argv[1:])                       # e.g. "intro": re-record just those parts
    captions_path = os.path.join(OUT_DIR, "captions.json")
    captions = {}
    if only and os.path.exists(captions_path):
        with open(captions_path, encoding="utf-8") as f:
            captions = json.load(f)
    for track, parts in SCRIPTS.items():
        for part, text in parts.items():
            if only and part not in only:
                continue
            audio, rate, timings = speak(kokoro, text)
            captions[f"{track}_{part}"] = timings
            wav = os.path.join(OUT_DIR, f"{track}_{part}.wav")
            mp3 = wav[:-4] + ".mp3"
            sf.write(wav, audio, rate)
            # light polish: a little warmth in the low end, level matched, small room reverb
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af",
                            "bass=g=3:f=120,aecho=0.8:0.5:40:0.12,loudnorm=I=-16:TP=-1.5",
                            "-ar", "44100", "-b:a", "128k", mp3], check=True)
            os.remove(wav)
            print(f"Wrote {os.path.relpath(mp3)} ({len(audio) / rate:.1f} s)")
    with open(captions_path, "w", encoding="utf-8") as f:
        json.dump(captions, f, indent=1, ensure_ascii=False)
    print("Wrote captions.json")


if __name__ == "__main__":
    main()
