"""Game controller: state machine, shooting, scoring and run flow.

Everything that changes over time is driven by ``update(dt)`` with an explicit
dt, so the whole simulation can run head-less (see ``selftest.py``) and pausing
is simply "do not call simulate".

States: menu | how_to | ready | playing | paused | level_complete | summary |
results
"""
from __future__ import annotations

import random

from ursina import mouse

import config
from attack_coordinator import AttackCoordinator
from effects import Effects
from enemy import Enemy
from player import PlayerState, compare_players
from sound import SoundManager
from ui import UIManager
from waves import WaveManager

MAX_FRAME_DT = 0.05


class Game:
    def __init__(self):
        self.sound = SoundManager()
        self.effects = Effects()
        self.ui = UIManager(self)
        self.coordinator = AttackCoordinator()

        self.mode = 1                       # number of players: 1 or 2
        self.players = [PlayerState(config.PLAYER_NAMES[0]),
                        PlayerState(config.PLAYER_NAMES[1])]
        self.player_index = 0
        self.waves = WaveManager(self)

        self.enemies = []
        self.boss = None
        self.spawn_count = 0
        self.level = 1
        self.state = 'menu'

        self.firing = False
        self.fire_cd = 0.0

        self.ui.show('main_menu')

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------
    @property
    def player(self):
        return self.players[self.player_index]

    @property
    def two_player(self):
        return self.mode >= 2

    def aim_position(self):
        try:
            return (mouse.x, mouse.y)
        except Exception:
            return (0.0, 0.0)

    def playfield_for(self, kind):
        """(x_min, x_max, y_min, y_max) of the area enemies may occupy."""
        field = config.BOSS_PLAYFIELD if kind == 'boss' else config.PLAYFIELD
        aspect = self.ui._aspect()
        half = max(0.2, aspect / 2 - field['side_margin'])
        return (-half, half, field['bottom'], field['top'])

    # ------------------------------------------------------------------
    # frame update / input
    # ------------------------------------------------------------------
    def update(self, dt):
        dt = min(max(dt, 0.0), MAX_FRAME_DT)
        if self.state == 'playing':
            self._simulate(dt)

        in_game = self.state in ('playing', 'paused', 'level_complete', 'summary')
        player = self.player if in_game else None
        wave = self.waves.wave_number if self.waves.wave_kinds else 1
        boss = self.boss if self.state == 'playing' else None
        self.ui.update(dt, player=player, level=self.level, wave=wave, boss=boss,
                       show_player_label=(self.two_player and self.state == 'playing'
                                          and player is not None))

    def _simulate(self, dt):
        player = self.player
        player.play_time += dt
        self.coordinator.update(dt)

        if self.fire_cd > 0:
            self.fire_cd = max(0.0, self.fire_cd - dt)
        if self.firing and self.fire_cd <= 0:
            self.shoot()

        self.waves.update(dt)
        for enemy in list(self.enemies):
            if enemy.alive:
                enemy.update(dt)
        self.effects.update(dt)

        x, y = self.aim_position()
        self.ui.set_crosshair(x, y)

    def on_key(self, key):
        if key == 'escape':
            if self.state == 'playing':
                self.pause()
            elif self.state == 'paused':
                if self.ui.confirm_visible():
                    self.ui.hide_confirm()
                else:
                    self.resume()
        elif key == 'left mouse down':
            if self.state == 'playing':
                self.firing = True
                self.shoot()
        elif key == 'left mouse up':
            self.firing = False

    # ------------------------------------------------------------------
    # shooting
    # ------------------------------------------------------------------
    def shoot(self, position=None):
        """Fire one shot.  Extra calls inside the cooldown do nothing (§4)."""
        if self.state != 'playing' or self.fire_cd > 0:
            return
        self.fire_cd = config.FIRE_COOLDOWN
        x, y = position if position is not None else self.aim_position()

        hits = [e for e in self.enemies if e.alive and e.contains_point(x, y)]
        # smaller z == nearer to the camera == the one drawn on top
        target = min(hits, key=lambda e: e.depth) if hits else None

        self.player.record_shot(target is not None)
        self.sound.play('shot')
        self.effects.muzzle_flash()
        self.ui.crosshair_pulse(target is not None)
        self.effects.hit_marker((x, y), on_target=target is not None)

        if target is None:
            return
        defeated = target.hit(1)
        if not defeated:
            self.sound.play('hit')

    # ------------------------------------------------------------------
    # world callbacks (used by Enemy and WaveManager)
    # ------------------------------------------------------------------
    def playfield_for_enemy(self, kind):
        return self.playfield_for(kind)

    def spawn_enemy(self, kind):
        self.spawn_count += 1
        enemy = Enemy(kind, self.level, self, index=self.spawn_count)
        x, y = self._pick_spawn_point(kind)
        enemy.set_position(x, y)
        self.enemies.append(enemy)
        if kind == 'boss':
            self.boss = enemy
        return enemy

    def _pick_spawn_point(self, kind):
        x_min, x_max, y_min, y_max = self.playfield_for(kind)
        best = None
        for _ in range(24):
            if kind == 'boss':
                # boss enters roughly in the middle
                span = (x_max - x_min)
                x = random.uniform(-span * 0.2, span * 0.2)
            else:
                x = random.uniform(x_min, x_max)
            y = random.uniform(y_min, y_max)
            best = (x, y)
            if all((enemy.position[0] - x) ** 2 + (enemy.position[1] - y) ** 2
                   >= config.SPAWN_MIN_DISTANCE ** 2
                   for enemy in self.enemies if enemy.alive):
                break
        return best

    def on_warning_started(self, enemy):
        pass    # hook: currently only the enemy's own visuals are used

    def on_enemy_attack(self, enemy):
        if self.state != 'playing':
            return
        player = self.player
        player.take_damage(enemy.damage)
        self.sound.play('damage')
        self.effects.damage_flash()
        if not player.alive:
            self.end_run(victory=False)

    def on_enemy_defeated(self, enemy):
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        if enemy is self.boss:
            self.boss = None
        self.waves.on_enemy_defeated(enemy)
        self.player.add_kill(enemy.points)
        self.sound.play('boss_defeat' if enemy.kind == 'boss' else 'defeat')

    def announce_wave(self, level, wave, boss):
        self.ui.announce(level, wave, boss)
        if boss:
            self.sound.play('boss_entrance')

    def level_complete(self):
        if self.state != 'playing':
            return
        self.player.level = self.level
        self.firing = False
        if self.level >= config.LEVELS:
            self.end_run(victory=True)
            return
        healed = config.HEAL_BETWEEN_LEVELS
        if healed:
            self.player.heal_full()
        self.sound.play('level_complete')
        self.state = 'level_complete'
        self.ui.show_level_complete(self.level, self.player.score, healed)

    # ------------------------------------------------------------------
    # run / match flow
    # ------------------------------------------------------------------
    def start_new_match(self, player_count):
        self.mode = player_count
        self.players = [PlayerState(config.PLAYER_NAMES[0]),
                        PlayerState(config.PLAYER_NAMES[1])]
        self.player_index = 0
        self.state = 'ready'
        self._clear_run()
        self.ui.show_ready(self.player.name, 1, handover=False)

    def start_new_match_again(self):
        self.start_new_match(self.mode)

    def next_player(self):
        self.player_index = 1
        self.state = 'ready'
        self._clear_run()
        self.ui.show_ready(self.player.name, 1, handover=True)

    def begin_run(self):
        self._start_run()

    def _start_run(self):
        self._clear_run()
        self.player.reset()
        self.level = 1
        self.fire_cd = 0.0
        self.firing = False
        self.coordinator.clear()
        self.state = 'playing'
        self.ui.show_gameplay()
        self.waves.start_level(self.level)

    def continue_to_next_level(self):
        if self.state != 'level_complete':
            return
        self.level += 1
        self.player.level = self.level
        self.state = 'playing'
        self.ui.show_gameplay()
        self.waves.start_level(self.level)

    def pause(self):
        if self.state != 'playing':
            return
        self.firing = False
        self.state = 'paused'
        self.ui.show('pause')

    def resume(self):
        if self.state != 'paused':
            return
        self.state = 'playing'
        self.ui.show_gameplay()

    def pause_restart(self):
        self.ui.show_confirm('Restart this run? Your progress will be lost.',
                             self._restart_current_run)

    def _restart_current_run(self):
        self.state = 'playing'
        self._start_run()

    def pause_main_menu(self):
        self.ui.show_confirm('Return to the main menu? Your run will be lost.',
                             self.back_to_menu)

    def back_to_menu(self):
        self.firing = False
        self._clear_run()
        self.state = 'menu'
        self.ui.show('main_menu')

    def show_how_to_play(self):
        self.state = 'how_to'
        self.ui.show('how_to_play')

    def toggle_sound(self):
        on = self.sound.toggle_muted()
        self.ui.set_sound_label(on)

    def quit(self):
        try:
            import ursina.application as application
            application.quit()
        except Exception:
            raise SystemExit(0)

    # ------------------------------------------------------------------
    # end of a run
    # ------------------------------------------------------------------
    def end_run(self, victory):
        self.firing = False
        player = self.player
        player.completed = bool(victory)
        player.level = self.level
        self.sound.play('victory' if victory else 'game_over')
        self.state = 'summary'

        if victory:
            lines = [
                f'Final score: {player.score}',
                'All three levels completed!',
                f'Enemies defeated: {player.enemies_defeated}',
                f'Accuracy: {player.accuracy:.0f}%  ({player.hits}/{player.shots} shots)',
                f'Play time: {player.play_time_text}',
                f'Health remaining: {player.hp}',
            ]
        else:
            lines = [
                f'Final score: {player.score}',
                f'Fell during level {self.level}, wave {self.waves.wave_number}',
                f'Enemies defeated: {player.enemies_defeated}',
                f'Accuracy: {player.accuracy:.0f}%  ({player.hits}/{player.shots} shots)',
                f'Play time: {player.play_time_text}',
            ]

        if victory:
            title, title_color = 'VICTORY!', config.UI['accent']
        else:
            title, title_color = 'GAME OVER', config.UI['danger']

        if self.two_player and self.player_index == 0:
            buttons = [('PLAYER 2 - GET READY', self.next_player),
                       ('MAIN MENU', self.back_to_menu)]
        elif self.two_player:
            buttons = [('SHOW RESULTS', self.show_results),
                       ('MAIN MENU', self.back_to_menu)]
        else:
            buttons = [('PLAY AGAIN', self._start_run),
                       ('MAIN MENU', self.back_to_menu)]

        self.ui.show_summary(title, title_color, lines, buttons)

    def show_results(self):
        a, b = self.players
        names = [a.name.upper(), b.name.upper()]
        columns = [
            [f'Score: {a.score}',
             f'Game completed: {"yes" if a.completed else "no"}',
             f'Health left: {a.hp}',
             f'Accuracy: {a.accuracy:.0f}%',
             f'Enemies defeated: {a.enemies_defeated}',
             f'Play time: {a.play_time_text}'],
            [f'Score: {b.score}',
             f'Game completed: {"yes" if b.completed else "no"}',
             f'Health left: {b.hp}',
             f'Accuracy: {b.accuracy:.0f}%',
             f'Enemies defeated: {b.enemies_defeated}',
             f'Play time: {b.play_time_text}'],
        ]
        winner = compare_players(a, b)
        if winner is None:
            winner_text = 'DRAW!'
        else:
            winner_text = f'WINNER: {names[winner]}'
        self.state = 'results'
        self.ui.show_results(names, columns, winner_text)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _clear_run(self):
        for enemy in self.enemies:
            if enemy.container is not None:
                from ursina import destroy
                destroy(enemy.container)
                enemy.container = None
            enemy.alive = False
        self.enemies = []
        self.boss = None
        self.effects.clear()
        self.waves.clear()
        self.coordinator.clear()
