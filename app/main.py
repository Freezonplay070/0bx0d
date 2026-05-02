# -*- coding: utf-8 -*-
"""0bx0d? -- DPI bypass tool v3.0"""
import ctypes, math, os, random, socket, struct, subprocess, sys, tempfile, time, winreg
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QPointF,
    QRect, QRectF, QSize,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPixmap, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QSizePolicy,
    QStackedWidget,
)

# =====================================================================
#  CONSTANTS
# =====================================================================
APP_NAME = "0bx0d"
VERSION  = "3.0"
BIN_DIR  = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

# -- palette --
BG       = "#0e0e12"
SURFACE  = "#141419"
CARD     = "#1a1a22"
CARD2    = "#20202c"
BORDER   = "#252530"
ACCENT   = "#e53935"
ACCENT2  = "#ff5252"
ACCENT_DK= "#7f1d1d"
GREEN    = "#4caf50"
YELLOW   = "#ffc107"
ORANGE   = "#ff6d00"
TEXT     = "#e0e0e6"
TEXT2    = "#8e8ea0"
TEXT3    = "#4a4a5a"

# -- discord domains (written to temp file for --blacklist) --
DISCORD_DOMAINS = [
    "discord.com", "discordapp.com", "discord.gg",
    "discord.media", "discordcdn.com",
]
_blacklist_path: str | None = None

def _ensure_blacklist_file() -> str:
    global _blacklist_path
    if _blacklist_path and os.path.exists(_blacklist_path):
        return _blacklist_path
    fd, path = tempfile.mkstemp(prefix="0bx0d_bl_", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        for d in DISCORD_DOMAINS:
            f.write(d + "\n")
    _blacklist_path = path
    return path

PRESETS = {
    "Discord + Game (UDP)": {
        "mode": "DISCORD",
        "args": ["-k","2","-e","2","-f","1","--wrong-chksum","--wrong-seq",
                 "--native-frag","--reverse-frag","--max-payload","1200"],
    },
    "Discord Only": {
        "mode": "DISCORD",
        "args": ["-k","2","-e","2","-f","1","--wrong-chksum",
                 "--native-frag","--reverse-frag","--max-payload","1200"],
    },
    "All Traffic": {
        "mode": "ALL",
        "args": ["-k","2","-e","2","-f","2","--wrong-chksum","--wrong-seq",
                 "--native-frag","--reverse-frag","--max-payload","1200"],
    },
    "Stealth Stream": {
        "mode": "ALL",
        "args": ["-k","2","-e","2","-f","2",
                 "--native-frag","--reverse-frag","--max-payload","1200"],
    },
}

def _blacklist_args(mode: str) -> list[str]:
    if mode == "DISCORD":
        return ["--blacklist", _ensure_blacklist_file()]
    return []

DNS_SERVERS = {
    "Google":     ("8.8.8.8",        "8.8.4.4"),
    "Cloudflare": ("1.1.1.1",        "1.0.0.1"),
    "Quad9":      ("9.9.9.9",        "149.112.112.112"),
    "AdGuard":    ("94.140.14.14",   "94.140.15.15"),
    "OpenDNS":    ("208.67.222.222", "208.67.220.220"),
    "Yandex":     ("77.88.8.8",      "77.88.8.1"),
}

# =====================================================================
#  FONTS
# =====================================================================
def ui_font(px: int, bold=False) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Roboto", "Arial"])
    f.setPixelSize(px)
    if bold: f.setWeight(QFont.Weight.DemiBold)
    return f

def mono_font(px: int, bold=False) -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"])
    f.setPixelSize(px)
    if bold: f.setWeight(QFont.Weight.Bold)
    return f

# =====================================================================
#  ADMIN / AUTOSTART
# =====================================================================
def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)

def set_autostart(on: bool):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                           winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if on:
            val = (sys.executable if getattr(sys, "frozen", False)
                   else f'"{sys.executable}" "{os.path.abspath(__file__)}"')
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, val)
        else:
            try: winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError: pass
        winreg.CloseKey(k)
    except: pass

def get_autostart() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k, APP_NAME); winreg.CloseKey(k); return True
    except: return False

# =====================================================================
#  DNS UTILITIES
# =====================================================================
_original_dns: dict[str, str] = {}

def get_adapters() -> list[str]:
    try:
        r = subprocess.run(["netsh", "interface", "show", "interface"],
                           capture_output=True, text=True, timeout=5)
        out = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] in ("Connected", "Enabled", u"Підключено"):
                out.append(" ".join(parts[3:]))
        return out or ["Wi-Fi", "Ethernet"]
    except: return ["Wi-Fi", "Ethernet"]

def get_dns_ips(adapter: str) -> tuple[str, str]:
    try:
        r = subprocess.run(["netsh", "interface", "ip", "show", "dns", adapter],
                           capture_output=True, text=True, timeout=5)
        ips = []
        for line in r.stdout.splitlines():
            for p in line.strip().split():
                if p.count(".") == 3:
                    try: socket.inet_aton(p); ips.append(p)
                    except: pass
        return (ips[0] if ips else "", ips[1] if len(ips) > 1 else "")
    except: return ("", "")

def save_original_dns(adapter: str):
    if adapter not in _original_dns:
        p, s = get_dns_ips(adapter)
        _original_dns[adapter] = f"{p},{s}"

def get_original_dns(adapter: str) -> tuple[str, str]:
    raw = _original_dns.get(adapter, ",")
    parts = raw.split(",", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def check_dns_latency(server_ip: str) -> float | None:
    try:
        tid = random.randint(1, 65535)
        hdr = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
        qname = b"\x06google\x03com\x00"
        question = qname + struct.pack(">HH", 1, 1)
        query = hdr + question
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        t0 = time.perf_counter()
        s.sendto(query, (server_ip, 53))
        s.recv(512)
        ms = (time.perf_counter() - t0) * 1000
        s.close()
        return round(ms, 1)
    except: return None

# =====================================================================
#  WORKERS
# =====================================================================
class TunnelWorker(QObject):
    log     = Signal(str)
    started = Signal()
    stopped = Signal()
    error   = Signal(str)
    _go     = Signal(list, bool)

    def __init__(self):
        super().__init__()
        self._proc = None; self._run = False
        self._cmd = []; self._ks = False
        self._go.connect(self._start)

    def launch(self, preset_name: str, ks: bool):
        p = PRESETS.get(preset_name, list(PRESETS.values())[0])
        cmd = [str(BIN_DIR / "goodbyedpi.exe")] + p["args"] + _blacklist_args(p["mode"])
        self._go.emit(cmd, ks)

    def _kill_old(self):
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if (proc.info["name"] or "").lower() == "goodbyedpi.exe":
                    proc.kill(); proc.wait(3)
            except: pass

    def _start(self, cmd, ks):
        self._run = True; self._cmd = cmd; self._ks = ks
        self._kill_old()
        self.log.emit("→ " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit()
            self._watch()
        except OSError as e:
            self.error.emit(str(e))

    def _watch(self):
        t_start = time.monotonic()
        while self._run:
            if not self._proc: break
            if self._proc.poll() is not None:
                uptime = time.monotonic() - t_start
                if self._run and self._ks:
                    if uptime < 5:
                        self.error.emit(
                            "Process exited in <5s — likely a config error. "
                            "Kill switch disabled to prevent loop.")
                        break
                    self.log.emit("⚡ kill switch triggered, restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        t_start = time.monotonic()
                        continue
                    except OSError as e:
                        self.error.emit(str(e)); break
                else:
                    self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line:
                    text = line.decode("utf-8", "replace").strip()
                    if text:
                        self.log.emit(text)
            else:
                time.sleep(0.05)

    def stop(self):
        self._run = False
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(4)
            except: self._proc.kill()
        self._proc = None; self._kill_old(); self.stopped.emit()


class PingWorker(QObject):
    result  = Signal(object)
    _active = False

    def run(self):
        self._active = True
        while self._active:
            try:
                s = socket.socket(); s.settimeout(2.5)
                t0 = time.perf_counter()
                s.connect(("discord.com", 443))
                self.result.emit(round((time.perf_counter() - t0) * 1000, 1))
                s.close()
            except:
                self.result.emit(None)
            time.sleep(5)

    def stop(self): self._active = False


class DnsWorker(QObject):
    log           = Signal(str)
    done          = Signal(bool, str)
    _go           = Signal(str, str, str)
    _rst          = Signal(str)
    check_all_req = Signal()
    dns_result    = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._go.connect(self._apply)
        self._rst.connect(self._reset)
        self.check_all_req.connect(self._check_all)

    def apply(self, adapter, primary, secondary): self._go.emit(adapter, primary, secondary)
    def reset(self, adapter): self._rst.emit(adapter)
    def check_latency(self): self.check_all_req.emit()

    def _apply(self, adapter, primary, secondary):
        save_original_dns(adapter)
        self.log.emit(f"Applying DNS → {primary}" + (f" / {secondary}" if secondary else ""))
        try:
            subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "static", primary],
                           capture_output=True, timeout=8)
            if secondary:
                subprocess.run(["netsh", "interface", "ip", "add", "dns", adapter, secondary, "index=2"],
                               capture_output=True, timeout=8)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, f"✓ DNS set to {primary}")
        except Exception as e:
            self.done.emit(False, f"✗ DNS error: {e}")

    def _reset(self, adapter):
        orig_p, orig_s = get_original_dns(adapter)
        if orig_p:
            self.log.emit(f"Restoring DNS → {orig_p}")
            try:
                subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "static", orig_p],
                               capture_output=True, timeout=8)
                if orig_s:
                    subprocess.run(["netsh", "interface", "ip", "add", "dns", adapter, orig_s, "index=2"],
                                   capture_output=True, timeout=8)
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
                self.done.emit(True, f"✓ Original DNS restored ({orig_p})")
                return
            except Exception as e:
                self.done.emit(False, f"✗ {e}"); return
        self.log.emit("Resetting DNS → DHCP auto")
        try:
            subprocess.run(["netsh", "interface", "ip", "set", "dns", adapter, "dhcp"],
                           capture_output=True, timeout=8)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, "✓ DNS reset to auto (DHCP)")
        except Exception as e:
            self.done.emit(False, f"✗ {e}")

    def _check_all(self):
        self.log.emit("Checking DNS latency...")
        for name, (ip, _) in DNS_SERVERS.items():
            ms = check_dns_latency(ip)
            self.dns_result.emit(name, ms)
        self.log.emit("✓ Latency check complete")

# =====================================================================
#  BACKGROUND FRAME (noise + vignette)
# =====================================================================
_NOISE_PIX: QPixmap | None = None

def _get_noise(w, h) -> QPixmap:
    global _NOISE_PIX
    if _NOISE_PIX and _NOISE_PIX.width() >= w and _NOISE_PIX.height() >= h:
        return _NOISE_PIX
    pix = QPixmap(w, h); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); rng = random.Random(42)
    for _ in range(w * h // 12):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        v = rng.randint(120, 220); a = rng.randint(2, 6)
        p.setPen(QColor(v, v, v, a)); p.drawPoint(x, y)
    p.end(); _NOISE_PIX = pix; return pix


class BgFrame(QWidget):
    def paintEvent(self, _):
        p = QPainter(self); r = self.rect()
        p.fillRect(r, QColor(BG))
        p.drawPixmap(0, 0, _get_noise(r.width(), r.height()))
        g = QRadialGradient(r.width() / 2, r.height() / 2, max(r.width(), r.height()) * 0.6)
        g.setColorAt(0.0, QColor(20, 8, 8, 8))
        g.setColorAt(0.6, QColor(0, 0, 0, 0))
        g.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.fillRect(r, g); p.end()

# =====================================================================
#  CARD
# =====================================================================
class Card(QWidget):
    def __init__(self, parent=None, radius=10):
        super().__init__(parent); self._r = radius

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor(CARD)); p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(r, self._r, self._r)
        g = QLinearGradient(0, 0, 0, 20)
        g.setColorAt(0, QColor(255, 255, 255, 4)); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, self._r, self._r)
        p.end()

# =====================================================================
#  SIDEBAR BUTTON (painted icons)
# =====================================================================
class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self, icon_id: str, tooltip="", parent=None):
        super().__init__(parent)
        self._id = icon_id; self._tip = tooltip
        self._hover = False; self._active = False
        self.setFixedSize(54, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip: self.setToolTip(tooltip)

    def set_active(self, v): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self._active:
            p.fillRect(r, QColor(26, 14, 14))
            p.fillRect(QRectF(0, 6, 2.5, r.height() - 12), QColor(ACCENT))
        elif self._hover:
            p.fillRect(r, QColor(22, 18, 20))

        col = QColor(ACCENT) if self._active else (QColor(TEXT2) if self._hover else QColor(TEXT3))
        cx, cy = r.width() / 2, r.height() / 2
        p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        if self._id == "home":
            s = 4
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                p.setBrush(col if self._active else Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(QRectF(cx + dx * 5 - s / 2, cy + dy * 5 - s / 2, s, s), 1, 1)
            p.setBrush(Qt.BrushStyle.NoBrush)
        elif self._id == "logs":
            for i, w in enumerate([16, 12, 14]):
                y = cy - 6 + i * 6
                p.drawLine(QPointF(cx - w / 2, y), QPointF(cx + w / 2, y))
        elif self._id == "settings":
            r2 = 7
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r2, r2)
            p.setBrush(col)
            p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)
        elif self._id == "dns":
            r2 = 8
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r2, r2)
            p.drawLine(QPointF(cx - r2, cy), QPointF(cx + r2, cy))
            path = QPainterPath()
            path.moveTo(cx, cy - r2)
            path.quadTo(cx - 5, cy, cx, cy + r2)
            p.drawPath(path)
            path2 = QPainterPath()
            path2.moveTo(cx, cy - r2)
            path2.quadTo(cx + 5, cy, cx, cy + r2)
            p.drawPath(path2)
        elif self._id == "info":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 8, 8)
            f = ui_font(12, bold=True); p.setFont(f)
            p.drawText(QRect(0, 0, r.width(), r.height()), Qt.AlignmentFlag.AlignCenter, "i")
        p.end()

# =====================================================================
#  STATUS BADGE
# =====================================================================
class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False; self._phase = 0.0
        self.setFixedSize(140, 26)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def set_on(self, v): self._on = v; self.update()

    def _tick(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        if self._on: self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())

        if self._on:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            bg, border = QColor(35, 12, 12), QColor(ACCENT)
            dot_col = QColor(255, int(80 + 80 * pulse), int(60 + 60 * pulse))
            text, text_col = "CONNECTED", QColor(ACCENT)
        else:
            pulse = 0
            bg, border = QColor(20, 20, 26), QColor(BORDER)
            dot_col = QColor(TEXT3)
            text, text_col = "OFFLINE", QColor(TEXT3)

        p.setBrush(bg); p.setPen(QPen(border, 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 13, 13)

        p.setBrush(dot_col); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(16, 13), 3.5, 3.5)
        if self._on:
            g = QRadialGradient(16, 13, 8)
            g.setColorAt(0, QColor(255, 60, 60, int(50 * pulse)))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.drawEllipse(QPointF(16, 13), 8, 8)

        f = ui_font(10, bold=True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(f); p.setPen(text_col)
        p.drawText(QRect(28, 0, self.width() - 30, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, text)
        p.end()

# =====================================================================
#  POWER BUTTON (replaces eye)
# =====================================================================
class PowerButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False; self._hover = False; self._phase = 0.0
        self.setFixedSize(160, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def _tick(self):
        self._phase = (self._phase + 0.04) % (2 * math.pi)
        if self._active or self._hover: self.update()

    def set_active(self, v): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 - 10
        R = 56

        if self._active:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            for i in range(4):
                g = QRadialGradient(cx, cy, R + 12 + i * 10)
                g.setColorAt(0, QColor(229, 57, 53, int((35 - i * 7) * (0.6 + 0.4 * pulse))))
                g.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), R + 12 + i * 10, R + 12 + i * 10)

            bg = QRadialGradient(cx, cy - 8, R)
            bg.setColorAt(0, QColor(55, 12, 12)); bg.setColorAt(1, QColor(30, 6, 6))
            p.setBrush(bg)
            p.setPen(QPen(QColor(229, 57, 53, int(160 + 90 * pulse)), 2))
            p.drawEllipse(QPointF(cx, cy), R, R)
            icon_col = QColor(255, 255, 255, 230)
        else:
            bg = QRadialGradient(cx, cy - 8, R)
            bg.setColorAt(0, QColor(32, 32, 42)); bg.setColorAt(1, QColor(22, 22, 30))
            p.setBrush(bg)
            border = QColor(ACCENT) if self._hover else QColor(BORDER)
            p.setPen(QPen(border, 1.5))
            p.drawEllipse(QPointF(cx, cy), R, R)
            icon_col = QColor(ACCENT) if self._hover else QColor(TEXT3)

        pen = QPen(icon_col, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 18), QPointF(cx, cy - 6))
        arc_r = 16
        arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
        p.drawArc(arc_rect, 50 * 16, -280 * 16)

        f = ui_font(10, bold=True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(f)
        label_y = int(cy + R + 14)
        if self._active:
            p.setPen(QColor(ACCENT2))
            p.drawText(QRect(0, label_y, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, "ACTIVE")
        else:
            p.setPen(QColor(ACCENT) if self._hover else QColor(TEXT3))
            p.drawText(QRect(0, label_y, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, "ACTIVATE")
        p.end()

# =====================================================================
#  TOGGLE SWITCH (modern pill)
# =====================================================================
class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, label, checked=False, parent=None):
        super().__init__(parent)
        self._c = checked; self._label = label; self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def isChecked(self): return self._c
    def setChecked(self, v): self._c = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._c = not self._c; self.update(); self.toggled.emit(self._c)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tw, th = 34, 18
        ty = (self.height() - th) // 2
        track = QRectF(0, ty, tw, th)
        if self._c:
            p.setBrush(QColor(ACCENT)); p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(BORDER)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track, th / 2, th / 2)

        thumb_r = (th - 6) / 2
        thumb_x = tw - thumb_r - 4 if self._c else thumb_r + 4
        thumb_y = ty + th / 2
        p.setBrush(QColor(255, 255, 255) if self._c else QColor(TEXT3))
        p.drawEllipse(QPointF(thumb_x, thumb_y), thumb_r, thumb_r)

        p.setFont(ui_font(11))
        p.setPen(QColor(TEXT) if (self._hover or self._c) else QColor(TEXT2))
        p.drawText(QRect(tw + 10, 0, 300, self.height()), Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()

    def sizeHint(self): return QSize(200, 26)

# =====================================================================
#  TERMINAL
# =====================================================================
class Terminal(QTextEdit):
    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        sz = 11 if not compact else 10
        self.document().setDefaultStyleSheet("p{margin:1px 0;padding:0;}")
        self.setStyleSheet(f"""
            QTextEdit {{
                background: #101014; color: {TEXT2};
                border: 1px solid {BORDER}; border-radius: 8px;
                padding: 10px 12px;
                font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;
                font-size: {sz}px; line-height: 1.6;
            }}
            QScrollBar:vertical {{
                background: #101014; width: 6px; border: none; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {TEXT3}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._queue: list[str] = []; self._busy = False

    def _col(self, t: str) -> str:
        lo = t.lower()
        if any(x in lo for x in ("error", "✗", "fail", "blocked", "no admin", "missing", "can't")):
            return ACCENT2
        if any(x in lo for x in ("✓", "ok", "activ", "enjoy", "▶", "alive", "success", "set", "restored")):
            return GREEN
        if "⚡" in lo or "warn" in lo or "restart" in lo:
            return ORANGE
        if t.startswith("→"):
            return TEXT3
        return TEXT2

    def queue_line(self, text: str):
        if not text.strip(): return
        ts = datetime.now().strftime("%H:%M:%S")
        col = self._col(text)
        html = (f'<p><span style="color:{TEXT3};font-size:9px">[{ts}]</span>'
                f'&nbsp;<span style="color:{col}">{text}</span></p>')
        self._queue.append(html)
        if not self._busy: self._pop()

    def _pop(self):
        if not self._queue: self._busy = False; return
        self._busy = True; self.append(self._queue.pop(0))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QTimer.singleShot(35, self._pop)

# =====================================================================
#  BUTTONS
# =====================================================================
class Btn(QPushButton):
    def __init__(self, text, accent=False, parent=None):
        super().__init__(text, parent)
        self._accent = accent; self._hover = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:none;background:transparent;")

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self._accent:
            bg = QColor(40, 12, 12) if self._hover else QColor(28, 8, 8)
            bc = QColor(ACCENT) if self._hover else QColor(ACCENT_DK)
        else:
            bg = QColor(26, 26, 34) if self._hover else QColor(CARD)
            bc = QColor(TEXT3) if self._hover else QColor(BORDER)
        p.setBrush(bg); p.setPen(QPen(bc, 1))
        p.drawRoundedRect(r, 6, 6)

        f = ui_font(10, bold=True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(f)
        col = QColor(ACCENT2) if (self._hover and self._accent) else \
              QColor(TEXT) if self._hover else QColor(TEXT2)
        p.setPen(col)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()

# =====================================================================
#  DNS CARD
# =====================================================================
class DnsCard(QWidget):
    selected = Signal(str)
    MAX_MS = 300.0

    def __init__(self, name, ip1, ip2="", parent=None):
        super().__init__(parent)
        self._name = name; self._ip1 = ip1; self._ip2 = ip2
        self._latency: float | None = None
        self._checking = False; self._sel = False; self._hover = False
        self.setMinimumWidth(100); self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_latency(self, ms): self._latency = ms; self._checking = False; self.update()
    def set_checking(self): self._checking = True; self.update()
    def set_selected(self, v): self._sel = v; self.update()
    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.selected.emit(self._name)

    def _lat_color(self, ms: float) -> QColor:
        if ms < 50: return QColor(GREEN)
        if ms < 100: return QColor(YELLOW)
        if ms < 200: return QColor(ORANGE)
        return QColor(ACCENT)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        bg = QColor(30, 14, 14) if self._sel else (QColor(26, 26, 34) if self._hover else QColor(CARD))
        bc = QColor(ACCENT) if self._sel else (QColor(TEXT3) if self._hover else QColor(BORDER))
        p.setBrush(bg); p.setPen(QPen(bc, 1))
        p.drawRoundedRect(r, 8, 8)

        if self._sel:
            p.fillRect(QRectF(1, 12, 2.5, r.height() - 22), QColor(ACCENT))

        p.setFont(ui_font(11, bold=True))
        p.setPen(QColor(TEXT) if self._sel else (QColor(TEXT) if self._hover else QColor(TEXT2)))
        p.drawText(QRect(12, 8, self.width() - 14, 18), Qt.AlignmentFlag.AlignLeft, self._name)

        p.setFont(mono_font(9))
        p.setPen(QColor(TEXT3))
        p.drawText(QRect(12, 24, self.width() - 14, 14), Qt.AlignmentFlag.AlignLeft, self._ip1)

        bar_x, bar_y, bar_h = 12, 42, 6
        bar_w = self.width() - 24
        p.setBrush(QColor(18, 18, 24)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        if self._checking:
            p.setBrush(QColor(35, 25, 25))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * 0.3, bar_h), 3, 3)
        elif self._latency is not None:
            fill = min(1.0, self._latency / self.MAX_MS)
            col = self._lat_color(self._latency)
            g = QLinearGradient(bar_x, 0, bar_x + bar_w * fill, 0)
            g.setColorAt(0, col); g.setColorAt(1, QColor(col.red() // 2, col.green() // 2, col.blue() // 2))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * fill, bar_h), 3, 3)

        p.setFont(mono_font(9, bold=True))
        if self._checking:
            p.setPen(QColor(TEXT3)); txt = "..."
        elif self._latency is None:
            p.setPen(QColor(TEXT3)); txt = "—"
        else:
            p.setPen(self._lat_color(self._latency))
            txt = f"{self._latency:.0f} ms"
        p.drawText(QRect(12, 52, self.width() - 14, 18), Qt.AlignmentFlag.AlignLeft, txt)
        p.end()

# =====================================================================
#  TITLE BAR
# =====================================================================
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._win = parent; self._drag = QPoint()
        self.setFixedHeight(42)
        self.setStyleSheet(f"background:{SURFACE};")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 8, 0); lay.setSpacing(0)
        lay.addSpacing(54)

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{BORDER}; max-width:1px;"); lay.addWidget(div)
        lay.addSpacing(14)

        title = QLabel(f"0bx0d?")
        title.setFont(ui_font(15, bold=True))
        title.setStyleSheet(f"color:{TEXT};"); lay.addWidget(title)

        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color:{TEXT3}; font-size:9px; font-family:monospace; margin-left:8px;")
        lay.addWidget(ver); lay.addStretch()

        self._badge = StatusBadge(); lay.addWidget(self._badge)
        lay.addSpacing(12)

        for sym, slot in [("—", parent.showMinimized), ("✕", parent.close)]:
            btn = QPushButton(sym); btn.setFixedSize(30, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{TEXT3};border:none;"
                "font-size:13px;font-weight:700;border-radius:4px;}"
                f"QPushButton:hover{{background:{BORDER};color:{TEXT};}}")
            btn.clicked.connect(slot); lay.addWidget(btn)

    def set_connected(self, on): self._badge.set_on(on)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(e.globalPosition().toPoint() - self._drag)

# =====================================================================
#  HELPERS
# =====================================================================
def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    f = ui_font(10, bold=True)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{TEXT3};")
    return lbl

def hdiv() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{BORDER}; max-height:1px;")
    return f

# =====================================================================
#  GLOBAL STYLESHEET
# =====================================================================
QSS = f"""
* {{ color: {TEXT}; }}
QWidget {{ background: transparent; }}
QComboBox {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 6px 12px;
    font-family: 'Segoe UI','Inter','Roboto',sans-serif; font-size: 12px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    selection-background-color: {BORDER}; selection-color: {ACCENT2};
    font-family: 'Segoe UI',sans-serif; outline: none; padding: 4px;
}}
QScrollBar:horizontal {{ height: 0; }}
QToolTip {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    font-family: 'Segoe UI',sans-serif; padding: 5px; font-size: 11px;
}}
"""

# =====================================================================
#  MAIN WINDOW
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(780, 560); self.resize(820, 600)
        self.setWindowTitle("0bx0d?")
        self._on = False; self._ping = None
        self._dns_sel: str | None = None
        self._setup_ui(); self._setup_workers()
        QTimer.singleShot(250, self._startup)

    def _setup_ui(self):
        root = BgFrame(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)

        sb = QWidget(); sb.setFixedWidth(54)
        sb.setStyleSheet(f"background:{SURFACE};")
        sl = QVBoxLayout(sb); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(2)
        sl.addSpacing(44)
        self._sbs = [
            SideBtn("home", "Dashboard"),
            SideBtn("logs", "Session Logs"),
            SideBtn("settings", "Settings"),
            SideBtn("dns", "DNS Manager"),
            SideBtn("info", "About"),
        ]
        self._sbs[0].set_active(True)
        for b in self._sbs: sl.addWidget(b)
        sl.addStretch()
        hl.addWidget(sb)

        right = QWidget()
        rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        self._tbar = TitleBar(self); rv.addWidget(self._tbar)
        rv.addWidget(hdiv())
        self._stack = QStackedWidget()
        for page in [self._build_dash(), self._build_logs(),
                     self._build_sett(), self._build_dns(), self._build_info()]:
            self._stack.addWidget(page)
        rv.addWidget(self._stack)
        hl.addWidget(right)

        for i, b in enumerate(self._sbs):
            b.clicked.connect(lambda _=None, idx=i: self._nav(idx))

    def _nav(self, i):
        self._stack.setCurrentIndex(i)
        for j, b in enumerate(self._sbs): b.set_active(j == i)

    # -- DASHBOARD --
    def _build_dash(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(14)

        top = QHBoxLayout(); top.setSpacing(20)
        self._pwr = PowerButton(); self._pwr.clicked.connect(self._toggle)
        top.addWidget(self._pwr, 0, Qt.AlignmentFlag.AlignVCenter)

        rc = Card(radius=10); rc_vl = QVBoxLayout(rc)
        rc_vl.setContentsMargins(18, 16, 18, 16); rc_vl.setSpacing(10)

        src_btn = Btn("VIEW SOURCE", accent=True); src_btn.setFixedHeight(42)
        src_btn.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        rc_vl.addWidget(src_btn)

        sub = QLabel("open source DPI bypass tool")
        sub.setFont(ui_font(10)); sub.setStyleSheet(f"color:{TEXT3};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); rc_vl.addWidget(sub)

        rc_vl.addWidget(hdiv())
        rc_vl.addWidget(section_label("PRESET"))
        self._preset = QComboBox()
        self._preset.addItems(list(PRESETS.keys()))
        rc_vl.addWidget(self._preset); rc_vl.addStretch()
        top.addWidget(rc)
        vl.addLayout(top)

        lc = Card(radius=10); lc_vl = QVBoxLayout(lc)
        lc_vl.setContentsMargins(14, 10, 14, 10); lc_vl.setSpacing(6)
        lc_vl.addWidget(section_label("LIVE LOGS"))
        self._term = Terminal(compact=True)
        self._term.setMinimumHeight(110); self._term.setMaximumHeight(150)
        lc_vl.addWidget(self._term)
        vl.addWidget(lc)

        bot = QHBoxLayout(); bot.setSpacing(20)
        self._auto = ToggleSwitch("Autostart", get_autostart())
        self._auto.toggled.connect(set_autostart)
        self._ks = ToggleSwitch("Kill Switch", True)
        bot.addWidget(self._auto); bot.addWidget(self._ks); bot.addStretch()
        bl = QLabel("by solevoyq")
        bl.setFont(ui_font(9)); bl.setStyleSheet(f"color:{TEXT3};")
        bot.addWidget(bl)
        vl.addLayout(bot)
        return page

    # -- LOGS --
    def _build_logs(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16)
        vl.addWidget(section_label("SESSION LOG")); vl.addSpacing(6)
        self._full = Terminal(); vl.addWidget(self._full)
        return page

    # -- SETTINGS --
    def _build_sett(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(12)
        vl.addWidget(section_label("SETTINGS")); vl.addWidget(hdiv())

        c1 = Card(radius=10); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(18, 16, 18, 16); c1l.setSpacing(12)

        c1l.addWidget(section_label("STARTUP"))
        a2 = ToggleSwitch("Launch on Windows login", get_autostart())
        a2.toggled.connect(set_autostart); a2.toggled.connect(self._auto.setChecked)
        c1l.addWidget(a2)

        c1l.addWidget(hdiv())
        c1l.addWidget(section_label("PROTECTION"))
        k2 = ToggleSwitch("Auto-restart on unexpected exit", True)
        k2.toggled.connect(self._ks.setChecked)
        c1l.addWidget(k2)
        vl.addWidget(c1)

        vl.addStretch()
        info = QLabel(f"0bx0d? v{VERSION}  ·  GoodbyeDPI v0.2.2  ·  MIT License")
        info.setFont(ui_font(10)); info.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(info)
        return page

    # -- DNS --
    def _build_dns(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(24, 20, 24, 16); vl.setSpacing(10)

        h = QHBoxLayout()
        h.addWidget(section_label("DNS MANAGER")); h.addStretch()
        ref = Btn("Refresh"); ref.setFixedWidth(90); ref.clicked.connect(self._dns_refresh)
        chk = Btn("Check All", accent=True); chk.setFixedWidth(100)
        chk.clicked.connect(self._dns_check_all)
        h.addWidget(ref); h.addSpacing(6); h.addWidget(chk)
        vl.addLayout(h); vl.addWidget(hdiv())

        ac = Card(radius=8); acl = QHBoxLayout(ac)
        acl.setContentsMargins(14, 10, 14, 10); acl.setSpacing(10)
        al = QLabel("Adapter")
        al.setFont(ui_font(10, bold=True)); al.setStyleSheet(f"color:{TEXT3};")
        al.setFixedWidth(60); acl.addWidget(al)
        self._adapter = QComboBox()
        self._adapter.addItems(get_adapters())
        self._adapter.currentTextChanged.connect(self._dns_show_current)
        acl.addWidget(self._adapter); acl.addSpacing(12)
        self._dns_cur_lbl = QLabel("—")
        self._dns_cur_lbl.setFont(mono_font(11))
        self._dns_cur_lbl.setStyleSheet(f"color:{TEXT2};")
        acl.addWidget(self._dns_cur_lbl, 1)
        vl.addWidget(ac)

        vl.addWidget(section_label("SERVERS"))
        self._dns_cards: dict[str, DnsCard] = {}
        grid_w = QWidget(); grid_l = QHBoxLayout(grid_w)
        grid_l.setContentsMargins(0, 0, 0, 0); grid_l.setSpacing(6)
        for name, (ip1, ip2) in DNS_SERVERS.items():
            card = DnsCard(name, ip1, ip2)
            card.selected.connect(self._dns_select)
            self._dns_cards[name] = card; grid_l.addWidget(card)
        vl.addWidget(grid_w)

        self._orig_lbl = QLabel("Original DNS not saved yet")
        self._orig_lbl.setFont(ui_font(9)); self._orig_lbl.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(self._orig_lbl)

        ab = QHBoxLayout(); ab.setSpacing(8)
        self._dns_act = Btn("Apply Selected", accent=True)
        self._dns_act.clicked.connect(self._dns_activate)
        self._dns_rst = Btn("Restore Original")
        self._dns_rst.clicked.connect(self._dns_restore)
        self._dns_dhcp = Btn("Reset to DHCP")
        self._dns_dhcp.clicked.connect(self._dns_reset_dhcp)
        ab.addWidget(self._dns_act); ab.addWidget(self._dns_rst); ab.addWidget(self._dns_dhcp)
        ab.addStretch(); vl.addLayout(ab)

        self._dns_log = Terminal(compact=True); self._dns_log.setMaximumHeight(80)
        vl.addWidget(self._dns_log)
        QTimer.singleShot(400, self._dns_show_current)
        return page

    # -- ABOUT --
    def _build_info(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page); vl.setContentsMargins(28, 24, 28, 20); vl.setSpacing(16)

        title = QLabel("0bx0d?")
        title.setFont(ui_font(28, bold=True))
        title.setStyleSheet(f"color:{ACCENT};"); vl.addWidget(title)

        c = Card(radius=10); cl = QVBoxLayout(c)
        cl.setContentsMargins(20, 18, 20, 18); cl.setSpacing(10)
        cl.addWidget(section_label("HOW IT WORKS"))
        desc = QLabel(
            "GoodbyeDPI intercepts TCP/UDP packets via the WinDivert driver "
            "and modifies headers — fragmentation, wrong checksums, fake ACKs — "
            "so that ISP deep packet inspection can't reassemble the stream.\n\n"
            "Discord Voice uses UDP on ports 50000–65535. "
            "The tool targets Discord CDN domains via a blacklist file passed to GoodbyeDPI."
        )
        desc.setWordWrap(True)
        desc.setFont(ui_font(11)); desc.setStyleSheet(f"color:{TEXT2}; line-height:1.5;")
        cl.addWidget(desc)
        vl.addWidget(c)

        brow = QHBoxLayout(); brow.setSpacing(8)
        gh = Btn("GitHub →", accent=True); gh.setFixedWidth(120)
        gh.clicked.connect(lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        brow.addWidget(gh); brow.addStretch()
        vl.addLayout(brow)
        vl.addStretch()

        ft = QLabel(f"v{VERSION}  ·  by solevoyq  ·  MIT  ·  not malware, just raw code")
        ft.setFont(ui_font(9)); ft.setStyleSheet(f"color:{TEXT3};")
        vl.addWidget(ft)
        return page

    # -- Workers --
    def _setup_workers(self):
        self._tw = TunnelWorker(); self._tt = QThread()
        self._tw.moveToThread(self._tt)
        self._tw.log.connect(self._log)
        self._tw.started.connect(self._on_start)
        self._tw.stopped.connect(self._on_stop)
        self._tw.error.connect(self._on_err)
        self._tt.start()

        self._pw = PingWorker(); self._pt = QThread()
        self._pw.moveToThread(self._pt)
        self._pw.result.connect(self._on_ping)
        self._pt.started.connect(self._pw.run); self._pt.start()

        self._dw = DnsWorker(); self._dt = QThread()
        self._dw.moveToThread(self._dt)
        self._dw.log.connect(self._dns_log.queue_line)
        self._dw.done.connect(self._dns_done)
        self._dw.dns_result.connect(self._dns_card_result)
        self._dt.start()

    def _log(self, t):
        self._term.queue_line(t); self._full.queue_line(t)

    # -- Startup --
    def _startup(self):
        admin = is_admin()
        self._log(f"Init: {APP_NAME}? v{VERSION} booting...")
        self._log(f"{'✓' if admin else '✗'} admin: {'OK' if admin else 'MISSING — restart as admin'}")
        miss = [f for f in ("goodbyedpi.exe", "WinDivert.dll", "WinDivert64.sys") if not (BIN_DIR / f).exists()]
        for f in miss: self._log(f"✗ missing: {f}")
        if not miss: self._log("✓ driver files: OK")
        try:
            socket.create_connection(("discord.com", 443), timeout=3).close()
            self._log("Network: discord.com → reachable")
        except:
            self._log("ERROR: Discord RTC blocked.")
        self._log("Status: Awaiting Activation...")

    # -- Tunnel --
    def _toggle(self):
        if self._on: self._tw.stop()
        else: self._tw.launch(self._preset.currentText(), self._ks.isChecked())

    def _on_start(self):
        self._on = True; self._pwr.set_active(True)
        self._tbar.set_connected(True); self._log("▶ ACTIVATED. enjoy your freedom.")

    def _on_stop(self):
        self._on = False; self._pwr.set_active(False)
        self._tbar.set_connected(False); self._log("■ deactivated.")

    def _on_err(self, msg): self._on_stop(); self._log(f"✗ error: {msg}")
    def _on_ping(self, ms): self._ping = ms

    # -- DNS --
    def _dns_show_current(self):
        adapter = self._adapter.currentText()
        p, s = get_dns_ips(adapter)
        self._dns_cur_lbl.setText(f"{p}  /  {s}" if p else "AUTO (DHCP)")
        op, os_ = get_original_dns(adapter)
        if op: self._orig_lbl.setText(f"Original saved:  {op}  /  {os_ or '—'}")
        else: self._orig_lbl.setText("Original DNS will be saved on first change")

    def _dns_refresh(self):
        ads = get_adapters(); cur = self._adapter.currentText()
        self._adapter.clear(); self._adapter.addItems(ads)
        if cur in ads: self._adapter.setCurrentText(cur)
        self._dns_show_current()
        self._dns_log.queue_line("✓ adapters refreshed")

    def _dns_select(self, name):
        self._dns_sel = name
        for n, c in self._dns_cards.items(): c.set_selected(n == name)

    def _dns_check_all(self):
        for c in self._dns_cards.values(): c.set_checking()
        self._dw.check_latency()

    def _dns_card_result(self, name, ms):
        if name in self._dns_cards: self._dns_cards[name].set_latency(ms)

    def _dns_activate(self):
        if not self._dns_sel:
            self._dns_log.queue_line("✗ select a server first"); return
        adapter = self._adapter.currentText()
        save_original_dns(adapter)
        p, s = DNS_SERVERS[self._dns_sel]
        self._dw.apply(adapter, p, s)

    def _dns_restore(self):
        self._dw.reset(self._adapter.currentText())

    def _dns_reset_dhcp(self):
        adapter = self._adapter.currentText()
        _original_dns.pop(adapter, None)
        self._dw.reset(adapter)

    def _dns_done(self, ok, msg):
        self._dns_log.queue_line(msg)
        QTimer.singleShot(500, self._dns_show_current)

    # -- Close --
    def closeEvent(self, e):
        if self._on: self._tw.stop()
        self._pw.stop()
        for t in (self._pt, self._tt, self._dt): t.quit(); t.wait(2000)
        e.accept()

# =====================================================================
#  ENTRY
# =====================================================================
def main():
    if sys.platform == "win32" and not is_admin():
        relaunch_admin()

    app = QApplication(sys.argv)
    app.setStyle("Fusion"); app.setApplicationName("0bx0d?")
    app.setStyleSheet(QSS)

    from PySide6.QtGui import QPalette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor("#101014"))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(ACCENT2))
    pal.setColor(QPalette.ColorRole.Button,          QColor(CARD))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Link,            QColor(ACCENT))
    app.setPalette(pal)

    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
