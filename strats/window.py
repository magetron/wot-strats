"""The app window: a real Windows window (Edge WebView2, through pywebview) with its own taskbar icon,
the same way banker does it. It shows the built page (index.html) from a small local server and gives the
page a few calls for managing strats (add from a StratSketch link, refresh, rename, remove)."""
import ctypes
import functools
import os
import subprocess
import sys
import threading
import traceback
import uuid
from ctypes import POINTER, WINFUNCTYPE, byref, c_long, c_ulong, c_ushort, c_void_p, c_wchar_p
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import importer
from .build import build
from .paths import DATA, INDEX, LOG, PKG, ROOT

TITLE = "WoT Strats"
APP_ID = "WoTStrats"  # the taskbar groups and pins by this, so the shortcut and the window must both carry it
HOST, PORT = "127.0.0.1", 54331
ICON = PKG / "static" / "icon.ico"
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
SHORTCUT = ROOT / "WoT Strats.lnk"
BACKGROUND = "#0c1012"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32")
shell32 = ctypes.WinDLL("shell32")
ole32 = ctypes.WinDLL("ole32")

# Windows property names (propkey.h): System.AppUserModel.*
PROPERTY_GROUP = uuid.UUID("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3").bytes_le
ID, RELAUNCH_COMMAND, RELAUNCH_ICON, RELAUNCH_NAME = 5, 2, 3, 4
IID_PROPERTY_STORE = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99").bytes_le)


class _Key(ctypes.Structure):  # PROPERTYKEY
    _fields_ = [("group", ctypes.c_byte * 16), ("id", c_ulong)]


class _Value(ctypes.Structure):  # PROPVARIANT holding a string (VT_LPWSTR)
    _fields_ = [("type", c_ushort), ("_reserved", c_ushort * 3), ("text", c_wchar_p), ("_rest", c_void_p)]


def _write_properties(store, values):
    """Set string properties on an IPropertyStore (a window's or a shortcut's) and release it."""
    methods = ctypes.cast(store, POINTER(POINTER(c_void_p))).contents
    set_value = WINFUNCTYPE(c_long, c_void_p, POINTER(_Key), POINTER(_Value))(methods[6])
    commit = WINFUNCTYPE(c_long, c_void_p)(methods[7])
    release = WINFUNCTYPE(c_ulong, c_void_p)(methods[2])
    group = (ctypes.c_byte * 16).from_buffer_copy(PROPERTY_GROUP)
    for key, text in values.items():
        result = set_value(store, byref(_Key(group, key)), byref(_Value(31, text=text)))
        if result < 0:
            raise OSError(f"couldn't set window property {key}: {result:#x}")
    commit(store)
    release(store)


def _set_relaunch(hwnd):
    """Tell the taskbar what this window is. Without it, pinning the window would pin bare pythonw.exe."""
    ole32.CoInitialize(None)  # this runs on a background thread
    store = c_void_p()
    shell32.SHGetPropertyStoreForWindow(c_void_p(hwnd), byref(IID_PROPERTY_STORE), byref(store))
    _write_properties(store, {
        ID: APP_ID,
        RELAUNCH_COMMAND: f'"{PYTHONW}" -m strats app',
        RELAUNCH_NAME: TITLE,
        RELAUNCH_ICON: f"{ICON},0",
    })


def make_shortcut():
    """(Re)create the shortcut in the project folder, carrying the same identity as the window."""
    make = (f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut("{SHORTCUT}"); $s.TargetPath = "{PYTHONW}"; '
            f'$s.Arguments = "-m strats app"; $s.WorkingDirectory = "{ROOT}"; $s.IconLocation = "{ICON},0"; $s.Save()')
    subprocess.run(["powershell", "-NoProfile", "-Command", make], check=True)
    ole32.CoInitialize(None)
    store = c_void_p()
    get_store = shell32.SHGetPropertyStoreFromParsingName
    get_store.argtypes = [ctypes.c_wchar_p, c_void_p, ctypes.c_int, c_void_p, POINTER(c_void_p)]
    result = get_store(str(SHORTCUT), None, 2, byref(IID_PROPERTY_STORE), byref(store))  # 2 = read and write
    if result < 0:
        raise OSError(f"couldn't open {SHORTCUT}: {result:#x}")
    _write_properties(store, {ID: APP_ID})
    return str(SHORTCUT)


def _already_open() -> bool:
    """If the app is already open, bring its window to the front."""
    kernel32.CreateMutexW(None, False, f"WoTStrats-{PORT}")  # released by Windows when this process ends
    if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
        return False
    hwnd = user32.FindWindowW(None, TITLE)
    if hwnd:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    return True


def storage() -> Path:
    """The window's own browser profile. It belongs to this PC and churns constantly, so it stays in the
    project folder but is marked for Dropbox not to sync."""
    folder = DATA / "window"
    if not folder.exists():
        folder.mkdir(parents=True)
        try:
            Path(f"{folder}:com.dropbox.ignored").write_text("1")
        except OSError:
            pass  # not NTFS: it just gets synced
    return folder


def log(text):
    """pythonw has no console, so failures would otherwise be silent."""
    DATA.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


class _Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            self.send_header("Cache-Control", "no-store")  # the page is rebuilt after every import
        super().end_headers()

    def log_message(self, *args):
        pass


def _serve():
    server = ThreadingHTTPServer((HOST, PORT), functools.partial(_Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()


class _Api:
    """What the page can call in this window. Each answers {ok: true, ...} or {ok: false, error: "..."}."""

    def _do(self, what, fn):
        try:
            result = fn() or {}
            log(f"{what}: ok {result}")
            return {"ok": True, **result}
        except importer.ImportError_ as e:
            log(f"{what}: {e}")
            return {"ok": False, "error": str(e)}
        except Exception as e:
            log(f"{what}: failed\n{traceback.format_exc()}")
            return {"ok": False, "error": f"Something went wrong ({type(e).__name__}). Details are in {LOG.name}."}

    def add(self, link, label=""):
        return self._do(f"add {link}", lambda: importer.import_link(link, label))

    def refresh(self, key):
        return self._do(f"refresh {key}", lambda: importer.import_link(key))

    def rename(self, key, label):
        return self._do(f"rename {key}", lambda: importer.rename(key, label))

    def remove(self, key):
        return self._do(f"remove {key}", lambda: importer.remove(key))

    def move(self, key, step):
        return self._do(f"move {key}", lambda: importer.move(key, int(step)))


def _run():
    if _already_open():
        return
    shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    import webview  # slow to load, and only the window needs it

    build()  # pick up template or data changes since the last run
    _serve()
    window = webview.create_window(TITLE, f"http://{HOST}:{PORT}/index.html", js_api=_Api(), maximized=True,
                                   background_color=BACKGROUND, text_select=True, zoomable=True)

    def boot():
        try:
            window.events.loaded.wait()
            form = window.native
            _set_relaunch(form.Handle.ToInt64())
            from System import Action  # .NET, loaded by webview.start

            def prepare():  # without this the keyboard stays on the outer window until you click
                form.browser.webview.Focus()
                form.browser.webview.CoreWebView2.Settings.AreDefaultContextMenusEnabled = True
            form.Invoke(Action(prepare))
            test = os.environ.get("STRATS_SELFTEST")  # developer check: drive the page's own Add form
            if test:
                window.evaluate_js("document.getElementById('bStrats').click();"
                                   f"document.getElementById('addUrl').value = {test!r};"
                                   "document.getElementById('addForm').requestSubmit();")
        except Exception:
            log(traceback.format_exc())

    webview.start(boot, gui="edgechromium", private_mode=False, storage_path=str(storage()), icon=str(ICON))


def main():
    try:
        _run()
    except Exception:
        log(traceback.format_exc())
        user32.MessageBoxW(None, f"WoT Strats couldn't open. See {LOG}", TITLE, 0x10)
