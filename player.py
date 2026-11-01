"""Per-run player state and the two-player ranking rules (idea.txt §3, §11)."""
from __future__ import annotations

import config


class PlayerState:
    def __init__(self, name='Player 1'):
        self.name = name
        self.reset()

    def reset(self):
        self.max_hp = config.PLAYER_MAX_HP
        self.hp = self.max_hp
        self.score = 0
        self.shots = 0
        self.hits = 0
        self.enemies_defeated = 0
        self.play_time = 0.0    # active play time only (pause/handover excluded)
        self.level = 1
        self.wave = 1
        self.completed = False

    # -- events ------------------------------------------------------------
    def record_shot(self, hit):
        self.shots += 1
        if hit:
            self.hits += 1

    def add_kill(self, points):
        self.enemies_defeated += 1
        self.score += points

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        return self.hp <= 0

    def heal_full(self):
        self.hp = self.max_hp

    # -- stats -------------------------------------------------------------
    @property
    def alive(self):
        return self.hp > 0

    @property
    def accuracy(self):
        """Hits / shots in percent; 0% when no shot has been fired (§11)."""
        if not self.shots:
            return 0.0
        return self.hits / self.shots * 100.0

    @property
    def play_time_text(self):
        minutes, seconds = divmod(int(self.play_time), 60)
        return f'{minutes}:{seconds:02d}'


def compare_players(a, b):
    """Return the index of the winner, or None for a draw (idea.txt §3).

    Ranking: completed game > score > remaining health > shorter active play
    time > draw.
    """
    if a.completed != b.completed:
        return 0 if a.completed else 1
    if a.score != b.score:
        return 0 if a.score > b.score else 1
    if a.hp != b.hp:
        return 0 if a.hp > b.hp else 1
    if abs(a.play_time - b.play_time) > config.DRAW_TIME_EPSILON:
        return 0 if a.play_time < b.play_time else 1
    return None
