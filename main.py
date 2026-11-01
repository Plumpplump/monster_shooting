"""Entry point: Monster Shooting Challenge.

Run with:  ../ursinavenv/bin/python main.py

Environment hooks used by the automated smoke test (not needed for normal play):
  MS_QUIT_AFTER=<seconds>  quit automatically after N seconds
  MS_AUTOPLAY=1            play a demo run that starts a match and shoots
  MS_SCREENSHOT_AT=a,b,..  save window screenshots at those times (seconds)
  MS_SCREENSHOT_DIR=<dir>  where to write them (default: current directory)
  MS_DEBUG_EXIT=1          trace sys.exit() calls with a stack trace
"""
from __future__ import annotations

import os
import random
import time as std_time

import compat

compat.apply()      # must happen before Ursina() is created

from ursina import Ursina, application, color, time, window   # noqa: E402

import config
from game import Game

if os.environ.get('MS_DEBUG_EXIT'):
    import sys as _sys
    import traceback as _tb
    _real_exit = _sys.exit

    def _traced_exit(*args):
        print(f'[dbg] sys.exit called t={std_time.time() - _START_TIME:.2f}s', args, flush=True)
        _tb.print_stack()
        return _real_exit(*args)

    _sys.exit = _traced_exit


def _quit(reason='requested'):
    print(f'[main] quitting ({reason}) at t={std_time.time() - _START_TIME:.1f}s', flush=True)
    try:
        application.quit()
    except SystemExit:
        raise


_QUIT_AFTER = float(os.environ.get('MS_QUIT_AFTER') or 0) or None
_AUTOPLAY = bool(os.environ.get('MS_AUTOPLAY'))
_START_TIME = std_time.time()

_shot_times = sorted(
    float(part) for part in (os.environ.get('MS_SCREENSHOT_AT') or '').split(',')
    if part.strip()
)
_SHOT_DIR = os.environ.get('MS_SCREENSHOT_DIR') or '.'
if _shot_times:
    os.makedirs(_SHOT_DIR, exist_ok=True)
_shots_done = 0


def _maybe_screenshot():
    global _shots_done
    if _shots_done >= len(_shot_times) or app.win is None:
        return
    elapsed = std_time.time() - _START_TIME
    while _shots_done < len(_shot_times) and elapsed >= _shot_times[_shots_done]:
        from panda3d.core import Filename
        path = os.path.join(_SHOT_DIR, f'ms_{elapsed:06.2f}.png')
        saved = app.win.save_screenshot(Filename(path))
        print(f'[main] screenshot {"->" if saved else "FAILED ->"} {path}', flush=True)
        _shots_done += 1

app = Ursina(
    title=config.GAME_TITLE,
    borderless=False,
    fullscreen=False,
    size=config.WINDOW_SIZE,
    vsync=True,
    development_mode=False,
)
window.color = color.rgb(config.UI['bg'][0], config.UI['bg'][1], config.UI['bg'][2])

# macOS: the 'aspectRatioChanged' event does not fire at startup, so force the
# UI orthographic lens to its correct film size before any UI exists.
compat.after_start()

game = Game()

if _AUTOPLAY:
    # This demo runs on an interactive desktop: stray real clicks, key presses
    # or window-close requests must not derail it (they used to hit the menu
    # QUIT button or close the window mid-run).  Real input is ignored during
    # autoplay; normal play is unaffected.
    app.win.setCloseRequestEvent('ms-autoplay-close-request')
    app.accept('ms-autoplay-close-request',
               lambda: print('[main] ignored window-close request (autoplay)', flush=True))

    def _keep_running_on_close():
        print('[main] ignored userExit during autoplay', flush=True)

    app.userExit = _keep_running_on_close

    from ursina import mouse as _mouse_singleton

    def _ignored_mouse_input(key):
        if 'mouse' in key:
            print(f'[main] ignored {key!r} (autoplay)', flush=True)

    _mouse_singleton.input = _ignored_mouse_input

_auto = {'shoot_t': 0.0, 'retarget': 0.0, 'target': None, 'log_t': 0.0, 'summary_t': 0.0}


def _autoplay():
    _auto['log_t'] += time.dt
    if _auto['log_t'] >= 1.0:
        _auto['log_t'] = 0.0
        p = game.player
        boss = game.boss
        boss_info = 'boss=None'
        if boss is not None:
            pos = ('gone' if boss.container is None
                   else f'({boss.container.x:.2f},{boss.container.y:.2f})')
            boss_info = (f'boss[hp={boss.hp}/{boss.max_hp} state={boss.state} '
                         f'timer={boss.timer:.2f} alive={boss.alive} pos={pos} '
                         f'visual={boss.visual_scale:.3f}]')
        target = _auto['target']
        target_info = 'target=None' if target is None else (
            f'target[id={id(target) % 1000} alive={target.alive} '
            f'same_as_boss={target is boss}]')
        print(f'[autoplay] t={std_time.time() - _START_TIME:6.1f} dt={time.dt:.5f} '
              f'state={game.state} level={game.level} '
              f'wave={game.waves.wave_number} score={p.score} hp={p.hp} '
              f'enemies={len(game.enemies)} coord_active={game.coordinator.active is not None} '
              f'{boss_info} {target_info}', flush=True)
    if game.state == 'menu':
        game.start_new_match(1)
    elif game.state == 'ready':
        game.begin_run()
    elif game.state == 'level_complete':
        game.continue_to_next_level()
    elif game.state == 'summary':
        _auto['summary_t'] += time.dt
        if _auto['summary_t'] > 4.0:
            _auto['summary_t'] = 0.0
            game.back_to_menu()
            game.start_new_match(1)
    elif game.state == 'playing':
        _auto['retarget'] -= time.dt
        if (_auto['retarget'] <= 0 or _auto['target'] is None
                or not _auto['target'].alive):
            alive = [e for e in game.enemies if e.alive]
            _auto['target'] = random.choice(alive) if alive else None
            _auto['retarget'] = 1.2
        if _auto['target'] is not None:
            game.ui.set_crosshair(*_auto['target'].position)
        _auto['shoot_t'] += time.dt
        if _auto['shoot_t'] >= 0.25:
            _auto['shoot_t'] = 0.0
            if _auto['target'] is not None:
                game.shoot(_auto['target'].position)


def update():
    try:
        _maybe_screenshot()
        game.update(time.dt)
        if _AUTOPLAY:
            _autoplay()
    except Exception:
        import traceback
        traceback.print_exc()
        raise
    if _QUIT_AFTER and std_time.time() - _START_TIME > _QUIT_AFTER:
        _quit('quit timer')


def input(key):
    if _AUTOPLAY:
        print(f'[main] ignored input {key!r} (autoplay)', flush=True)
        return
    game.on_key(key)


try:
    app.run()
except SystemExit as exc:
    print(f'[main] SystemExit: {exc!r}', flush=True)
except BaseException:
    import traceback
    traceback.print_exc()
    raise
print('[main] main loop ended cleanly', flush=True)
