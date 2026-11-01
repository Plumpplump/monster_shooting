# AGENTS.md

## Repo state

- The game from `idea.txt` is implemented and playable: a stationary
  mouse-aimed shooting gallery in Python + Ursina (3 levels, 4 enemy types,
  interruptible attacks, 1-player and alternating-2-player modes). "§n" below
  refers to idea.txt sections.
- `README.md` (purpose, install, how to play) exists.
- No git repo, CI or test runner. Verification = `selftest.py` (110 headless
  logic checks) + windowed smoke runs.

## Environment

- Python 3.13.16 + ursina 8.3.0 + Panda3D 1.10.16 live in the sibling venv
  `../ursinavenv`. Run things as `../ursinavenv/bin/python <script>.py`;
  install extra packages with `../ursinavenv/bin/pip install <pkg>`.
- A fresh login shell's `python3` is the system Python and has no ursina —
  always use the venv path explicitly.
- No Ursina reference docs are available offline: when unsure about an API,
  read the installed source at `../ursinavenv/lib/python3.13/site-packages/ursina`.

## macOS quirks (keep the compat entry points!)

`main.py` calls `compat.apply()` before `Ursina()` and `compat.after_start()`
after it. Without these the game is a black window on this machine. What
`compat` fixes and why:

- Ursina's shaders are `#version 130/140`; a Core Profile context
  (`gl-version 3 2`) needs them bumped to 150 — `Shader.compile` is wrapped
  for that.
- `TransparencyAttrib.M_dual` never blends in Core Profile: every model
  (including the pre-made `camera.overlay`, which otherwise paints the whole
  window) is switched to `M_alpha`.
- The startup `aspectRatioChanged` event never fires, leaving `camera.ui`'s
  film size at 1x1 (20x-zoomed UI); `after_start()` calls
  `window.update_aspect_ratio()` once.
- The text shader's `smoothstep(0.5 - fwidth(dist), ...)` misbehaves on this
  driver and renders solid blocks instead of glyphs; `compat` replaces the
  fragment with direct coverage sampling.
- `Ursina` is a singleton — "restart run" must reset state in place (clear
  enemies, timers, effects, statistics, per §14), never recreate the app.
- Headless logic checks work: `Ursina(window_type='none',
  development_mode=False)` plus manual `app.step()` frames (no camera/render
  wiring in this mode). Exit via the module-level `application.quit()` — the
  app object has no `.quit()`.

## Spec details that are easy to get wrong

- Only enemy HP and defeat points scale ×3 per level (`base × 3^(level-1)`);
  attack damage is the same at every level: 10 easy / 13 medium / 17 hard /
  30 boss (§5).
- Level-1 stats: easy 1 HP & 10 pts; medium 3/20; hard 5/40; boss 20/100.
  Hard = 40 pts and alternating two-player runs are flagged planning
  assumptions in §1, not fixed requirements.
- Shooting: 1 damage per shot; fire on mouse-down, then every 0.15 s while
  held; extra clicks must not bypass the cooldown; each shot hits exactly one
  enemy — the closest one under the crosshair (§4).
- Enemy attack cycle: Enter → Wait → Warn → Attack → Recover. A hit during Warn
  cancels the attack (the shot still damages; enemy goes to Recover). Shots at
  other stages don't reset the timer. Only one warning at a time, ≥0.5 s
  between warnings, and pausing freezes all attack timers (§7).
- Waves: 4 per level — 4 easy / 3 easy + 2 medium / 2 medium + 2 hard / boss
  alone. Max 3 regular enemies alive (later ones spawn as others die); 1 s
  entrance immunity; next wave only after the current one is cleared; 2 s wave
  announcement (§8).
- Health: 100 start and cap, persists between waves, restored to 100 after
  levels 1 and 2 only; no pickups (§9).
- Score: points only when an enemy is defeated — no per-hit, miss or bonus
  points; max 330 / 990 / 2,970 / 4,290 across the levels; accuracy shows 0%
  when no shots have been fired (§11).
- Two-player mode is alternating full runs on one mouse. Ranking: completed
  game > score > remaining health > shorter active play time (pause and
  handover excluded) > draw (§3).
- Enemy stats, timings and wave definitions belong in config data; §14 lists
  the expected small systems (game controller, player state, weapon, enemy,
  wave manager, attack coordinator, UI manager, audio manager).
- Don't add enemies or increase attack damage until the full loop has been
  playtested (§8).

## Verification

- `../ursinavenv/bin/python selftest.py` → 110/110 headless checks.
- Windowed smoke run: `MS_AUTOPLAY=1 MS_QUIT_AFTER=260 ../ursinavenv/bin/python
  -u main.py`. Autoplay reaches victory (score 4290) in ~4-5 minutes; the
  level-3 boss (180 HP) alone takes ~1 minute of autoplay shooting, so a run
  that ends mid-boss is normal — not a deadlock.
- The desktop is interactive: stray real clicks and window-close requests land
  on the window during runs. `MS_AUTOPLAY` ignores real input and close
  requests (see main.py); keep that or smoke runs die at random (a stray click
  on the menu QUIT button used to end them).
- Screenshots: `MS_SCREENSHOT_AT=1,20,..` + `MS_SCREENSHOT_DIR=<dir>` (created
  automatically); `GraphicsWindow.save_screenshot` returns False on failure.
