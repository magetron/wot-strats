# wot-strats

Patrick's in-game strat reference (see README.md). He wants it simple, like banker: no extra features or
on-page instructions unless he asks. Keep replies short.

- Run: `.venv/Scripts/python -m strats app`. Other commands: `import <link> [--label X]`, `build`, `shortcut`.
- The window (`strats/window.py`) follows banker's `window.py`: pywebview on Edge WebView2, its own taskbar identity,
  a local server on port 54331 serving this folder, failures logged to `data/strats.log` (pythonw has no console).
- The page is `strats/page.template.html`; `build.py` inlines fonts and data into `index.html`. After editing the
  template run `python -m strats build` (the app also rebuilds when it opens).
- `data/`, `maps/` and `index.html` are fetched or built, and git-ignored. Don't downscale the maps (2880px originals).
- Import reads StratSketch's page internals (`strats/extract.js`: the briefing object via React props, then its
  scene-graph nodes). Check an import against StratSketch's own drawing after changing it.
- To see the real window without clicking through it: start the app with `STRATS_SELFTEST=<link>` set and it submits
  its own Add form; the result lands in `data/strats.log`.
- Release: bump `strats/__init__.py`, then `python tools/release.py` builds `dist/WoT-Strats-Setup-<version>.exe`: one
  PyInstaller exe that is the app and its own per-user installer (`strats/install.py`; named "...Setup..." it installs,
  `uninstall` removes). Packaged, `paths.py` reads its files from the bundle and keeps data/maps/index.html in
  `%LOCALAPPDATA%\WoT Strats` (or beside the exe if strats are already there, as 0.1 did). Run from source,
  everything stays in this folder.
- Before publishing run `python tools/check_setup.py`: it installs, imports and uninstalls with `LOCALAPPDATA`,
  `APPDATA`, `TEMP` redirected under `build/`, a spare port (`WOT_STRATS_PORT`) so the normal app can stay open, the
  exe marked as downloaded (what broke 0.1.0), and its own registry entry (`WOT_STRATS_REGKEY`).
- Keep installs, caches, builds and test copies inside this folder (`.venv`, `build/`, `dist/`); nothing global.
