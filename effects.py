"""Short-lived visual feedback: hit markers, floating points, muzzle flash,
particles, screen-edge damage flash.

Every effect is a small entity with a lifetime; they are advanced from the
game's update loop with the same dt the simulation uses, so pausing freezes
them too.
"""
from __future__ import annotations

import math
import random

from ursina import Entity, Text, camera, color, destroy, window

import config


def rgba(values, alpha=1.0):
    return color.rgba(values[0], values[1], values[2], alpha)


class Effects:
    def __init__(self, parent=None):
        self.layer = Entity(parent=parent or camera.ui, name='effects_layer', z=-1, add_to_scene_entities=False)
        self._items = []

    # -- lifecycle ---------------------------------------------------------
    def clear(self):
        for item in self._items:
            destroy(item['entity'])
        self._items = []

    def update(self, dt):
        live = []
        for item in self._items:
            item['elapsed'] += dt
            t = min(1.0, item['elapsed'] / item['duration'])
            try:
                item['tick'](item['entity'], t)
            except Exception:
                t = 1.0
            if t >= 1.0:
                destroy(item['entity'])
            else:
                live.append(item)
        self._items = live
        if len(live) > 300:            # safety valve, keeps frame time stable
            for item in live[:-300]:
                destroy(item['entity'])
            self._items = live[-300:]

    def _add(self, entity, duration, tick):
        self._items.append(dict(entity=entity, elapsed=0.0, duration=duration, tick=tick))
        return entity

    # -- effects -----------------------------------------------------------
    def hit_marker(self, position, on_target=True):
        """Small X marker at the crosshair when a shot connects."""
        col = (1.0, 0.35, 0.3, 1.0) if not on_target else (1.0, 1.0, 1.0, 1.0)
        holder = Entity(parent=self.layer, position=(position[0], position[1], -0.06))
        for angle in (45, -45):
            Entity(parent=holder, model='quad', color=rgba(col),
                   rotation_z=angle, scale=(0.055, 0.010))

        def tick(ent, t):
            s = 1.0 + 0.35 * t
            ent.scale = (s, s, 1)
            for child in ent.children:
                child.color = rgba(col, 1.0 - t)
        self._add(holder, 0.14, tick)

    def floating_text(self, position, text, values, scale=1.1):
        t = Text(text=text, parent=self.layer, origin=(0, 0),
                 position=(position[0], position[1] + 0.05, -0.04),
                 scale=scale, color=rgba(values))
        start_y = position[1] + 0.05

        def tick(ent, k):
            ent.y = start_y + 0.10 * k
            ent.color = rgba(values, 1.0 - k * k)
        self._add(t, 0.9, tick)

    def muzzle_flash(self):
        """Short yellow flash at the bottom-centre of the screen."""
        e = Entity(parent=self.layer, model='quad', texture='radial_gradient',
                   color=rgba((1.0, 0.85, 0.45), 0.9), scale=(0.14, 0.14, 1),
                   position=(0, -0.44, -0.03), rotation_z=random.uniform(0, 360))

        def tick(ent, t):
            s = 0.14 * (1.0 - 0.45 * t)
            ent.scale = (s, s * 1.2, 1)
            ent.color = rgba((1.0, 0.85, 0.45), 0.9 * (1.0 - t))
        self._add(e, 0.07, tick)

    def damage_flash(self):
        """Red vignette pulse around the screen edges when the player is hurt."""
        aspect = max(1.0, window.aspect_ratio)
        e = Entity(parent=self.layer, model='quad', texture='vignette',
                   color=rgba((1.0, 0.18, 0.12), 0.0), scale=(aspect + 0.02, 1.02, 1),
                   position=(0, 0, 0.5))

        def tick(ent, t):
            alpha = 0.85 * (1.0 - t)
            ent.color = rgba((1.0, 0.18, 0.12), alpha)
            s = 1.0 + 0.03 * t
            ent.scale = ((aspect + 0.02) * s, 1.02 * s, 1)
        self._add(e, 0.55, tick)

    def burst(self, position, values, count=12, speed=0.30):
        """Particle burst when an enemy is defeated."""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            velocity = random.uniform(0.35, 1.0) * speed
            vx, vy = math.cos(angle) * velocity, math.sin(angle) * velocity
            size = random.uniform(0.012, 0.026)
            particle = Entity(parent=self.layer, model='quad', texture='radial_gradient',
                              color=rgba(values, 1.0),
                              position=(position[0], position[1]))

            def make_tick(vx=vx, vy=vy, size=size):
                def tick(ent, t):
                    ent.x = position[0] + vx * t * 0.9
                    ent.y = position[1] + vy * t * 0.9 - 0.12 * t * t
                    s = size * (1.0 - t)
                    ent.scale = (s, s, 1)
                    ent.color = rgba(values, 1.0 - t)
                return tick
            self._add(particle, random.uniform(0.35, 0.6), make_tick())

    def defeat_ring(self, position, values):
        e = Entity(parent=self.layer, model='quad', texture='circle_hollow',
                   color=rgba(values, 0.9), position=(position[0], position[1], -0.02),
                   scale=(0.05, 0.05, 1))

        def tick(ent, t):
            s = 0.05 + 0.30 * t
            ent.scale = (s, s, 1)
            ent.color = rgba(values, 0.9 * (1.0 - t))
        self._add(e, 0.35, tick)
