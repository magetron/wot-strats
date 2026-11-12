# wot-strats

World of Tanks strat reference for the loading screen: type a map name, see that map's slide from each
StratSketch strat you've imported.

## Install

Run `WoT-Strats-Setup-<version>.exe` from [Releases](https://github.com/magetron/wot-strats/releases).
Windows 10/11, no admin rights. Uninstall from Settings > Apps.

## Use

- Type a map name. `1`–`9` switch strat, scroll zooms, drag pans, `0` fits.
- **Strats…**: paste a StratSketch link to add it; refresh, rename, reorder or remove strats.

## From source

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m strats app
```

Release build: `pip install -e .[release]`, then `python tools/release.py` and `python tools/check_setup.py`.

## Notes

- World of Tanks strats only.
- Importing reads StratSketch's page (`strats/extract.js`), so it can break if their site changes.
- Strats and maps are kept in `%LOCALAPPDATA%\WoT Strats` when installed, or in this folder when run from source.
