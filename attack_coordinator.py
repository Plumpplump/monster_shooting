"""Attack warning arbitration (idea.txt §7).

Only one enemy may be in its warning stage at a time and there must be at least
``WARN_GAP`` seconds between the end of one warning and the start of the next.
The coordinator owns no timers: the game controller advances ``now``.
"""
from __future__ import annotations

import config


class AttackCoordinator:
    def __init__(self, gap=config.WARN_GAP):
        self.gap = gap
        self.now = 0.0
        self.active = None       # enemy currently in its warning stage
        self.next_allowed = 0.0  # earliest time another warning may start

    def update(self, dt):
        self.now += dt

    def request(self, enemy) -> bool:
        """Called by an enemy that finished its wait period."""
        if self.active is not None or self.now < self.next_allowed:
            return False
        self.active = enemy
        return True

    def warning_ended(self, enemy):
        """Called when a warning ends, whether the attack fired or was interrupted."""
        if self.active is enemy:
            self.active = None
            self.next_allowed = self.now + self.gap

    def clear(self):
        self.active = None
        self.now = 0.0
        self.next_allowed = 0.0
