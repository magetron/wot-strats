"""Build the release: dist/WoT-Strats-Setup-<version>.exe, one exe that is the app and its own installer.

    .venv/Scripts/python -m pip install --no-cache-dir -e .[release]
    .venv/Scripts/python tools/release.py

Run under a name containing "Setup" it installs itself for the current user (strats/install.py); renamed to
anything else it just runs as the app. It holds the app only, no strats and no map images.
Everything this script writes stays in the repo folder (build/, dist/).
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "WoT Strats"


def main():
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "strats" / "__init__.py").read_text(encoding="utf-8")).group(1)
    dist, work = ROOT / "dist", ROOT / "build"
    data = [("strats/extract.js", "strats"), ("strats/page.template.html", "strats"),
            ("strats/static/icon.ico", "strats/static"), ("fonts", "fonts")]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onefile", "--name", NAME,
           "--icon", str(ROOT / "strats/static/icon.ico"), "--distpath", str(work / "exe"), "--workpath", str(work),
           "--specpath", str(work), "--paths", str(ROOT)]
    for src, dest in data:
        cmd += ["--add-data", f"{ROOT / src};{dest}"]
    # keep PyInstaller's cache inside the project (it defaults to a per-user folder)
    env = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(work / "pyinstaller-cache")}
    subprocess.run(cmd + [str(ROOT / "tools" / "launcher.py")], check=True, cwd=ROOT, env=env)
    dist.mkdir(exist_ok=True)
    setup = dist / f"WoT-Strats-Setup-{version}.exe"
    shutil.copyfile(work / "exe" / f"{NAME}.exe", setup)
    print(setup, f"{setup.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
