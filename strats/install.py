"""Install and uninstall for the packaged exe, per user (no admin rights).

The release is one exe that is its own installer: started under a name containing "Setup" (or with `install`)
it copies itself to %LOCALAPPDATA%\\Programs\\WoT Strats, adds a Start menu shortcut and registers itself in
Windows' installed-apps list. Uninstalling from that list runs the installed exe with `uninstall`, which removes
all of that and, if the user says so, their strats and map images in %LOCALAPPDATA%\\WoT Strats.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

from . import __version__
from .paths import ROOT
from .window import APP_ID, PORT, TITLE, make_shortcut

EXE_NAME = "WoT Strats.exe"
# The test hook: another key name keeps a trial install apart from a real one in the installed-apps list.
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + "\\" + os.environ.get("WOT_STRATS_REGKEY", APP_ID)
OK, CANCEL, YES, NO = 1, 2, 6, 7
user32 = ctypes.WinDLL("user32")
kernel32 = ctypes.WinDLL("kernel32")


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def install_dir() -> Path:
    return _local() / "Programs" / TITLE


def data_dir() -> Path:
    return _local() / TITLE


def start_menu_shortcut() -> Path:
    roaming = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{TITLE}.lnk"


def _ask(text, buttons=1, icon=0x20) -> int:  # 1 = OK/Cancel, 4 = Yes/No; 0x20 = question mark
    return user32.MessageBoxW(None, text, f"{TITLE} {__version__}", buttons | icon)


def _tell(text, icon=0x40):
    user32.MessageBoxW(None, text, f"{TITLE} {__version__}", icon)


def _app_running() -> bool:
    kernel32.OpenMutexW.restype = ctypes.c_void_p
    handle = kernel32.OpenMutexW(0x00100000, False, f"WoTStrats-{PORT}")  # SYNCHRONIZE
    if handle:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
    return bool(handle)


def install(quiet=False) -> int:
    """Copy this exe into place, add the shortcut and the installed-apps entry, then open the app."""
    target = install_dir() / EXE_NAME
    source = Path(sys.executable)
    if _app_running():
        if not quiet:
            _tell(f"{TITLE} is open. Close it, then run this again.", 0x30)
        return 1
    if not quiet and _ask(f"Install {TITLE} {__version__} for your Windows account?\n\n"
                          f"It goes in {install_dir()} and a Start menu shortcut is added. "
                          "You can remove it later from Windows' installed apps.") != OK:
        return 1
    install_dir().mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)  # contents only, so the copy has no "downloaded" mark
    make_shortcut(start_menu_shortcut(), target, "", install_dir(), f"{target},0")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
        for name, value in {
            "DisplayName": TITLE, "DisplayVersion": __version__, "Publisher": "magetron",
            "DisplayIcon": f"{target},0", "InstallLocation": str(install_dir()),
            "UninstallString": f'"{target}" uninstall', "QuietUninstallString": f'"{target}" uninstall --quiet',
            "URLInfoAbout": "https://github.com/magetron/wot-strats",
        }.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, target.stat().st_size // 1024)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    if not quiet:
        subprocess.Popen([str(target)], cwd=install_dir())
    return 0


def uninstall(quiet=False, keep_data=False) -> int:
    """Remove the shortcut, the installed-apps entry, the program folder and (if wanted) the user's strats."""
    if _app_running():
        if not quiet:
            _tell(f"{TITLE} is open. Close it, then uninstall again.", 0x30)
        return 1
    if not quiet:
        if _ask(f"Remove {TITLE} from this PC?") != OK:
            return 1
        data = data_dir()
        keep_data = not data.exists() or _ask(
            f"Also delete your imported strats and downloaded map images?\n\n{data}", buttons=4) != YES
    start_menu_shortcut().unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass
    if not keep_data:
        shutil.rmtree(data_dir(), ignore_errors=True)
    if not quiet:
        _tell(f"{TITLE} has been removed." + (f"\n\nYour strats are still in {data_dir()}." if keep_data and data_dir().exists() else ""))
    # Some folders can't go yet: this exe is running from the program folder, and the browser part of the app
    # can hold files in the data folder for a few seconds after the app closes. Hand what's left to a command
    # that outlives this process and keeps trying for a while (started last, once the message above is closed).
    folder = install_dir()
    if Path(sys.executable).resolve().parent != folder.resolve():
        shutil.rmtree(folder, ignore_errors=True)
    left = [d for d in ([folder] if keep_data else [folder, data_dir()]) if d.exists()]
    if left:
        remove = " & ".join(f'rmdir /s /q "{d}" 2>nul' for d in left)
        gone = " ".join(f'if not exist "{d}"' for d in left)
        subprocess.Popen(f"cmd /c for /l %i in (1,1,30) do (ping -n 2 127.0.0.1 >nul & {remove} & {gone} exit)",
                         cwd=str(_local()), creationflags=0x08000000)  # no window
    return 0
