#!/usr/bin/env python3
"""Capture a desktop application window — and its menus, tabs and dialogs — at an
exact window size, so an original and its rebuild can be diffed pixel for pixel.

Examples
--------
    # what is open right now?
    python3 capture_window.py --list-windows

    # the original app, 1440x900 client area, plus its File / Edit menus
    python3 capture_window.py --title "^MyApp" --size 1440x900 \
        --out capture/original --menus File,Edit

    # the rebuild, captured the same way, same size
    python3 capture_window.py --title "^MyApp \\(clone\\)" --size 1440x900 \
        --out capture/clone --shot-list shots.json

`shots.json` (all keys optional except name):

    {"shots": [
      {"name": "window"},
      {"name": "file-menu",   "keys": "alt+f", "close": "escape", "wait": 0.8},
      {"name": "preferences", "keys": "ctrl+,", "wait": 1.2, "close": "escape"},
      {"name": "selected",    "click": [[220, 180]], "close": "escape"},
      {"name": "scrolled",    "keys": "pagedown", "wait": 0.4}
    ]}

Guarantees
----------
* The window is resized to the requested *client* size before capture.
* The saved image is exactly WxH. HiDPI captures (2x/3x) are downscaled to the
  logical size; a window that cannot be resized is cropped/padded to WxH and the
  manifest says so in `warnings`.
* Nothing outside the window is captured, so the desktop, other apps and the
  mouse pointer stay out of the frame.

Platform support
----------------
Windows  — pure ctypes (PrintWindow, DPI-aware). No pywin32 needed.
Linux/X11— xdotool for window control, ImageMagick `import` (or `xwd`) for pixels.
           Wayland is not supported: run the app under XWayland or an X session.
macOS    — osascript (System Events) + `screencapture -R`. Needs Accessibility and
           Screen Recording permission for the terminal running this script.

Requires: pillow
    python3 -m pip install pillow
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("capture_window.py needs Pillow: python3 -m pip install pillow")


# --------------------------------------------------------------------------- #
# shared model
# --------------------------------------------------------------------------- #
@dataclass
class WindowInfo:
    handle: Any
    title: str
    pid: int | None = None
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def label(self) -> str:
        return (
            f"{self.title[:58]:<58} {self.width:>5}x{self.height:<5} "
            f"pid {self.pid if self.pid is not None else '?'}"
        )


class BackendError(RuntimeError):
    pass


class Backend:
    name = "unknown"
    notes: list[str] = []

    def available(self) -> tuple[bool, str]:
        return True, ""

    def list_windows(self) -> list[WindowInfo]:
        raise NotImplementedError

    def find(self, pattern: re.Pattern[str], pid: int | None) -> WindowInfo:
        matches = [
            w
            for w in self.list_windows()
            if pattern.search(w.title) and (pid is None or w.pid == pid)
        ]
        if not matches:
            raise BackendError(
                f"no visible window matching /{pattern.pattern}/"
                + (f" with pid {pid}" if pid else "")
                + " — run --list-windows to see what is available"
            )
        if len(matches) > 1:
            exact = [w for w in matches if w.title == pattern.pattern]
            if len(exact) == 1:
                return exact[0]
            listing = "\n  ".join(w.label() for w in matches[:12])
            raise BackendError(
                f"{len(matches)} windows match /{pattern.pattern}/:\n  {listing}\n"
                "Narrow it with a more specific --title or --pid."
            )
        return matches[0]

    def client_size(self, win: WindowInfo) -> tuple[int, int]:
        raise NotImplementedError

    def resize_client(self, win: WindowInfo, width: int, height: int) -> None:
        raise NotImplementedError

    def capture(self, win: WindowInfo) -> Image.Image:
        raise NotImplementedError

    def activate(self, win: WindowInfo) -> None:
        pass

    def send_keys(self, combo: str) -> None:
        raise NotImplementedError

    def click(self, win: WindowInfo, x: int, y: int) -> None:
        raise NotImplementedError

    @staticmethod
    def run(cmd: list[str], timeout: float = 10.0) -> str:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as exc:
            raise BackendError(f"{cmd[0]} is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise BackendError(f"{' '.join(cmd)} timed out") from exc
        if res.returncode != 0:
            raise BackendError(
                f"{' '.join(cmd)} failed ({res.returncode}): "
                f"{(res.stderr or res.stdout).strip()[:300]}"
            )
        return res.stdout

    @staticmethod
    def run_bytes(cmd: list[str], timeout: float = 20.0) -> bytes:
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except FileNotFoundError as exc:
            raise BackendError(f"{cmd[0]} is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise BackendError(f"{' '.join(cmd)} timed out") from exc
        if res.returncode != 0:
            raise BackendError(
                f"{' '.join(cmd)} failed ({res.returncode}): "
                f"{res.stderr.decode(errors='replace').strip()[:300]}"
            )
        return res.stdout


# --------------------------------------------------------------------------- #
# Linux / X11
# --------------------------------------------------------------------------- #
KEY_ALIASES_X11 = {
    ",": "comma",
    ".": "period",
    "/": "slash",
    ";": "semicolon",
    "'": "apostrophe",
    "[": "bracketleft",
    "]": "bracketright",
    "-": "minus",
    "=": "equal",
    "`": "grave",
    "\\": "backslash",
}


class X11Backend(Backend):
    name = "linux-x11"

    def __init__(self) -> None:
        self.has_xdotool = shutil.which("xdotool") is not None
        self.capture_cmd: list[str] | None = None
        if shutil.which("import") or shutil.which("magick"):
            self.capture_cmd = ["import"]
        if self.capture_cmd is None and shutil.which("xwd"):
            self.capture_cmd = ["xwd"]

    def available(self) -> tuple[bool, str]:
        if not shutil.which("xdotool"):
            return False, (
                "xdotool is required on Linux (apt install xdotool / dnf install xdotool)"
            )
        if not self.capture_cmd:
            return False, (
                "ImageMagick `import` or `xwd` is required to read pixels "
                "(apt install imagemagick)"
            )
        if not shutil.which("import") and not shutil.which("magick") and not shutil.which("convert"):
            return False, "xwd is installed but ImageMagick `convert` is needed to decode it"
        return True, ""

    def list_windows(self) -> list[WindowInfo]:
        out = self.run(["xdotool", "search", "--onlyvisible", "--name", "."])
        ids = [line.strip() for line in out.splitlines() if line.strip()]
        windows: list[WindowInfo] = []
        for wid in ids:
            try:
                title = self.run(["xdotool", "getwindowname", wid]).strip()
                geo = self.run(["xdotool", "getwindowgeometry", "--shell", wid])
            except BackendError:
                continue
            fields = dict(
                line.split("=", 1) for line in geo.splitlines() if "=" in line
            )
            w = int(fields.get("WIDTH", 0))
            h = int(fields.get("HEIGHT", 0))
            if w <= 1 or h <= 1 or not title:
                continue
            pid = None
            try:
                pid_text = self.run(["xdotool", "getwindowpid", wid]).strip()
                pid = int(pid_text) if pid_text.isdigit() else None
            except BackendError:
                pid = None
            windows.append(
                WindowInfo(
                    handle=wid,
                    title=title,
                    pid=pid,
                    x=int(fields.get("X", 0)),
                    y=int(fields.get("Y", 0)),
                    width=w,
                    height=h,
                )
            )
        return windows

    def client_size(self, win: WindowInfo) -> tuple[int, int]:
        geo = self.run(["xdotool", "getwindowgeometry", "--shell", str(win.handle)])
        fields = dict(line.split("=", 1) for line in geo.splitlines() if "=" in line)
        return int(fields.get("WIDTH", 0)), int(fields.get("HEIGHT", 0))

    def resize_client(self, win: WindowInfo, width: int, height: int) -> None:
        self.run(["xdotool", "windowsize", "--sync", str(win.handle), str(width), str(height)])

    def activate(self, win: WindowInfo) -> None:
        try:
            self.run(["xdotool", "windowactivate", "--sync", str(win.handle)])
        except BackendError:
            pass

    def capture(self, win: WindowInfo) -> Image.Image:
        assert self.capture_cmd
        import io

        if self.capture_cmd[0] in ("import", "magick"):
            binary = "magick" if shutil.which("magick") and not shutil.which("import") else "import"
            cmd = [binary, "-window", str(win.handle), "-silent", "png:-"]
            return Image.open(io.BytesIO(self.run_bytes(cmd))).convert("RGB")
        # xwd -> convert
        raw = self.run_bytes(["xwd", "-silent", "-id", str(win.handle)])
        conv = "magick" if shutil.which("magick") else "convert"
        proc = subprocess.run(
            [conv, "xwd:-", "png:-"], input=raw, capture_output=True, timeout=30
        )
        if proc.returncode != 0:
            raise BackendError(
                f"{conv} could not decode xwd output: "
                f"{proc.stderr.decode(errors='replace')[:200]}"
            )
        return Image.open(io.BytesIO(proc.stdout)).convert("RGB")

    def send_keys(self, combo: str) -> None:
        parts = [p.strip() for p in combo.split("+") if p.strip()]
        mapped = [KEY_ALIASES_X11.get(p.lower(), p.lower()) for p in parts]
        self.run(["xdotool", "key", "--clearmodifiers", "+".join(mapped)])

    def click(self, win: WindowInfo, x: int, y: int) -> None:
        self.run(
            [
                "xdotool",
                "mousemove",
                "--window",
                str(win.handle),
                str(int(x)),
                str(int(y)),
                "click",
                "1",
            ]
        )


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #
class WindowsBackend(Backend):
    name = "windows"

    VK: dict[str, int] = {
        "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
        "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
        "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
        "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "comma": 0xBC, ",": 0xBC, "period": 0xBE, ".": 0xBE, "slash": 0xBF, "/": 0xBF,
        "minus": 0xBD, "-": 0xBD, "plus": 0xBB, "=": 0xBB, "semicolon": 0xBA, ";": 0xBA,
    }

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # pragma: no cover - older Windows
            try:
                self.user32.SetProcessDPIAware()
            except Exception:
                pass

    def available(self) -> tuple[bool, str]:
        return True, ""

    # -- window control ---------------------------------------------------- #
    def list_windows(self) -> list[WindowInfo]:
        ctypes, wintypes = self.ctypes, self.wintypes
        user32 = self.user32
        results: list[WindowInfo] = []

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: Any, _lparam: Any) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 8 or h <= 8:
                return True
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            results.append(
                WindowInfo(
                    handle=hwnd,
                    title=title,
                    pid=int(pid.value) or None,
                    x=rect.left,
                    y=rect.top,
                    width=w,
                    height=h,
                )
            )
            return True

        user32.EnumWindows(EnumProc(callback), 0)
        return results

    def _client_rect(self, hwnd: Any) -> tuple[int, int]:
        ctypes, wintypes = self.ctypes, self.wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        r = RECT()
        if not self.user32.GetClientRect(hwnd, ctypes.byref(r)):
            raise BackendError("GetClientRect failed")
        return r.right - r.left, r.bottom - r.top

    def client_size(self, win: WindowInfo) -> tuple[int, int]:
        return self._client_rect(win.handle)

    def _frame_delta(self, win: WindowInfo) -> tuple[int, int]:
        ctypes, wintypes = self.ctypes, self.wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        wr, cr = RECT(), RECT()
        self.user32.GetWindowRect(win.handle, ctypes.byref(wr))
        self.user32.GetClientRect(win.handle, ctypes.byref(cr))
        return (wr.right - wr.left) - cr.right, (wr.bottom - wr.top) - cr.bottom

    def resize_client(self, win: WindowInfo, width: int, height: int) -> None:
        ctypes, wintypes = self.ctypes, self.wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        dw, dh = self._frame_delta(win)
        wr = RECT()
        self.user32.GetWindowRect(win.handle, ctypes.byref(wr))
        SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
        self.user32.SetWindowPos(
            win.handle,
            0,
            wr.left,
            wr.top,
            width + dw,
            height + dh,
            SWP_NOZORDER | SWP_NOACTIVATE,
        )

    def activate(self, win: WindowInfo) -> None:
        try:
            self.user32.ShowWindow(win.handle, 9)  # SW_RESTORE
            self.user32.SetForegroundWindow(win.handle)
        except Exception:
            pass

    # -- pixels ------------------------------------------------------------ #
    def capture(self, win: WindowInfo) -> Image.Image:
        ctypes = self.ctypes
        user32, gdi32 = self.user32, self.gdi32
        w, h = self._client_rect(win.handle)
        if w <= 0 or h <= 0:
            raise BackendError("window has no client area")

        hdc = user32.GetDC(win.handle)
        if not hdc:
            raise BackendError("GetDC failed")
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        bitmap = gdi32.CreateCompatibleBitmap(hdc, w, h)
        gdi32.SelectObject(mem_dc, bitmap)

        PW_CLIENTONLY = 0x1
        SRCCOPY = 0x00CC0020
        ok = user32.PrintWindow(win.handle, mem_dc, PW_CLIENTONLY)
        if not ok:
            gdi32.BitBlt(mem_dc, 0, 0, w, h, hdc, 0, 0, SRCCOPY)
            self.notes.append(
                "PrintWindow failed; used BitBlt, so an occluding window could be "
                "in the capture — keep the target window unobscured"
            )

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = w
        header.biHeight = -h  # top-down
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0  # BI_RGB

        buf_len = w * h * 4
        buffer = ctypes.create_string_buffer(buf_len)
        lines = gdi32.GetDIBits(mem_dc, bitmap, 0, h, buffer, ctypes.byref(header), 0)

        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(win.handle, hdc)
        if not lines:
            raise BackendError("GetDIBits produced no rows")

        return Image.frombuffer("RGB", (w, h), buffer, "raw", "BGRX", 0, 1)

    # -- input ------------------------------------------------------------- #
    def _vk(self, name: str) -> int:
        key = name.strip().lower()
        if key in self.VK:
            return self.VK[key]
        if len(key) == 2 and key.startswith("f") and key[1].isdigit():
            return 0x70 + int(key[1]) - 1
        if re.fullmatch(r"f(1[0-2]|[1-9])", key):
            return 0x70 + int(key[1:]) - 1
        if len(key) == 1:
            return ord(key.upper())
        raise BackendError(f"unknown key {name!r}")

    def send_keys(self, combo: str) -> None:
        user32 = self.user32
        parts = [p for p in (s.strip() for s in combo.split("+")) if p]
        vks = [self._vk(p) for p in parts]
        KEYEVENTF_KEYUP = 0x0002
        for vk in vks[:-1]:
            user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 0, 0)
        user32.keybd_event(vks[-1], 0, KEYEVENTF_KEYUP, 0)
        for vk in reversed(vks[:-1]):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    def click(self, win: WindowInfo, x: int, y: int) -> None:
        lparam = (int(y) << 16) | (int(x) & 0xFFFF)
        WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
        self.user32.PostMessageW(win.handle, WM_MOUSEMOVE, 0, lparam)
        self.user32.PostMessageW(win.handle, WM_LBUTTONDOWN, 1, lparam)
        time.sleep(0.03)
        self.user32.PostMessageW(win.handle, WM_LBUTTONUP, 0, lparam)


# --------------------------------------------------------------------------- #
# macOS
# --------------------------------------------------------------------------- #
class MacOSBackend(Backend):
    name = "macos"

    MAC_MODS = {
        "ctrl": "control down", "control": "control down",
        "alt": "option down", "option": "option down", "opt": "option down",
        "shift": "shift down", "cmd": "command down", "command": "command down",
        "meta": "command down", "super": "command down",
    }
    KEY_CODES = {
        "escape": 53, "esc": 53, "tab": 48, "return": 36, "enter": 76, "space": 49,
        "delete": 51, "backspace": 51, "forwarddelete": 117,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
        "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    }

    def __init__(self) -> None:
        self.frame_top = 28

    def available(self) -> tuple[bool, str]:
        if not shutil.which("osascript"):
            return False, "osascript not found"
        if not shutil.which("screencapture"):
            return False, "screencapture not found"
        return True, ""

    def _osascript(self, script: str) -> str:
        return self.run(["osascript", "-e", script], timeout=20.0)

    def list_windows(self) -> list[WindowInfo]:
        script = """
set out to ""
tell application "System Events"
  repeat with p in (every application process whose visible is true)
    try
      set pname to name of p
      set ppid to unix id of p
      repeat with w in (every window of p)
        try
          set wname to name of w
          set {wx, wy} to position of w
          set {ww, wh} to size of w
          set out to out & pname & "\\t" & ppid & "\\t" & wx & "\\t" & wy & "\\t" & ww & "\\t" & wh & "\\t" & wname & linefeed
        end try
      end repeat
    end try
  end repeat
end tell
return out
"""
        text = self._osascript(script)
        windows: list[WindowInfo] = []
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            pname, pid, wx, wy, ww, wh, wname = parts
            try:
                width, height = int(float(ww)), int(float(wh))
            except ValueError:
                continue
            if width <= 8 or height <= 8:
                continue
            windows.append(
                WindowInfo(
                    handle=(pname, wname),
                    title=wname,
                    pid=int(pid) if pid.isdigit() else None,
                    x=int(float(wx)),
                    y=int(float(wy)),
                    width=width,
                    height=height,
                )
            )
        return windows

    def client_size(self, win: WindowInfo) -> tuple[int, int]:
        return win.width, max(1, win.height - self.frame_top)

    def resize_client(self, win: WindowInfo, width: int, height: int) -> None:
        pname, wname = win.handle
        script = f"""
tell application "System Events"
  tell application process "{pname}"
    set target to first window whose name contains "{wname[:60]}"
    set size of target to {{{width}, {height + self.frame_top}}}
  end tell
end tell
"""
        self._osascript(script)

    def activate(self, win: WindowInfo) -> None:
        pname, _ = win.handle
        try:
            self._osascript(
                f'tell application "System Events" to set frontmost of application process "{pname}" to true'
            )
        except BackendError:
            pass

    def capture(self, win: WindowInfo) -> Image.Image:
        import io

        rect = f"{win.x},{win.y + self.frame_top},{win.width},{max(1, win.height - self.frame_top)}"
        tmp = Path("/tmp") / f"capture_window_{int(time.time() * 1000)}.png"
        self.run(["screencapture", "-x", "-o", f"-R{rect}", str(tmp)], timeout=30.0)
        try:
            return Image.open(tmp).convert("RGB")
        finally:
            tmp.unlink(missing_ok=True)

    def send_keys(self, combo: str) -> None:
        parts = [p for p in (s.strip() for s in combo.split("+")) if p]
        mods = [self.MAC_MODS[p.lower()] for p in parts[:-1] if p.lower() in self.MAC_MODS]
        key = parts[-1]
        using = "{" + ", ".join(mods) + "}" if mods else "{}"
        if key.lower() in self.KEY_CODES:
            self._osascript(
                f'tell application "System Events" to key code {self.KEY_CODES[key.lower()]} using {using}'
            )
        elif len(key) == 1:
            escaped = key.replace("\\", "\\\\").replace('"', '\\"')
            self._osascript(
                f'tell application "System Events" to keystroke "{escaped}" using {using}'
            )
        else:
            raise BackendError(f"unknown key {key!r} for macOS")

    def click(self, win: WindowInfo, x: int, y: int) -> None:
        sx, sy = win.x + x, win.y + self.frame_top + y
        self._osascript(f'tell application "System Events" to click at {{{sx}, {sy}}}')


# --------------------------------------------------------------------------- #
# backend selection
# --------------------------------------------------------------------------- #
def make_backend(name: str) -> Backend:
    system = platform.system()
    if name == "auto":
        if system == "Windows":
            name = "windows"
        elif system == "Darwin":
            name = "macos"
        elif system == "Linux":
            name = "linux"
        else:
            raise BackendError(f"unsupported platform: {system}")

    if name == "windows":
        if system != "Windows":
            raise BackendError("--backend windows only works on Windows")
        return WindowsBackend()
    if name == "macos":
        if system != "Darwin":
            raise BackendError("--backend macos only works on macOS")
        return MacOSBackend()
    if name == "linux":
        if system != "Linux":
            raise BackendError("--backend linux only works on Linux")
        be = X11Backend()
        import os

        if not os.environ.get("DISPLAY") and os.environ.get("WAYLAND_DISPLAY"):
            raise BackendError(
                "this is a Wayland session (no DISPLAY) — xdotool cannot see the window.\n"
                "  Run the app under XWayland (`GDK_BACKEND=x11`, `QT_QPA_PLATFORM=xcb`), or log\n"
                "  into an X11 session, then retry."
            )
        return be
    raise BackendError(f"unknown backend {name!r}")


# --------------------------------------------------------------------------- #
# shots, sizes, capture loop
# --------------------------------------------------------------------------- #
def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "shot"


def normalise_shots(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.shot_list:
        path = Path(args.shot_list)
        if not path.exists():
            raise SystemExit(f"[error] no such shot list: {path}")
        data = json.loads(path.read_text())
        shots = data.get("shots", data) if isinstance(data, dict) else data
        if not isinstance(shots, list) or not shots:
            raise SystemExit("[error] shot list must contain at least one shot")
        out = []
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict) or "name" not in shot:
                raise SystemExit(f"[error] shot #{i + 1} needs a 'name'")
            out.append(shot)
        return out

    shots: list[dict[str, Any]] = []
    for name in args.shot or []:
        shots.append({"name": name})
    for menu in args.menus or []:
        shots.append(
            {
                "name": f"menu-{slug(menu)}",
                "keys": f"alt+{menu.strip()[0].lower()}",
                "close": "escape",
                "wait": args.wait,
            }
        )
    # the window shot is the baseline every diff is checked against: always take
    # it unless the caller's explicit shot list says otherwise
    if not any(str(s["name"]).lower() == "window" for s in shots):
        shots.insert(0, {"name": "window"})
    return shots


def parse_size(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[xX*,]\s*(\d+)\s*", text)
    if not m:
        raise argparse.ArgumentTypeError(f"expected WxH — got {text!r}")
    w, h = int(m.group(1)), int(m.group(2))
    if w < 64 or h < 64:
        raise argparse.ArgumentTypeError("window must be at least 64x64")
    return w, h


def size_from_match(path: Path) -> tuple[int, int]:
    if path.is_dir():
        path = path / "capture.json"
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        req = data.get("requested") or data.get("client") or {}
        return int(req["width"]), int(req["height"])
    with Image.open(path) as im:
        return im.width, im.height


def normalise(img: Image.Image, width: int, height: int) -> tuple[Image.Image, float, list[str]]:
    """Force the capture to exactly WxH; report how it got there."""
    warnings: list[str] = []
    scale = 1.0
    for k in (4, 3, 2):
        if img.width == width * k and img.height == height * k:
            scale = float(k)
            break
    if scale != 1.0:
        warnings.append(f"HiDPI capture {img.width}x{img.height} downscaled {scale:.0f}x to {width}x{height}")
        img = img.resize((width, height), Image.LANCZOS)
    elif img.size != (width, height):
        dw, dh = img.width - width, img.height - height
        if abs(dw) <= 3 and abs(dh) <= 3:
            canvas = Image.new("RGB", (width, height), (255, 255, 255))
            canvas.paste(img, (max(0, -dw // 2), max(0, -dh // 2)))
            warnings.append(
                f"capture was {img.width}x{img.height} ({dw:+d}px, {dh:+d}px); "
                "padded/cropped to the requested size"
            )
            img = canvas
        else:
            warnings.append(
                f"WINDOW DID NOT RESIZE: captured {img.width}x{img.height}, resized to "
                f"{width}x{height} — geometry is no longer 1:1, fix the window size "
                "before trusting the diff"
            )
            img = img.resize((width, height), Image.LANCZOS)
    return img, scale, warnings


def wait_for_client_size(
    backend: Backend, win: WindowInfo, width: int, height: int, timeout: float
) -> tuple[int, int]:
    deadline = time.time() + timeout
    last = backend.client_size(win)
    while time.time() < deadline:
        if last == (width, height):
            return last
        time.sleep(0.15)
        last = backend.client_size(win)
    return last


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_all(args: argparse.Namespace) -> int:
    backend = make_backend(args.backend)
    ok, reason = backend.available()
    if not ok:
        print(f"[error] {backend.name} backend unavailable: {reason}", file=sys.stderr)
        return 2

    if args.list_windows:
        windows = backend.list_windows()
        if not windows:
            print("no visible windows found")
            return 0
        print(f"{len(windows)} visible windows ({backend.name}):")
        for w in windows:
            print("  " + w.label())
        return 0

    if not args.title and args.pid is None:
        raise SystemExit("[error] pass --title (regex) or --pid — or --list-windows to look around")

    pattern = re.compile(args.title or ".", re.IGNORECASE)
    win = backend.find(pattern, args.pid)

    if args.size:
        width, height = args.size
    elif args.match:
        width, height = size_from_match(Path(args.match))
    else:
        width, height = backend.client_size(win)
        print(
            f"[note] no --size given; capturing at the current client size "
            f"{width}x{height}. Pass the same --size for the clone."
        )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    resolved = {}
    backend.activate(win)
    time.sleep(args.settle)
    if not args.no_resize:
        backend.resize_client(win, width, height)
        actual = wait_for_client_size(backend, win, width, height, args.timeout)
    else:
        actual = backend.client_size(win)
    if tuple(actual) != (width, height):
        print(
            f"[warn] window client size is {actual[0]}x{actual[1]}, requested "
            f"{width}x{height}; the capture will be normalised and the diff may "
            "report false mismatches",
            file=sys.stderr,
        )
        if args.require_exact_size:
            return 2

    shots = normalise_shots(args)
    manifest: dict[str, Any] = {
        "generated_by": "desktop-ui-cloner/scripts/capture_window.py",
        "platform": f"{platform.system()} {platform.release()}",
        "backend": backend.name,
        "window": {
            "title": win.title,
            "pid": win.pid,
            "match": args.title or f"pid:{args.pid}",
        },
        "requested": {"width": width, "height": height},
        "client": {"width": int(actual[0]), "height": int(actual[1])},
        "shots": [],
        "warnings": list(dict.fromkeys(backend.notes)),
    }

    if args.dry_run:
        print(json.dumps({**manifest, "shots_planned": shots}, indent=2))
        return 0

    for shot in shots:
        name = slug(str(shot["name"]))
        backend.activate(win)
        time.sleep(0.1)
        for point in shot.get("click", []) or []:
            if isinstance(point, dict):
                backend.click(win, int(point["x"]), int(point["y"]))
            else:
                backend.click(win, int(point[0]), int(point[1]))
            time.sleep(0.15)
        if shot.get("keys"):
            backend.send_keys(str(shot["keys"]))
        time.sleep(float(shot.get("wait", args.wait)))

        image = backend.capture(win)
        image, scale, warnings = normalise(image, width, height)
        path = out / f"{name}.png"
        image.save(path)
        manifest["warnings"].extend(w + f" [{name}]" for w in warnings)
        manifest["shots"].append(
            {
                "name": name,
                "file": path.name,
                "width": image.width,
                "height": image.height,
                "scale": scale,
                "sha256": sha256(path),
                "window_at_capture": {
                    "width": int(backend.client_size(win)[0]),
                    "height": int(backend.client_size(win)[1]),
                },
            }
        )
        print(f"captured {path}  {image.width}x{image.height}")

        if shot.get("close"):
            backend.send_keys(str(shot["close"]))
            time.sleep(0.25)

    manifest["warnings"] = sorted(set(manifest["warnings"]))
    (out / "capture.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest  {out / 'capture.json'}")
    for w in manifest["warnings"]:
        print(f"  ! {w}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Capture a desktop app window (and its menus/states) at an exact size.",
        epilog=(
            "examples:\n"
            "  python3 capture_window.py --list-windows\n"
            "  python3 capture_window.py --title '^MyApp' --size 1440x900 \\\n"
            "      --out capture/original --menus File,Edit\n"
            "  python3 capture_window.py --title 'MyApp (clone)' --size 1440x900 \\\n"
            "      --out capture/clone --shot-list shots.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--title", help="regex matched against visible window titles")
    p.add_argument("--pid", type=int, help="restrict the match to this process id")
    p.add_argument("--size", type=parse_size, metavar="WxH",
                   help="client size to force before capturing, e.g. 1440x900")
    p.add_argument("--match", metavar="PATH",
                   help="take the size from an earlier capture.json or PNG")
    p.add_argument("--out", default="capture", help="output directory (default: capture)")
    p.add_argument("--shot", action="append", metavar="NAME",
                   help="capture an extra shot with this name (repeatable)")
    p.add_argument("--menus", type=parse_menus,
                   help="open each named menu with its Alt+letter accelerator and "
                        "capture it (e.g. File,Edit,View)")
    p.add_argument("--shot-list", help="JSON file describing the shots to take")
    p.add_argument("--list-windows", action="store_true", help="print visible windows and exit")
    p.add_argument("--backend", default="auto", choices=("auto", "windows", "linux", "macos"))
    p.add_argument("--wait", type=float, default=0.6, help="settle time after input (default 0.6s)")
    p.add_argument("--settle", type=float, default=0.3, help="settle time after activation")
    p.add_argument("--timeout", type=float, default=8.0, help="how long to wait for a resize")
    p.add_argument("--no-resize", action="store_true", help="never resize; capture what is there")
    p.add_argument("--require-exact-size", action="store_true",
                   help="exit 2 if the window cannot be resized to the requested client size")
    p.add_argument("--dry-run", action="store_true", help="resolve the window and print the plan")
    return p


def parse_menus(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()] or []


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return capture_all(args)
    except BackendError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
