"""Enemy entity: visuals, movement and the attack cycle (idea.txt §6, §7).

Life cycle of one enemy:

    enter -> wait -> warn -> (attack | interrupted) -> recover -> wait -> ...

A shot during the ``warn`` stage interrupts the attack (the shot still deals
its damage and the enemy goes to ``recover``).  Shots at any other stage do
not touch the attack timer.
"""
from __future__ import annotations

import math
import random

from ursina import Entity, Text, camera, destroy

import config
from effects import rgba


class Enemy:
    def __init__(self, kind, level, world, index=0):
        self.kind = kind
        self.stats = config.ENEMY_TYPES[kind]
        self.level = level
        self.world = world
        self.index = index

        scale_factor = config.HP_SCALE_PER_LEVEL ** (level - 1)
        self.max_hp = self.stats['hp'] * scale_factor
        self.hp = self.max_hp
        self.points = self.stats['points'] * scale_factor
        self.damage = self.stats['damage']
        self.size = self.stats['size']
        self.warn_duration = self.stats['warn']

        self.alive = True
        self.state = 'enter'
        self.timer = 0.0
        self.visual_scale = self.size * 0.35
        self.flash_timer = 0.0
        self.lunge_timer = 0.0
        self.phase = random.uniform(0, math.tau)

        self.base_color = rgba(self.stats['color'])
        self.label_color = rgba(self.stats['label_color'])

        # -- visuals -------------------------------------------------------
        # z note: for UI entities, smaller (more negative) z is nearer to the
        # UI camera, so gameplay sits behind the HUD (z ~ 2..0) and children
        # are layered with slightly decreasing z going towards the viewer.
        self.container = Entity(parent=camera.ui, name=f'{kind}_{index}',
                                z=2.0 - (index % 40) * 0.05)
        self.body = Entity(parent=self.container, model=self.stats['model'],
                           color=self.base_color, scale=(self.visual_scale, self.visual_scale, 1))
        if kind == 'medium':    # an armour plate to make 'M' look sturdier
            self.plate = Entity(parent=self.container, model='quad',
                                color=rgba((0.12, 0.28, 0.55)),
                                scale=(self.size * 0.55, self.size * 0.55, 1), z=-0.01)
        if kind == 'boss':
            self.ring = Entity(parent=self.container, model='quad', texture='circle_hollow',
                               color=rgba((0.85, 0.6, 1.0), 0.85),
                               scale=(self.size * 1.28, self.size * 1.28, 1), z=-0.02)

        label_scale = self.size * (3.0 / 0.3 if kind == 'boss' else 17.0)
        self.label = Text(text=self.stats['label'], parent=self.container, origin=(0, 0),
                          scale=label_scale, color=self.label_color, z=-0.06)

        # health bar above the enemy (the boss uses the big bar on top instead)
        self.hp_bar = None
        if kind != 'boss':
            bar_w = max(0.07, self.size * 1.35)
            bar_h = max(0.012, self.size * 0.13)
            bar_y = self.size * 0.72 + bar_h
            Entity(parent=self.container, model='quad', color=rgba(config.UI['hp_bar_bg']),
                   scale=(bar_w, bar_h, 1), position=(0, bar_y, -0.04))
            self.hp_bar = Entity(parent=self.container, model='quad', color=rgba(config.UI['hp_good']),
                                 origin=(-0.5, 0),
                                 scale=(bar_w - 0.006, bar_h * 0.62, 1),
                                 position=(-(bar_w - 0.006) / 2, bar_y, -0.05))

        # warning ring (hidden until the warning stage starts)
        self.warn_ring = Entity(parent=self.container, model='quad', texture='circle_hollow',
                                color=rgba(config.UI['danger'], 0.85),
                                scale=(self.size * 2.0, self.size * 2.0, 1), z=-0.03,
                                enabled=False)

        # -- movement ------------------------------------------------------
        self.vx = 0.0
        speed_mult = config.LEVEL_SPEED_MULT[level - 1]
        if self.stats['movement'] == 'horizontal':
            self.vx = self.stats['speed'] * speed_mult * random.choice((-1, 1))
        elif self.stats['movement'] == 'boss':
            self.vx = config.BOSS_SPEED[level] * random.choice((-1, 1))
        self.dir_timer = config.BOSS_DIR_CHANGE[level] or 0.0

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    @property
    def position(self):
        return (self.container.x, self.container.y)

    @property
    def depth(self):
        return self.container.z

    def set_position(self, x, y):
        self.container.x = x
        self.container.y = y

    def contains_point(self, px, py):
        """Is the crosshair over this enemy?  Matches the drawn shape."""
        if not self.alive or self.container is None:
            return False
        dx = px - self.container.x
        dy = py - self.container.y
        half = max(self.visual_scale, self.size * 0.35) * 0.5
        shape = self.stats['hit_shape']
        if shape == 'circle':
            return dx * dx + dy * dy <= half * half
        if shape == 'square':
            return abs(dx) <= half and abs(dy) <= half
        return abs(dx) + abs(dy) <= half * 1.15  # diamond

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------
    def hit(self, damage=1):
        """Take one shot.  Returns True if this shot defeated the enemy."""
        if not self.alive:
            return False
        self.hp -= damage
        self.flash_timer = 0.09
        if self.hp_bar is not None:
            self._refresh_hp_bar()
        if self.hp <= 0:
            self.die()
            return True
        if self.state == 'warn':
            # Interrupt: the warning ends, the attack never fires.
            self.world.coordinator.warning_ended(self)
            self._enter_recover()
        return False

    def die(self):
        if not self.alive:
            return
        self.alive = False
        if self.warn_ring is not None:
            self.warn_ring.enabled = False
        if self.state == 'warn':
            self.world.coordinator.warning_ended(self)
        position = self.position
        self.world.effects.defeat_ring(position, self.stats['color'])
        self.world.effects.burst(position, self.stats['color'],
                                 count=26 if self.kind == 'boss' else 12)
        self.world.effects.floating_text(
            position, f'+{self.points}', config.UI['accent'],
            scale=1.4 if self.kind == 'boss' else 1.0)
        if self.container is not None:
            destroy(self.container)
            self.container = None
        self.world.on_enemy_defeated(self)

    def _enter_recover(self):
        self.state = 'recover'
        self.timer = self.stats['recover']
        if self.warn_ring is not None:
            self.warn_ring.enabled = False
        self.body.color = self.base_color
        self._reset_body_scale()

    def _start_warning(self):
        self.state = 'warn'
        self.timer = self.warn_duration
        if self.warn_ring is not None:
            self.warn_ring.enabled = True
        self.world.sound.play('warning')
        self.world.on_warning_started(self)

    def _fire_attack(self):
        self.world.on_enemy_attack(self)
        self.world.coordinator.warning_ended(self)
        self.lunge_timer = 0.28
        self._enter_recover()

    # ------------------------------------------------------------------
    # per-frame update
    # ------------------------------------------------------------------
    def update(self, dt):
        if not self.alive or self.container is None:
            return
        self.phase += dt
        self._update_timers(dt)
        self._update_movement(dt)
        self._update_visuals(dt)

    def _update_timers(self, dt):
        if self.state == 'enter':
            self.timer += dt
            if self.timer >= config.ENTRANCE_TIME:
                self.state = 'wait'
                self.timer = 0.0
        elif self.state == 'wait':
            self.timer += dt
            if self.timer >= self.stats['wait'] and self.world.coordinator.request(self):
                self._start_warning()
        elif self.state == 'warn':
            self.timer -= dt
            if self.timer <= 0:
                self._fire_attack()
        elif self.state == 'recover':
            self.timer -= dt
            if self.timer <= 0:
                self.state = 'wait'
                self.timer = 0.0

    def _update_movement(self, dt):
        if self.stats['movement'] == 'still':
            return
        x_min, x_max, _y_min, _y_max = self.world.playfield_for(self.kind)
        self.container.x += self.vx * dt
        if self.container.x <= x_min:
            self.container.x = x_min
            self.vx = abs(self.vx)
        elif self.container.x >= x_max:
            self.container.x = x_max
            self.vx = -abs(self.vx)
        if self.kind == 'boss' and self.dir_timer:
            self.dir_timer -= dt
            if self.dir_timer <= 0:
                self.dir_timer = config.BOSS_DIR_CHANGE[self.level] * random.uniform(0.75, 1.25)
                self.vx = -self.vx

    def _update_visuals(self, dt):
        # entrance pop-in
        if self.state == 'enter':
            t = min(1.0, self.timer / config.ENTRANCE_TIME)
            eased = 1.0 - (1.0 - t) ** 3
            self.visual_scale = self.size * (0.35 + 0.65 * eased)
        else:
            self.visual_scale = self.size

        # hit flash
        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - dt)
            blend = 0.85 * (self.flash_timer / 0.09)
            self.body.color = color_blend(self.base_color, rgba((1, 1, 1)), blend)
        elif self.state == 'warn':
            pulse = 0.5 + 0.5 * math.sin(self.phase * 12.0)
            blend = 0.15 + 0.45 * pulse
            self.body.color = color_blend(self.base_color, rgba((1, 1, 1)), blend)
        else:
            self.body.color = self.base_color

        # idle bob for the "mostly stationary" easy enemy
        if self.stats['movement'] == 'still':
            self.body.y = self.stats['bob_amplitude'] * math.sin(self.phase * self.stats['bob_speed'])
        else:
            self.body.y = 0.0

        # attack lunge
        if self.lunge_timer > 0:
            self.lunge_timer = max(0.0, self.lunge_timer - dt)
            k = self.lunge_timer / 0.28
            scale = self.visual_scale * (1.0 + 0.18 * k)
        else:
            scale = self.visual_scale
        self.body.scale = (scale, scale, 1)
        if getattr(self, 'plate', None) is not None:
            self.plate.scale = (self.visual_scale * 0.55, self.visual_scale * 0.55, 1)
        if getattr(self, 'ring', None) is not None:
            self.ring.scale = (self.visual_scale * 1.28, self.visual_scale * 1.28, 1)

        # warning ring countdown
        if self.warn_ring is not None and self.warn_ring.enabled:
            frac = max(0.0, self.timer / self.warn_duration)
            s = self.size * (1.15 + 1.05 * frac)
            self.warn_ring.scale = (s, s, 1)
            alpha = 0.45 + 0.45 * (0.5 + 0.5 * math.sin(self.phase * 14.0))
            self.warn_ring.color = rgba(config.UI['danger'], alpha)

    def _reset_body_scale(self):
        self.body.scale = (self.visual_scale, self.visual_scale, 1)

    def _refresh_hp_bar(self):
        frac = max(0.0, self.hp / self.max_hp)
        full_w = max(0.07, self.size * 1.35) - 0.006
        self.hp_bar.scale = (max(0.001, full_w * frac), self.hp_bar.scale_y, 1)
        if frac > 0.6:
            hp_color = config.UI['hp_good']
        elif frac > 0.3:
            hp_color = config.UI['hp_mid']
        else:
            hp_color = config.UI['hp_low']
        self.hp_bar.color = rgba(hp_color)


def color_blend(a, b, k):
    k = max(0.0, min(1.0, k))
    return rgba((( a[0] + (b[0] - a[0]) * k),
                 (a[1] + (b[1] - a[1]) * k),
                 (a[2] + (b[2] - a[2]) * k)), a[3] + (b[3] - a[3]) * k)
