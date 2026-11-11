"""Import a strat from a StratSketch link.

StratSketch has no export, so the app loads the link in a hidden browser window (the same WebView2 the
app window uses), waits for the strat to finish loading, and reads it out with extract.js. Then it
fetches whatever that strat needs that isn't here yet (map images, base icons, the map pack) and rebuilds
the page.
"""
import json
import re
import threading
import time
import urllib.request

from .build import build, read_json, write_json
from .paths import MAPS, NAMES, PACK, PKG, SITE, STRATS_DIR, STRATS_LIST

_LINK = re.compile(r"^(?:https?://)?(?:www\.)?stratsketch\.com/([A-Za-z0-9_-]{6,20})/?(?:[?#].*)?$")
_CODE = re.compile(r"^[A-Za-z0-9_-]{8,20}$")
_busy = threading.Lock()


class ImportError_(Exception):
    """Something the user should be told in plain words."""


def parse_link(text: str) -> str:
    text = (text or "").strip()
    m = _LINK.match(text)
    if m:
        return m.group(1)
    if _CODE.match(text):
        return text
    raise ImportError_("That doesn't look like a StratSketch link (https://stratsketch.com/…).")


def _download(url: str, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def read_page(window, timeout=45) -> dict:
    """Wait for the strat in `window` (a webview on stratsketch.com/<code>) to finish loading, then read it."""
    script = (PKG / "extract.js").read_text(encoding="utf-8")
    deadline = time.time() + timeout
    last, steady, probe = None, 0, {}
    while time.time() < deadline:
        time.sleep(0.7)
        try:
            if not window.evaluate_js("typeof window.__stratProbe === 'function'"):
                window.evaluate_js(script)
            probe = json.loads(window.evaluate_js("window.__stratProbe()") or "{}")
        except Exception:
            continue  # page still navigating
        if not probe.get("found") or not probe.get("n") or probe.get("maps", 0) == 0:
            if "404" in (probe.get("title") or ""):
                raise ImportError_("StratSketch says that strat doesn't exist.")
            last, steady = None, 0
            continue
        now = (probe["n"], probe["ents"], probe["maps"])
        steady = steady + 1 if now == last else 0
        last = now
        if steady >= 2:  # same slide and item counts three polls running
            break
    else:
        raise ImportError_("StratSketch didn't finish loading that strat. Check the link opens in a browser.")
    if probe.get("game") != "wot":
        raise ImportError_(f"That strat is for another game ({probe.get('game')}), not World of Tanks.")
    return json.loads(window.evaluate_js("window.__stratExtract()"))


def fetch(code: str) -> dict:
    """Open stratsketch.com/<code> in a hidden window and read the strat. Needs the app's GUI loop running."""
    import webview
    window = webview.create_window("Importing strat", f"{SITE}/{code}", hidden=True, width=1280, height=900)
    try:
        if not window.events.loaded.wait(40):
            raise ImportError_("StratSketch didn't load. Is the internet connection up?")
        return read_page(window)
    finally:
        try:
            window.destroy()
        except Exception:
            pass


def store(strat: dict, label: str | None = None) -> dict:
    """Save an extracted strat, fetch the files it needs, add it to the list and rebuild the page."""
    code = strat["code"]
    slides = [s for s in strat["slides"] if s.get("m")]
    if not slides:
        raise ImportError_("That strat has no slides on a World of Tanks map.")
    write_json(STRATS_DIR / f"{code}.json", strat)

    names = read_json(NAMES, {})
    names.update(strat.get("names") or {})
    write_json(NAMES, names)

    version = (strat.get("game") or {}).get("version")
    pack = read_json(PACK, None)
    pack_maps = {m["name"] for m in pack["maps"]} if pack else set()
    if pack is None or pack.get("version") != version or any(s["m"] not in pack_maps for s in slides):
        try:
            _download(f"{SITE}/api/packs/game/wot?v={version}", PACK)
            pack = read_json(PACK, pack)
        except OSError:
            pass  # keep the old pack: only base flags depend on it

    missing = []
    for s in slides:
        dest = MAPS / f"{s['m']}.webp"
        if not dest.exists():
            src = s.get("bg") or f"/img/games/wot/maps/{s['m']}.webp"
            try:
                _download(src if src.startswith("http") else SITE + src, dest)
            except OSError:
                missing.append(s["m"])
    if pack:
        icon_names = {b["id"]: b["name"] for b in pack["bases"]}
        by_name = {m["name"]: m for m in pack["maps"]}
        wanted = {icon_names.get(b["icon"]) for s in slides for b in by_name.get(s["m"], {}).get("bases", [])
                  if b["variant"] == s.get("v", 1) and b["team"] in (2, 3)}
        for icon in filter(None, wanted):
            for side in ("friendly", "enemy"):
                dest = MAPS / f"{icon}_{side}.webp"
                if not dest.exists():
                    try:
                        _download(f"{SITE}/img/games/wot/icons/{icon}_{side}.webp?v={version}", dest)
                    except OSError:
                        pass

    entries = read_json(STRATS_LIST, [])
    entry = next((e for e in entries if e["key"] == code), None)
    if entry is None:
        entry = {"key": code, "label": "", "url": f"{SITE}/{code}"}
        entries.append(entry)
    entry["title"] = strat["title"]
    if label and label.strip():
        entry["label"] = label.strip()
    elif not entry["label"]:
        entry["label"] = strat["title"][:28]
    write_json(STRATS_LIST, entries)
    build()
    return {"key": code, "label": entry["label"], "slides": len(slides), "skipped": len(strat["slides"]) - len(slides),
            "missing_maps": sorted(set(missing))}


def import_link(link: str, label: str | None = None) -> dict:
    code = parse_link(link)
    if not _busy.acquire(blocking=False):
        raise ImportError_("Another import is still running.")
    try:
        return store(fetch(code), label)
    finally:
        _busy.release()


def remove(key: str):
    entries = [e for e in read_json(STRATS_LIST, []) if e["key"] != key]
    write_json(STRATS_LIST, entries)
    (STRATS_DIR / f"{key}.json").unlink(missing_ok=True)
    build()


def rename(key: str, label: str):
    entries = read_json(STRATS_LIST, [])
    for e in entries:
        if e["key"] == key and label.strip():
            e["label"] = label.strip()
    write_json(STRATS_LIST, entries)
    build()


def move(key: str, step: int):
    entries = read_json(STRATS_LIST, [])
    i = next((n for n, e in enumerate(entries) if e["key"] == key), None)
    if i is None or not 0 <= i + step < len(entries):
        return
    entries[i], entries[i + step] = entries[i + step], entries[i]
    write_json(STRATS_LIST, entries)
    build()
