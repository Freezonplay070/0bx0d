# -*- coding: utf-8 -*-
"""0bx0d? — DPI bypass tool v2.0"""
import ctypes, math, os, random, socket, subprocess, sys, time, winreg
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QPointF, QRect, QRectF, QSize,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPixmap, QMouseEvent, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QSizePolicy,
    QStackedWidget,
)

# ── Constants ─────────────────────────────────────────────────────────
APP_NAME = "0bx0d"
VERSION  = "2.0"
BIN_DIR  = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

C_BG     = "#111213"
C_SIDE   = "#0c0d0e"
C_RED    = "#8b0000"
C_RED2   = "#cc0000"
C_RED3   = "#ff3030"
C_ASH    = "#c0b8b0"
C_DIM    = "#3a2020"
C_BORDER = "#1e0606"

PRESETS = {
    "Discord + Game (UDP)": {
        "mode": "DISCORD",
        "args": ["-k","2","-e","2","-f","1","--wrong-chksum","--wrong-seq",
                 "--native-frag","--reverse-frag","--max-payload","--desync-any-protocol"],
    },
    "Discord Only": {
        "mode": "DISCORD",
        "args": ["-k","2","-e","2","-f","1","--wrong-chksum",
                 "--native-frag","--reverse-frag","--max-payload"],
    },
    "All Traffic": {
        "mode": "ALL",
        "args": ["-k","2","-e","2","-f","2","--wrong-chksum","--wrong-seq",
                 "--native-frag","--reverse-frag","--max-payload","--desync-any-protocol"],
    },
    "Stealth Stream": {
        "mode": "ALL",
        "args": ["-k","2","-e","2","-f","2","--native-frag","--reverse-frag","--max-payload"],
    },
}
BLACKLIST = {
    "DISCORD": ["--blacklist","discord.com","--blacklist","discordapp.com",
                "--blacklist","discord.gg","--blacklist","discord.media"],
    "ALL": [],
}

# ── Admin ─────────────────────────────────────────────────────────────
def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit(0)

# ── Tunnel worker ─────────────────────────────────────────────────────
class TunnelWorker(QObject):
    log     = Signal(str)
    started = Signal()
    stopped = Signal()
    error   = Signal(str)
    _go     = Signal(str, list, bool)

    def __init__(self):
        super().__init__()
        self._proc = None
        self._run  = False
        self._cmd  = []
        self._ks   = False
        self._go.connect(self._start)

    def launch(self, preset_name: str, killswitch: bool):
        p   = PRESETS.get(preset_name, list(PRESETS.values())[0])
        cmd = [str(BIN_DIR / "goodbyedpi.exe")] + p["args"] + BLACKLIST.get(p["mode"], [])
        self._go.emit(preset_name, cmd, killswitch)

    def _kill_old(self):
        for p in psutil.process_iter(["name", "pid"]):
            try:
                if (p.info["name"] or "").lower() == "goodbyedpi.exe":
                    p.kill(); p.wait(3)
            except Exception: pass

    def _start(self, _name, cmd, ks):
        self._run = True; self._cmd = cmd; self._ks = ks
        self._kill_old()
        self.log.emit("CMD: " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit()
            self._watch()
        except OSError as e:
            self.error.emit(str(e))

    def _watch(self):
        while self._run:
            if not self._proc: break
            if self._proc.poll() is not None:
                if self._run and self._ks:
                    self.log.emit("⚡ kill switch: restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        continue
                    except OSError as e:
                        self.error.emit(str(e)); break
                else:
                    self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line: self.log.emit(line.decode("utf-8", "replace").strip())
            else:
                time.sleep(0.05)

    def stop(self):
        self._run = False
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(4)
            except: self._proc.kill()
        self._proc = None
        self._kill_old()
        self.stopped.emit()

# ── Ping worker ───────────────────────────────────────────────────────
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
            except Exception:
                self.result.emit(None)
            time.sleep(4)

    def stop(self): self._active = False

# ── Autostart ─────────────────────────────────────────────────────────
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
    except OSError: pass

def get_autostart() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k, APP_NAME); winreg.CloseKey(k); return True
    except: return False

# ══════════════════════════════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════════════════════════════

def mono(size: int, weight=QFont.Weight.Normal) -> QFont:
    f = QFont(); f.setFamilies(["JetBrains Mono", "Consolas", "Courier New"])
    f.setPixelSize(size); f.setWeight(weight); return f

def orb(size: int, weight=QFont.Weight.Black) -> QFont:
    f = QFont(); f.setFamilies(["Orbitron", "Arial Black", "Arial"])
    f.setPixelSize(size); f.setWeight(weight); return f


# ── Noise background ──────────────────────────────────────────────────
_NOISE: QPixmap | None = None

def _noise_pix(w: int, h: int) -> QPixmap:
    global _NOISE
    if _NOISE and _NOISE.width() >= w and _NOISE.height() >= h:
        return _NOISE
    pix = QPixmap(w, h); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); rng = random.Random(1337)
    for _ in range(w * h // 7):
        x = rng.randint(0, w - 1); y = rng.randint(0, h - 1)
        v = rng.randint(120, 255);  a = rng.randint(2, 12)
        p.setPen(QColor(v, v, v, a)); p.drawPoint(x, y)
    p.end(); _NOISE = pix; return pix


class NoiseFrame(QWidget):
    def paintEvent(self, _):
        p = QPainter(self); r = self.rect()
        p.fillRect(r, QColor(C_BG))
        p.drawPixmap(0, 0, _noise_pix(r.width(), r.height()))
        p.end()


# ── Glitch label ──────────────────────────────────────────────────────
class GlitchLabel(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text; self._ox = 0; self._oy = 0; self._g = False
        t = QTimer(self); t.timeout.connect(self._tick); t.start(90)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _tick(self):
        if random.random() < 0.08:
            self._g = True; self._ox = random.randint(-2, 2); self._oy = random.randint(-1, 1)
        else:
            self._g = False; self._ox = 0; self._oy = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = orb(14); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        p.setFont(f); r = self.rect()
        if self._g:
            p.setPen(QColor(139, 0, 0, 150))
            p.drawText(r.translated(self._ox + 2, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
            p.setPen(QColor(0, 160, 160, 70))
            p.drawText(r.translated(self._ox - 1, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
        p.setPen(QColor(C_ASH))
        p.drawText(r.translated(self._ox, self._oy), Qt.AlignmentFlag.AlignVCenter, self._text)
        p.end()

    def sizeHint(self): return QSize(120, 24)


# ── Sidebar button ────────────────────────────────────────────────────
class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self, icon: str, parent=None):
        super().__init__(parent)
        self._icon = icon; self._hover = False; self._active = False
        self.setFixedSize(52, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, v: bool): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True;  self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self._active:
            p.fillRect(r, QColor(18, 0, 0))
            p.fillRect(0, 10, 3, r.height() - 20, QColor(C_RED2))
        elif self._hover:
            p.fillRect(r, QColor(14, 4, 4))
        f = orb(17); p.setFont(f)
        p.setPen(QColor(C_RED2) if (self._active or self._hover) else QColor(C_DIM))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._icon)
        p.end()


# ── Eye button ────────────────────────────────────────────────────────
class EyeButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False; self._hover = False
        self._phase  = 0.0;   self._pdir  = 1
        self._open   = 0.0    # 0=closed → 1=open (startup anim)
        self._glitch = 0
        self.setFixedSize(210, 210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._tick_t = QTimer(self); self._tick_t.timeout.connect(self._tick); self._tick_t.start(25)
        self._lid_t  = QTimer(self); self._lid_t.timeout.connect(self._open_lid); self._lid_t.start(16)

    def _open_lid(self):
        self._open = min(1.0, self._open + 0.035)
        self.update()
        if self._open >= 1.0: self._lid_t.stop()

    def _tick(self):
        speed = 0.030 if (self._active or self._hover) else 0.008
        self._phase += speed * self._pdir
        if self._phase >= 1.0: self._pdir = -1
        if self._phase <= 0.0: self._pdir =  1
        if self._active and random.random() < 0.03:
            self._glitch = 3
        if self._glitch > 0: self._glitch -= 1
        self.update()

    def set_active(self, v: bool): self._active = v; self.update()
    def enterEvent(self, _): self._hover = True
    def leaveEvent(self, _): self._hover = False
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2; cy = self.height() / 2
        R  = min(cx, cy) - 10

        # Outer glow
        if self._active:
            gr = R + 18 + 8 * self._phase
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0,   QColor(170, 0, 0, int(55 + 45 * self._phase)))
            g.setColorAt(0.5, QColor(80,  0, 0, int(25 + 20 * self._phase)))
            g.setColorAt(1,   QColor(0,   0, 0, 0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        elif self._hover:
            g = QRadialGradient(cx, cy, R + 14)
            g.setColorAt(0, QColor(70, 0, 0, 35)); g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - R - 14, cy - R - 14, (R + 14) * 2, (R + 14) * 2))

        # Circle body
        bg = QRadialGradient(cx, cy - R * 0.15, R)
        if self._active:
            bg.setColorAt(0, QColor(38, 3, 3)); bg.setColorAt(1, QColor(8, 0, 0))
        else:
            bg.setColorAt(0, QColor(22, 16, 16)); bg.setColorAt(1, QColor(7, 4, 4))
        bw = 1 + int(self._phase) if self._active else 1
        bc = QColor(C_RED2) if self._active else (QColor(C_RED) if self._hover else QColor(C_BORDER))
        p.setBrush(bg); p.setPen(QPen(bc, bw))
        p.drawEllipse(QRectF(cx - R, cy - R, R * 2, R * 2))

        # Eye shape
        ew = R * 0.70; eh = R * 0.36 * self._open
        if eh > 1:
            path = QPainterPath()
            path.moveTo(cx - ew, cy)
            path.quadTo(cx, cy - eh, cx + ew, cy)
            path.quadTo(cx, cy + eh * 0.75, cx - ew, cy)

            sc = QColor(18, 2, 2) if self._active else QColor(10, 4, 4)
            p.setBrush(sc); p.setPen(QPen(QColor(C_RED), 1))
            p.drawPath(path)

            # Iris
            ir = eh * 0.58
            if ir > 2:
                ig = QRadialGradient(cx, cy, ir)
                if self._active:
                    ig.setColorAt(0,   QColor(210, 10, 10, 230))
                    ig.setColorAt(0.4, QColor(139, 0,  0,  210))
                    ig.setColorAt(1,   QColor(50,  0,  0,  180))
                else:
                    ig.setColorAt(0,   QColor(110, 10, 10, 190))
                    ig.setColorAt(0.5, QColor(65,  0,  0,  165))
                    ig.setColorAt(1,   QColor(22,  0,  0,  140))
                p.setBrush(ig); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), ir, ir)

                # Pupil
                p.setBrush(QColor(2, 0, 0, 240))
                p.drawEllipse(QPointF(cx, cy), ir * 0.36, ir * 0.36)

                # Specular
                p.setBrush(QColor(255, 90, 90, 75))
                p.drawEllipse(QPointF(cx - ir * 0.26, cy - ir * 0.26), ir * 0.16, ir * 0.16)

        # Label under eye
        ox = random.randint(-2, 2) if (self._glitch and self._active) else 0
        f  = mono(10, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(f)
        ty = int(cy + R * 0.60)
        tr = QRect(ox, ty, self.width(), 20)
        if self._active:
            p.setPen(QColor(255, 255, 255, int(185 + 70 * self._phase)))
            p.drawText(tr, Qt.AlignmentFlag.AlignHCenter, "KILL  —  FEED")
        else:
            p.setPen(QColor(C_RED2) if self._hover else QColor(C_RED))
            p.drawText(tr, Qt.AlignmentFlag.AlignHCenter, "EAT  —  .EXE")
        p.end()


# ── Vein overlay ──────────────────────────────────────────────────────
class VeinOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._opacity = 0.0; self._dir = 0; self._phase = 0.0
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
        self._paths = []
        w, h = self.width(), self.height()
        rng = random.Random(42)
        for (cx, cy) in [(0, 0), (w, 0), (0, h), (w, h)]:
            for _ in range(3):
                path, x, y = [], float(cx), float(cy)
                dx = (1 if cx == 0 else -1) * rng.uniform(0.3, 0.9)
                dy = (1 if cy == 0 else -1) * rng.uniform(0.3, 0.9)
                for _ in range(rng.randint(5, 10)):
                    path.append(QPointF(x, y))
                    x += dx * rng.uniform(25, 55)
                    y += dy * rng.uniform(18, 45)
                    dx = max(-1.0, min(1.0, dx + rng.uniform(-0.35, 0.35)))
                    dy = max(-1.0, min(1.0, dy + rng.uniform(-0.35, 0.35)))
                self._paths.append(path)

    def _tick(self):
        if self._dir == 1:
            self._opacity = min(1.0, self._opacity + 0.06)
            if self._opacity >= 1.0: self._dir = 0
        elif self._dir == -1:
            self._opacity = max(0.0, self._opacity - 0.06)
            if self._opacity <= 0.0: self._dir = 0; self._t.stop()
        self._phase += 0.05
        self.update()

    def paintEvent(self, _):
        if self._opacity <= 0: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        alpha = int(self._opacity * (90 + 55 * pulse))
        for path in self._paths:
            if len(path) < 2: continue
            p.setPen(QPen(QColor(170, 0, 0, alpha), 1.5))
            for i in range(len(path) - 1):
                p.drawLine(path[i], path[i + 1])
            if len(path) > 3:
                mid = path[len(path) // 2]
                rng = random.Random(int(path[0].x()))
                p.setPen(QPen(QColor(100, 0, 0, alpha // 2), 1))
                p.drawLine(mid, QPointF(mid.x() + rng.randint(-35, 35),
                                        mid.y() + rng.randint(-25, 25)))
        p.end()


# ── Typewriter terminal ───────────────────────────────────────────────
class Terminal(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(
            "QTextEdit { background: #0a0b0c; color: #884444;"
            "border: 1px solid #1e0606; padding: 8px;"
            "font-family: 'JetBrains Mono','Consolas','Courier New',monospace; font-size: 11px; }"
            "QScrollBar:vertical { background: #0a0b0c; width: 4px; border: none; }"
            "QScrollBar::handle:vertical { background: #2a0000; border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._queue: list[str] = []
        self._busy = False

    def _color(self, t: str) -> str:
        lo = t.lower()
        if any(x in lo for x in ("error", "✗", "fail", "blocked")): return "#ff3030"
        if any(x in lo for x in ("✓", "ok", "activ", "enjoy", "alive", "success", "▶")): return "#cc3333"
        if "⚡" in lo or "warn" in lo: return "#cc6600"
        return "#884444"

    def queue_line(self, text: str):
        ts   = datetime.now().strftime("%H:%M:%S")
        col  = self._color(text)
        html = (f'<span style="color:#2a0000">[{ts}]</span> '
                f'<span style="color:{col}">{text}</span>')
        self._queue.append(html)
        if not self._busy: self._pop()

    def _pop(self):
        if not self._queue: self._busy = False; return
        self._busy = True
        self.append(self._queue.pop(0))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QTimer.singleShot(45, self._pop)


# ── X-mark toggle ─────────────────────────────────────────────────────
class XToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, label: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked; self._label = label; self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def isChecked(self): return self._checked
    def setChecked(self, v: bool): self._checked = v; self.update()
    def enterEvent(self, _): self._hover = True;  self.update()
    def leaveEvent(self, _): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update(); self.toggled.emit(self._checked)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bx, by, bs = 0, 5, 12
        p.setPen(QPen(QColor(C_RED if (self._hover or self._checked) else C_DIM), 1))
        p.setBrush(QColor("#0a0000") if self._checked else Qt.BrushStyle.NoBrush)
        p.drawRect(bx, by, bs, bs)
        if self._checked:
            pen = QPen(QColor(C_RED2), 1.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); m = 2
            p.drawLine(bx + m, by + m, bx + bs - m, by + bs - m)
            p.drawLine(bx + bs - m, by + m, bx + m, by + bs - m)
        f = mono(10); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(f)
        p.setPen(QColor(C_RED) if (self._hover or self._checked) else QColor(C_DIM))
        p.drawText(QRect(bs + 7, 0, 300, 22), Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()

    def sizeHint(self): return QSize(160, 22)


# ── LOOK button ───────────────────────────────────────────────────────
class LookButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("LOOK  —  SOURCE")
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: none; background: transparent;")
        self._hover = False

    def enterEvent(self, _): self._hover = True;  self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        p.setBrush(QColor("#140000") if self._hover else QColor("#0c0000"))
        p.setPen(QPen(QColor(C_RED2) if self._hover else QColor(C_BORDER), 1))
        p.drawRect(r.adjusted(0, 0, -1, -1))
        f = orb(11); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        p.setFont(f)
        p.setPen(QColor(C_RED2) if self._hover else QColor(C_RED))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


# ── Title bar ─────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._win = parent; self._drag = QPoint()
        self.setFixedHeight(38)
        self.setStyleSheet(f"background: {C_SIDE};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 6, 0); lay.setSpacing(8)
        lay.addSpacing(52)

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color: {C_BORDER};"); lay.addWidget(div)

        self._title = GlitchLabel("0bx0d?"); lay.addWidget(self._title)

        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color: {C_DIM}; font-size: 9px; font-family: monospace;")
        lay.addWidget(ver); lay.addStretch()

        self._sys = QLabel("SYSTEM:  [ DISCONNECTED ]")
        self._sys.setStyleSheet(
            f"color: {C_DIM}; font-size: 10px; "
            "font-family: 'JetBrains Mono','Consolas',monospace; letter-spacing: 1px;")
        lay.addWidget(self._sys); lay.addSpacing(8)

        for sym, slot in [("—", parent.showMinimized), ("✕", parent.close)]:
            btn = QPushButton(sym); btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #3a1010; border: none;"
                "font-size: 12px; font-weight: bold; border-radius: 3px; }"
                "QPushButton:hover { background: #1e0000; color: #ff3030; }")
            btn.clicked.connect(slot); lay.addWidget(btn)

    def set_status(self, on: bool, ping=None):
        if on:
            extra = f"  {ping}ms" if ping else ""
            self._sys.setText(f"SYSTEM:  [ CONNECTED{extra} ]")
            self._sys.setStyleSheet(
                "color: #cc3333; font-size: 10px; "
                "font-family: 'JetBrains Mono','Consolas',monospace; letter-spacing: 1px;")
        else:
            self._sys.setText("SYSTEM:  [ DISCONNECTED ]")
            self._sys.setStyleSheet(
                f"color: {C_DIM}; font-size: 10px; "
                "font-family: 'JetBrains Mono','Consolas',monospace; letter-spacing: 1px;")

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(e.globalPosition().toPoint() - self._drag)


# ══════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(680, 540); self.resize(740, 590)
        self.setWindowTitle("0bx0d?")
        self._on    = False
        self._ping  = None
        self._setup_ui()
        self._setup_workers()
        QTimer.singleShot(200, self._startup)

    # ── Build UI ─────────────────────────────────────────────────────
    def _setup_ui(self):
        root = NoiseFrame(); self.setCentralWidget(root)
        hl = QHBoxLayout(root); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)

        # Sidebar
        sb = QWidget(); sb.setFixedWidth(52)
        sb.setStyleSheet(f"background: {C_SIDE};")
        sl = QVBoxLayout(sb); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)
        sl.addSpacing(38)
        self._sb0 = SideBtn("⊞"); self._sb0.set_active(True)
        self._sb1 = SideBtn("≡")
        self._sb2 = SideBtn("⚙")
        for b in (self._sb0, self._sb1, self._sb2): sl.addWidget(b)
        sl.addStretch()
        sl.addWidget(SideBtn("☥")); sl.addSpacing(8)
        hl.addWidget(sb)

        # Right
        right = QWidget(); right.setStyleSheet("background: transparent;")
        rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        self._tbar = TitleBar(self); rv.addWidget(self._tbar)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {C_BORDER}; max-height:1px;"); rv.addWidget(div)
        self._stack = QStackedWidget(); self._stack.setStyleSheet("background: transparent;")
        self._stack.addWidget(self._build_main())
        self._stack.addWidget(self._build_logs())
        self._stack.addWidget(self._build_settings())
        rv.addWidget(self._stack)
        hl.addWidget(right)

        self._sb0.clicked.connect(lambda: self._nav(0))
        self._sb1.clicked.connect(lambda: self._nav(1))
        self._sb2.clicked.connect(lambda: self._nav(2))

        self._vein = VeinOverlay(self); self._vein.resize(self.size())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_vein"): self._vein.resize(self.size())

    def _nav(self, i: int):
        self._stack.setCurrentIndex(i)
        self._sb0.set_active(i == 0)
        self._sb1.set_active(i == 1)
        self._sb2.set_active(i == 2)

    # ── Dashboard page ───────────────────────────────────────────────
    def _build_main(self) -> QWidget:
        page = QWidget(); page.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(page); vl.setContentsMargins(20, 14, 20, 14); vl.setSpacing(10)

        # Center: eye + controls
        center = QHBoxLayout(); center.setSpacing(20)
        self._eye = EyeButton(); self._eye.clicked.connect(self._toggle)
        center.addWidget(self._eye, 0, Qt.AlignmentFlag.AlignVCenter)

        rc = QVBoxLayout(); rc.setSpacing(8)
        self._look = LookButton()
        self._look.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        rc.addWidget(self._look)

        sub = QLabel("[ pure code,  raw power ]")
        sub.setStyleSheet(f"color:{C_DIM}; font-size:9px; "
                          "font-family:'JetBrains Mono',monospace; letter-spacing:1px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); rc.addWidget(sub)

        div2 = QFrame(); div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"color:{C_BORDER};"); rc.addWidget(div2)

        pl = QLabel("SETTINGS PRESET")
        pl.setStyleSheet(f"color:{C_DIM}; font-size:9px; "
                         "font-family:monospace; letter-spacing:3px;"); rc.addWidget(pl)

        self._preset = QComboBox()
        self._preset.addItems([f"[ {k} ]" for k in PRESETS])
        self._preset.setStyleSheet(
            "QComboBox { background:#0c0000; color:#cc3333; border:1px solid #1e0606;"
            "padding:6px 10px; font-family:'JetBrains Mono',monospace; font-size:10px;"
            "letter-spacing:1px; }"
            "QComboBox::drop-down { border:none; width:18px; }"
            "QComboBox QAbstractItemView { background:#0c0000; color:#cc3333;"
            "border:1px solid #1e0606; selection-background-color:#1a0000;"
            "font-family:'JetBrains Mono',monospace; }")
        rc.addWidget(self._preset); rc.addStretch()
        center.addLayout(rc)
        vl.addLayout(center)

        ll = QLabel("LIVE LOGS")
        ll.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        vl.addWidget(ll)

        self._term = Terminal(); self._term.setMinimumHeight(130); self._term.setMaximumHeight(170)
        vl.addWidget(self._term)

        bot = QHBoxLayout(); bot.setSpacing(14)
        self._auto = XToggle("AUTOSTART", get_autostart()); self._auto.toggled.connect(set_autostart)
        self._ks   = XToggle("KILL SWITCH", True)
        bot.addWidget(self._auto); bot.addWidget(self._ks); bot.addStretch()
        bl = QLabel("by solevoyq")
        bl.setStyleSheet(f"color:{C_BORDER}; font-size:9px; font-family:monospace;")
        bot.addWidget(bl); vl.addLayout(bot)
        return page

    # ── Logs page ────────────────────────────────────────────────────
    def _build_logs(self) -> QWidget:
        page = QWidget(); page.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(page); vl.setContentsMargins(20, 14, 20, 14)
        lbl = QLabel("FULL LOG")
        lbl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; "
                          "letter-spacing:4px; margin-bottom:6px;")
        vl.addWidget(lbl)
        self._full = Terminal(); vl.addWidget(self._full)
        return page

    # ── Settings page ────────────────────────────────────────────────
    def _build_settings(self) -> QWidget:
        page = QWidget(); page.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(page); vl.setContentsMargins(20, 14, 20, 14); vl.setSpacing(12)
        lbl = QLabel("SETTINGS")
        lbl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        vl.addWidget(lbl)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_BORDER};"); vl.addWidget(div)
        a2 = XToggle("AUTOSTART  —  run on windows login", get_autostart())
        a2.toggled.connect(set_autostart); a2.toggled.connect(self._auto.setChecked)
        k2 = XToggle("KILL SWITCH  —  restart on crash", True)
        k2.toggled.connect(self._ks.setChecked)
        vl.addWidget(a2); vl.addWidget(k2); vl.addStretch()
        vl.addWidget(QLabel(f"0bx0d? v{VERSION}  ·  by solevoyq  ·  MIT"))
        return page

    # ── Workers ──────────────────────────────────────────────────────
    def _setup_workers(self):
        self._tw = TunnelWorker(); self._tt = QThread()
        self._tw.moveToThread(self._tt)
        self._tw.log.connect(self._log); self._tw.started.connect(self._on_start)
        self._tw.stopped.connect(self._on_stop); self._tw.error.connect(self._on_err)
        self._tt.start()
        self._pw = PingWorker(); self._pt = QThread()
        self._pw.moveToThread(self._pt); self._pw.result.connect(self._on_ping)
        self._pt.started.connect(self._pw.run); self._pt.start()

    def _log(self, t: str):
        self._term.queue_line(t); self._full.queue_line(t)

    # ── Startup checks ───────────────────────────────────────────────
    def _startup(self):
        self._log(f"Init: {APP_NAME}? v{VERSION} booting...")
        self._log("✓ admin privileges: OK" if is_admin() else "✗ ERROR: no admin — restart as administrator")
        missing = [f for f in ("goodbyedpi.exe", "WinDivert.dll", "WinDivert64.sys")
                   if not (BIN_DIR / f).exists()]
        for f in missing: self._log(f"✗ missing: {f}")
        if not missing: self._log("✓ driver files: OK")
        try:
            socket.create_connection(("discord.com", 443), timeout=3).close()
            self._log("Network: DNS check... OK")
        except OSError:
            self._log("ERROR: Discord Voice RTC blocked.")
        self._log("Status: Awaiting Activation...")

    # ── Tunnel control ───────────────────────────────────────────────
    def _toggle(self):
        if self._on:
            self._tw.stop()
        else:
            key = list(PRESETS)[self._preset.currentIndex()]
            self._tw.launch(key, self._ks.isChecked())

    def _on_start(self):
        self._on = True; self._eye.set_active(True); self._vein.activate()
        self._tbar.set_status(True, self._ping); self._log("▶ ACTIVATED. enjoy your freedom.")

    def _on_stop(self):
        self._on = False; self._eye.set_active(False); self._vein.deactivate()
        self._tbar.set_status(False); self._log("■ deactivated.")

    def _on_err(self, msg: str): self._on_stop(); self._log(f"✗ error: {msg}")

    def _on_ping(self, ms):
        self._ping = ms
        if self._on: self._tbar.set_status(True, ms)

    # ── Close ─────────────────────────────────────────────────────────
    def closeEvent(self, e):
        if self._on: self._tw.stop()
        self._pw.stop()
        for t in (self._pt, self._tt): t.quit(); t.wait(2000)
        e.accept()


# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
def main():
    if sys.platform == "win32" and not is_admin():
        relaunch_admin()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("0bx0d?")

    from PySide6.QtGui import QPalette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,     QColor(C_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C_RED2))
    pal.setColor(QPalette.ColorRole.Base,       QColor("#0a0b0c"))
    pal.setColor(QPalette.ColorRole.Text,       QColor(C_RED2))
    pal.setColor(QPalette.ColorRole.Button,     QColor("#0c0000"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(C_RED2))
    pal.setColor(QPalette.ColorRole.Highlight,  QColor(C_RED))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
