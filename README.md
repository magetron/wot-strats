# wot-strats

A World of Tanks strat reference for the loading screen. Type a map name and it shows that map's slide from
each StratSketch strat you've imported, one tab per strat, on the full-resolution map.

StratSketch slides are untitled and have no per-slide link, which is why this exists.

## Use

- Open `WoT Strats.lnk` (or `.venv\Scripts\pythonw -m strats app`).
- Type a map name anywhere; `1`–`9` switch strat; scroll or `+` `−` zoom, drag to pan, `0` fits.
- **Strats…** (top right): paste a StratSketch link to import it, or refresh, rename, reorder and remove strats.

## Set up on a new PC

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m strats shortcut
.venv\Scripts\python -m strats import https://stratsketch.com/<code> --label "Heavy"
```

Windows only (Edge WebView2, through pywebview). Imported strats, map images and the built page (`data/`, `maps/`,
`index.html`) are not in the repo: importing a link fetches what it needs.

## How it works

- `strats/window.py`: the app window and the calls the page can make.
- `strats/importer.py` + `strats/extract.js`: StratSketch has no export, so the app loads the link in a hidden
  browser window and reads the strat from the page, then downloads any map images and base icons it lacks.
  If StratSketch changes its site, `extract.js` is the part that breaks.
- `strats/build.py`: writes `index.html` (one self-contained page) from `data/`, using `strats/page.template.html`.
  `index.html` also opens on its own in a browser, without the Strats panel.

Only World of Tanks strats; slides drawn on a custom image instead of a WoT map are left out.
