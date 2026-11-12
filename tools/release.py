"""Build the release zip: dist/WoT-Strats-<version>.zip, holding a folder with "WoT Strats.exe".

    .venv/Scripts/python -m pip install --no-cache-dir -e .[release]
    .venv/Scripts/python tools/release.py

The zip has the app only: no strats and no map images. Whoever runs it pastes StratSketch links and the app
fetches what those need. Their strats, maps and the built page are written beside the exe.
Everything this writes stays in the repo folder (build/, dist/).
"""
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "WoT Strats"


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    dist, work = ROOT / "dist", ROOT / "build"
    shutil.rmtree(dist / NAME, ignore_errors=True)
    data = [("strats/extract.js", "strats"), ("strats/page.template.html", "strats"),
            ("strats/static/icon.ico", "strats/static"), ("fonts", "fonts")]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
           "--icon", str(ROOT / "strats/static/icon.ico"), "--distpath", str(dist), "--workpath", str(work),
           "--specpath", str(work), "--paths", str(ROOT)]
    for src, dest in data:
        cmd += ["--add-data", f"{ROOT / src};{dest}"]
    # keep PyInstaller's cache inside the project (it defaults to a per-user folder)
    env = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(work / "pyinstaller-cache")}
    subprocess.run(cmd + [str(ROOT / "tools" / "launcher.py")], check=True, cwd=ROOT, env=env)
    readme = (ROOT / "tools" / "README.txt").read_text(encoding="utf-8").replace("{version}", version)
    (dist / NAME / "README.txt").write_text(readme, encoding="utf-8")
    archive = shutil.make_archive(str(dist / f"WoT-Strats-{version}"), "zip", dist, NAME)
    print(archive, f"{Path(archive).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
