"""Wave and level progression (idea.txt §8).

* 4 waves per level: 4 easy / 3 easy + 2 medium / 2 medium + 2 hard / boss.
* Max 3 regular enemies alive; later enemies spawn as earlier ones die.
* The next wave only starts once the current one is cleared, after a 2 s
  announcement.
* Difficulty is data-driven: enemy health, points and speed scale with the
  level, the wave layout stays the same.

The manager only talks to the game controller through a small world interface
(`spawn_enemy`, `announce_wave`, `level_complete`), which keeps it testable
without Ursina.
"""
from __future__ import annotations

import config


class WaveManager:
    def __init__(self, world):
        self.world = world
        self.level = 1
        self.wave_index = 0
        self.queue = []
        self.alive = []
        self.phase = 'idle'    # idle | announce | spawning | done
        self.announce_timer = 0.0
        self.spawn_timer = 0.0
        self.wave_kinds = []

    # -- queries -----------------------------------------------------------
    @property
    def wave_number(self):
        return self.wave_index + 1

    @property
    def boss_wave(self):
        return self.wave_kinds == ['boss'] and self.phase != 'idle'

    @property
    def current_boss(self):
        for enemy in self.alive:
            return enemy
        return None

    def enemies_remaining(self):
        return len(self.queue) + len(self.alive)

    # -- control -----------------------------------------------------------
    def start_level(self, level):
        self.level = level
        self.wave_index = -1
        self.queue = []
        self.alive = []
        self.phase = 'idle'
        self.start_next_wave()

    def start_next_wave(self):
        self.wave_index += 1
        self.wave_kinds = list(config.WAVES[self.level - 1][self.wave_index])
        self.queue = list(self.wave_kinds)
        self.phase = 'announce'
        self.announce_timer = config.WAVE_ANNOUNCE_TIME
        self.spawn_timer = 0.0
        self.world.announce_wave(self.level, self.wave_number, self.boss_wave)

    def on_enemy_defeated(self, enemy):
        if enemy in self.alive:
            self.alive.remove(enemy)

    def clear(self):
        self.alive = []
        self.queue = []
        self.phase = 'idle'

    # -- per-frame update --------------------------------------------------
    def update(self, dt):
        if self.phase == 'announce':
            self.announce_timer -= dt
            if self.announce_timer <= 0:
                self.phase = 'spawning'
                self.spawn_timer = 0.0
        elif self.phase == 'spawning':
            self.spawn_timer -= dt
            max_alive = 1 if self.boss_wave else config.MAX_REGULAR_ENEMIES
            if self.queue and len(self.alive) < max_alive and self.spawn_timer <= 0:
                kind = self.queue.pop(0)
                enemy = self.world.spawn_enemy(kind)
                if enemy is not None:
                    self.alive.append(enemy)
                self.spawn_timer = config.SPAWN_STAGGER
            if not self.queue and not self.alive:
                self._wave_cleared()

    def _wave_cleared(self):
        self.phase = 'done'
        if self.wave_index >= config.WAVES_PER_LEVEL - 1:
            self.world.level_complete()
        else:
            self.start_next_wave()
