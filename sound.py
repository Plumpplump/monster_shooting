"""Sound manager.  Sounds are optional: if the audio device is missing or a
file cannot be loaded, playback silently degrades to doing nothing.
"""
from __future__ import annotations

import config


class SoundManager:
    def __init__(self):
        self.muted = False
        self.available = False
        self._tracks = {}
        try:
            from ursina import Audio
            for key, (path, _volume) in config.SOUNDS.items():
                track = Audio(path, autoplay=False)
                self._tracks[key] = track
            self.available = True
        except Exception:
            self.available = False

    def play(self, key, volume=1.0):
        if self.muted or not self.available:
            return
        track = self._tracks.get(key)
        if track is None:
            return
        if getattr(track, 'clip', None) is None:  # file failed to load
            return
        try:
            track.volume = volume * config.SOUNDS[key][1]
            track.play()
        except Exception:
            pass

    def toggle_muted(self):
        self.muted = not self.muted
        return not self.muted
