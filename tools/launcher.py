"""Entry point for the packaged exe (PyInstaller needs a plain script, not `-m strats`)."""
import sys

from strats.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
