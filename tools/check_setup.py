"""End-to-end check of the built Setup exe: install, open and import a strat, uninstall (keeping, then deleting, data).

    .venv/Scripts/python tools/check_setup.py      (after tools/release.py; takes about two minutes)

It presses the installer's own dialogs, so they flash on screen. Folders are redirected under build/test and the
port is changed, so the real app and real app data are left alone. The installed-apps entry can't be redirected:
the check uses its own registry entry (WoTStrats-test) and confirms it is gone at the end.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from strats import __version__ as VERSION  # noqa: E402
T = ROOT / "build" / "test"
MARK = "wot-strats\\build\\test"
REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\WoTStrats-test"
u = ctypes.WinDLL("user32")
u.FindWindowW.restype = ctypes.c_void_p
u.FindWindowExW.restype = ctypes.c_void_p


def stop_app():
    """End the test copy and the browser processes it started (they carry the test folder in their command line)."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*" + MARK + "*' -or $_.ExecutablePath -like '*"
          + MARK + "*') -and $_.Name -notin 'powershell.exe','python.exe','bash.exe' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


stop_app()
for _ in range(10):
    shutil.rmtree(T, ignore_errors=True)
    if not T.exists(): break
    time.sleep(2)
for d in ("dl", "local", "roaming", "tmp"):
    (T / d).mkdir(parents=True, exist_ok=True)
ENV = {**os.environ, "LOCALAPPDATA": str(T / "local"), "APPDATA": str(T / "roaming"), "TEMP": str(T / "tmp"),
       "TMP": str(T / "tmp"), "WOT_STRATS_PORT": "54399", "WOT_STRATS_REGKEY": "WoTStrats-test"}
setup = T / "dl" / f"WoT-Strats-Setup-{VERSION}.exe"
shutil.copyfile(ROOT / "dist" / setup.name, setup)
Path(f"{setup}:Zone.Identifier").write_text("[ZoneTransfer]\r\nZoneId=3\r\n")  # as if downloaded
prog = T / "local" / "Programs" / "WoT Strats"
exe = prog / "WoT Strats.exe"
data = T / "local" / "WoT Strats"
lnk = T / "roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "WoT Strats.lnk"


def reg():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            return winreg.QueryValueEx(k, "DisplayName")[0] + " " + winreg.QueryValueEx(k, "DisplayVersion")[0]
    except OSError:
        return None


def dialog(button, timeout=30):
    """Wait for the app's message box, print its first line, press a button (1 OK, 2 Cancel, 6 Yes, 7 No)."""
    end = time.time() + timeout
    while time.time() < end:
        h = u.FindWindowW("#32770", f"WoT Strats {VERSION}")
        if h:
            text, st = "", u.FindWindowExW(ctypes.c_void_p(h), None, "Static", None)
            while st:  # the icon is a Static too; take the one with text
                buf = ctypes.create_unicode_buffer(600); u.GetWindowTextW(ctypes.c_void_p(st), buf, 600)
                if buf.value: text = buf.value
                st = u.FindWindowExW(ctypes.c_void_p(h), ctypes.c_void_p(st), "Static", None)
            ids, bt = [], u.FindWindowExW(ctypes.c_void_p(h), None, "Button", None)
            while bt:
                ids.append(u.GetDlgCtrlID(ctypes.c_void_p(bt)))
                bt = u.FindWindowExW(ctypes.c_void_p(h), ctypes.c_void_p(bt), "Button", None)
            print("   dialog:", text.split("\n")[0][:70])
            u.PostMessageW(ctypes.c_void_p(h), 0x0111, button if button in ids else ids[0], 0)  # an OK-only box has one button
            time.sleep(0.8)
            return True
        time.sleep(0.2)
    print("   NO DIALOG"); return False


def served():
    try:
        return urllib.request.urlopen("http://127.0.0.1:54399/index.html", timeout=1).status == 200
    except OSError:
        return False


def wait(cond, seconds):
    end = time.time() + seconds
    while time.time() < end and not cond():
        time.sleep(0.5)
    return cond()


def state(label):
    maps = len(list((data / "maps").glob("*.webp"))) if (data / "maps").exists() else 0
    print(f"{label}: exe={exe.exists()} shortcut={lnk.exists()} registry={reg()} "
          f"strats={(data / 'data' / 'strats.json').exists()} maps={maps}")


print("1. Setup, Cancel"); p = subprocess.Popen([str(setup)], env=ENV); dialog(2); p.wait(20); state("   after cancel")

print("2. Setup, OK (then it opens the app)")
p = subprocess.Popen([str(setup)], env={**ENV, "STRATS_SELFTEST": "https://stratsketch.com/yTppLobZInS"}); dialog(1); p.wait(60)
print("   app serving its page:", wait(served, 30))
log = data / "data" / "strats.log"
wait(lambda: log.exists() and "add " in log.read_text(encoding="utf-8"), 90)
print("   log:", log.read_text(encoding="utf-8").strip().splitlines()[-1][:100])
state("   after install + import")
print("   installed exe marked as downloaded:", os.path.exists(f"{exe}:Zone.Identifier"))
tgt = subprocess.run(["powershell", "-NoProfile", "-Command",
                      f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').TargetPath"], capture_output=True, text=True).stdout.strip()
print("   shortcut points at installed exe:", Path(tgt) == exe)

print("3. Uninstall while the app is open"); p = subprocess.Popen([str(exe), "uninstall"], env=ENV)
dialog(1); p.wait(20); state("   after refused uninstall")

print("4. Close the app, uninstall straight away, keep strats"); stop_app(); time.sleep(1)
p = subprocess.Popen([str(exe), "uninstall"], env=ENV); dialog(1); dialog(7); dialog(1); p.wait(20)
print("   program folder gone:", wait(lambda: not prog.exists(), 40)); state("   after uninstall (keep)")

print("5. Install again quietly, open and close the app, uninstall straight away and delete strats")
subprocess.run([str(setup), "install", "--quiet"], env=ENV, timeout=60); state("   reinstalled")
subprocess.Popen([str(exe)], env=ENV); print("   app opened again:", wait(served, 30)); time.sleep(3); stop_app(); time.sleep(1)
p = subprocess.Popen([str(exe), "uninstall"], env=ENV); dialog(1); dialog(6); dialog(1); p.wait(20)
print("   program folder gone:", wait(lambda: not prog.exists(), 40), "| data folder gone:", wait(lambda: not data.exists(), 40))
state("   after uninstall (delete)")
print("   test registry entry gone:", reg() is None)
real = Path(os.environ["LOCALAPPDATA"])
print("   real app data untouched:", not (real / "WoT Strats").exists() and not (real / "Programs" / "WoT Strats").exists())
