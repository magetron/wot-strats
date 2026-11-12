"""python -m strats app | import <link> [--label NAME] | build | shortcut"""
import argparse
import json
import sys


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
    args = p.parse_args(sys.argv[1:] or ["app"])  # double-clicking the packaged exe opens the app
    from .paths import unblock_bundle
    unblock_bundle()  # before anything loads .NET

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
