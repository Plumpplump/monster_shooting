"""All screens and in-game interface (idea.txt §12).

Layering note: for UI entities parented to `camera.ui`, a **smaller (more
negative) z is nearer to the UI camera**, i.e. drawn in front.  The layout is:

    gameplay (z ~ 2 .. 0.05)  <  HUD (0)  <  effects (-1)  <  crosshair (-2)
    <  screens (-2.5, content -3)  <  confirm dialog (-4)

Screens fully replace the HUD while they are visible, so nothing depends on
hairline z differences.
"""
from __future__ import annotations

from ursina import Button, Entity, Text, camera, color, destroy, window

import config

HUD_Z = 0
CROSSHAIR_Z = -2
SCREEN_Z = -2.5
CONFIRM_Z = -4


def rgba(values, alpha=None):
    a = values[3] if len(values) > 3 else 1.0
    if alpha is not None:
        a = alpha
    return color.rgba(values[0], values[1], values[2], a)


class Crosshair:
    """The mouse crosshair with a shot/impact pulse."""

    def __init__(self):
        self.root = Entity(parent=camera.ui, name='crosshair', z=CROSSHAIR_Z,
                           add_to_scene_entities=False, enabled=False)
        edge = rgba((0.06, 0.06, 0.08), 0.85)
        core = rgba((1, 1, 1), 0.95)
        gap, length = 0.010, 0.020
        offset = gap + length / 2
        self._bars = []
        for dx, dy, rotate in ((0, offset, 0), (0, -offset, 0),
                               (-offset, 0, 90), (offset, 0, 90)):
            outline = Entity(parent=self.root, model='quad', color=edge,
                             position=(dx, dy, 0), rotation_z=rotate,
                             scale=(length + 0.006, 0.008, 1))
            bar = Entity(parent=self.root, model='quad', color=core,
                         position=(dx, dy, -0.01), rotation_z=rotate,
                         scale=(length, 0.0028, 1))
            self._bars.append((outline, bar))
        Entity(parent=self.root, model='quad', color=edge, scale=(0.0062, 0.0062, 1))
        Entity(parent=self.root, model='quad', color=core, position=(0, 0, -0.01),
               scale=(0.0028, 0.0028, 1))
        self.pulse_t = 0.0

    def set_visible(self, visible):
        self.root.enabled = visible

    def set_position(self, x, y):
        self.root.x = x
        self.root.y = y

    def pulse(self):
        self.pulse_t = 0.10

    def update(self, dt):
        if self.pulse_t > 0:
            self.pulse_t = max(0.0, self.pulse_t - dt)
        k = self.pulse_t / 0.10
        scale = 1.0 + 0.30 * k
        self.root.scale = (scale, scale, 1)


class UIManager:
    def __init__(self, game):
        self.game = game
        self.crosshair = Crosshair()
        self.screens = {}          # name -> container entity
        self.dynamic = {}          # name -> content entity (rebuildable)
        self._fullscreen = []      # quads that must follow the window aspect
        self.announce_text = None
        self.announce_sub = None
        self._announce_t = 0.0
        self._hp_frac = 1.0
        self._build_hud()
        self._build_screens()

    def _aspect(self):
        """Window aspect ratio with a safe fallback (headless / zero-size)."""
        try:
            aspect = window.aspect_ratio
            if aspect and aspect == aspect and aspect > 0.1:
                return aspect
        except Exception:
            pass
        return 16 / 9

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _wrap(self, callback):
        def handler():
            self.game.sound.play('click')
            if callback:
                callback()
        return handler

    def _button(self, parent, text, y, callback, x=0.0,
                scale=(0.30, 0.062), text_size=1.05):
        return Button(
            text=text, parent=parent, scale=scale, position=(x, y),
            color=rgba(config.UI['button']),
            highlight_color=rgba(config.UI['button_hover']),
            pressed_color=rgba(config.UI['button_pressed']),
            text_size=text_size, radius=0.09,
            on_click=self._wrap(callback),
        )

    def _label(self, parent, text, y, scale=1.0, values=None, x=0.0, z=-0.5):
        return Text(text=text, parent=parent, origin=(0, 0),
                    position=(x, y, z), scale=scale,
                    color=rgba(values or config.UI['text']))

    def _fullscreen_quad(self, parent, values, z=0.0, texture=None):
        quad = Entity(parent=parent, model='quad', texture=texture, color=rgba(values),
                      scale=(self._aspect(), 1.0, 1), position=(0, 0, z))
        self._fullscreen.append(quad)
        return quad

    def _screen(self, name, dim_values=None):
        """Create a screen container with a full-screen dim layer and a content
        child that sits in front of it."""
        container = Entity(parent=camera.ui, name=f'screen_{name}', z=SCREEN_Z,
                           enabled=False, add_to_scene_entities=False)
        if dim_values is not None:
            self._fullscreen_quad(container, dim_values, z=0.0)
        content = Entity(parent=container, name='content', z=-0.5,
                         add_to_scene_entities=False)
        self.screens[name] = container
        return content

    def _rebuild(self, name):
        old = self.dynamic.get(name)
        if old is not None:
            destroy(old)
        screen = self.screens[name]
        content = Entity(parent=screen, name='dynamic', z=-0.6,
                         add_to_scene_entities=False)
        self.dynamic[name] = content
        return content

    def show(self, name):
        """Show one screen (hides all others) and hide the HUD."""
        self.hide_all_screens()
        self.screens[name].enabled = True
        self.hud.enabled = False
        self.crosshair.set_visible(False)

    def hide_all_screens(self):
        for screen in self.screens.values():
            screen.enabled = False
        self.confirm_screen.enabled = False

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _build_hud(self):
        self.hud = Entity(parent=camera.ui, name='hud', z=HUD_Z,
                          enabled=False, add_to_scene_entities=False)
        hud = self.hud

        self.hp_bar_bg = Entity(parent=hud, model='quad', scale=(0.40, 0.045, 1),
                                color=rgba(config.UI['hp_bar_bg']))
        self.hp_bar_fill = Entity(parent=hud, model='quad', origin=(-0.5, 0),
                                  color=rgba(config.UI['hp_good']), z=-0.01)
        self.hp_text = Text(parent=hud, origin=(0, 0), scale=0.95,
                            color=rgba(config.UI['text']), z=-0.02)
        self.score_text = Text(parent=hud, origin=(0, 0), scale=1.05,
                               color=rgba(config.UI['text']), z=-0.02)
        self.level_text = Text(parent=hud, origin=(0, 0), scale=0.9,
                               color=rgba(config.UI['text_dim']), z=-0.02)
        self.player_text = Text(parent=hud, origin=(0, 0), scale=1.0,
                                color=rgba(config.UI['accent']), z=-0.02)
        self.player_text.enabled = False

        # boss bar (top of the screen)
        self.boss_box = Entity(parent=hud, z=-0.3, enabled=False)
        self.boss_label = Text(parent=self.boss_box, text='BOSS', origin=(0, 0),
                               position=(0, 0.477), scale=1.25,
                               color=rgba(config.UI['danger']))
        Entity(parent=self.boss_box, model='quad', scale=(0.90, 0.034, 1),
               color=rgba(config.UI['hp_bar_bg']), position=(0, 0.44))
        self.boss_fill = Entity(parent=self.boss_box, model='quad', origin=(-0.5, 0),
                                color=rgba(config.UI['danger']),
                                position=(-0.897 / 2, 0.44), scale=(0.897, 0.026, 1))
        self.boss_hp_text = Text(parent=self.boss_box, origin=(0, 0),
                                 position=(0, 0.44), scale=0.75,
                                 color=rgba(config.UI['text']), z=-0.01)

        # wave announcement
        self.announce_text = Text(parent=hud, origin=(0, 0), position=(0, 0.17),
                                  scale=1.9, color=rgba(config.UI['accent']), z=-0.05)
        self.announce_sub = Text(parent=hud, origin=(0, 0), position=(0, 0.10),
                                 scale=1.0, color=rgba(config.UI['text_dim']), z=-0.05)
        self.announce_text.enabled = False
        self.announce_sub.enabled = False

    def _layout_hud(self):
        half = self._aspect() / 2
        left = -half + 0.035
        right = half - 0.035
        bottom = -0.455

        self.hp_bar_bg.position = (left + 0.20, bottom + 0.028, 0)
        self.hp_bar_fill.position = (left + 0.004, bottom + 0.028, -0.01)
        self.hp_bar_fill.scale = (0.392 * self._hp_frac, 0.03, 1)
        self.hp_text.x = left + self.hp_text.width / 2
        self.hp_text.y = bottom + 0.058

        self.score_text.x = right - self.score_text.width / 2
        self.score_text.y = bottom + 0.02

        self.level_text.x = 0
        self.level_text.y = bottom + 0.02

        self.player_text.x = left + self.player_text.width / 2
        self.player_text.y = 0.455

    # ------------------------------------------------------------------
    # screens
    # ------------------------------------------------------------------
    def _build_screens(self):
        self._build_main_menu()
        self._build_how_to_play()
        self._build_ready()
        self._build_pause()
        self._build_confirm()
        self._build_level_complete()
        self._build_summary()
        self._build_results()

    def _build_main_menu(self):
        content = self._screen('main_menu', dim_values=config.UI['bg'])
        self._label(content, config.GAME_TITLE.upper(), 0.34, 2.1,
                    config.UI['accent'])
        self._label(content, 'Three levels - four monster types - one or two players',
                    0.265, 0.85, config.UI['text_dim'])
        self._main_menu_buttons = {}
        self._main_menu_buttons['one_player'] = self._button(
            content, 'ONE PLAYER', 0.12, lambda: self.game.start_new_match(1))
        self._main_menu_buttons['two_players'] = self._button(
            content, 'TWO PLAYERS', 0.035, lambda: self.game.start_new_match(2))
        self._button(content, 'HOW TO PLAY', -0.05, self.game.show_how_to_play)
        self._main_menu_buttons['sound'] = self._button(
            content, 'SOUND: ON', -0.135, self.game.toggle_sound)
        self._button(content, 'QUIT', -0.22, self.game.quit)
        self._label(content, 'Move the mouse to aim - hold left click to fire - Esc to pause',
                    -0.40, 0.75, config.UI['text_dim'])

    def set_sound_label(self, sound_on):
        button = self._main_menu_buttons.get('sound')
        if button and button.text_entity:
            button.text_entity.text = f'SOUND: {"ON" if sound_on else "OFF"}'

    def _build_how_to_play(self):
        content = self._screen('how_to_play', dim_values=config.UI['bg'])
        self._label(content, 'HOW TO PLAY', 0.40, 1.6, config.UI['accent'])
        lines = (
            'Aim with the mouse. Hold the left mouse button to shoot\n'
            '(one shot every 0.15 s - extra clicks cannot fire faster).\n'
            '\n'
            'Each level has four waves. Clear every monster in a wave\n'
            'to advance; clear the fourth wave to finish the level.\n'
            '\n'
            'A monster flashes and shows a red ring before it attacks.\n'
            'Shoot it during the warning to interrupt the attack!\n'
            '\n'
            'Every shot deals 1 damage, defeating monsters scores points.\n'
            'You start with 100 health; attacks cost 10-30 health.\n'
            'Health carries between waves and is restored after levels 1-2.\n'
            '\n'
            'Two players share one mouse and play one full run each.'
        )
        self._label(content, lines, 0.14, 0.83, config.UI['text'])
        self._button(content, 'BACK', -0.40, self.game.back_to_menu)

    def _build_ready(self):
        content = self._screen('ready', dim_values=config.UI['dim'])
        self._ready_title = self._label(content, 'PLAYER 1', 0.22, 1.9,
                                        config.UI['accent'])
        self._ready_info = self._label(content, '', 0.10, 1.0, config.UI['text'])
        self._ready_hint = self._label(content, '', 0.02, 0.85, config.UI['text_dim'])
        self._button(content, 'START', -0.12, self.game.begin_run)
        self._button(content, 'MAIN MENU', -0.235, self.game.back_to_menu,
                     scale=(0.24, 0.05), text_size=0.9)

    def show_ready(self, player_name, level, handover=False):
        self.show('ready')
        self._ready_title.text = player_name.upper()
        self._ready_info.text = f'Full run - starting from level {level}'
        if handover:
            self._ready_hint.text = 'Hand the mouse to the other player, then click START.'
        else:
            self._ready_hint.text = 'Get comfortable - click START when you are ready.'

    def _build_pause(self):
        content = self._screen('pause', dim_values=config.UI['dim'])
        self._label(content, 'PAUSED', 0.14, 2.0, config.UI['text'])
        self._button(content, 'RESUME', 0.01, self.game.resume)
        self._button(content, 'RESTART RUN', -0.075, self.game.pause_restart)
        self._button(content, 'MAIN MENU', -0.16, self.game.pause_main_menu)

    def _build_confirm(self):
        content = self._screen('confirm', dim_values=(0, 0, 0, 0.55))
        self.confirm_screen = self.screens['confirm']
        self.confirm_screen.z = CONFIRM_Z
        Entity(parent=content, model='quad', scale=(0.78, 0.34, 1), z=-0.3,
               color=rgba(config.UI['panel']))
        self._confirm_message = Text(parent=content, origin=(0, 0),
                                     position=(0, 0.06, -0.4),
                                     scale=1.0, color=rgba(config.UI['text']))
        self._confirm_yes = Button(text='YES', parent=content, scale=(0.22, 0.055),
                                   position=(-0.14, -0.08, -0.4),
                                   color=rgba(config.UI['button']),
                                   highlight_color=rgba(config.UI['button_hover']),
                                   pressed_color=rgba(config.UI['button_pressed']),
                                   text_size=0.95, radius=0.09)
        self._confirm_cancel = Button(text='CANCEL', parent=content, scale=(0.22, 0.055),
                                      position=(0.14, -0.08, -0.4),
                                      color=rgba(config.UI['button']),
                                      highlight_color=rgba(config.UI['button_hover']),
                                      pressed_color=rgba(config.UI['button_pressed']),
                                      text_size=0.95, radius=0.09,
                                      on_click=self._wrap(self.hide_confirm))
        self.confirm_screen.enabled = False

    def confirm_visible(self):
        return self.confirm_screen.enabled

    def show_confirm(self, message, on_yes):
        self._confirm_message.text = message
        self._confirm_yes.on_click = self._wrap(lambda: (self.hide_confirm(), on_yes()))
        self.confirm_screen.enabled = True

    def hide_confirm(self):
        self.confirm_screen.enabled = False

    def _build_level_complete(self):
        content = self._screen('level_complete', dim_values=config.UI['dim'])
        self._level_complete_title = self._label(content, 'LEVEL 1 COMPLETE!', 0.20, 1.9,
                                                 config.UI['accent'])
        self._level_complete_score = self._label(content, '', 0.08, 1.1, config.UI['text'])
        self._level_complete_heal = self._label(content, '', 0.0, 0.9, config.UI['text_dim'])
        self._label(content, 'The next level begins with four new waves.',
                    -0.07, 0.85, config.UI['text_dim'])
        self._button(content, 'CONTINUE', -0.20, self.game.continue_to_next_level)

    def show_level_complete(self, level, score, healed):
        self.show('level_complete')
        self._level_complete_title.text = f'LEVEL {level} COMPLETE!'
        self._level_complete_score.text = f'Score: {score}'
        self._level_complete_heal.text = ('Health restored to 100 HP' if healed
                                          else 'Health carries over to the next level.')

    def _build_summary(self):
        self._screen('summary', dim_values=config.UI['dim'])

    def show_summary(self, title, values, stats_lines, buttons):
        """Run-end screen: game over or victory.

        `buttons` is a list of (label, callback) tuples.
        """
        self.show('summary')
        content = self._rebuild('summary')
        self._label(content, title, 0.28, 2.0, values)
        self._label(content, '\n'.join(stats_lines), 0.04, 0.95, config.UI['text'])
        y = -0.17
        for label, callback in buttons:
            self._button(content, label, y, callback)
            y -= 0.085

    def _build_results(self):
        self._screen('results', dim_values=config.UI['bg'])

    def show_results(self, names, columns, winner_text):
        """Two-player comparison screen. `columns` is a list of line-lists."""
        self.show('results')
        content = self._rebuild('results')
        self._label(content, 'MATCH RESULTS', 0.36, 1.8, config.UI['accent'])
        for i, name in enumerate(names):
            x = -0.42 if i == 0 else 0.42
            self._label(content, name, 0.26, 1.3, config.UI['text'], x=x)
            self._label(content, '\n'.join(columns[i]), 0.03, 0.9,
                        config.UI['text_dim'], x=x)
        self._label(content, winner_text, -0.20, 1.5, config.UI['accent'])
        self._button(content, 'PLAY ANOTHER MATCH', -0.31, self.game.start_new_match_again)
        self._button(content, 'MAIN MENU', -0.40, self.game.back_to_menu,
                     scale=(0.24, 0.05), text_size=0.9)

    # ------------------------------------------------------------------
    # in-game API
    # ------------------------------------------------------------------
    def show_gameplay(self):
        self.hide_all_screens()
        self.hud.enabled = True
        self.crosshair.set_visible(True)

    def hide_all(self):
        self.hide_all_screens()
        self.hud.enabled = False
        self.crosshair.set_visible(False)

    def announce(self, level, wave, boss):
        self._announce_t = config.WAVE_ANNOUNCE_TIME
        if boss:
            self.announce_text.text = f'LEVEL {level}'
            self.announce_sub.text = 'BOSS WAVE'
        else:
            self.announce_text.text = f'LEVEL {level}'
            self.announce_sub.text = f'WAVE {wave}'
        self.announce_text.enabled = True
        self.announce_sub.enabled = True
        self.announce_text.color = rgba(config.UI['accent'], 1.0)
        self.announce_sub.color = rgba(config.UI['text'], 1.0)

    def update(self, dt, player=None, level=1, wave=1, boss=None, show_player_label=False):
        self.crosshair.update(dt)
        self._layout_hud()
        aspect = self._aspect()
        for quad in self._fullscreen:
            quad.scale = (aspect, 1.0, 1)

        if self._announce_t > 0:
            self._announce_t = max(0.0, self._announce_t - dt)
            alpha = min(1.0, self._announce_t / 0.4)       # fade out at the end
            fade_in = min(1.0, (config.WAVE_ANNOUNCE_TIME - self._announce_t) / 0.25)
            alpha = min(alpha, fade_in)
            self.announce_text.color = rgba(config.UI['accent'], alpha)
            self.announce_sub.color = rgba(config.UI['text'], alpha)
            if self._announce_t <= 0:
                self.announce_text.enabled = False
                self.announce_sub.enabled = False

        if player is None:
            return
        self._hp_frac = max(0.0, player.hp / player.max_hp)
        self.hp_bar_fill.scale = (0.392 * self._hp_frac, 0.03, 1)
        if self._hp_frac > 0.6:
            self.hp_bar_fill.color = rgba(config.UI['hp_good'])
        elif self._hp_frac > 0.3:
            self.hp_bar_fill.color = rgba(config.UI['hp_mid'])
        else:
            self.hp_bar_fill.color = rgba(config.UI['hp_low'])
        self.hp_text.text = f'{player.hp} / {player.max_hp} HP'
        self.score_text.text = f'SCORE {player.score}'
        self.level_text.text = f'LEVEL {level} - WAVE {wave}'
        self.player_text.text = player.name.upper()
        self.player_text.enabled = show_player_label

        if boss is not None:
            self.boss_box.enabled = True
            frac = max(0.0, min(1.0, boss.hp / boss.max_hp))
            self.boss_fill.scale = (0.897 * frac, 0.026, 1)
            self.boss_hp_text.text = f'{max(0, boss.hp)} / {boss.max_hp}'
        else:
            self.boss_box.enabled = False

    def set_crosshair(self, x, y):
        self.crosshair.set_position(x, y)

    def crosshair_pulse(self, hit):
        self.crosshair.pulse()
