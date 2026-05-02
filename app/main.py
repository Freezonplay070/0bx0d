# -*- coding: utf-8 -*-
"""0bx0d? — DPI bypass tool v2.2"""
import ctypes, math, os, random, socket, struct, subprocess, sys, time, winreg
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QPointF,
    QRect, QRectF, QSize, QEasingCurve, QPropertyAnimation,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QRadialGradient,
    QLinearGradient, QConicalGradient, QPixmap, QMouseEvent, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QSizePolicy,
    QStackedWidget, QScrollArea,
)

# ═══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
APP_NAME = "0bx0d"
VERSION  = "2.2"
BIN_DIR  = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Palette
BG       = "#0d0d0f"
SURFACE  = "#141416"
CARD     = "#181820"
BORDER   = "#2a0808"
BORDER2  = "#3d0d0d"
RED      = "#c62828"
RED2     = "#e53935"
RED3     = "#ff1744"
SILVER   = "#d4d4d8"
SILVER2  = "#8a8a9a"
DIM      = "#3a2525"
DIM2     = "#1e1218"

# ── BUG FIX: removed --desync-any-protocol (not in v0.2.2), --max-payload needs value ──
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
BLACKLIST = {
    "DISCORD": ["--blacklist","discord.com","--blacklist","discordapp.com",
                "--blacklist","discord.gg","--blacklist","discord.media"],
    "ALL": [],
}

DNS_SERVERS = {
    "GOOGLE":     ("8.8.8.8",        "8.8.4.4"),
    "CLOUDFLARE": ("1.1.1.1",        "1.0.0.1"),
    "QUAD9":      ("9.9.9.9",        "149.112.112.112"),
    "ADGUARD":    ("94.140.14.14",   "94.140.15.15"),
    "OPENDNS":    ("208.67.222.222", "208.67.220.220"),
    "YANDEX":     ("77.88.8.8",      "77.88.8.1"),
}

# ═══════════════════════════════════════════════════════════════════════
#  FONTS
# ═══════════════════════════════════════════════════════════════════════
def mono(px: int, w=QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Consolas", "Roboto Mono", "Courier New"])
    f.setPixelSize(px); f.setWeight(w)
    return f

def display(px: int, w=QFont.Weight.Black) -> QFont:
    f = QFont()
    f.setFamilies(["Orbitron", "Exo 2", "Rajdhani", "Arial Black"])
    f.setPixelSize(px); f.setWeight(w)
    return f

# ═══════════════════════════════════════════════════════════════════════
#  ADMIN / AUTOSTART
# ═══════════════════════════════════════════════════════════════════════
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
            val = (sys.executable if getattr(sys,"frozen",False)
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

# ═══════════════════════════════════════════════════════════════════════
#  DNS UTILITIES
# ═══════════════════════════════════════════════════════════════════════
_original_dns: dict[str, str] = {}   # adapter → "ip1,ip2" before any change

def get_adapters() -> list[str]:
    try:
        r = subprocess.run(["netsh","interface","show","interface"],
                           capture_output=True, text=True, timeout=5)
        out = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] in ("Connected","Enabled","Підключено"):
                out.append(" ".join(parts[3:]))
        return out or ["Wi-Fi","Ethernet"]
    except: return ["Wi-Fi","Ethernet"]

def get_dns_ips(adapter: str) -> tuple[str, str]:
    """Returns (primary, secondary) IPs or ('','')"""
    try:
        r = subprocess.run(["netsh","interface","ip","show","dns",adapter],
                           capture_output=True, text=True, timeout=5)
        ips = []
        for line in r.stdout.splitlines():
            parts = line.strip().split()
            for p in parts:
                if p.count(".") == 3:
                    try: socket.inet_aton(p); ips.append(p)
                    except: pass
        return (ips[0] if len(ips)>0 else "", ips[1] if len(ips)>1 else "")
    except: return ("","")

def save_original_dns(adapter: str):
    if adapter not in _original_dns:
        p, s = get_dns_ips(adapter)
        _original_dns[adapter] = f"{p},{s}"

def get_original_dns(adapter: str) -> tuple[str, str]:
    raw = _original_dns.get(adapter, ",")
    parts = raw.split(",", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def check_dns_latency(server_ip: str) -> float | None:
    """UDP DNS query to measure server latency in ms."""
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

# ═══════════════════════════════════════════════════════════════════════
#  WORKERS
# ═══════════════════════════════════════════════════════════════════════
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
        p   = PRESETS.get(preset_name, list(PRESETS.values())[0])
        cmd = [str(BIN_DIR / "goodbyedpi.exe")] + p["args"] + BLACKLIST.get(p["mode"],[])
        self._go.emit(cmd, ks)

    def _kill_old(self):
        for proc in psutil.process_iter(["name","pid"]):
            try:
                if (proc.info["name"] or "").lower() == "goodbyedpi.exe":
                    proc.kill(); proc.wait(3)
            except: pass

    def _start(self, cmd, ks):
        self._run=True; self._cmd=cmd; self._ks=ks
        self._kill_old()
        self.log.emit("→ " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit()
            self._watch()
        except OSError as e: self.error.emit(str(e))

    def _watch(self):
        while self._run:
            if not self._proc: break
            if self._proc.poll() is not None:
                if self._run and self._ks:
                    self.log.emit("⚡ kill switch triggered, restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        continue
                    except OSError as e: self.error.emit(str(e)); break
                else: self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line:
                    text = line.decode("utf-8","replace").strip()
                    # Skip long help/usage dumps
                    if text and not text.startswith("-") and "OPTION" not in text:
                        self.log.emit(text)
            else: time.sleep(0.05)

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
                self.result.emit(round((time.perf_counter()-t0)*1000, 1))
                s.close()
            except: self.result.emit(None)
            time.sleep(5)

    def stop(self): self._active = False


class DnsWorker(QObject):
    log    = Signal(str)
    done   = Signal(bool, str)
    _go    = Signal(str, str, str)
    _rst   = Signal(str)
    check_all_req = Signal()
    dns_result    = Signal(str, object)  # name, ms|None

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
            subprocess.run(["netsh","interface","ip","set","dns",adapter,"static",primary],
                           capture_output=True, timeout=8)
            if secondary:
                subprocess.run(["netsh","interface","ip","add","dns",adapter,secondary,"index=2"],
                               capture_output=True, timeout=8)
            subprocess.run(["ipconfig","/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, f"✓ DNS set to {primary}")
        except Exception as e: self.done.emit(False, f"✗ DNS error: {e}")

    def _reset(self, adapter):
        orig_p, orig_s = get_original_dns(adapter)
        if orig_p:
            self.log.emit(f"Restoring DNS → {orig_p}")
            try:
                subprocess.run(["netsh","interface","ip","set","dns",adapter,"static",orig_p],
                               capture_output=True, timeout=8)
                if orig_s:
                    subprocess.run(["netsh","interface","ip","add","dns",adapter,orig_s,"index=2"],
                                   capture_output=True, timeout=8)
                subprocess.run(["ipconfig","/flushdns"], capture_output=True, timeout=5)
                self.done.emit(True, f"✓ Original DNS restored ({orig_p})")
                return
            except Exception as e: self.done.emit(False, f"✗ {e}"); return
        # Fall back to DHCP
        self.log.emit("Resetting DNS → DHCP auto")
        try:
            subprocess.run(["netsh","interface","ip","set","dns",adapter,"dhcp"],
                           capture_output=True, timeout=8)
            subprocess.run(["ipconfig","/flushdns"], capture_output=True, timeout=5)
            self.done.emit(True, "✓ DNS reset to auto (DHCP)")
        except Exception as e: self.done.emit(False, f"✗ {e}")

    def _check_all(self):
        self.log.emit("Checking DNS latency...")
        for name, (ip, _) in DNS_SERVERS.items():
            ms = check_dns_latency(ip)
            self.dns_result.emit(name, ms)
        self.log.emit("✓ Latency check complete")

# ═══════════════════════════════════════════════════════════════════════
#  BACKGROUND: NOISE + VIGNETTE
# ═══════════════════════════════════════════════════════════════════════
_NOISE_PIX: QPixmap | None = None

def _get_noise(w, h) -> QPixmap:
    global _NOISE_PIX
    if _NOISE_PIX and _NOISE_PIX.width() >= w and _NOISE_PIX.height() >= h:
        return _NOISE_PIX
    pix = QPixmap(w, h); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); rng = random.Random(42)
    for _ in range(w * h // 9):
        x = rng.randint(0, w-1); y = rng.randint(0, h-1)
        v = rng.randint(100, 240); a = rng.randint(2, 9)
        p.setPen(QColor(v, v, v, a)); p.drawPoint(x, y)
    p.end(); _NOISE_PIX = pix; return pix


class BgFrame(QWidget):
    def paintEvent(self, _):
        p = QPainter(self); r = self.rect()
        cx, cy = r.width()/2, r.height()/2
        p.fillRect(r, QColor(BG))
        p.drawPixmap(0, 0, _get_noise(r.width(), r.height()))
        # Vignette
        g = QRadialGradient(cx, cy, max(cx, cy) * 1.05)
        g.setColorAt(0.0, QColor(30, 5, 5, 15))
        g.setColorAt(0.5, QColor(0, 0, 0, 0))
        g.setColorAt(1.0, QColor(0, 0, 0, 140))
        p.fillRect(r, g); p.end()

# ═══════════════════════════════════════════════════════════════════════
#  CARD PANEL
# ═══════════════════════════════════════════════════════════════════════
class Card(QWidget):
    def __init__(self, parent=None, radius=10):
        super().__init__(parent); self._r = radius

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        # Fill
        p.setBrush(QColor(CARD)); p.setPen(QPen(QColor(BORDER2), 1))
        p.drawRoundedRect(r, self._r, self._r)
        # Top highlight
        g = QLinearGradient(0, 0, 0, 30)
        g.setColorAt(0, QColor(255, 255, 255, 8)); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, self._r, self._r)
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  GLITCH LABEL
# ═══════════════════════════════════════════════════════════════════════
class GlitchLabel(QWidget):
    def __init__(self, text, px=15, parent=None):
        super().__init__(parent)
        self._text=text; self._px=px; self._ox=0; self._oy=0; self._g=False
        t = QTimer(self); t.timeout.connect(self._tick); t.start(100)
        self.setFixedHeight(self._px + 10)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _tick(self):
        if random.random() < 0.07:
            self._g=True; self._ox=random.randint(-2,2); self._oy=random.randint(-1,1)
        else: self._g=False; self._ox=0; self._oy=0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = display(self._px); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(f); r = self.rect()
        if self._g:
            p.setPen(QColor(180, 0, 0, 140))
            p.drawText(r.translated(self._ox+2, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
            p.setPen(QColor(0, 140, 140, 60))
            p.drawText(r.translated(self._ox-1, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
        p.setPen(QColor(SILVER))
        p.drawText(r.translated(self._ox, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
        p.end()

    def sizeHint(self): return QSize(130, self._px+10)

# ═══════════════════════════════════════════════════════════════════════
#  SIDEBAR BUTTON
# ═══════════════════════════════════════════════════════════════════════
class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self, icon, tooltip="", parent=None):
        super().__init__(parent)
        self._icon=icon; self._tip=tooltip
        self._hover=False; self._active=False; self._gx=0; self._gy=0; self._g=False
        self.setFixedSize(52, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip: self.setToolTip(tooltip)
        # Random glitch
        t = QTimer(self); t.timeout.connect(self._glitch)
        t.start(random.randint(4000, 14000))

    def _glitch(self):
        self._g=True; self._gx=random.randint(-2,2); self._gy=random.randint(-1,1)
        self.update(); QTimer.singleShot(90, self._end_g)

    def _end_g(self): self._g=False; self.update()

    def set_active(self, v): self._active=v; self.update()
    def enterEvent(self, _): self._hover=True;  self.update()
    def leaveEvent(self, _): self._hover=False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self._active:
            p.fillRect(r, QColor(22, 2, 2))
            # Left accent bar
            path = QPainterPath()
            path.moveTo(0, 12); path.lineTo(3, 12)
            path.lineTo(3, r.height()-12); path.lineTo(0, r.height()-12)
            p.fillPath(path, QColor(RED2))
        elif self._hover: p.fillRect(r, QColor(16, 4, 4))

        # Icon
        ox, oy = (self._gx, self._gy) if self._g else (0, 0)
        if self._g:
            p.setPen(QColor(180, 0, 0, 90))
            p.setFont(display(18))
            p.drawText(r.translated(ox+1, oy), Qt.AlignmentFlag.AlignCenter, self._icon)
        col = QColor(RED2) if (self._active or self._hover) else QColor(DIM)
        p.setPen(col); p.setFont(display(18))
        p.drawText(r.translated(ox, oy), Qt.AlignmentFlag.AlignCenter, self._icon)
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  STATUS BADGE
# ═══════════════════════════════════════════════════════════════════════
class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on=False; self._phase=0.0
        self.setFixedSize(160, 28)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def set_on(self, v): self._on=v; self.update()

    def _tick(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        if self._on: self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())

        if self._on:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            bg = QColor(40, 2, 2)
            border = QColor(RED2)
            dot_col = QColor(255, int(50+100*pulse), int(50+100*pulse))
            text = "CONNECTED"
            text_col = QColor(RED2)
        else:
            pulse = 0
            bg = QColor(18, 12, 12)
            border = QColor(BORDER2)
            dot_col = QColor(60, 20, 20)
            text = "OFFLINE"
            text_col = QColor(DIM)

        p.setBrush(bg); p.setPen(QPen(border, 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)

        # Dot
        dr = 7
        if self._on:
            # Glow
            g = QRadialGradient(14, 14, dr + 4)
            g.setColorAt(0, QColor(255, 50, 50, int(80 * (0.5+0.5*math.sin(self._phase)))))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(14, 14), dr+4, dr+4)
        p.setBrush(dot_col); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(14, 14), dr*0.6, dr*0.6)

        f = mono(9, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(f); p.setPen(text_col)
        p.drawText(QRect(26, 0, self.width()-26, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, text)
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  EYE BUTTON
# ═══════════════════════════════════════════════════════════════════════
class EyeButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active=False; self._hover=False
        self._phase=0.0; self._pdir=1
        self._open=0.0; self._glitch=0
        self.setFixedSize(200, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(25)
        lt = QTimer(self); lt.timeout.connect(self._open_lid); lt.start(14)
        self._lt = lt

    def _open_lid(self):
        self._open = min(1.0, self._open + 0.04); self.update()
        if self._open >= 1.0: self._lt.stop()

    def _tick(self):
        spd = 0.03 if (self._active or self._hover) else 0.007
        self._phase += spd * self._pdir
        if self._phase >= 1.0: self._pdir = -1
        if self._phase <= 0.0: self._pdir  =  1
        if self._active and random.random() < 0.025: self._glitch = 3
        if self._glitch > 0: self._glitch -= 1
        self.update()

    def set_active(self, v): self._active=v; self.update()
    def enterEvent(self, _): self._hover=True
    def leaveEvent(self, _): self._hover=False
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx=self.width()/2; cy=self.height()/2; R=min(cx,cy)-12

        # ── Outer glow ──
        if self._active:
            gr = R + 20 + 10*self._phase
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0,   QColor(210, 0, 0, int(65+50*self._phase)))
            g.setColorAt(0.45,QColor(110, 0, 0, int(30+20*self._phase)))
            g.setColorAt(1,   QColor(0, 0, 0, 0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-gr, cy-gr, gr*2, gr*2))
            # Ring
            g2 = QRadialGradient(cx, cy, R+2)
            g2.setColorAt(0.82, QColor(0, 0, 0, 0))
            g2.setColorAt(0.95, QColor(200, 0, 0, int(60*self._phase)))
            g2.setColorAt(1.0,  QColor(200, 0, 0, int(90*self._phase)))
            p.setBrush(g2)
            p.drawEllipse(QRectF(cx-R-2, cy-R-2, (R+2)*2, (R+2)*2))
        elif self._hover:
            g = QRadialGradient(cx, cy, R+16)
            g.setColorAt(0, QColor(60, 0, 0, 30)); g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-R-16, cy-R-16, (R+16)*2, (R+16)*2))

        # ── Body ──
        bg = QRadialGradient(cx, cy - R*0.18, R*0.9)
        if self._active:
            bg.setColorAt(0, QColor(45, 5, 5)); bg.setColorAt(0.6, QColor(22, 2, 2))
            bg.setColorAt(1, QColor(8, 0, 0))
        else:
            bg.setColorAt(0, QColor(28, 18, 18)); bg.setColorAt(0.6, QColor(16, 10, 10))
            bg.setColorAt(1, QColor(8, 5, 5))
        bw = 1.5 if self._active else 1
        bc = QColor(RED2) if self._active else (QColor(RED) if self._hover else QColor(BORDER2))
        p.setBrush(bg); p.setPen(QPen(bc, bw))
        p.drawEllipse(QRectF(cx-R, cy-R, R*2, R*2))

        # ── Eye ──
        ew = R * 0.68; eh = R * 0.36 * self._open
        if eh > 1:
            path = QPainterPath()
            path.moveTo(cx-ew, cy)
            path.quadTo(cx, cy-eh, cx+ew, cy)
            path.quadTo(cx, cy+eh*0.72, cx-ew, cy)
            p.setBrush(QColor(14, 2, 2) if self._active else QColor(8, 4, 4))
            p.setPen(QPen(QColor(RED), 0.8))
            p.drawPath(path)

            # Iris
            ir = eh * 0.62
            if ir > 2:
                ig = QRadialGradient(cx, cy, ir)
                if self._active:
                    ig.setColorAt(0,   QColor(230, 14, 14, 240))
                    ig.setColorAt(0.4, QColor(160, 0,  0,  220))
                    ig.setColorAt(1,   QColor(60,  0,  0,  190))
                else:
                    ig.setColorAt(0,   QColor(120, 12, 12, 200))
                    ig.setColorAt(0.5, QColor(75,  0,  0,  175))
                    ig.setColorAt(1,   QColor(28,  0,  0,  150))
                p.setBrush(ig); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), ir, ir)
                # Pupil
                p.setBrush(QColor(3, 0, 0, 250))
                p.drawEllipse(QPointF(cx, cy), ir*0.33, ir*0.33)
                # Specular
                p.setBrush(QColor(255, 80, 80, 80))
                p.drawEllipse(QPointF(cx-ir*0.26, cy-ir*0.27), ir*0.14, ir*0.14)

        # ── Label ──
        ox = random.randint(-2,2) if (self._glitch and self._active) else 0
        f = display(10); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        p.setFont(f)
        ty = int(cy + R*0.64)
        tr = QRect(ox, ty, self.width(), 20)
        if self._active:
            p.setPen(QColor(255, 255, 255, int(195+60*self._phase)))
            p.drawText(tr, Qt.AlignmentFlag.AlignHCenter, "KILL  —  FEED")
        else:
            p.setPen(QColor(RED2) if self._hover else QColor(RED))
            p.drawText(tr, Qt.AlignmentFlag.AlignHCenter, "EAT  —  .EXE")
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  VEIN OVERLAY
# ═══════════════════════════════════════════════════════════════════════
class VeinOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        for attr in (Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                     Qt.WidgetAttribute.WA_NoSystemBackground,
                     Qt.WidgetAttribute.WA_TranslucentBackground):
            self.setAttribute(attr)
        self._opacity=0.0; self._dir=0; self._phase=0.0; self._flicker=1.0
        self._paths: list[list[QPointF]] = []
        self._t = QTimer(self); self._t.timeout.connect(self._tick)

    def activate(self):
        if not self._paths: self._gen()
        self._dir = 1
        if not self._t.isActive(): self._t.start(20)

    def deactivate(self):
        self._dir = -1
        if not self._t.isActive(): self._t.start(20)

    def _gen(self):
        self._paths = []; w, h = self.width(), self.height()
        rng = random.Random(99)
        for (cx, cy) in [(0,0),(w,0),(0,h),(w,h)]:
            for _ in range(3):
                path=[]; x,y=float(cx),float(cy)
                dx=(1 if cx==0 else -1)*rng.uniform(0.3,0.85)
                dy=(1 if cy==0 else -1)*rng.uniform(0.3,0.85)
                for _ in range(rng.randint(5,11)):
                    path.append(QPointF(x,y))
                    x+=dx*rng.uniform(20,55); y+=dy*rng.uniform(15,42)
                    dx=max(-1.0,min(1.0,dx+rng.uniform(-0.3,0.3)))
                    dy=max(-1.0,min(1.0,dy+rng.uniform(-0.3,0.3)))
                self._paths.append(path)

    def _tick(self):
        if self._dir==1:
            self._opacity=min(1.0,self._opacity+0.06)
            if self._opacity>=1.0: self._dir=0
        elif self._dir==-1:
            self._opacity=max(0.0,self._opacity-0.06)
            if self._opacity<=0.0: self._dir=0; self._t.stop()
        self._phase+=0.055
        if self._opacity>0.5 and random.random()<0.12:
            self._flicker=0.6+random.random()*0.4
        else: self._flicker=min(1.0,self._flicker+0.08)
        self.update()

    def paintEvent(self, _):
        if self._opacity<=0: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pulse = 0.5+0.5*math.sin(self._phase)
        base_a = int(self._opacity*self._flicker*(75+45*pulse))
        for path in self._paths:
            if len(path)<2: continue
            p.setPen(QPen(QColor(155,0,0,base_a), 1.5,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(len(path)-1): p.drawLine(path[i],path[i+1])
            if len(path)>3:
                mid=path[len(path)//2]
                rng=random.Random(int(path[0].x()))
                p.setPen(QPen(QColor(80,0,0,base_a//2),1))
                p.drawLine(mid,QPointF(mid.x()+rng.randint(-30,30),
                                        mid.y()+rng.randint(-20,20)))
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  TERMINAL
# ═══════════════════════════════════════════════════════════════════════
class Terminal(QTextEdit):
    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        sz = "11px" if not compact else "10px"
        self.document().setDefaultStyleSheet("p{margin:1px 0;padding:0;}")
        self.setStyleSheet(f"""
            QTextEdit {{
                background:#0c0d0f; color:#6a6a7a;
                border:1px solid {BORDER}; border-radius:8px;
                padding:10px 12px;
                font-family:'JetBrains Mono','Cascadia Code','Consolas',monospace;
                font-size:{sz}; line-height:1.7;
            }}
            QScrollBar:vertical {{
                background:#0c0d0f; width:5px; border:none; border-radius:2px;
            }}
            QScrollBar::handle:vertical {{
                background:{BORDER2}; border-radius:2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._queue: list[str] = []; self._busy = False

    def _col(self, t: str) -> str:
        lo = t.lower()
        if any(x in lo for x in ("error","✗","fail","blocked","no admin","missing")): return RED3
        if any(x in lo for x in ("✓","ok","activ","enjoy","▶","alive","success","set","restored")): return RED2
        if "⚡" in lo or "warn" in lo or "restart" in lo: return "#e65c00"
        if t.startswith("→"): return DIM
        return SILVER2

    def queue_line(self, text: str):
        if not text.strip(): return
        ts  = datetime.now().strftime("%H:%M:%S")
        col = self._col(text)
        html = (f'<p><span style="color:{DIM};font-size:9px">[{ts}]</span>'
                f'&nbsp;<span style="color:{col}">{text}</span></p>')
        self._queue.append(html)
        if not self._busy: self._pop()

    def _pop(self):
        if not self._queue: self._busy=False; return
        self._busy=True; self.append(self._queue.pop(0))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QTimer.singleShot(35, self._pop)

# ═══════════════════════════════════════════════════════════════════════
#  X-TOGGLE
# ═══════════════════════════════════════════════════════════════════════
class XToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, label, checked=False, parent=None):
        super().__init__(parent)
        self._c=checked; self._l=label; self._h=False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def isChecked(self): return self._c
    def setChecked(self, v): self._c=v; self.update()
    def enterEvent(self, _): self._h=True;  self.update()
    def leaveEvent(self, _): self._h=False; self.update()
    def mousePressEvent(self, e):
        if e.button()==Qt.MouseButton.LeftButton:
            self._c=not self._c; self.update(); self.toggled.emit(self._c)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bx,by,bs=0,5,12
        p.setPen(QPen(QColor(RED if (self._h or self._c) else DIM),1))
        p.setBrush(QColor("#0f0000") if self._c else Qt.BrushStyle.NoBrush)
        p.drawRect(bx,by,bs,bs)
        if self._c:
            pen=QPen(QColor(RED2),1.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); m=2
            p.drawLine(bx+m,by+m,bx+bs-m,by+bs-m)
            p.drawLine(bx+bs-m,by+m,bx+m,by+bs-m)
        f=mono(10); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,1)
        p.setFont(f)
        p.setPen(QColor(RED if (self._h or self._c) else DIM))
        p.drawText(QRect(bs+7,0,300,22),Qt.AlignmentFlag.AlignVCenter,self._l)
        p.end()

    def sizeHint(self): return QSize(160,22)

# ═══════════════════════════════════════════════════════════════════════
#  STYLED BUTTONS
# ═══════════════════════════════════════════════════════════════════════
class GhostBtn(QPushButton):
    """Transparent border button with hover inner glow."""
    def __init__(self, text, accent=False, parent=None):
        super().__init__(text, parent)
        self._accent=accent; self._h=False
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:none;background:transparent;")

    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect(); rf=QRectF(r).adjusted(0.5,0.5,-0.5,-0.5)

        if self._accent:
            bg=QColor(38,3,3) if self._h else QColor(22,2,2)
            bc=QColor(RED2) if self._h else QColor(RED)
        else:
            bg=QColor(20,6,6) if self._h else Qt.BrushStyle.NoBrush
            bc=QColor(RED) if self._h else QColor(BORDER2)

        p.setBrush(bg); p.setPen(QPen(bc,1))
        p.drawRoundedRect(rf,6,6)

        if self._h:
            for i in range(3):
                p.setPen(QPen(QColor(200,0,0,18-i*5),1))
                p.drawRoundedRect(rf.adjusted(i,i,-i,-i),6,6)

        if self._accent and self._h:
            p.fillRect(QRectF(0,6,3,r.height()-12), QColor(RED2))

        f=mono(10,QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,3)
        p.setFont(f)
        col=QColor(RED2) if (self._h and self._accent) else \
            QColor(RED)  if self._h else QColor(DIM)
        p.setPen(col)
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,self.text())
        p.end()


class LookBtn(GhostBtn):
    def __init__(self, parent=None):
        super().__init__("LOOK  —  SOURCE", parent=parent)
        self.setFixedHeight(48)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect(); rf = QRectF(r).adjusted(0.5,0.5,-0.5,-0.5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(RED2) if self._h else QColor(BORDER2), 1))
        p.drawRoundedRect(rf, 8, 8)
        if self._h:
            for i in range(4):
                p.setPen(QPen(QColor(200,0,0,22-i*5),1))
                p.drawRoundedRect(rf.adjusted(i,i,-i,-i),8,8)
            p.fillRect(QRectF(0,8,3,r.height()-16), QColor(RED2))
        f = display(11); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,4)
        p.setFont(f)
        p.setPen(QColor(RED2) if self._h else QColor(RED))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,self.text())
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  DNS SERVER CARD  (latency checker card)
# ═══════════════════════════════════════════════════════════════════════
class DnsCard(QWidget):
    selected = Signal(str)

    MAX_MS = 300.0

    def __init__(self, name, ip1, ip2="", parent=None):
        super().__init__(parent)
        self._name=name; self._ip1=ip1; self._ip2=ip2
        self._latency: float|None = None
        self._checking=False; self._sel=False; self._h=False
        self.setMinimumWidth(100); self.setFixedHeight(86)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_latency(self, ms):
        self._latency=ms; self._checking=False; self.update()

    def set_checking(self): self._checking=True; self.update()
    def set_selected(self, v): self._sel=v; self.update()
    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.selected.emit(self._name)

    def _lat_color(self, ms: float) -> QColor:
        if ms < 50:  return QColor(50, 200, 80)
        if ms < 100: return QColor(200, 180, 30)
        if ms < 200: return QColor(220, 100, 20)
        return QColor(RED3)

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect()).adjusted(1,1,-1,-1)

        # Background
        bg=QColor(28,5,5) if self._sel else (QColor(22,8,8) if self._h else QColor(CARD))
        bc=QColor(RED2) if self._sel else (QColor(RED) if self._h else QColor(BORDER))
        p.setBrush(bg); p.setPen(QPen(bc,1))
        p.drawRoundedRect(r,8,8)

        # Selection indicator
        if self._sel:
            p.fillRect(QRectF(0,10,3,r.height()-20),QColor(RED2))

        # Name
        f=display(11); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,2)
        p.setFont(f)
        p.setPen(QColor(SILVER) if self._sel else QColor(RED if self._h else SILVER2))
        p.drawText(QRect(10,8,self.width()-12,18),Qt.AlignmentFlag.AlignLeft,self._name)

        # IP
        f2=mono(8); p.setFont(f2); p.setPen(QColor(DIM))
        p.drawText(QRect(10,24,self.width()-12,14),Qt.AlignmentFlag.AlignLeft,self._ip1)

        # Latency bar area
        bar_x,bar_y,bar_h=10,42,8
        bar_w=self.width()-20

        # Bar background
        p.setBrush(QColor(12,5,5)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x,bar_y,bar_w,bar_h),4,4)

        # Bar fill
        if self._checking:
            # Animated checking bar (shimmer)
            p.setBrush(QColor(40,10,10))
            p.drawRoundedRect(QRectF(bar_x,bar_y,bar_w*0.4,bar_h),4,4)
        elif self._latency is not None:
            fill_ratio = min(1.0, self._latency/self.MAX_MS)
            col=self._lat_color(self._latency)
            # Gradient fill
            g=QLinearGradient(bar_x,0,bar_x+bar_w,0)
            g.setColorAt(0,col); g.setColorAt(1,QColor(col.red()//2,col.green()//2,col.blue()//2))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(bar_x,bar_y,bar_w*fill_ratio,bar_h),4,4)

        # Latency text
        f3=mono(9,QFont.Weight.Bold); p.setFont(f3)
        if self._checking:
            p.setPen(QColor(DIM)); txt="checking..."
        elif self._latency is None:
            p.setPen(QColor(DIM)); txt="—"
        else:
            col=self._lat_color(self._latency); p.setPen(col)
            txt=f"{self._latency:.0f} ms"
        p.drawText(QRect(10,54,self.width()-12,18),Qt.AlignmentFlag.AlignLeft,txt)
        p.end()

# ═══════════════════════════════════════════════════════════════════════
#  TITLE BAR
# ═══════════════════════════════════════════════════════════════════════
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._win=parent; self._drag=QPoint()
        self.setFixedHeight(42)
        self.setStyleSheet(f"background:{SURFACE};")
        lay=QHBoxLayout(self); lay.setContentsMargins(0,0,8,0); lay.setSpacing(0)
        lay.addSpacing(52)

        div=QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{BORDER}; max-width:1px;"); lay.addWidget(div)
        lay.addSpacing(14)

        self._title=GlitchLabel("0bx0d?",15); lay.addWidget(self._title)
        ver=QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color:{DIM}; font-size:9px; font-family:monospace; margin-left:6px;")
        lay.addWidget(ver); lay.addStretch()

        self._badge=StatusBadge(); lay.addWidget(self._badge)
        lay.addSpacing(10)

        for sym,slot in [("—",parent.showMinimized),("✕",parent.close)]:
            btn=QPushButton(sym); btn.setFixedSize(30,30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#4a1818;border:none;"
                "font-size:13px;font-weight:700;border-radius:4px;}"
                "QPushButton:hover{background:#220000;color:#ff3030;}")
            btn.clicked.connect(slot); lay.addWidget(btn)

    def set_connected(self, on): self._badge.set_on(on)

    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            self._drag=e.globalPosition().toPoint()-self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(e.globalPosition().toPoint()-self._drag)

# ═══════════════════════════════════════════════════════════════════════
#  SECTION HEADER
# ═══════════════════════════════════════════════════════════════════════
def section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{DIM}; font-size:9px; font-family:'JetBrains Mono',monospace;"
        "letter-spacing:4px; text-transform:uppercase;")
    return lbl

def hdiv() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{BORDER}; max-height:1px;")
    return f

# ═══════════════════════════════════════════════════════════════════════
#  GLOBAL STYLESHEET
# ═══════════════════════════════════════════════════════════════════════
QSS = f"""
* {{ color:{SILVER}; }}
QWidget {{ background:transparent; }}
QComboBox {{
    background:{CARD}; color:{RED2}; border:1px solid {BORDER2};
    border-radius:6px; padding:5px 10px;
    font-family:'JetBrains Mono','Consolas',monospace; font-size:10px; letter-spacing:1px;
}}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{
    background:{CARD}; color:{RED2}; border:1px solid {BORDER2};
    selection-background-color:{BORDER}; selection-color:{RED2};
    font-family:'JetBrains Mono','Consolas',monospace; outline:none;
}}
QScrollBar:horizontal {{ height:0; }}
QToolTip {{
    background:{CARD}; color:{SILVER}; border:1px solid {BORDER2};
    font-family:monospace; padding:4px;
}}
"""

# ═══════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(760, 570); self.resize(800, 610)
        self.setWindowTitle("0bx0d?")
        self._on=False; self._ping=None
        self._dns_sel: str|None = None
        self._setup_ui(); self._setup_workers()
        QTimer.singleShot(250, self._startup)

    # ── Build UI ─────────────────────────────────────────────────────
    def _setup_ui(self):
        root = BgFrame(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)

        # Sidebar
        sb = QWidget(); sb.setFixedWidth(52)
        sb.setStyleSheet(f"background:{SURFACE};")
        sl = QVBoxLayout(sb); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        sl.addSpacing(42)
        self._sbs = [
            SideBtn("⊹", "Dashboard"),
            SideBtn("≋", "Full Logs"),
            SideBtn("◎", "Settings"),
            SideBtn("⬡", "DNS Manager"),
            SideBtn("⟁", "About"),
        ]
        self._sbs[0].set_active(True)
        for b in self._sbs: sl.addWidget(b)
        sl.addStretch(); sl.addSpacing(8)
        hl.addWidget(sb)

        # Right
        right = QWidget(); right.setStyleSheet("background:transparent;")
        rv = QVBoxLayout(right); rv.setContentsMargins(0,0,0,0); rv.setSpacing(0)
        self._tbar = TitleBar(self); rv.addWidget(self._tbar)
        rv.addWidget(hdiv())
        self._stack = QStackedWidget(); self._stack.setStyleSheet("background:transparent;")
        for page in [self._build_dash(), self._build_logs(),
                     self._build_sett(), self._build_dns(), self._build_info()]:
            self._stack.addWidget(page)
        rv.addWidget(self._stack)
        hl.addWidget(right)

        for i,b in enumerate(self._sbs):
            b.clicked.connect(lambda _=None,idx=i: self._nav(idx))

        self._vein = VeinOverlay(self); self._vein.resize(self.size())

    def resizeEvent(self,e):
        super().resizeEvent(e)
        if hasattr(self,"_vein"): self._vein.resize(self.size())

    def _nav(self, i):
        self._stack.setCurrentIndex(i)
        for j,b in enumerate(self._sbs): b.set_active(j==i)

    # ── DASHBOARD ────────────────────────────────────────────────────
    def _build_dash(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,16,20,16); vl.setSpacing(12)

        # Top row: eye + right panel
        top=QHBoxLayout(); top.setSpacing(16)
        self._eye=EyeButton(); self._eye.clicked.connect(self._toggle)
        top.addWidget(self._eye, 0, Qt.AlignmentFlag.AlignVCenter)

        # Right card
        rc=Card(radius=10); rc_vl=QVBoxLayout(rc); rc_vl.setContentsMargins(16,14,16,14)
        rc_vl.setSpacing(10)
        self._look=LookBtn()
        self._look.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        rc_vl.addWidget(self._look)

        sub=QLabel("[ pure code,  raw power ]")
        sub.setStyleSheet(f"color:{DIM}; font-size:9px; font-family:monospace; letter-spacing:1px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); rc_vl.addWidget(sub)
        rc_vl.addWidget(hdiv())
        rc_vl.addWidget(section_header("PRESET"))
        self._preset=QComboBox()
        self._preset.addItems(list(PRESETS.keys()))
        rc_vl.addWidget(self._preset); rc_vl.addStretch()
        top.addWidget(rc)
        vl.addLayout(top)

        # Logs card
        lc=Card(radius=10); lc_vl=QVBoxLayout(lc); lc_vl.setContentsMargins(14,10,14,10)
        lc_vl.setSpacing(6)
        lc_vl.addWidget(section_header("LIVE LOGS"))
        self._term=Terminal(compact=True)
        self._term.setMinimumHeight(120); self._term.setMaximumHeight(155)
        lc_vl.addWidget(self._term)
        vl.addWidget(lc)

        # Bottom bar
        bot=QHBoxLayout(); bot.setSpacing(16)
        self._auto=XToggle("AUTOSTART",get_autostart()); self._auto.toggled.connect(set_autostart)
        self._ks=XToggle("KILL SWITCH",True)
        bot.addWidget(self._auto); bot.addWidget(self._ks); bot.addStretch()
        bl=QLabel("by solevoyq")
        bl.setStyleSheet(f"color:{BORDER2}; font-size:9px; font-family:monospace;")
        bot.addWidget(bl); vl.addLayout(bot)
        return page

    # ── LOGS ──────────────────────────────────────────────────────────
    def _build_logs(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,16,20,16)
        vl.addWidget(section_header("FULL SESSION LOG"))
        vl.addSpacing(4)
        self._full=Terminal(); vl.addWidget(self._full)
        return page

    # ── SETTINGS ──────────────────────────────────────────────────────
    def _build_sett(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,16,20,16); vl.setSpacing(10)
        vl.addWidget(section_header("SETTINGS")); vl.addWidget(hdiv())

        c1=Card(radius=10); c1l=QVBoxLayout(c1); c1l.setContentsMargins(16,14,16,14)
        c1l.setSpacing(10)
        c1l.addWidget(section_header("STARTUP"))
        a2=XToggle("AUTOSTART  —  launch on Windows login",get_autostart())
        a2.toggled.connect(set_autostart); a2.toggled.connect(self._auto.setChecked)
        c1l.addWidget(a2)
        c1l.addWidget(hdiv())
        c1l.addWidget(section_header("PROTECTION"))
        k2=XToggle("KILL SWITCH  —  restart on unexpected exit",True)
        k2.toggled.connect(self._ks.setChecked)
        c1l.addWidget(k2)
        vl.addWidget(c1)

        vl.addStretch()
        vl.addWidget(QLabel(f"0bx0d? v{VERSION}  ·  GoodbyeDPI v0.2.2  ·  MIT"))
        return page

    # ── DNS ───────────────────────────────────────────────────────────
    def _build_dns(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,16,20,16); vl.setSpacing(10)

        # Header row
        h=QHBoxLayout()
        h.addWidget(section_header("DNS MANAGER")); h.addStretch()
        ref=GhostBtn("⟳ REFRESH"); ref.setFixedWidth(100); ref.clicked.connect(self._dns_refresh)
        chk=GhostBtn("⚡ CHECK ALL",accent=True); chk.setFixedWidth(110)
        chk.clicked.connect(self._dns_check_all)
        h.addWidget(ref); h.addSpacing(6); h.addWidget(chk)
        vl.addLayout(h); vl.addWidget(hdiv())

        # Adapter + current DNS
        ac=Card(radius=8); acl=QHBoxLayout(ac); acl.setContentsMargins(14,10,14,10)
        acl.setSpacing(10)
        al=QLabel("ADAPTER:"); al.setStyleSheet(f"color:{DIM}; font-size:9px; font-family:monospace; letter-spacing:2px;")
        al.setFixedWidth(70); acl.addWidget(al)
        self._adapter=QComboBox()
        self._adapter.addItems(get_adapters())
        self._adapter.currentTextChanged.connect(self._dns_show_current)
        acl.addWidget(self._adapter); acl.addSpacing(16)
        self._dns_cur_lbl=QLabel("—")
        self._dns_cur_lbl.setStyleSheet(f"color:{SILVER2}; font-size:10px; font-family:'JetBrains Mono',monospace;")
        acl.addWidget(self._dns_cur_lbl,1)
        vl.addWidget(ac)

        # DNS server cards
        vl.addWidget(section_header("SERVERS  (click to select, ⚡ to measure latency)"))
        self._dns_cards: dict[str, DnsCard] = {}
        grid_w=QWidget(); grid_l=QHBoxLayout(grid_w); grid_l.setContentsMargins(0,0,0,0); grid_l.setSpacing(8)
        for name,(ip1,ip2) in DNS_SERVERS.items():
            card=DnsCard(name,ip1,ip2)
            card.selected.connect(self._dns_select)
            self._dns_cards[name]=card; grid_l.addWidget(card)
        vl.addWidget(grid_w)

        # Original DNS restore info
        self._orig_lbl=QLabel("original DNS not saved yet")
        self._orig_lbl.setStyleSheet(f"color:{DIM}; font-size:9px; font-family:monospace; letter-spacing:1px;")
        vl.addWidget(self._orig_lbl)

        # Action buttons
        ab=QHBoxLayout(); ab.setSpacing(8)
        self._dns_act=GhostBtn("APPLY SELECTED",accent=True)
        self._dns_act.clicked.connect(self._dns_activate)
        self._dns_rst=GhostBtn("↩ RESTORE ORIGINAL")
        self._dns_rst.clicked.connect(self._dns_restore)
        self._dns_dhcp=GhostBtn("RESET TO AUTO")
        self._dns_dhcp.clicked.connect(self._dns_reset_dhcp)
        ab.addWidget(self._dns_act); ab.addWidget(self._dns_rst); ab.addWidget(self._dns_dhcp)
        ab.addStretch(); vl.addLayout(ab)

        # DNS log
        self._dns_log=Terminal(compact=True); self._dns_log.setMaximumHeight(90)
        vl.addWidget(self._dns_log)

        QTimer.singleShot(400, self._dns_show_current)
        return page

    # ── INFO ──────────────────────────────────────────────────────────
    def _build_info(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(24,20,24,20); vl.setSpacing(16)

        title=QLabel("0bx0d?")
        f=display(32); title.setFont(f)
        title.setStyleSheet(f"color:{RED2};"); vl.addWidget(title)

        c=Card(radius=10); cl=QVBoxLayout(c); cl.setContentsMargins(18,16,18,16); cl.setSpacing(8)
        cl.addWidget(section_header("HOW IT WORKS"))
        desc=QLabel(
            "GoodbyeDPI intercepts TCP/UDP packets via the WinDivert kernel driver "
            "and modifies headers — fragmentation, wrong checksums, fake ACKs — "
            "so that ISP deep packet inspection can't correctly reassemble the stream "
            "and lets the connection through.\n\n"
            "Discord Voice (RTC, UDP 50000-65535) is handled by targeting "
            "Discord's CDN domains with --blacklist flags."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{SILVER2}; font-size:11px; font-family:'JetBrains Mono',monospace;")
        cl.addWidget(desc)
        vl.addWidget(c)

        brow=QHBoxLayout(); brow.setSpacing(8)
        gh=GhostBtn("GITHUB →",accent=True); gh.setFixedWidth(130)
        gh.clicked.connect(lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        brow.addWidget(gh); brow.addStretch()
        vl.addLayout(brow)
        vl.addStretch()

        ft=QLabel(f"v{VERSION}  ·  by solevoyq  ·  MIT  ·  not malware, just raw code")
        ft.setStyleSheet(f"color:{BORDER2}; font-size:9px; font-family:monospace;")
        vl.addWidget(ft)
        return page

    # ── Workers ────────────────────────────────────────────────────────
    def _setup_workers(self):
        self._tw=TunnelWorker(); self._tt=QThread()
        self._tw.moveToThread(self._tt)
        self._tw.log.connect(self._log)
        self._tw.started.connect(self._on_start)
        self._tw.stopped.connect(self._on_stop)
        self._tw.error.connect(self._on_err)
        self._tt.start()

        self._pw=PingWorker(); self._pt=QThread()
        self._pw.moveToThread(self._pt)
        self._pw.result.connect(self._on_ping)
        self._pt.started.connect(self._pw.run); self._pt.start()

        self._dw=DnsWorker(); self._dt=QThread()
        self._dw.moveToThread(self._dt)
        self._dw.log.connect(self._dns_log.queue_line)
        self._dw.done.connect(self._dns_done)
        self._dw.dns_result.connect(self._dns_card_result)
        self._dt.start()

    def _log(self, t):
        self._term.queue_line(t); self._full.queue_line(t)

    # ── Startup ────────────────────────────────────────────────────────
    def _startup(self):
        admin=is_admin()
        self._log(f"Init: {APP_NAME}? v{VERSION} booting...")
        self._log(f"{'✓' if admin else '✗'} admin: {'OK' if admin else 'MISSING — restart as administrator'}")
        miss=[f for f in ("goodbyedpi.exe","WinDivert.dll","WinDivert64.sys") if not (BIN_DIR/f).exists()]
        for f in miss: self._log(f"✗ missing: {f}")
        if not miss: self._log("✓ driver files: OK")
        try:
            socket.create_connection(("discord.com",443),timeout=3).close()
            self._log("Network: discord.com → reachable")
        except: self._log("ERROR: Discord Voice RTC blocked.")
        self._log("Status: Awaiting Activation...")

    # ── Tunnel ─────────────────────────────────────────────────────────
    def _toggle(self):
        if self._on: self._tw.stop()
        else: self._tw.launch(self._preset.currentText(), self._ks.isChecked())

    def _on_start(self):
        self._on=True; self._eye.set_active(True); self._vein.activate()
        self._tbar.set_connected(True); self._log("▶ ACTIVATED. enjoy your freedom.")

    def _on_stop(self):
        self._on=False; self._eye.set_active(False); self._vein.deactivate()
        self._tbar.set_connected(False); self._log("■ deactivated.")

    def _on_err(self,msg): self._on_stop(); self._log(f"✗ error: {msg}")

    def _on_ping(self,ms):
        self._ping=ms
        if self._on: self._tbar.set_connected(True)

    # ── DNS ────────────────────────────────────────────────────────────
    def _dns_show_current(self):
        adapter=self._adapter.currentText()
        p,s=get_dns_ips(adapter)
        txt=f"{p}  /  {s}" if p else "AUTO (DHCP)"
        self._dns_cur_lbl.setText(txt)
        op,os_=get_original_dns(adapter)
        if op: self._orig_lbl.setText(f"original saved:  {op}  /  {os_ or '—'}")
        else:   self._orig_lbl.setText("original DNS not saved yet (will be saved on first change)")

    def _dns_refresh(self):
        ads=get_adapters(); cur=self._adapter.currentText()
        self._adapter.clear(); self._adapter.addItems(ads)
        if cur in ads: self._adapter.setCurrentText(cur)
        self._dns_show_current()
        self._dns_log.queue_line("✓ adapters refreshed")

    def _dns_select(self, name):
        self._dns_sel=name
        for n,c in self._dns_cards.items(): c.set_selected(n==name)

    def _dns_check_all(self):
        for c in self._dns_cards.values(): c.set_checking()
        self._dw.check_latency()

    def _dns_card_result(self, name, ms):
        if name in self._dns_cards:
            self._dns_cards[name].set_latency(ms)

    def _dns_activate(self):
        if not self._dns_sel:
            self._dns_log.queue_line("✗ select a server first"); return
        adapter=self._adapter.currentText()
        save_original_dns(adapter)
        p,s=DNS_SERVERS[self._dns_sel]
        self._dw.apply(adapter,p,s)

    def _dns_restore(self):
        adapter=self._adapter.currentText()
        self._dw.reset(adapter)

    def _dns_reset_dhcp(self):
        adapter=self._adapter.currentText()
        # Force DHCP by clearing saved original
        _original_dns.pop(adapter, None)
        self._dw.reset(adapter)

    def _dns_done(self, ok, msg):
        self._dns_log.queue_line(msg)
        QTimer.singleShot(500, self._dns_show_current)

    # ── Close ──────────────────────────────────────────────────────────
    def closeEvent(self, e):
        if self._on: self._tw.stop()
        self._pw.stop()
        for t in (self._pt,self._tt,self._dt): t.quit(); t.wait(2000)
        e.accept()

# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
def main():
    if sys.platform=="win32" and not is_admin():
        relaunch_admin()

    app=QApplication(sys.argv)
    app.setStyle("Fusion"); app.setApplicationName("0bx0d?")
    app.setStyleSheet(QSS)

    from PySide6.QtGui import QPalette
    pal=QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(SILVER))
    pal.setColor(QPalette.ColorRole.Base,            QColor("#0c0d0f"))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.Text,            QColor(SILVER))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(RED3))
    pal.setColor(QPalette.ColorRole.Button,          QColor(CARD))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(RED2))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(RED))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(SILVER))
    pal.setColor(QPalette.ColorRole.Link,            QColor(RED2))
    app.setPalette(pal)

    win=MainWindow(); win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
