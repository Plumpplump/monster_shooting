"""Generate the small arcade sound effects used by the game (stdlib only).

Usage:
    ../ursinavenv/bin/python tools/generate_sounds.py

Writes 16-bit mono WAV files into assets/sounds/.  Re-run any time; the files
are deterministic except for the noise components.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
OUT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'sounds'


# ---------------------------------------------------------------- building blocks
def silence(duration):
    return [0.0] * int(SAMPLE_RATE * duration)


def tone(freq, duration, kind='sine', volume=0.5, attack=0.005, decay=None):
    """One tone with a quick attack and exponential decay."""
    samples = []
    n = int(SAMPLE_RATE * duration)
    decay = duration if decay is None else decay
    for i in range(n):
        t = i / SAMPLE_RATE
        if kind == 'sine':
            v = math.sin(2 * math.pi * freq * t)
        elif kind == 'square':
            v = 1.0 if (t * freq) % 1.0 < 0.5 else -1.0
        elif kind == 'saw':
            v = 2.0 * ((t * freq) % 1.0) - 1.0
        else:
            v = 0.0
        env = min(1.0, t / attack) if attack > 0 else 1.0
        env *= math.exp(-t / (decay / 5.0))
        samples.append(v * env * volume)
    return samples


def sweep(freq_from, freq_to, duration, volume=0.5):
    """Sine sweep with a smooth decay envelope."""
    samples = []
    n = int(SAMPLE_RATE * duration)
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        frac = i / max(1, n - 1)
        freq = freq_from + (freq_to - freq_from) * frac
        phase += 2 * math.pi * freq / SAMPLE_RATE
        env = math.exp(-3.5 * frac)
        samples.append(math.sin(phase) * env * volume)
    return samples


def noise(duration, volume=0.3, decay=None):
    samples = []
    n = int(SAMPLE_RATE * duration)
    decay = duration if decay is None else decay
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t / (decay / 5.0))
        samples.append(random.uniform(-1, 1) * env * volume)
    return samples


def mix(*tracks):
    length = max(len(t) for t in tracks)
    out = [0.0] * length
    for track in tracks:
        for i, v in enumerate(track):
            out[i] += v
    return out


def sequence(*tracks):
    out = []
    for track in tracks:
        out.extend(track)
    return out


def fade(samples, fade_in=0.004, fade_out=0.02):
    n = len(samples)
    fi = min(int(SAMPLE_RATE * fade_in), n // 2)
    fo = min(int(SAMPLE_RATE * fade_out), n // 2)
    out = list(samples)
    for i in range(fi):
        out[i] *= i / fi
    for i in range(fo):
        out[n - 1 - i] *= i / fo
    return out


def write_wav(name, samples):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = min(1.0, 0.85 / peak)
    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, s * scale)) * 32767)
        frames += struct.pack('<h', v)
    path = OUT_DIR / name
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(frames))
    print(f'wrote {path}  ({len(samples) / SAMPLE_RATE:.2f} s)')


# ---------------------------------------------------------------- the sounds
def build_all():
    random.seed(7)

    write_wav('shot.wav', fade(sweep(1200, 320, 0.09, volume=0.5)))

    write_wav('hit.wav', fade(mix(
        noise(0.05, volume=0.25),
        tone(900, 0.05, 'square', volume=0.25),
    )))

    write_wav('defeat.wav', fade(mix(
        sweep(700, 180, 0.18, volume=0.4),
        noise(0.18, volume=0.18),
    )))

    write_wav('boss_defeat.wav', fade(mix(
        noise(0.6, volume=0.35, decay=0.9),
        sweep(420, 60, 0.6, volume=0.45),
        tone(70, 0.5, 'square', volume=0.2, decay=0.8),
    ), fade_out=0.1))

    write_wav('warning.wav', fade(sequence(
        tone(740, 0.11, 'square', volume=0.3),
        silence(0.04),
        tone(880, 0.13, 'square', volume=0.3),
    )))

    write_wav('damage.wav', fade(mix(
        sweep(320, 70, 0.28, volume=0.5),
        noise(0.28, volume=0.3),
    )))

    write_wav('boss_entrance.wav', fade(mix(
        sweep(60, 220, 0.9, volume=0.5),
        tone(55, 0.9, 'square', volume=0.2, decay=1.2),
    ), fade_out=0.15))

    write_wav('level_complete.wav', fade(sequence(
        tone(523, 0.10, 'square', volume=0.3),
        tone(659, 0.10, 'square', volume=0.3),
        tone(784, 0.10, 'square', volume=0.3),
        tone(1046, 0.22, 'square', volume=0.32, decay=0.35),
    )))

    write_wav('victory.wav', fade(sequence(
        tone(523, 0.12, 'square', volume=0.3),
        tone(659, 0.12, 'square', volume=0.3),
        tone(784, 0.12, 'square', volume=0.3),
        tone(1046, 0.14, 'square', volume=0.3),
        silence(0.03),
        tone(784, 0.12, 'square', volume=0.3),
        tone(1046, 0.34, 'square', volume=0.35, decay=0.5),
    )))

    write_wav('game_over.wav', fade(sequence(
        tone(440, 0.18, 'square', volume=0.3),
        tone(349, 0.18, 'square', volume=0.3),
        tone(262, 0.40, 'square', volume=0.35, decay=0.6),
    )))

    write_wav('click.wav', fade(tone(1500, 0.03, 'square', volume=0.35, decay=0.05)))


if __name__ == '__main__':
    build_all()
