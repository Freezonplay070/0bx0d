# -*- coding: utf-8 -*-
"""
0bx0d? — DPI bypass tool
"""
import ctypes
import os
import socket
import subprocess
import sys
import time
import winreg
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QFontDatabase, QPen,
    QLinearGradient, QRadialGradient, QPixmap, QIcon,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QCheckBox,
    QSizePolicy, QGraphicsOpacityEffect,
)

# ── Constants ────────────────────────────────────────────────────────
APP_NAME  = "0bx0d"
VERSION   = "1.0.0"
BIN_DIR   = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
REG_KEY   = r"Software\Microsoft\Windows\CurrentVersion\Run"

RED       = "#8b0000"
RED_BRIGHT = "#cc0000"
RED_GLOW  = "#ff2020"
BLACK     = "#000000"
SURFACE   = "#0a0a0a"
BORDER    = "#1a0000"

PRESETS = {
    "DEFAULT": ["-k","2","-e","2","-f","1","--wrong-chksum","--wrong-seq",
                "--native-frag","--reverse-frag","--max-payload","--desync-any-protocol"],
    "GAMING":  ["-k","2","-e","2","-f","1","--native-frag","--desync-any-protocol"],
    "STREAM":  ["-k","2","-e","2","-f","2","--wrong-chksum","--wrong-seq",
                "--native-frag","--reverse-frag","--max-payload","--desync-any-protocol"],
}

MODES = {
    "DISCORD": ["--blacklist","discord.com","--blacklist","discordapp.com",
                "--blacklist","discord.gg","--blacklist","discord.media"],
    "ALL":     [],
}

# ── Admin check ──────────────────────────────────────────────────────
def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None,"runas",sys.executable,
        " ".join(f'"{a}"' for a in sys.argv),None,1)
    sys.exit(0)

# ── Tunnel worker ────────────────────────────────────────────────────
class TunnelWorker(QObject):
    log     = Signal(str)
    started = Signal()
    stopped = Signal()
    error   = Signal(str)
    _go     = Signal(str, str, bool)

    def __init__(self):
        super().__init__()
        self._proc: subprocess.Popen | None = None
        self._run  = False
        self._go.connect(self._start)

    def launch(self, mode: str, preset: str, killswitch: bool):
        self._go.emit(mode, preset, killswitch)

    def _kill_old(self):
        for p in psutil.process_iter(["name","pid"]):
            try:
                if (p.info["name"] or "").lower() == "goodbyedpi.exe":
                    p.kill(); p.wait(3)
            except Exception: pass

    def _build_cmd(self, mode: str, preset: str) -> list[str]:
        exe  = str(BIN_DIR / "goodbyedpi.exe")
        args = [exe] + PRESETS.get(preset, PRESETS["DEFAULT"])
        args += MODES.get(mode, [])
        return args

    def _start(self, mode: str, preset: str, killswitch: bool):
        self._run = True
        self._kill_old()
        cmd = self._build_cmd(mode, preset)
        self.log.emit("CMD: " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit()
            self._watch(killswitch, mode, preset)
        except OSError as e:
            self.error.emit(str(e))

    def _watch(self, ks: bool, mode: str, preset: str):
        while self._run:
            if not self._proc: break
            rc = self._proc.poll()
            if rc is not None:
                if self._run and ks:
                    self.log.emit("⚡ Kill Switch: restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._build_cmd(mode, preset),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        continue
                    except OSError as e:
                        self.error.emit(str(e)); break
                else:
                    self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line: self.log.emit(line.decode("utf-8","replace").strip())
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

# ── Ping worker ──────────────────────────────────────────────────────
class PingWorker(QObject):
    result  = Signal(object)
    _active = False

    def run(self):
        self._active = True
        while self._active:
            try:
                s = socket.socket()
                s.settimeout(2.5)
                t0 = time.perf_counter()
                s.connect(("discord.com", 443))
                ms = (time.perf_counter() - t0) * 1000
                s.close()
                self.result.emit(round(ms, 1))
            except Exception:
                self.result.emit(None)
            time.sleep(4)

    def stop(self): self._active = False

# ── Registry autostart ───────────────────────────────────────────────
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
    except OSError: pass

def get_autostart() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k, APP_NAME); winreg.CloseKey(k); return True
    except: return False

# ═══════════════════════════════════════════════════════════════════════
#   UI WIDGETS
# ═══════════════════════════════════════════════════════════════════════

# ── Pulsing activate button ──────────────────────────────────────────
class ActivateButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active   = False
        self._glow     = 0.0
        self._glow_dir = 1
        self.setText("ACTIVATE")
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self.setStyleSheet("border: none; background: transparent;")

    def set_active(self, v: bool):
        self._active = v
        if v:
            self._timer.start(30)
        else:
            self._timer.stop()
            self._glow = 0.0
        self.update()

    def _pulse(self):
        self._glow += 0.04 * self._glow_dir
        if self._glow >= 1.0: self._glow_dir = -1
        if self._glow <= 0.0: self._glow_dir = 1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self._active:
            # Glow aura
            aura = QRadialGradient(r.center(), r.width() * 0.55)
            aura.setColorAt(0, QColor(255, 30, 30, int(60 + 80 * self._glow)))
            aura.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(r, aura)

            # Border glow
            pen_col = QColor(255, int(20 + 180 * self._glow), int(20 + 180 * self._glow))
            p.setPen(QPen(pen_col, 2))
        else:
            p.setPen(QPen(QColor(RED_BRIGHT), 2))

        # Button body
        bg_col = QColor("#1a0000") if not self._active else QColor(int(40 + 30 * self._glow), 0, 0)
        p.setBrush(bg_col)
        clip = [
            QPoint(12, 0), QPoint(r.width(), 0),
            QPoint(r.width() - 12, r.height()), QPoint(0, r.height()),
        ]
        from PySide6.QtGui import QPolygon
        p.drawPolygon(QPolygon(clip))

        # Text
        font = QFont("Orbitron", 20, QFont.Weight.Black)
        if not QFontDatabase.families().__contains__("Orbitron"):
            font = QFont("Arial", 20, QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        p.setFont(font)
        if self._active:
            p.setPen(QColor(255, 255, 255, int(200 + 55 * self._glow)))
        else:
            p.setPen(QColor(RED_BRIGHT))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


# ── Custom title bar ─────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._win      = parent
        self._drag_pos = QPoint()
        self.setFixedHeight(36)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {BLACK}; border-bottom: 1px solid {BORDER};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(0)

        logo = QLabel("0bx<span style='color:#8b0000'>0</span>d<span style='color:#cc0000'>?</span>")
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setStyleSheet("font-family: 'Orbitron', Arial; font-size: 13px; font-weight: 900;"
                           "letter-spacing: 3px; color: white;")
        lay.addWidget(logo)
        lay.addStretch()

        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet("color: #3a0000; font-size: 10px; margin-right: 14px;")
        lay.addWidget(ver)

        for sym, slot in [("—", parent.showMinimized), ("✕", parent.close)]:
            btn = QPushButton(sym)
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #4a0000; border: none;"
                "              font-size: 14px; font-weight: bold; border-radius: 4px; }"
                "QPushButton:hover { background: #2a0000; color: #ff3030; }"
            )
            btn.clicked.connect(slot)
            lay.addWidget(btn)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self._win.move(e.globalPosition().toPoint() - self._drag_pos)


# ── Log terminal widget ──────────────────────────────────────────────
class Terminal(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(
            f"QTextEdit {{ background: {BLACK}; color: #cc0000;"
            f"border: 1px solid {BORDER}; padding: 10px;"
            f"font-family: 'Cascadia Code','Consolas',monospace; font-size: 11px; }}"
        )

    def append_line(self, text: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        col = "#cc0000" if "error" in text.lower() or "✗" in text else (
              "#00cc44" if ("ok" in text.lower() or "✓" in text or "started" in text.lower() or "ACTIVATED" in text) else
              "#884444")
        self.append(f'<span style="color:#3a0000">[{ts}]</span> <span style="color:{col}">{text}</span>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ═══════════════════════════════════════════════════════════════════════
#   MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(540, 620)
        self.resize(560, 650)
        self.setWindowTitle("0bx0d?")
        self._tunnel_on = False

        self._setup_ui()
        self._setup_workers()
        self._startup_checks()

    # ── UI ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background: {BLACK};")
        self.setCentralWidget(root)

        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Title bar
        vbox.addWidget(TitleBar(self))

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {BLACK};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(16)

        # ── Status row ──
        status_row = QHBoxLayout()

        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet("border-radius: 5px; background: #2a0000;")
        status_row.addWidget(self._dot)

        self._status_lbl = QLabel("OFFLINE")
        self._status_lbl.setStyleSheet(
            "color: #3a0000; font-family: 'Orbitron',Arial; font-size: 11px;"
            "font-weight: 900; letter-spacing: 4px;")
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()

        self._ping_lbl = QLabel("PING —")
        self._ping_lbl.setStyleSheet("color: #2a0000; font-size: 11px; font-family: monospace;")
        status_row.addWidget(self._ping_lbl)
        bl.addLayout(status_row)

        # ── Divider ──
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {BORDER};"); bl.addWidget(div)

        # ── Mode / Preset row ──
        ctrl_row = QHBoxLayout(); ctrl_row.setSpacing(12)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["DISCORD", "ALL TRAFFIC"])
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["DEFAULT", "GAMING", "STREAM"])

        for cb in (self._mode_combo, self._preset_combo):
            cb.setStyleSheet(
                f"QComboBox {{ background: #0a0000; color: {RED_BRIGHT}; border: 1px solid {BORDER};"
                "border-radius: 0; padding: 6px 10px; font-family: monospace; font-size: 11px;"
                "letter-spacing: 2px; }}"
                f"QComboBox::drop-down {{ border: none; }}"
                f"QComboBox QAbstractItemView {{ background: #0a0000; color: {RED_BRIGHT};"
                f"border: 1px solid {BORDER}; selection-background-color: #1a0000; }}"
            )
            ctrl_row.addWidget(cb)

        bl.addLayout(ctrl_row)

        # ── ACTIVATE button ──
        self._act_btn = ActivateButton()
        self._act_btn.clicked.connect(self._toggle)
        bl.addWidget(self._act_btn)

        # ── Terminal ──
        self._term = Terminal()
        self._term.setMinimumHeight(200)
        bl.addWidget(self._term)

        # ── Bottom options ──
        opt_row = QHBoxLayout(); opt_row.setSpacing(20)

        self._auto_cb = QCheckBox("AUTOSTART")
        self._auto_cb.setChecked(get_autostart())
        self._auto_cb.toggled.connect(set_autostart)
        self._ks_cb   = QCheckBox("KILL SWITCH")
        self._ks_cb.setChecked(True)

        for cb in (self._auto_cb, self._ks_cb):
            cb.setStyleSheet(
                f"QCheckBox {{ color: #3a0000; font-size: 10px; font-family: monospace;"
                f"letter-spacing: 2px; spacing: 6px; }}"
                f"QCheckBox::indicator {{ width: 14px; height: 14px;"
                f"border: 1px solid {BORDER}; background: {BLACK}; }}"
                f"QCheckBox::indicator:checked {{ background: {RED}; border-color: {RED_BRIGHT}; }}"
            )
            opt_row.addWidget(cb)

        opt_row.addStretch()

        brand = QLabel("by solevoyq")
        brand.setStyleSheet("color: #1a0000; font-size: 10px;")
        opt_row.addWidget(brand)
        bl.addLayout(opt_row)

        vbox.addWidget(body)

    # ── Workers ─────────────────────────────────────────────────────

    def _setup_workers(self):
        self._tw = TunnelWorker()
        self._tt = QThread(); self._tw.moveToThread(self._tt)
        self._tw.log.connect(self._term.append_line)
        self._tw.started.connect(self._on_start)
        self._tw.stopped.connect(self._on_stop)
        self._tw.error.connect(self._on_err)
        self._tt.start()

        self._pw = PingWorker()
        self._pt = QThread(); self._pw.moveToThread(self._pt)
        self._pw.result.connect(self._on_ping)
        self._pt.started.connect(self._pw.run)
        self._pt.start()

    # ── Startup ──────────────────────────────────────────────────────

    def _startup_checks(self):
        log = self._term.append_line

        log("0bx0d? initializing...")
        if is_admin():
            log("✓ admin privileges: OK")
        else:
            log("✗ NO ADMIN — restart as administrator")

        missing = [f for f in ("goodbyedpi.exe","WinDivert.dll","WinDivert64.sys")
                   if not (BIN_DIR / f).exists()]
        if missing:
            for f in missing: log(f"✗ missing: {f}")
        else:
            log("✓ all driver files: OK")

        try:
            socket.create_connection(("discord.com", 443), timeout=3).close()
            log("✓ discord.com: reachable")
        except OSError:
            log("✗ discord.com: unreachable")

    # ── Tunnel control ───────────────────────────────────────────────

    def _toggle(self):
        if self._tunnel_on:
            self._tw.stop()
            self._on_stop()
        else:
            mode   = "DISCORD" if self._mode_combo.currentIndex() == 0 else "ALL"
            preset = self._preset_combo.currentText()
            ks     = self._ks_cb.isChecked()
            self._tw.launch(mode, preset, ks)

    def _on_start(self):
        self._tunnel_on = True
        self._act_btn.set_active(True)
        self._act_btn.setText("DEACTIVATE")
        self._dot.setStyleSheet("border-radius: 5px; background: #cc0000;")
        self._status_lbl.setStyleSheet(
            "color: #cc0000; font-family: 'Orbitron',Arial; font-size: 11px;"
            "font-weight: 900; letter-spacing: 4px;")
        self._status_lbl.setText("ACTIVE")
        self._term.append_line("▶ ACTIVATED. enjoy your freedom.")

    def _on_stop(self):
        self._tunnel_on = False
        self._act_btn.set_active(False)
        self._act_btn.setText("ACTIVATE")
        self._dot.setStyleSheet("border-radius: 5px; background: #2a0000;")
        self._status_lbl.setStyleSheet(
            "color: #3a0000; font-family: 'Orbitron',Arial; font-size: 11px;"
            "font-weight: 900; letter-spacing: 4px;")
        self._status_lbl.setText("OFFLINE")
        self._term.append_line("■ deactivated.")

    def _on_err(self, msg: str):
        self._on_stop()
        self._term.append_line(f"✗ error: {msg}")

    def _on_ping(self, ms):
        if ms is None:
            self._ping_lbl.setText("PING —")
            self._ping_lbl.setStyleSheet("color: #2a0000; font-size: 11px;")
        else:
            col = "#00aa33" if ms < 80 else "#cc6600" if ms < 150 else "#cc0000"
            self._ping_lbl.setText(f"PING {ms}ms")
            self._ping_lbl.setStyleSheet(f"color: {col}; font-size: 11px; font-family: monospace;")

    # ── Close ────────────────────────────────────────────────────────

    def closeEvent(self, e):
        if self._tunnel_on:
            self._tw.stop()
        self._pw.stop()
        for t in (self._pt, self._tt):
            t.quit(); t.wait(2000)
        e.accept()


# ═══════════════════════════════════════════════════════════════════════
#   ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
def main():
    if sys.platform == "win32" and not is_admin():
        relaunch_admin()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("0bx0d?")

    # Dark fusion palette
    from PySide6.QtGui import QPalette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,       QColor(0, 0, 0))
    pal.setColor(QPalette.ColorRole.WindowText,   QColor(200, 0, 0))
    pal.setColor(QPalette.ColorRole.Base,         QColor(5, 0, 0))
    pal.setColor(QPalette.ColorRole.Text,         QColor(200, 0, 0))
    pal.setColor(QPalette.ColorRole.Button,       QColor(10, 0, 0))
    pal.setColor(QPalette.ColorRole.ButtonText,   QColor(200, 0, 0))
    pal.setColor(QPalette.ColorRole.Highlight,    QColor(139, 0, 0))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
