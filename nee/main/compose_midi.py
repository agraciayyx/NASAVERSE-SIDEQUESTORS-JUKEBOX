# Earth Jukebox - Track 04 "The planet breathing", orchestral version
# Turn data/nee_features.csv into a MIDI score for strings and timpani. Open it in
# MuseScore 4 (Muse Sounds), export a WAV, then run nee/finalize_audio.py.
#
# Timing: 1 beat = 1 month (180 BPM, so 1/3 s), 12/4 time so 1 bar = 1 year (4 s).
# 15 bars (2003-2017) = 60.0 s, the length of the video. Every note sits on its month.
#
# What plays (A minor, harmonic minor G# in the tense chords):
# - Chords: one per month from that month's net exchange (absorbing - releasing),
#   ranked against the whole record. Strong uptake = calm chords, weak = tense chords.
# - Violins I: the engine. A climbing arpeggio of the chord in 8th notes. In the 30% of
#   months with the most releasing it doubles to 16th notes, an octave up. Louder with release.
# - Solo violin: the inhale. One long note per month, pitch from northern absorbing (A4-A6).
# - Violas: quiet sustained chord tones.
# - Cellos: the exhale. The chord root, low, louder with release.
# - Contrabass: the root of the year's main chord, one note per bar.
# - Timpani: a hit each January, louder in weaker years. The 2 weakest years get a roll.
#
# run  >  python nee/main/compose_midi.py
# needs > pip install mido numpy
# out  >  output/nee.mid

import csv
import os
from collections import Counter

import mido
import numpy as np

NEE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the nee/ folder
FEATURES_CSV = os.path.join(NEE_DIR, "data", "nee_features.csv")
OUT_MID = os.path.join(NEE_DIR, "output", "nee.mid")

START_YEAR = 2003
MONTHS = 180
TICKS = 480                 # ticks per beat (= per month)
BPM = 180                   # 1 beat = 1 month = 1/3 s
BEATS_PER_BAR = 12          # 12/4: 1 bar = 1 year

# chords as MIDI pitch classes (0 = C), root first. Ordered calm -> tense.
CHORDS = [
    ("Am", [9, 0, 4]),
    ("C", [0, 4, 7]),
    ("F", [5, 9, 0]),
    ("Dm", [2, 5, 9]),
    ("E7", [4, 8, 11, 2]),          # G# from A harmonic minor
    ("Bdim", [11, 2, 5]),
    ("Am(add2,b6)", [9, 11, 0, 5]),  # cluster: A B C F
]
# lower edge of the net-uptake rank (0 = weakest month, 1 = strongest) for each chord above
CHORD_RANKS = [0.80, 0.65, 0.50, 0.35, 0.20, 0.08, 0.0]

A_MINOR = [9, 11, 0, 2, 4, 5, 7]   # A B C D E F G
FAST_RELEASE_SHARE = 0.30          # top share of months (by release) that switch to 16th notes
SOLO_RANGE = (69, 93)              # A4 .. A6
OSTINATO_LOW = 57                  # A3: the arpeggio starts here
VIOLA_LOW = 55                     # G3: viola chord tones sit in G3..F#4
CELLO_LOW = 36                     # C2: cello roots sit in C2..B2
BASS_LOW = 33                      # A1: bass roots sit in A1..G#2
TIMPANI_LOW = 40                   # E2: timpani roots sit in E2..D#3
ROLL_YEARS = 2                     # weakest years that get a timpani roll
ROLL_STEP = 40                     # ticks between roll strokes (12 per month)

# velocities (MIDI 1..127)
OSTINATO_VEL = (48, 105)           # quietest -> most releasing
SOLO_VEL = (62, 96)                # weakest -> strongest northern absorbing
VIOLA_VEL = 44
CELLO_VEL = (45, 100)
BASS_VEL = 70
TIMPANI_VEL = (50, 120)            # strongest -> weakest year

# (track name, GM program, channel)
PARTS = {
    "ostinato": ("Violins I", 48, 0),
    "solo": ("Solo Violin", 40, 1),
    "violas": ("Violas", 41, 2),
    "cellos": ("Cellos", 42, 3),
    "bass": ("Contrabass", 43, 4),
    "timpani": ("Timpani", 47, 5),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(m):
    return f"{NOTE_NAMES[m % 12]}{m // 12 - 1}"


def scale01(x):
    lo, hi = float(np.min(x)), float(np.max(x))
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def lerp(pair, x):
    return int(round(pair[0] + (pair[1] - pair[0]) * x))


def in_octave(pc, low):
    # the pitch with class pc at or just above low
    return low + (pc - low) % 12


def load_months():
    with open(FEATURES_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    month = np.array([(int(r["year"]) - START_YEAR) * 12 + int(r["month"]) - 1 for r in rows])
    cols = {k: np.array([float(r[k]) for r in rows]) for k in ("absorb", "release", "north_absorb")}
    return {k: np.array([v[month == i].mean() for i in range(MONTHS)]) for k, v in cols.items()}


def pick_chord(rank):
    for (name, pcs), edge in zip(CHORDS, CHORD_RANKS):
        if rank >= edge:
            return name, pcs
    return CHORDS[-1]


def solo_pitch(level, chord_pcs):
    # map 0..1 onto the A minor scale between SOLO_RANGE; G becomes G# under E7
    scale = [p for p in range(SOLO_RANGE[0], SOLO_RANGE[1] + 1) if p % 12 in A_MINOR]
    p = scale[int(round(level * (len(scale) - 1)))]
    if p % 12 == 7 and 8 in chord_pcs:
        p += 1
    return p


def main():
    d = load_months()
    years = np.arange(MONTHS) // 12 + START_YEAR
    net = d["absorb"] - d["release"]
    rank = np.argsort(np.argsort(net)) / (MONTHS - 1)       # 0 = weakest month of the record
    release = scale01(d["release"])
    fast = d["release"] >= np.quantile(d["release"], 1 - FAST_RELEASE_SHARE)
    north_in = scale01(d["north_absorb"])
    chords = [pick_chord(r) for r in rank]

    year_list = list(range(START_YEAR, START_YEAR + MONTHS // 12))
    yearly_net = np.array([net[years == y].mean() for y in year_list])
    year_weakness = 1 - scale01(yearly_net)                 # 1 = weakest year
    roll_years = set(np.array(year_list)[np.argsort(yearly_net)[:ROLL_YEARS]].tolist())

    notes = {k: [] for k in PARTS}                          # (start tick, length, pitch, velocity)

    # Violins I: climbing arpeggio. The counter keeps running across months, so it spirals.
    step = 0
    for m in range(MONTHS):
        pcs = sorted(chords[m][1], key=lambda pc: (pc - 9) % 12)    # chord tones upward from A
        per_beat = 4 if fast[m] else 2
        length = TICKS // per_beat
        vel = lerp(OSTINATO_VEL, release[m])
        for k in range(per_beat):
            idx = step % (len(pcs) * 2)
            pitch = in_octave(pcs[idx % len(pcs)], OSTINATO_LOW) + 12 * (idx // len(pcs))
            pitch += 12 if fast[m] else 0
            notes["ostinato"].append((m * TICKS + k * length, int(length * 0.9), pitch, vel))
            step += 1

    # Solo violin: one legato note per month, tied (merged) when the pitch repeats
    solo = [solo_pitch(north_in[m], chords[m][1]) for m in range(MONTHS)]
    m = 0
    while m < MONTHS:
        end = m + 1
        while end < MONTHS and solo[end] == solo[m]:
            end += 1
        notes["solo"].append((m * TICKS, (end - m) * TICKS, solo[m], lerp(SOLO_VEL, north_in[m])))
        m = end

    # Violas: chord tones (3rd and 5th) held while the chord stays the same, re-struck every half bar
    half = BEATS_PER_BAR // 2
    m = 0
    while m < MONTHS:
        end = m + 1
        while end < MONTHS and chords[end][0] == chords[m][0] and end % half != 0:
            end += 1
        for pc in chords[m][1][1:3]:
            notes["violas"].append((m * TICKS, (end - m) * TICKS, in_octave(pc, VIOLA_LOW), VIOLA_VEL))
        m = end

    # Cellos: chord root, low, one note per month
    for m in range(MONTHS):
        root = chords[m][1][0]
        notes["cellos"].append((m * TICKS, TICKS, in_octave(root, CELLO_LOW), lerp(CELLO_VEL, release[m])))

    # Contrabass and timpani: once per bar (January), from the year's main chord
    for i, y in enumerate(year_list):
        main_chord = Counter(chords[m][0] for m in range(i * 12, i * 12 + 12)).most_common(1)[0][0]
        root = dict(CHORDS)[main_chord][0]
        start = i * 12 * TICKS
        notes["bass"].append((start, BEATS_PER_BAR * TICKS, in_octave(root, BASS_LOW), BASS_VEL))
        tvel = lerp(TIMPANI_VEL, year_weakness[i])
        tpitch = in_octave(root, TIMPANI_LOW)
        if y in roll_years:
            strokes = TICKS // ROLL_STEP
            for k in range(strokes):                       # roll through the first month, swelling in
                v = int(round(tvel * (0.55 + 0.45 * k / (strokes - 1))))
                notes["timpani"].append((start + k * ROLL_STEP, ROLL_STEP, tpitch, v))
        else:
            notes["timpani"].append((start, TICKS, tpitch, tvel))

    write_midi(notes)

    print(f"Wrote {OUT_MID}")
    print(f"16th-note months: {int(fast.sum())} ({', '.join(f'{y}:{int(fast[years == y].sum())}' for y in year_list)})")
    print(f"Timpani rolls: {sorted(roll_years)}")


def write_midi(notes):
    mid = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("track_name", name="The planet breathing", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=BEATS_PER_BAR, denominator=4, time=0))
    meta.append(mido.MetaMessage("key_signature", key="Am", time=0))
    meta.append(mido.MetaMessage("end_of_track", time=MONTHS * TICKS))
    mid.tracks.append(meta)

    for key, (name, program, ch) in PARTS.items():
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", program=program, channel=ch, time=0))
        events = []
        for start, length, pitch, vel in notes[key]:
            events.append((start + length, 0, pitch, 0))      # note-offs sort before note-ons at the same tick
            events.append((start, 1, pitch, vel))
        events.sort()
        now = 0
        for tick, is_on, pitch, vel in events:
            kind = "note_on" if is_on else "note_off"
            track.append(mido.Message(kind, note=pitch, velocity=vel, channel=ch, time=tick - now))
            now = tick
        track.append(mido.MetaMessage("end_of_track", time=MONTHS * TICKS - now))
        mid.tracks.append(track)

    os.makedirs(os.path.dirname(OUT_MID), exist_ok=True)
    mid.save(OUT_MID)


if __name__ == "__main__":
    main()
