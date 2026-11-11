"""Build index.html from the imported strats in data/. The page is one self-contained file plus maps/."""
import base64
import json
import re
from collections import Counter

from .paths import FONTS, INDEX, MAPS, NAMES, PACK, PKG, STRATS_DIR, STRATS_LIST

# Extra search words (nicknames, spellings). Prefixes of the display name and the words in the
# map's internal code match anyway, so only other words are needed here.
ALIASES = {
    "29_el_hallouf": ["halluf", "el haluf"], "59_asia_great_wall": ["empires border", "border"],
    "06_ensk_big": ["ensk"], "36_fishing_bay": ["fishermans bay", "fisherman"],
    "04_himmelsdorf": ["himmel"], "44_north_america": ["oaks"], "38_mannerheim_line": ["mannerheim"],
    "37_caucasus": ["pass"], "101_dday": ["d day", "normandy"], "121_lost_paradise_v": ["oyster"],
    "112_eiffel_tower_ctf": ["eiffel"], "60_asia_miao": ["pearl"], "05_prohorovka": ["prokhorovka", "fiery salient"],
    "127_japort": ["haven"], "28_desert": ["sand", "river"], "47_canada_a": ["serene"],
    "14_siegfried_line": ["siegfried"], "35_steppes": ["steppe"], "99_poland": ["studz"],
}


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


def off_map(t) -> bool:
    x, y, w = t[0], t[1], t[2]
    return x < 0 or x + w > 1000 or y < 0 or y > 1000


def load_strat(entry):
    d = read_json(STRATS_DIR / f"{entry['key']}.json", None)
    if d is None:
        return None
    slides_in = [s for s in d["slides"] if s.get("m")]
    # Off-map text copied to the same spot on 2+ slides (e.g. a legend) is strat-level.
    key = lambda t: (t[5], round(t[0] / 10), round(t[1] / 10))
    counts = Counter(k for s in slides_in for k in {key(t) for t in s["t"] if off_map(t)})
    repeated = {k for k, c in counts.items() if c >= 2}
    extra = {}
    for s in slides_in:
        for t in sorted(s["t"], key=lambda t: t[1]):
            if key(t) in repeated and t[5] not in extra:
                extra[t[5]] = [t[4], t[5]]
        s["t"] = [t for t in s["t"] if not (off_map(t) and key(t) in repeated)]
    legend, rules = [], []
    for colour, text in d["rules"] + list(extra.values()):
        if text.strip().lower() == "legend":
            continue
        (legend if len(text.split()) <= 3 else rules).append([colour, text])
    # Notes written beside the first slide apply to the whole strat.
    general = []
    if slides_in and d["slides"][0] is slides_in[0]:
        first = slides_in[0]
        general = sorted((t for t in first["t"] if off_map(t)), key=lambda t: t[1])
        first["t"] = [t for t in first["t"] if not off_map(t)]
    slides = []
    for n, s in enumerate(d["slides"], 1):
        if not s.get("m"):
            continue
        slide = {"n": n, "m": s["m"], "v": s.get("v", 1), "team": s["team"], "i": s["i"], "s": s["s"], "t": s["t"]}
        if s.get("nm"):
            slide["nm"] = s["nm"]
        slides.append(slide)
    return {
        "key": entry["key"], "label": entry["label"], "url": entry["url"], "title": d["title"],
        "total": len(d["slides"]), "legend": legend, "rules": rules,
        "general": [[t[4], t[5]] for t in general], "slides": slides, "icons": d["icons"],
    }


def font_faces() -> str:
    """Embed the fonts (Latin subset, from Google Fonts) so the page works offline."""
    faces = [("Barlow Condensed", "500", "BarlowCondensed-500.woff2"),
             ("Barlow Condensed", "600", "BarlowCondensed-600.woff2"),
             ("Barlow Condensed", "700", "BarlowCondensed-700.woff2"),
             ("Source Sans 3", "200 900", "SourceSans3-var.woff2")]
    css = []
    for family, weight, file in faces:
        b64 = base64.b64encode((FONTS / file).read_bytes()).decode()
        css.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};font-display:swap;"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "\n".join(css)


def build() -> dict:
    entries = read_json(STRATS_LIST, [])
    names = read_json(NAMES, {})
    pack = read_json(PACK, {"maps": [], "bases": []})
    pack_maps = {m["name"]: m for m in pack["maps"]}
    base_icons = {b["id"]: b["name"] for b in pack["bases"]}
    strats = [s for s in (load_strat(e) for e in entries) if s]
    icons = strats[0]["icons"] if strats else []
    for s in strats:
        del s["icons"]

    def name_of(code):
        return names.get(code) or re.sub(r"^\d+_", "", code).replace("_", " ").title()

    used = {}  # map code -> variants its slides use
    for s in strats:
        for sl in s["slides"]:
            used.setdefault(sl["m"], set()).add(sl["v"])
    codes = sorted((c for c in used if (MAPS / f"{c}.webp").exists()), key=name_of)
    for s in strats:
        s["slides"] = [sl for sl in s["slides"] if sl["m"] in codes]
    maps = {}
    for code in codes:
        bases = {}
        for b in pack_maps.get(code, {}).get("bases", []):
            icon = base_icons.get(b["icon"])
            if b["variant"] in used[code] and b["team"] in (2, 3) and icon and (MAPS / f"{icon}_friendly.webp").exists():
                bases.setdefault(str(b["variant"]), []).append(
                    [round(b["position"][0] * 1000), round(b["position"][1] * 1000), b["team"], icon])
        maps[code] = {"name": name_of(code), "slug": slug(name_of(code)), "alias": ALIASES.get(code, []), "bases": bases}
    data = {"maps": maps, "order": codes, "strats": strats, "icons": icons}
    page = (PKG / "page.template.html").read_text(encoding="utf-8")
    page = page.replace("/*__FONTS__*/", font_faces())
    page = page.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    INDEX.write_text(page, encoding="utf-8")
    return {"strats": [(s["label"], len(s["slides"])) for s in strats], "maps": len(codes), "kb": len(page) // 1024}
