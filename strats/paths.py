from pathlib import Path

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent                    # strat-lookup/
DATA = ROOT / "data"
STRATS_DIR = DATA / "strats"         # one JSON per imported strat, named by its StratSketch code
STRATS_LIST = DATA / "strats.json"   # [{key, label, url, title}] in tab order
NAMES = DATA / "maps.json"           # map code -> display name, as StratSketch labels them
PACK = DATA / "pack.json"            # StratSketch's WoT map pack (base positions)
MAPS = ROOT / "maps"                 # map images (2880px originals) and base icons
FONTS = ROOT / "fonts"
INDEX = ROOT / "index.html"          # the built page; the app window shows this
LOG = DATA / "strats.log"
SITE = "https://stratsketch.com"
