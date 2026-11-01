"""Headless self-test for Monster Shooting Challenge.

Runs the real game logic inside Ursina's windowless mode and drives
``game.update(dt)`` frame by frame, exactly like the windowed build does.

Usage:
    ../ursinavenv/bin/python selftest.py

Exit code 0 = all checks passed.
"""
from __future__ import annotations

import sys

import compat

compat.apply()

from ursina import Text, Ursina        # noqa: E402

app = Ursina(window_type='none', development_mode=False)

import config                          # noqa: E402
from game import Game                  # noqa: E402
from player import PlayerState, compare_players   # noqa: E402

FRAME = 1 / 60
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    if cond:
        print(f'[PASS] {name}')
    else:
        print(f'[FAIL] {name}   -- {detail}')


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def setup_playing(g, level=1):
    g.mode = 1
    g.player_index = 0
    g._clear_run()
    g.player.reset()
    g.level = level
    g.state = 'playing'
    g.fire_cd = 0.0
    g.firing = False
    g.ui.show_gameplay()
    g.waves.start_level(level)


def run(g, seconds, hook=None):
    for i in range(int(round(seconds / FRAME))):
        g.update(FRAME)
        if hook:
            hook(g, (i + 1) * FRAME)


def shoot_now(g, position):
    g.fire_cd = 0.0
    g.shoot(position)


def kill_everything(g, max_seconds=600, stop_at_level_complete=False):
    """Play through the current run, one-shotting every enemy on sight."""
    for _ in range(int(max_seconds / FRAME)):
        if g.state == 'level_complete':
            if stop_at_level_complete:
                break
            g.continue_to_next_level()
            continue
        if g.state != 'playing':
            break
        for enemy in list(g.enemies):
            if enemy.alive:
                shoot_now(g, enemy.position)
        g.update(FRAME)


def kill_until(g, predicate, max_seconds=600):
    for _ in range(int(max_seconds / FRAME)):
        if predicate() or g.state != 'playing':
            break
        for enemy in list(g.enemies):
            if enemy.alive:
                shoot_now(g, enemy.position)
        g.update(FRAME)


def text_in(entity, needle):
    if isinstance(entity, Text) and needle in (entity.text or ''):
        return True
    for child in getattr(entity, 'children', []):
        if text_in(child, needle):
            return True
    return False


# ======================================================================
# 1. configuration / spec numbers
# ======================================================================
def test_config():
    kinds = config.ENEMY_TYPES
    check('L1 easy = 1 hp / 10 pts', (kinds['easy']['hp'], kinds['easy']['points']) == (1, 10))
    check('L1 medium = 3 hp / 20 pts', (kinds['medium']['hp'], kinds['medium']['points']) == (3, 20))
    check('L1 hard = 5 hp / 40 pts', (kinds['hard']['hp'], kinds['hard']['points']) == (5, 40))
    check('L1 boss = 20 hp / 100 pts', (kinds['boss']['hp'], kinds['boss']['points']) == (20, 100))
    check('attack damage fixed at every level',
          [kinds[k]['damage'] for k in ('easy', 'medium', 'hard', 'boss')] == [10, 13, 17, 30])
    check('level scaling is x3 per level',
          [config.HP_SCALE_PER_LEVEL ** (n - 1) for n in (1, 2, 3)] == [1, 3, 9])
    check('L3 boss hp = 180', kinds['boss']['hp'] * 9 == 180)

    layouts = config.WAVES[0]
    check('waves per level = 4', len(config.WAVES) == 3 and all(len(w) == 4 for w in config.WAVES))
    check('wave 1 = 4 easy', layouts[0] == ['easy'] * 4)
    check('wave 2 = 3 easy + 2 medium', sorted(layouts[1]) == sorted(['easy'] * 3 + ['medium'] * 2))
    check('wave 3 = 2 medium + 2 hard', sorted(layouts[2]) == sorted(['medium'] * 2 + ['hard'] * 2))
    check('wave 4 = boss alone', layouts[3] == ['boss'])

    def level_max(level):
        factor = config.HP_SCALE_PER_LEVEL ** (level - 1)
        return sum(kinds[kind]['points'] * factor
                   for wave in config.WAVES[level - 1] for kind in wave)

    maxima = [level_max(i) for i in (1, 2, 3)]
    check('max score per level = 330 / 990 / 2970', maxima == [330, 990, 2970], str(maxima))
    check('grand total = 4290', sum(maxima) == 4290)
    total_enemies = sum(len(w) for waves in config.WAVES for w in waves)
    check('42 enemies in a full run', total_enemies == 42, str(total_enemies))

    a = PlayerState('A')
    check('accuracy is 0% with no shots', a.accuracy == 0.0)

    check('two players start fresh', PlayerState().hp == 100 and PlayerState().score == 0)


def test_ranking_unit():
    a, b = PlayerState('A'), PlayerState('B')
    a.completed, b.completed = True, False
    b.score = 9999
    check('completed beats higher score', compare_players(a, b) == 0)
    a.completed = b.completed = True
    check('higher score wins', compare_players(a, b) == 1)
    b.score = a.score = 0
    b.hp = 50
    check('higher health breaks ties', compare_players(a, b) == 0)
    b.hp = a.hp = 80
    a.play_time, b.play_time = 100.0, 99.0
    check('shorter play time wins', compare_players(a, b) == 1)
    b.play_time = 100.0
    check('identical runs are a draw', compare_players(a, b) is None)


# ======================================================================
# 2. shooting
# ======================================================================
def test_shooting():
    g = Game()
    setup_playing(g)
    p = g.player
    check('no shots = 0% accuracy', p.accuracy == 0.0)

    g.shoot((0.0, 0.40))
    check('shot fires when cooldown is ready', p.shots == 1)
    g.shoot((0.0, 0.40))
    g.shoot((0.0, 0.40))
    check('extra clicks cannot bypass the cooldown', p.shots == 1, f'shots={p.shots}')

    run(g, config.FIRE_COOLDOWN + 0.01)
    g.shoot((0.0, 0.40))
    check('next shot allowed after 0.15 s', p.shots == 2, f'shots={p.shots}')
    check('career accuracy counts hits/shots', p.hits == 0 and p.accuracy == 0.0)

    # hold to fire
    setup_playing(g)
    p = g.player
    g.on_key('left mouse down')
    check('mouse-down fires immediately', p.shots == 1, f'shots={p.shots}')
    run(g, 1.0)
    check('holding fires every ~0.15 s', 6 <= p.shots <= 8, f'shots={p.shots}')
    g.on_key('left mouse up')
    held = p.shots
    run(g, 0.5)
    check('releasing the button stops the fire', p.shots == held, f'{p.shots} vs {held}')


def test_hit_selection_and_scoring():
    g = Game()
    setup_playing(g, 1)
    p = g.player
    e = g.spawn_enemy('easy')
    e.set_position(0.0, 0.0)
    shoot_now(g, (0.0, 0.0))
    check('shot on target defeats 1 hp enemy', p.score == 10 and p.hits == 1 and p.shots == 1)
    check('defeated enemy removed from play', e not in g.enemies and not e.alive)
    check('wave tracking updated', e not in g.waves.alive)

    # depth: overlapping enemies, the front-most (newest) is hit
    setup_playing(g, 3)
    back = g.spawn_enemy('medium')
    back.set_position(0.1, 0.0)
    front = g.spawn_enemy('medium')
    front.set_position(0.1, 0.0)
    check('newest enemy is in front', front.depth < back.depth)
    shoot_now(g, (0.1, 0.0))
    check('shot hits the front-most enemy', front.hp == front.max_hp - 1 and back.hp == back.max_hp)
    check('level 3 medium has 27 hp (3*3^2)', front.max_hp == 27, str(front.max_hp))

    # hp / points scaling at level 3 with an easy enemy
    setup_playing(g, 3)
    p = g.player
    e = g.spawn_enemy('easy')
    e.set_position(0.0, 0.0)
    check('level 3 easy has 9 hp', e.max_hp == 9)
    for _ in range(8):
        shoot_now(g, (0.0, 0.0))
    check('8 shots do not defeat a 9 hp enemy', e.alive and e.hp == 1)
    shoot_now(g, (0.0, 0.0))
    check('9th shot defeats it and scores 90', not e.alive and p.score == 90)


# ======================================================================
# 3. attack cycle / interruption / warnings
# ======================================================================
def test_attack_cycle():
    g = Game()
    setup_playing(g, 1)
    p = g.player
    e = g.spawn_enemy('easy')
    run(g, 0.5)
    check('no attack activity during entrance', e.state == 'enter')
    run(g, 1.0)
    check('enters wait after the entrance period', e.state == 'wait')
    hp = p.hp
    run(g, 3.9)
    check('starts warning after its wait time', e.state == 'warn')
    check('no damage yet while warning', p.hp == hp)
    run(g, 2.3)
    check('easy attack hits for 10 after the warning', p.hp == hp - 10, f'hp={p.hp}')
    check('enemy recovers after attacking', e.state == 'recover')
    run(g, 3.4)
    check('attack cycle repeats (back to wait)', e.state == 'wait')


def test_interrupt():
    g = Game()
    setup_playing(g, 1)
    p = g.player
    e = g.spawn_enemy('medium')
    run(g, 5.6)
    check('medium enemy warns at the expected time', e.state == 'warn')
    hp_before = p.hp
    shoot_now(g, e.position)
    check('shot during warning still damages', e.hp == e.max_hp - 1)
    check('warning is interrupted -> recover', e.state == 'recover')
    check('attack coordinator released', g.coordinator.active is None)
    check('warning ring hidden', not e.warn_ring.enabled)
    run(g, 3.0)
    check('interrupted attack never fires', p.hp == hp_before)
    check('enemy eventually returns to wait', e.state in ('wait', 'recover'))


def test_no_timer_reset_on_hit():
    g = Game()
    setup_playing(g, 1)
    p = g.player
    e = g.spawn_enemy('medium')
    run(g, 2.0)
    check('enemy waiting', e.state == 'wait')
    timer_before = e.timer
    score_before = p.score
    shoot_now(g, e.position)
    check('hit during wait deals damage', e.hp == e.max_hp - 1)
    check('no points for a non-defeating hit', p.score == score_before)
    check('hit does not reset the wait timer', e.state == 'wait' and e.timer >= timer_before)


def test_one_warning_at_a_time():
    g = Game()
    setup_playing(g, 1)
    for _ in range(3):
        g.spawn_enemy('easy')
    starts = []
    seen = set()
    violations = []

    def hook(g, t):
        warning = [e for e in g.enemies if e.state == 'warn']
        if len(warning) > 1:
            violations.append(t)
        for e in warning:
            if id(e) not in seen:
                seen.add(id(e))
                starts.append(t)

    run(g, 25.0, hook=hook)
    # the player may run out of hp here, that's fine - we only watch warnings
    check('never more than one attacker warning', not violations, str(violations[:3]))
    check('several warnings happened', len(starts) >= 2, str(starts))
    gaps = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
    check('warnings are at least 0.5 s apart', all(gp >= config.WARN_GAP - 1e-6 for gp in gaps), str(gaps))


# ======================================================================
# 4. waves / levels / health
# ======================================================================
def test_spawn_limit_and_announcement():
    g = Game()
    setup_playing(g, 1)
    check('wave announcement is shown', g.ui.announce_text.enabled and g.ui._announce_t > 0)
    peak = [0]

    def hook(g, t):
        peak[0] = max(peak[0], sum(1 for e in g.enemies if e.alive))

    run(g, 6.0, hook=hook)
    check('at most 3 regular enemies at once', peak[0] <= 3, f'peak={peak[0]}')
    check('wave 2 does not start before wave 1 is cleared',
          g.waves.wave_number == 1 and g.waves.queue == ['easy'])


def test_health_persistence_and_level_heal():
    g = Game()
    setup_playing(g, 1)
    p = g.player
    run(g, 9.4)
    check('first enemy attack took 10 hp', p.hp == 90, f'hp={p.hp}')
    kill_until(g, lambda: g.waves.wave_number == 2 and g.waves.phase == 'announce')
    check('health persists into the next wave', p.hp == 90, f'hp={p.hp}')
    kill_everything(g, stop_at_level_complete=True)
    check('level 1 cleared with perfect score 330',
          g.state == 'level_complete' and p.score == 330,
          f'state={g.state} score={p.score}')
    check('health restored to 100 after level 1', p.hp == 100)
    g.continue_to_next_level()
    check('level 2 starts', g.state == 'playing' and g.level == 2)


def test_full_run_scores():
    g = Game()
    g.start_new_match(1)
    g.begin_run()
    level_scores = []
    seen_levels = set()
    guard = 0
    while g.state in ('playing', 'level_complete') and guard < 60 * 60 * 10:
        if g.state == 'level_complete':
            if g.level not in seen_levels:
                seen_levels.add(g.level)
                level_scores.append(g.player.score)
            g.continue_to_next_level()
            continue
        for enemy in list(g.enemies):
            if enemy.alive:
                shoot_now(g, enemy.position)
        g.update(FRAME)
        guard += 1

    check('full run reaches the summary screen', g.state == 'summary', f'state={g.state}')
    p = g.player
    if p.completed:
        level_scores.append(p.score)   # level 3 ends directly with victory
    check('victory is recorded', p.completed)
    check('cumulative score after each level = 330 / 1320 / 4290',
          level_scores == [330, 1320, 4290], str(level_scores))
    check('final score is the 4290 maximum', p.score == 4290, str(p.score))
    check('42 enemies defeated', p.enemies_defeated == 42, str(p.enemies_defeated))
    check('never lost health when one-shotting everything', p.hp == 100, str(p.hp))
    check('summary screen is visible', g.ui.screens['summary'].enabled)
    check('victory text shown', text_in(g.ui.dynamic['summary'], 'VICTORY'))


def test_boss_bar():
    g = Game()
    setup_playing(g, 1)
    boss = g.spawn_enemy('boss')
    g.update(FRAME)
    check('boss health bar appears', g.ui.boss_box.enabled)
    check('boss bar shows 20 / 20', g.ui.boss_hp_text.text == '20 / 20', g.ui.boss_hp_text.text)
    while boss.alive and g.player.shots < 200:
        shoot_now(g, boss.position)
    g.update(FRAME)
    check('boss bar hides after the boss dies', not g.ui.boss_box.enabled)
    check('boss defeat scores 100', g.player.score == 100, str(g.player.score))
    check('boss removed from the live boss slot', g.boss is None)


# ======================================================================
# 5. pause / restart / menus
# ======================================================================
def test_pause_freezes_everything():
    g = Game()
    setup_playing(g, 1)
    e = g.spawn_enemy('easy')
    run(g, 5.5)
    check('enemy warning running before pause', e.state == 'warn', e.state)
    g.pause()
    check('game reports paused', g.state == 'paused' and g.ui.screens['pause'].enabled)
    snapshot = (e.state, round(e.timer, 6), g.player.hp, round(g.fire_cd, 6), round(g.player.play_time, 6))
    run(g, 1.0)
    now = (e.state, round(e.timer, 6), g.player.hp, round(g.fire_cd, 6), round(g.player.play_time, 6))
    check('pause freezes enemy + player timers', snapshot == now, f'{snapshot} vs {now}')
    g.resume()
    check('resume returns to play', g.state == 'playing' and not g.ui.screens['pause'].enabled)
    run(g, 2.0)
    check('attack fires after resume', g.player.hp == 90, f'hp={g.player.hp}')


def test_restart_resets_run():
    g = Game()
    setup_playing(g, 1)
    run(g, 3.2)
    check('wave 1 enemies spawned', len(g.enemies) > 0)
    old_enemies = list(g.enemies)
    g.player.score = 77
    g.player.take_damage(30)
    g._restart_current_run()
    check('restart destroys old enemies', len(g.enemies) == 0 and all(not e.alive for e in old_enemies))
    check('restart resets the player', g.player.score == 0 and g.player.hp == 100
          and g.player.shots == 0 and g.player.play_time == 0)
    check('restart returns to level 1 wave 1',
          g.level == 1 and g.waves.level == 1 and g.waves.wave_number == 1 and g.state == 'playing')
    check('restart shows the HUD again', g.ui.hud.enabled)


def test_menu_flow():
    g = Game()
    check('starts at the main menu', g.state == 'menu' and g.ui.screens['main_menu'].enabled)
    check('HUD hidden in menu', not g.ui.hud.enabled and not g.ui.crosshair.root.enabled)
    g.toggle_sound()
    g.toggle_sound()
    g.show_how_to_play()
    check('how-to-play screen', g.state == 'how_to' and g.ui.screens['how_to_play'].enabled)
    g.back_to_menu()
    g.start_new_match(1)
    check('ready screen after choosing 1 player',
          g.state == 'ready' and g.ui.screens['ready'].enabled and g.mode == 1)
    g.begin_run()
    check('HUD + crosshair visible in game',
          g.ui.hud.enabled and g.ui.crosshair.root.enabled
          and not any(s.enabled for s in g.ui.screens.values()))
    g.pause()
    g.pause_restart()
    check('confirmation dialog opens', g.ui.confirm_screen.enabled)
    g.on_key('escape')
    check('escape closes the confirmation but stays paused',
          not g.ui.confirm_screen.enabled and g.state == 'paused')
    g.on_key('escape')
    check('escape resumes the game', g.state == 'playing')
    g.pause()
    g.pause_main_menu()
    g.ui.hide_confirm()
    g.back_to_menu()
    check('back at the main menu', g.state == 'menu' and not g.ui.hud.enabled)


def test_two_player_match():
    g = Game()
    g.start_new_match(2)
    check('2P match starts with player 1', g.player_index == 0 and g.mode == 2)
    g.begin_run()
    kill_everything(g)
    check('player 1 finishes with victory', g.state == 'summary' and g.players[0].completed)
    check('player 1 score kept', g.players[0].score == 4290)
    g.next_player()
    check('handover to player 2', g.player_index == 1 and g.state == 'ready')
    g.begin_run()
    check('player 2 starts fresh', g.player.score == 0 and g.player.hp == 100)
    kill_everything(g)
    check('player 2 finishes', g.state == 'summary' and g.players[1].completed)
    g.show_results()
    check('results screen shown', g.state == 'results' and g.ui.screens['results'].enabled)
    check('identical runs are reported as a draw', text_in(g.ui.dynamic['results'], 'DRAW'))
    g.players[1].play_time += 3.0
    g.show_results()
    check('shorter play time wins the match',
          text_in(g.ui.dynamic['results'], 'WINNER: PLAYER 1'))

    # ranking edge: completion beats a bigger score
    g.players[0].completed = False
    g.players[0].score = 0
    g.players[1].score = 4000
    g.show_results()
    check('completed game beats raw score', text_in(g.ui.dynamic['results'], 'WINNER: PLAYER 2'))


def main():
    test_config()
    test_ranking_unit()
    test_shooting()
    test_hit_selection_and_scoring()
    test_attack_cycle()
    test_interrupt()
    test_no_timer_reset_on_hit()
    test_one_warning_at_a_time()
    test_spawn_limit_and_announcement()
    test_health_persistence_and_level_heal()
    test_full_run_scores()
    test_boss_bar()
    test_pause_freezes_everything()
    test_restart_resets_run()
    test_menu_flow()
    test_two_player_match()

    passed = sum(1 for _, ok in RESULTS if ok)
    failed = [name for name, ok in RESULTS if not ok]
    print(f'\n===== {passed}/{len(RESULTS)} checks passed =====')
    if failed:
        print('failed checks:')
        for name in failed:
            print('  -', name)
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
