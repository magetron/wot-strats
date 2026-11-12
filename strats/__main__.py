"""python -m strats app | import <link> [--label NAME] | build | shortcut   (packaged exe also: install | uninstall)"""
import argparse
import json
import sys
from pathlib import Path


def _import_from_cli(link, label):
    """Importing needs a browser window, so this starts the GUI loop with nothing showing."""
    import webview
    from . import importer
    from .window import storage
    out = {}
    holder = webview.create_window("WoT Strats import", html="<body></body>", hidden=True)

    def run():
        try:
            out["result"] = importer.import_link(link, label)
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
        holder.destroy()

    webview.start(run, gui="edgechromium", private_mode=False, storage_path=str(storage()))
    print(json.dumps(out, ensure_ascii=False))
    return 1 if "error" in out else 0


def main():
    p = argparse.ArgumentParser(prog="strats")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("app", help="open the app window")
    imp = sub.add_parser("import", help="import (or refresh) a strat from a StratSketch link")
    imp.add_argument("link")
    imp.add_argument("--label")
    sub.add_parser("build", help="rebuild index.html from data/")
    sub.add_parser("shortcut", help="(re)create the shortcut in the project folder")
    ins = sub.add_parser("install", help="(packaged exe) install for this Windows account")
    ins.add_argument("--quiet", action="store_true")
    unins = sub.add_parser("uninstall", help="(packaged exe) remove the app")
    unins.add_argument("--quiet", action="store_true")
    unins.add_argument("--keep-data", action="store_true")
    from .paths import FROZEN, unblock_bundle
    # Double-clicking the packaged exe: the download is named ...Setup..., which installs; otherwise open the app.
    default = "install" if FROZEN and "setup" in Path(sys.executable).name.lower() else "app"
    args = p.parse_args(sys.argv[1:] or [default])
    unblock_bundle()  # before anything loads .NET

    if args.cmd in ("install", "uninstall"):
        if not FROZEN:
            p.error("install and uninstall are for the packaged exe; from source just run `app`")
        from . import install
        if args.cmd == "install":
            return install.install(args.quiet)
        return install.uninstall(args.quiet, args.keep_data)

    if args.cmd == "app":
        from .window import main as run_window
        return run_window()
    if args.cmd == "import":
        return _import_from_cli(args.link, args.label)
    if args.cmd == "build":
        from .build import build
        return print(json.dumps(build(), ensure_ascii=False))
    if args.cmd == "shortcut":
        from .window import make_shortcut
        return print(make_shortcut())


if __name__ == "__main__":
    sys.exit(main())
