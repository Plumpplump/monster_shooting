"""Central configuration: rules, enemy stats, timings and wave definitions.

Everything tunable lives here (idea.txt section 14: "store enemy values and wave
definitions in configuration data").  Only enemy health and defeat points scale
with the level (x3 per level); attack damage is identical at every level.
"""
from __future__ import annotations

GAME_TITLE = 'Monster Shooting Challenge'
WINDOW_SIZE = (1280, 720)

# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------
PLAYER_MAX_HP = 100
FIRE_COOLDOWN = 0.15        # seconds between shots while the button is held
MAX_REGULAR_ENEMIES = 3     # on screen at the same time (boss waves: 1)
ENTRANCE_TIME = 1.0         # enemies cannot attack during this period
WAVE_ANNOUNCE_TIME = 2.0    # seconds the "Level x - Wave y" banner stays up
WARN_GAP = 0.5              # minimum gap between two attack warnings (§7)
SPAWN_STAGGER = 0.35        # seconds between spawns inside one wave
HEAL_BETWEEN_LEVELS = True  # levels 1 and 2 restore health to 100 (§9)
LEVELS = 3
WAVES_PER_LEVEL = 4
DRAW_TIME_EPSILON = 0.05    # play-time difference below this counts as a draw

# Playfield bounds in UI coordinates.  Y is fixed (-0.5 .. 0.5 across the
# window); X bounds are computed from the window aspect ratio at runtime.
PLAYFIELD = dict(top=0.30, bottom=-0.24, side_margin=0.14)
BOSS_PLAYFIELD = dict(top=0.36, bottom=-0.28, side_margin=0.22)
SPAWN_MIN_DISTANCE = 0.24   # try to keep new spawns this far from live enemies

# --------------------------------------------------------------------------
# enemy types (level-1 values)
# --------------------------------------------------------------------------
ENEMY_TYPES = {
    'easy': dict(
        label='E', hp=1, points=10, damage=10,
        wait=4.0, warn=2.0, recover=3.0,
        size=0.09, model='circle', hit_shape='circle',
        color=(0.30, 0.82, 0.38), label_color=(1, 1, 1),
        movement='still', speed=0.0,
        bob_amplitude=0.014, bob_speed=1.6,          # gentle idle sway
    ),
    'medium': dict(
        label='M', hp=3, points=20, damage=13,
        wait=3.5, warn=1.7, recover=2.5,
        size=0.125, model='quad', hit_shape='square',
        color=(0.24, 0.55, 0.95), label_color=(1, 1, 1),
        movement='horizontal', speed=0.085,
    ),
    'hard': dict(
        label='H', hp=5, points=40, damage=17,
        wait=3.0, warn=1.4, recover=2.0,
        size=0.13, model='diamond', hit_shape='diamond',
        color=(1.0, 0.55, 0.13), label_color=(0.12, 0.10, 0.06),
        movement='horizontal', speed=0.15,
    ),
    'boss': dict(
        label='BOSS', hp=20, points=100, damage=30,
        wait=3.0, warn=1.8, recover=2.5,
        size=0.30, model='circle', hit_shape='circle',
        color=(0.63, 0.33, 0.90), label_color=(1, 1, 1),
        movement='boss', speed=0.05,
    ),
}
HP_SCALE_PER_LEVEL = 3              # hp and points: base * 3 ** (level - 1)
LEVEL_SPEED_MULT = (1.0, 1.35, 1.75)  # movement speed multiplier per level
BOSS_SPEED = {1: 0.035, 2: 0.09, 3: 0.17}   # UI units per second, per level
BOSS_DIR_CHANGE = {1: None, 2: None, 3: 2.4}  # L3: flip direction every n sec


def _level_waves():
    """4 waves per level (§8): 4 easy / 3 easy + 2 medium / 2 medium + 2 hard / boss."""
    return [
        ['easy', 'easy', 'easy', 'easy'],
        ['easy', 'easy', 'easy', 'medium', 'medium'],
        ['medium', 'medium', 'hard', 'hard'],
        ['boss'],
    ]


WAVES = [_level_waves() for _ in range(LEVELS)]

# --------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------
UI = dict(
    bg=(0.055, 0.06, 0.09, 1.0),
    dim=(0.0, 0.0, 0.0, 0.62),          # behind menus
    panel=(0.11, 0.12, 0.17, 1.0),
    text=(0.93, 0.94, 0.97, 1.0),
    text_dim=(0.70, 0.72, 0.80, 1.0),
    button=(0.17, 0.19, 0.27, 1.0),
    button_hover=(0.31, 0.44, 0.78, 1.0),
    button_pressed=(0.24, 0.34, 0.62, 1.0),
    accent=(1.0, 0.79, 0.28, 1.0),
    hp_good=(0.33, 0.85, 0.42, 1.0),
    hp_mid=(0.95, 0.77, 0.20, 1.0),
    hp_low=(0.93, 0.28, 0.25, 1.0),
    hp_bar_bg=(0.10, 0.10, 0.14, 0.9),
    danger=(0.96, 0.24, 0.22, 1.0),
    hud_bg=(0.08, 0.09, 0.13, 0.72),
)

SOUNDS = {
    'shot': ('sounds/shot.wav', 0.35),
    'hit': ('sounds/hit.wav', 0.30),
    'defeat': ('sounds/defeat.wav', 0.55),
    'boss_defeat': ('sounds/boss_defeat.wav', 0.60),
    'warning': ('sounds/warning.wav', 0.45),
    'damage': ('sounds/damage.wav', 0.55),
    'boss_entrance': ('sounds/boss_entrance.wav', 0.60),
    'level_complete': ('sounds/level_complete.wav', 0.50),
    'victory': ('sounds/victory.wav', 0.55),
    'game_over': ('sounds/game_over.wav', 0.50),
    'click': ('sounds/click.wav', 0.35),
}

PLAYER_NAMES = ('Player 1', 'Player 2')
