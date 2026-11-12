import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)   # running as the packaged exe (PyInstaller)
if FROZEN:
    BUNDLE = Path(sys._MEIPASS)          # read-only files shipped inside the package
    PKG = BUNDLE / "strats"
    ROOT = Path(sys.executable).parent   # the unzipped folder: strats, maps and the built page live beside the exe
else:
    PKG = Path(__file__).resolve().parent
    BUNDLE = ROOT = PKG.parent           # the repo folder
DATA = ROOT / "data"
STRATS_DIR = DATA / "strats"         # one JSON per imported strat, named by its StratSketch code
STRATS_LIST = DATA / "strats.json"   # [{key, label, url, title}] in tab order
NAMES = DATA / "maps.json"           # map code -> display name, as StratSketch labels them
PACK = DATA / "pack.json"            # StratSketch's WoT map pack (base positions)
MAPS = ROOT / "maps"                 # map images (2880px originals) and base icons
FONTS = BUNDLE / "fonts"
INDEX = ROOT / "index.html"          # the built page; the app window shows this
LOG = DATA / "strats.log"
SITE = "https://stratsketch.com"
