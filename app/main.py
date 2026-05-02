# -*- coding: utf-8 -*-
"""0bx0d? — DPI bypass tool v2.1"""
import ctypes, math, os, random, socket, subprocess, sys, time, winreg
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QPointF,
    QRect, QRectF, QSize, QSizeF,
)
from PySide6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush,
    QRadialGradient, QLinearGradient,
    QPixmap, QMouseEvent, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QComboBox, QSizePolicy,
    QStackedWidget, QGraphicsDropShadowEffect,
)

# ── Constants ─────────────────────────────────────────────────────────
APP_NAME = "0bx0d"
VERSION  = "2.1"
BIN_DIR  = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

C_BG     = "#111213"
C_SIDE   = "#0c0d0e"
C_RED    = "#8b0000"
C_RED2   = "#cc0000"
C_RED3   = "#ff0000"
C_SILVER = "#b0b0b0"
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

DNS_PRESETS = {
    "GOOGLE":     ("8.8.8.8",        "8.8.4.4"),
    "CLOUDFLARE": ("1.1.1.1",        "1.0.0.1"),
    "QUAD9":      ("9.9.9.9",        "149.112.112.112"),
    "ADGUARD":    ("94.140.14.14",   "94.140.15.15"),
    "OPENDNS":    ("208.67.222.222", "208.67.220.220"),
    "AUTO":       ("", ""),
}

# ── Fonts ─────────────────────────────────────────────────────────────
def mono(px: int, w=QFont.Weight.Normal) -> QFont:
    f = QFont(); f.setFamilies(["JetBrains Mono","Consolas","Roboto Mono","Courier New"])
    f.setPixelSize(px); f.setWeight(w); return f

def orb(px: int, w=QFont.Weight.Black) -> QFont:
    f = QFont(); f.setFamilies(["Orbitron","Arial Black","Arial"])
    f.setPixelSize(px); f.setWeight(w); return f

# ── Admin ─────────────────────────────────────────────────────────────
def is_admin() -> bool:
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None,"runas",sys.executable," ".join(f'"{a}"' for a in sys.argv),None,1)
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════════
#  WORKERS
# ══════════════════════════════════════════════════════════════════════

class TunnelWorker(QObject):
    log     = Signal(str)
    started = Signal()
    stopped = Signal()
    error   = Signal(str)
    _go     = Signal(str, list, bool)

    def __init__(self):
        super().__init__()
        self._proc = None; self._run = False
        self._cmd = []; self._ks = False
        self._go.connect(self._start)

    def launch(self, preset_name: str, ks: bool):
        p   = PRESETS.get(preset_name, list(PRESETS.values())[0])
        cmd = [str(BIN_DIR/"goodbyedpi.exe")] + p["args"] + BLACKLIST.get(p["mode"],[])
        self._go.emit(preset_name, cmd, ks)

    def _kill_old(self):
        for p in psutil.process_iter(["name","pid"]):
            try:
                if (p.info["name"] or "").lower() == "goodbyedpi.exe":
                    p.kill(); p.wait(3)
            except: pass

    def _start(self, _n, cmd, ks):
        self._run=True; self._cmd=cmd; self._ks=ks
        self._kill_old()
        self.log.emit("CMD: "+" ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.started.emit(); self._watch()
        except OSError as e: self.error.emit(str(e))

    def _watch(self):
        while self._run:
            if not self._proc: break
            if self._proc.poll() is not None:
                if self._run and self._ks:
                    self.log.emit("⚡ kill switch: restarting...")
                    time.sleep(1); self._kill_old()
                    try:
                        self._proc = subprocess.Popen(
                            self._cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        continue
                    except OSError as e: self.error.emit(str(e)); break
                else: self.stopped.emit(); break
            if self._proc and self._proc.stdout:
                line = self._proc.stdout.readline()
                if line: self.log.emit(line.decode("utf-8","replace").strip())
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
                s.connect(("discord.com",443))
                self.result.emit(round((time.perf_counter()-t0)*1000,1))
                s.close()
            except: self.result.emit(None)
            time.sleep(4)

    def stop(self): self._active = False


class DnsWorker(QObject):
    log    = Signal(str)
    done   = Signal(bool, str)
    _go    = Signal(str, str, str, str)
    _reset = Signal(str)

    def __init__(self):
        super().__init__()
        self._go.connect(self._set)
        self._reset.connect(self._do_reset)

    def set_dns(self, adapter, primary, secondary):
        self._go.emit(adapter, primary, secondary, "")

    def reset_dns(self, adapter):
        self._reset.emit(adapter)

    def _set(self, adapter, primary, secondary, _):
        try:
            self.log.emit(f"Setting DNS → {primary} / {secondary or 'none'}")
            subprocess.run(
                ["netsh","interface","ip","set","dns",adapter,"static",primary],
                capture_output=True,timeout=8)
            if secondary:
                subprocess.run(
                    ["netsh","interface","ip","add","dns",adapter,secondary,"index=2"],
                    capture_output=True,timeout=8)
            subprocess.run(["ipconfig","/flushdns"],capture_output=True,timeout=5)
            self.done.emit(True, f"✓ DNS set: {primary}")
        except Exception as e:
            self.done.emit(False, f"✗ DNS error: {e}")

    def _do_reset(self, adapter):
        try:
            self.log.emit("Resetting DNS → DHCP")
            subprocess.run(
                ["netsh","interface","ip","set","dns",adapter,"dhcp"],
                capture_output=True,timeout=8)
            subprocess.run(["ipconfig","/flushdns"],capture_output=True,timeout=5)
            self.done.emit(True,"✓ DNS reset to auto")
        except Exception as e:
            self.done.emit(False,f"✗ reset error: {e}")


def get_adapters() -> list[str]:
    try:
        r = subprocess.run(
            ["netsh","interface","show","interface"],
            capture_output=True,text=True,timeout=5)
        out = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] in ("Connected","Enabled","Підключено","Enabled"):
                out.append(" ".join(parts[3:]))
        return out or ["Wi-Fi","Ethernet"]
    except: return ["Wi-Fi","Ethernet"]

def get_current_dns(adapter: str) -> str:
    try:
        r = subprocess.run(
            ["netsh","interface","ip","show","dns",adapter],
            capture_output=True,text=True,timeout=5)
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        ips = [l for l in lines if any(c.isdigit() for c in l) and "." in l]
        return "  /  ".join(ips[:2]) if ips else "AUTO (DHCP)"
    except: return "unknown"

# ── Autostart ─────────────────────────────────────────────────────────
def set_autostart(on: bool):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,REG_KEY,0,
                           winreg.KEY_SET_VALUE|winreg.KEY_QUERY_VALUE)
        if on:
            val = (sys.executable if getattr(sys,"frozen",False)
                   else f'"{sys.executable}" "{os.path.abspath(__file__)}"')
            winreg.SetValueEx(k,APP_NAME,0,winreg.REG_SZ,val)
        else:
            try: winreg.DeleteValue(k,APP_NAME)
            except FileNotFoundError: pass
        winreg.CloseKey(k)
    except: pass

def get_autostart() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,REG_KEY,0,winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k,APP_NAME); winreg.CloseKey(k); return True
    except: return False

# ══════════════════════════════════════════════════════════════════════
#  NOISE + VIGNETTE BACKGROUND
# ══════════════════════════════════════════════════════════════════════
_NOISE_PIX: QPixmap | None = None

def _noise(w,h) -> QPixmap:
    global _NOISE_PIX
    if _NOISE_PIX and _NOISE_PIX.width()>=w and _NOISE_PIX.height()>=h:
        return _NOISE_PIX
    pix=QPixmap(w,h); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); rng=random.Random(1337)
    for _ in range(w*h//7):
        x=rng.randint(0,w-1); y=rng.randint(0,h-1)
        v=rng.randint(110,255); a=rng.randint(2,10)
        p.setPen(QColor(v,v,v,a)); p.drawPoint(x,y)
    p.end(); _NOISE_PIX=pix; return pix


class NoiseFrame(QWidget):
    def paintEvent(self,_):
        p=QPainter(self); r=self.rect()
        cx,cy=r.width()/2,r.height()/2
        p.fillRect(r,QColor(C_BG))
        p.drawPixmap(0,0,_noise(r.width(),r.height()))
        # Vignette: dark edges, faint red tint at center
        g=QRadialGradient(cx,cy,max(cx,cy)*1.1)
        g.setColorAt(0.0,QColor(25,4,4,18))
        g.setColorAt(0.55,QColor(0,0,0,0))
        g.setColorAt(1.0,QColor(0,0,0,110))
        p.fillRect(r,g); p.end()

# ══════════════════════════════════════════════════════════════════════
#  GLITCH LABEL
# ══════════════════════════════════════════════════════════════════════
class GlitchLabel(QWidget):
    def __init__(self,text,parent=None):
        super().__init__(parent)
        self._text=text; self._ox=0; self._oy=0; self._g=False
        t=QTimer(self); t.timeout.connect(self._tick); t.start(90)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)

    def _tick(self):
        if random.random()<0.07:
            self._g=True; self._ox=random.randint(-2,2); self._oy=random.randint(-1,1)
        else: self._g=False; self._ox=0; self._oy=0
        self.update()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f=orb(14); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,4)
        p.setFont(f); r=self.rect()
        if self._g:
            p.setPen(QColor(139,0,0,150))
            p.drawText(r.translated(self._ox+2,self._oy),Qt.AlignmentFlag.AlignVCenter,self._text)
            p.setPen(QColor(0,155,155,65))
            p.drawText(r.translated(self._ox-1,self._oy),Qt.AlignmentFlag.AlignVCenter,self._text)
        p.setPen(QColor(C_SILVER))
        p.drawText(r.translated(self._ox,self._oy),Qt.AlignmentFlag.AlignVCenter,self._text)
        p.end()

    def sizeHint(self): return QSize(110,24)

# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR BUTTON  (with periodic glitch)
# ══════════════════════════════════════════════════════════════════════
class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self,icon,parent=None):
        super().__init__(parent)
        self._icon=icon; self._hover=False; self._active=False
        self._gx=0; self._gy=0; self._glitch=False
        self.setFixedSize(52,52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Random glitch every 5-12s
        t=QTimer(self); t.timeout.connect(self._do_glitch)
        t.start(random.randint(5000,12000))

    def _do_glitch(self):
        self._glitch=True; self._gx=random.randint(-2,2); self._gy=random.randint(-1,1)
        self.update()
        QTimer.singleShot(80,self._end_glitch)

    def _end_glitch(self):
        self._glitch=False; self._gx=0; self._gy=0; self.update()

    def set_active(self,v): self._active=v; self.update()
    def enterEvent(self,_): self._hover=True;  self.update()
    def leaveEvent(self,_): self._hover=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect()
        if self._active:
            p.fillRect(r,QColor(20,0,0))
            p.fillRect(0,10,3,r.height()-20,QColor(C_RED2))
        elif self._hover: p.fillRect(r,QColor(15,4,4))
        f=orb(17); p.setFont(f)
        ox,oy=(self._gx,self._gy) if self._glitch else (0,0)
        if self._glitch:
            p.setPen(QColor(139,0,0,100))
            p.drawText(r.translated(ox+1,oy),Qt.AlignmentFlag.AlignCenter,self._icon)
        p.setPen(QColor(C_RED2) if (self._active or self._hover) else QColor(C_DIM))
        p.drawText(r.translated(ox,oy),Qt.AlignmentFlag.AlignCenter,self._icon)
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  EYE BUTTON
# ══════════════════════════════════════════════════════════════════════
class EyeButton(QWidget):
    clicked=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self._active=False; self._hover=False
        self._phase=0.0; self._pdir=1
        self._open=0.0; self._glitch=0
        self.setFixedSize(210,210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t=QTimer(self); t.timeout.connect(self._tick); t.start(25)
        lt=QTimer(self); lt.timeout.connect(self._open_lid); lt.start(16)
        self._lt=lt

    def _open_lid(self):
        self._open=min(1.0,self._open+0.032); self.update()
        if self._open>=1.0: self._lt.stop()

    def _tick(self):
        spd=0.032 if (self._active or self._hover) else 0.007
        self._phase+=spd*self._pdir
        if self._phase>=1.0: self._pdir=-1
        if self._phase<=0.0: self._pdir=1
        if self._active and random.random()<0.03: self._glitch=3
        if self._glitch>0: self._glitch-=1
        self.update()

    def set_active(self,v): self._active=v; self.update()
    def enterEvent(self,_): self._hover=True
    def leaveEvent(self,_): self._hover=False
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx=self.width()/2; cy=self.height()/2; R=min(cx,cy)-10

        # Outer glow (stronger when active)
        if self._active:
            gr=R+22+12*self._phase
            g=QRadialGradient(cx,cy,gr)
            g.setColorAt(0,  QColor(200,0,0,int(70+55*self._phase)))
            g.setColorAt(0.4,QColor(100,0,0,int(35+25*self._phase)))
            g.setColorAt(1,  QColor(0,0,0,0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-gr,cy-gr,gr*2,gr*2))
            # Second ring
            g2=QRadialGradient(cx,cy,R+5)
            g2.setColorAt(0,QColor(0,0,0,0))
            g2.setColorAt(0.85,QColor(180,0,0,int(40*self._phase)))
            g2.setColorAt(1,  QColor(180,0,0,int(80*self._phase)))
            p.setBrush(g2)
            p.drawEllipse(QRectF(cx-R-6,cy-R-6,(R+6)*2,(R+6)*2))
        elif self._hover:
            g=QRadialGradient(cx,cy,R+14)
            g.setColorAt(0,QColor(65,0,0,32)); g.setColorAt(1,QColor(0,0,0,0))
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-R-14,cy-R-14,(R+14)*2,(R+14)*2))

        # Body
        bg=QRadialGradient(cx,cy-R*0.15,R)
        if self._active:
            bg.setColorAt(0,QColor(42,3,3)); bg.setColorAt(1,QColor(9,0,0))
        else:
            bg.setColorAt(0,QColor(24,17,17)); bg.setColorAt(1,QColor(8,5,5))
        bw=1+int(self._phase) if self._active else 1
        bc=QColor(C_RED2) if self._active else (QColor(C_RED) if self._hover else QColor(C_BORDER))
        p.setBrush(bg); p.setPen(QPen(bc,bw))
        p.drawEllipse(QRectF(cx-R,cy-R,R*2,R*2))

        # Eye
        ew=R*0.70; eh=R*0.37*self._open
        if eh>1:
            path=QPainterPath()
            path.moveTo(cx-ew,cy)
            path.quadTo(cx,cy-eh,cx+ew,cy)
            path.quadTo(cx,cy+eh*0.75,cx-ew,cy)
            sc=QColor(16,2,2) if self._active else QColor(9,4,4)
            p.setBrush(sc); p.setPen(QPen(QColor(C_RED),1))
            p.drawPath(path)
            ir=eh*0.60
            if ir>2:
                ig=QRadialGradient(cx,cy,ir)
                if self._active:
                    ig.setColorAt(0,  QColor(220,12,12,235))
                    ig.setColorAt(0.4,QColor(145,0,0,215))
                    ig.setColorAt(1,  QColor(55,0,0,185))
                else:
                    ig.setColorAt(0,  QColor(115,12,12,195))
                    ig.setColorAt(0.5,QColor(70,0,0,170))
                    ig.setColorAt(1,  QColor(25,0,0,145))
                p.setBrush(ig); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx,cy),ir,ir)
                p.setBrush(QColor(2,0,0,245))
                p.drawEllipse(QPointF(cx,cy),ir*0.35,ir*0.35)
                p.setBrush(QColor(255,80,80,80))
                p.drawEllipse(QPointF(cx-ir*0.27,cy-ir*0.27),ir*0.15,ir*0.15)

        # Label
        ox=random.randint(-2,2) if (self._glitch and self._active) else 0
        f=mono(11,QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,4)
        p.setFont(f)
        ty=int(cy+R*0.62)
        tr=QRect(ox,ty,self.width(),20)
        if self._active:
            p.setPen(QColor(255,255,255,int(190+65*self._phase)))
            p.drawText(tr,Qt.AlignmentFlag.AlignHCenter,"KILL  —  FEED")
        else:
            p.setPen(QColor(C_RED2) if self._hover else QColor(C_RED))
            p.drawText(tr,Qt.AlignmentFlag.AlignHCenter,"EAT  —  .EXE")
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  VEIN OVERLAY  (with flicker)
# ══════════════════════════════════════════════════════════════════════
class VeinOverlay(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._opacity=0.0; self._dir=0; self._phase=0.0; self._flicker=1.0
        self._paths: list[list[QPointF]]=[]
        self._t=QTimer(self); self._t.timeout.connect(self._tick)

    def activate(self):
        if not self._paths: self._gen()
        self._dir=1
        if not self._t.isActive(): self._t.start(20)

    def deactivate(self):
        self._dir=-1
        if not self._t.isActive(): self._t.start(20)

    def _gen(self):
        self._paths=[]; w,h=self.width(),self.height()
        rng=random.Random(42)
        for (cx,cy) in [(0,0),(w,0),(0,h),(w,h)]:
            for _ in range(3):
                path,x,y=[],float(cx),float(cy)
                dx=(1 if cx==0 else -1)*rng.uniform(0.35,0.9)
                dy=(1 if cy==0 else -1)*rng.uniform(0.35,0.9)
                for _ in range(rng.randint(5,10)):
                    path.append(QPointF(x,y))
                    x+=dx*rng.uniform(22,52); y+=dy*rng.uniform(16,42)
                    dx=max(-1.0,min(1.0,dx+rng.uniform(-0.32,0.32)))
                    dy=max(-1.0,min(1.0,dy+rng.uniform(-0.32,0.32)))
                self._paths.append(path)

    def _tick(self):
        if self._dir==1:
            self._opacity=min(1.0,self._opacity+0.055)
            if self._opacity>=1.0: self._dir=0
        elif self._dir==-1:
            self._opacity=max(0.0,self._opacity-0.055)
            if self._opacity<=0.0: self._dir=0; self._t.stop()
        self._phase+=0.055
        # Subtle flicker when active
        if self._opacity>0.5:
            self._flicker=0.7+random.random()*0.3 if random.random()<0.15 else min(1.0,self._flicker+0.05)
        self.update()

    def paintEvent(self,_):
        if self._opacity<=0: return
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pulse=0.5+0.5*math.sin(self._phase)
        base_a=int(self._opacity*self._flicker*(85+50*pulse))
        for path in self._paths:
            if len(path)<2: continue
            p.setPen(QPen(QColor(160,0,0,base_a),1.5,Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            for i in range(len(path)-1): p.drawLine(path[i],path[i+1])
            if len(path)>3:
                mid=path[len(path)//2]
                rng=random.Random(int(path[0].x()))
                p.setPen(QPen(QColor(95,0,0,base_a//2),1))
                p.drawLine(mid,QPointF(mid.x()+rng.randint(-32,32),
                                       mid.y()+rng.randint(-22,22)))
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  TERMINAL  (silver text, neon red errors, line spacing)
# ══════════════════════════════════════════════════════════════════════
class Terminal(QTextEdit):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setDefaultStyleSheet(
            "p { margin:0; padding:0; line-height:160%; }")
        self.setStyleSheet(
            "QTextEdit { background:#0a0b0c; color:#884444;"
            "border:1px solid #1e0606; padding:8px 10px;"
            "font-family:'JetBrains Mono','Consolas','Roboto Mono',monospace;"
            "font-size:11px; line-height:1.6; }"
            "QScrollBar:vertical { background:#0a0b0c; width:4px; border:none; }"
            "QScrollBar::handle:vertical { background:#2a0000; border-radius:2px; }"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }"
        )
        self._queue: list[str]=[]
        self._busy=False

    def _col(self,t:str)->str:
        lo=t.lower()
        if any(x in lo for x in ("error","✗","fail","blocked","no admin")): return C_RED3
        if any(x in lo for x in ("✓","ok","activ","enjoy","▶","alive","success","set:")): return "#cc3333"
        if "⚡" in lo or "warn" in lo or "restart" in lo: return "#cc6600"
        return C_SILVER

    def queue_line(self,text:str):
        ts=datetime.now().strftime("%H:%M:%S")
        col=self._col(text)
        html=(f'<p><span style="color:#2a0000;font-size:10px">[{ts}]</span> '
              f'<span style="color:{col}">{text}</span></p>')
        self._queue.append(html)
        if not self._busy: self._pop()

    def _pop(self):
        if not self._queue: self._busy=False; return
        self._busy=True
        self.append(self._queue.pop(0))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QTimer.singleShot(40,self._pop)

# ══════════════════════════════════════════════════════════════════════
#  X-TOGGLE
# ══════════════════════════════════════════════════════════════════════
class XToggle(QWidget):
    toggled=Signal(bool)

    def __init__(self,label,checked=False,parent=None):
        super().__init__(parent)
        self._c=checked; self._l=label; self._h=False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)

    def isChecked(self): return self._c
    def setChecked(self,v): self._c=v; self.update()
    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            self._c=not self._c; self.update(); self.toggled.emit(self._c)

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bx,by,bs=0,5,12
        p.setPen(QPen(QColor(C_RED if (self._h or self._c) else C_DIM),1))
        p.setBrush(QColor("#0a0000") if self._c else Qt.BrushStyle.NoBrush)
        p.drawRect(bx,by,bs,bs)
        if self._c:
            pen=QPen(QColor(C_RED2),1.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); m=2
            p.drawLine(bx+m,by+m,bx+bs-m,by+bs-m)
            p.drawLine(bx+bs-m,by+m,bx+m,by+bs-m)
        f=mono(10); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,2)
        p.setFont(f)
        p.setPen(QColor(C_RED if (self._h or self._c) else C_DIM))
        p.drawText(QRect(bs+7,0,300,22),Qt.AlignmentFlag.AlignVCenter,self._l)
        p.end()

    def sizeHint(self): return QSize(170,22)

# ══════════════════════════════════════════════════════════════════════
#  LOOK BUTTON  (sidebar-style with hover glow)
# ══════════════════════════════════════════════════════════════════════
class LookButton(QPushButton):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setText("LOOK  —  SOURCE")
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:none; background:transparent;")
        self._h=False

    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect()
        # Transparent bg, 1px border like sidebar tabs
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(C_RED2) if self._h else QColor(C_BORDER),1))
        p.drawRect(r.adjusted(0,0,-1,-1))
        # Inner glow on hover (layered rectangles)
        if self._h:
            for i in range(4):
                a=28-i*6
                p.setPen(QPen(QColor(180,0,0,a),1))
                p.drawRect(r.adjusted(i,i,-i,-i))
        # Left accent bar (like active sidebar)
        if self._h:
            p.fillRect(0,6,2,r.height()-12,QColor(C_RED2))
        f=orb(11); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,4)
        p.setFont(f)
        p.setPen(QColor(C_RED2) if self._h else QColor(C_RED))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,self.text())
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  DNS PRESET BUTTON
# ══════════════════════════════════════════════════════════════════════
class DnsBtn(QWidget):
    clicked=Signal()

    def __init__(self,label,parent=None):
        super().__init__(parent)
        self._l=label; self._h=False; self._sel=False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)

    def set_selected(self,v): self._sel=v; self.update()
    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.clicked.emit()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect()
        bg=QColor(20,0,0) if self._sel else (QColor(14,3,3) if self._h else QColor(8,0,0))
        p.fillRect(r,bg)
        bc=QColor(C_RED2) if (self._sel or self._h) else QColor(C_BORDER)
        p.setPen(QPen(bc,1)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r.adjusted(0,0,-1,-1))
        if self._sel: p.fillRect(0,4,2,r.height()-8,QColor(C_RED2))
        f=mono(10,QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,2)
        p.setFont(f)
        p.setPen(QColor(C_RED2) if (self._sel or self._h) else QColor(C_DIM))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,self._l)
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  ACTION BUTTON  (ACTIVATE / RESET style)
# ══════════════════════════════════════════════════════════════════════
class ActionBtn(QPushButton):
    def __init__(self,text,accent=False,parent=None):
        super().__init__(text,parent)
        self._accent=accent; self._h=False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:none; background:transparent;")

    def enterEvent(self,_): self._h=True;  self.update()
    def leaveEvent(self,_): self._h=False; self.update()

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.rect()
        if self._accent:
            bg=QColor(35,0,0) if self._h else QColor(20,0,0)
            bc=QColor(C_RED2) if self._h else QColor(C_RED)
        else:
            bg=QColor(14,4,4) if self._h else QColor(8,2,2)
            bc=QColor(C_RED) if self._h else QColor(C_BORDER)
        p.fillRect(r,bg)
        p.setPen(QPen(bc,1)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r.adjusted(0,0,-1,-1))
        if self._h and self._accent:
            for i in range(3):
                p.setPen(QPen(QColor(180,0,0,22-i*6),1))
                p.drawRect(r.adjusted(i,i,-i,-i))
        f=mono(10,QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,3)
        p.setFont(f)
        p.setPen(QColor(C_RED2) if (self._h and self._accent) else
                 QColor(C_RED)  if self._h else QColor(C_DIM))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,self.text())
        p.end()

# ══════════════════════════════════════════════════════════════════════
#  TITLE BAR
# ══════════════════════════════════════════════════════════════════════
class TitleBar(QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self._win=parent; self._drag=QPoint()
        self.setFixedHeight(38)
        self.setStyleSheet(f"background:{C_SIDE};")
        lay=QHBoxLayout(self); lay.setContentsMargins(8,0,6,0); lay.setSpacing(8)
        lay.addSpacing(52)
        div=QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{C_BORDER};"); lay.addWidget(div)
        self._title=GlitchLabel("0bx0d?"); lay.addWidget(self._title)
        ver=QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace;")
        lay.addWidget(ver); lay.addStretch()
        self._sys=QLabel("SYSTEM:  [ DISCONNECTED ]")
        self._sys.setStyleSheet(
            f"color:{C_DIM}; font-size:10px; "
            "font-family:'JetBrains Mono','Consolas',monospace; letter-spacing:1px;")
        lay.addWidget(self._sys); lay.addSpacing(8)
        for sym,slot in [("—",parent.showMinimized),("✕",parent.close)]:
            btn=QPushButton(sym); btn.setFixedSize(26,26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#3a1010;border:none;"
                "font-size:12px;font-weight:bold;border-radius:3px;}"
                "QPushButton:hover{background:#1e0000;color:#ff3030;}")
            btn.clicked.connect(slot); lay.addWidget(btn)

    def set_status(self,on,ping=None):
        if on:
            extra=f"  {ping}ms" if ping else ""
            self._sys.setText(f"SYSTEM:  [ CONNECTED{extra} ]")
            self._sys.setStyleSheet(
                "color:#cc3333; font-size:10px; "
                "font-family:'JetBrains Mono','Consolas',monospace; letter-spacing:1px;")
        else:
            self._sys.setText("SYSTEM:  [ DISCONNECTED ]")
            self._sys.setStyleSheet(
                f"color:{C_DIM}; font-size:10px; "
                "font-family:'JetBrains Mono','Consolas',monospace; letter-spacing:1px;")

    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            self._drag=e.globalPosition().toPoint()-self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(e.globalPosition().toPoint()-self._drag)

# ══════════════════════════════════════════════════════════════════════
#  QSS GLOBAL  (no Windows defaults anywhere)
# ══════════════════════════════════════════════════════════════════════
GLOBAL_QSS = f"""
QWidget {{ color:{C_SILVER}; background:transparent; }}
QComboBox {{
    background:#0c0000; color:{C_RED2}; border:1px solid {C_BORDER};
    padding:5px 10px;
    font-family:'JetBrains Mono','Consolas',monospace; font-size:10px;
    letter-spacing:1px;
}}
QComboBox::drop-down {{ border:none; width:18px; }}
QComboBox::down-arrow {{ color:{C_RED}; }}
QComboBox QAbstractItemView {{
    background:#0c0000; color:{C_RED2}; border:1px solid {C_BORDER};
    selection-background-color:#1a0000; selection-color:{C_RED2};
    font-family:'JetBrains Mono','Consolas',monospace;
    outline:none;
}}
QScrollBar:horizontal {{ height:0; }}
QToolTip {{ background:#0c0000; color:{C_SILVER}; border:1px solid {C_BORDER}; }}
"""

# ══════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(720,560); self.resize(760,600)
        self.setWindowTitle("0bx0d?")
        self._on=False; self._ping=None
        self._dns_sel: str|None=None
        self._setup_ui(); self._setup_workers()
        QTimer.singleShot(200,self._startup)

    # ── UI ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        root=NoiseFrame(); self.setCentralWidget(root)
        hl=QHBoxLayout(root); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)

        # Sidebar
        sb=QWidget(); sb.setFixedWidth(52)
        sb.setStyleSheet(f"background:{C_SIDE};")
        sl=QVBoxLayout(sb); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        sl.addSpacing(38)
        self._sb=[SideBtn("⊞"),SideBtn("≡"),SideBtn("⚙"),SideBtn("☁"),SideBtn("☥")]
        self._sb[0].set_active(True)
        for b in self._sb: sl.addWidget(b)
        sl.addStretch(); sl.addSpacing(8)
        hl.addWidget(sb)

        # Right side
        right=QWidget(); right.setStyleSheet("background:transparent;")
        rv=QVBoxLayout(right); rv.setContentsMargins(0,0,0,0); rv.setSpacing(0)
        self._tbar=TitleBar(self); rv.addWidget(self._tbar)
        div=QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_BORDER}; max-height:1px;"); rv.addWidget(div)
        self._stack=QStackedWidget(); self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._build_dash())   # 0
        self._stack.addWidget(self._build_logs())   # 1
        self._stack.addWidget(self._build_sett())   # 2
        self._stack.addWidget(self._build_dns())    # 3
        self._stack.addWidget(self._build_info())   # 4
        rv.addWidget(self._stack)
        hl.addWidget(right)

        for i,b in enumerate(self._sb):
            b.clicked.connect(lambda _=None,idx=i: self._nav(idx))

        self._vein=VeinOverlay(self); self._vein.resize(self.size())

    def resizeEvent(self,e):
        super().resizeEvent(e)
        if hasattr(self,"_vein"): self._vein.resize(self.size())

    def _nav(self,i):
        self._stack.setCurrentIndex(i)
        for j,b in enumerate(self._sb): b.set_active(j==i)

    # ── Dashboard ─────────────────────────────────────────────────────
    def _build_dash(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,14,20,14); vl.setSpacing(10)

        center=QHBoxLayout(); center.setSpacing(20)
        self._eye=EyeButton(); self._eye.clicked.connect(self._toggle)
        center.addWidget(self._eye,0,Qt.AlignmentFlag.AlignVCenter)

        rc=QVBoxLayout(); rc.setSpacing(8)
        self._look=LookButton()
        self._look.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        rc.addWidget(self._look)
        sub=QLabel("[ pure code,  raw power ]")
        sub.setStyleSheet(f"color:{C_DIM}; font-size:9px; "
                          "font-family:'JetBrains Mono',monospace; letter-spacing:1px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); rc.addWidget(sub)
        d2=QFrame(); d2.setFrameShape(QFrame.Shape.HLine)
        d2.setStyleSheet(f"color:{C_BORDER};"); rc.addWidget(d2)
        pl=QLabel("SETTINGS PRESET")
        pl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:3px;")
        rc.addWidget(pl)
        self._preset=QComboBox()
        self._preset.addItems([f"[ {k} ]" for k in PRESETS])
        rc.addWidget(self._preset); rc.addStretch()
        center.addLayout(rc)
        vl.addLayout(center)

        ll=QLabel("LIVE LOGS")
        ll.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        vl.addWidget(ll)
        self._term=Terminal(); self._term.setMinimumHeight(130); self._term.setMaximumHeight(165)
        vl.addWidget(self._term)

        bot=QHBoxLayout(); bot.setSpacing(14)
        self._auto=XToggle("AUTOSTART",get_autostart()); self._auto.toggled.connect(set_autostart)
        self._ks=XToggle("KILL SWITCH",True)
        bot.addWidget(self._auto); bot.addWidget(self._ks); bot.addStretch()
        bl=QLabel("by solevoyq")
        bl.setStyleSheet(f"color:{C_BORDER}; font-size:9px; font-family:monospace;")
        bot.addWidget(bl); vl.addLayout(bot)
        return page

    # ── Full logs ──────────────────────────────────────────────────────
    def _build_logs(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,14,20,14)
        lbl=QLabel("FULL LOG")
        lbl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        vl.addWidget(lbl)
        self._full=Terminal(); vl.addWidget(self._full)
        return page

    # ── Settings ───────────────────────────────────────────────────────
    def _build_sett(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,14,20,14); vl.setSpacing(12)
        lbl=QLabel("SETTINGS")
        lbl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        vl.addWidget(lbl)
        div=QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_BORDER};"); vl.addWidget(div)
        a2=XToggle("AUTOSTART  —  run on windows login",get_autostart())
        a2.toggled.connect(set_autostart); a2.toggled.connect(self._auto.setChecked)
        k2=XToggle("KILL SWITCH  —  restart on crash",True)
        k2.toggled.connect(self._ks.setChecked)
        vl.addWidget(a2); vl.addWidget(k2); vl.addStretch()
        vl.addWidget(QLabel(f"0bx0d? v{VERSION}  ·  by solevoyq  ·  MIT"))
        return page

    # ── DNS ────────────────────────────────────────────────────────────
    def _build_dns(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(20,14,20,14); vl.setSpacing(10)

        # Header
        h=QHBoxLayout()
        lbl=QLabel("DNS MANAGER")
        lbl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:4px;")
        h.addWidget(lbl); h.addStretch()
        ref_btn=ActionBtn("REFRESH"); ref_btn.setFixedWidth(90)
        ref_btn.clicked.connect(self._dns_refresh)
        h.addWidget(ref_btn); vl.addLayout(h)

        div=QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_BORDER};"); vl.addWidget(div)

        # Adapter row
        ar=QHBoxLayout()
        al=QLabel("ADAPTER:")
        al.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:2px;")
        al.setFixedWidth(72); ar.addWidget(al)
        self._adapter=QComboBox()
        self._adapter.addItems(get_adapters())
        self._adapter.currentTextChanged.connect(self._dns_show_current)
        ar.addWidget(self._adapter); vl.addLayout(ar)

        # Current DNS display
        self._dns_cur=QLabel("current:  —")
        self._dns_cur.setStyleSheet(
            f"color:{C_SILVER}; font-size:10px; "
            "font-family:'JetBrains Mono','Consolas',monospace; letter-spacing:1px;")
        vl.addWidget(self._dns_cur)

        div2=QFrame(); div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"color:{C_BORDER};"); vl.addWidget(div2)

        # Preset buttons grid
        pl=QLabel("PRESETS")
        pl.setStyleSheet(f"color:{C_DIM}; font-size:9px; font-family:monospace; letter-spacing:3px;")
        vl.addWidget(pl)
        self._dns_btns: dict[str,DnsBtn]={}
        grid=QHBoxLayout(); grid.setSpacing(6)
        for name in DNS_PRESETS:
            b=DnsBtn(name); b.clicked.connect(lambda _=None,n=name: self._dns_select(n))
            self._dns_btns[name]=b; grid.addWidget(b)
        vl.addLayout(grid)

        # Selected DNS info
        self._dns_info=QLabel("primary:  —\nsecondary:  —")
        self._dns_info.setStyleSheet(
            f"color:{C_SILVER}; font-size:10px; "
            "font-family:'JetBrains Mono','Consolas',monospace; letter-spacing:1px;")
        vl.addWidget(self._dns_info)

        # Action buttons
        ab=QHBoxLayout(); ab.setSpacing(8)
        act=ActionBtn("ACTIVATE DNS",accent=True)
        act.clicked.connect(self._dns_activate)
        rst=ActionBtn("RESET TO AUTO")
        rst.clicked.connect(self._dns_reset)
        ab.addWidget(act); ab.addWidget(rst); vl.addLayout(ab)

        # DNS log
        self._dns_log=Terminal(); self._dns_log.setMaximumHeight(100)
        vl.addWidget(self._dns_log)

        QTimer.singleShot(300,self._dns_show_current)
        return page

    # ── Info ───────────────────────────────────────────────────────────
    def _build_info(self)->QWidget:
        page=QWidget(); page.setStyleSheet("background:transparent;")
        vl=QVBoxLayout(page); vl.setContentsMargins(24,18,24,18); vl.setSpacing(14)

        title=QLabel("0bx0d?")
        title.setFont(orb(28)); title.setStyleSheet(f"color:{C_RED2};")
        vl.addWidget(title)

        desc=QLabel(
            f"v{VERSION}  ·  DPI bypass for Discord\n\n"
            "GoodbyeDPI + WinDivert — intercepts TCP/UDP packets\n"
            "and modifies headers so ISP deep packet inspection\n"
            "can't block the connection.\n\n"
            "Discord Voice (RTC, UDP 50000-65535) works via\n"
            "--desync-any-protocol flag.\n\n"
            "No VPN. No ping overhead. No bullshit."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C_SILVER}; font-size:11px; "
                           "font-family:'JetBrains Mono','Consolas',monospace; line-height:1.6;")
        vl.addWidget(desc)

        div=QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C_BORDER};"); vl.addWidget(div)

        links_row=QHBoxLayout()
        gh_btn=ActionBtn("GITHUB →",accent=True); gh_btn.setFixedWidth(120)
        gh_btn.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/Freezonplay070/0bx0d"))
        links_row.addWidget(gh_btn); links_row.addStretch()
        vl.addLayout(links_row)

        vl.addStretch()
        footer=QLabel("by solevoyq  ·  MIT license  ·  not malware")
        footer.setStyleSheet(f"color:{C_BORDER}; font-size:9px; font-family:monospace;")
        vl.addWidget(footer)
        return page

    # ── Workers setup ──────────────────────────────────────────────────
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
        self._dt.start()

    def _log(self,t):
        self._term.queue_line(t); self._full.queue_line(t)

    # ── Startup ────────────────────────────────────────────────────────
    def _startup(self):
        admin=is_admin()
        shield="🛡 " if admin else "⚠ "
        self._log(f"Init: {APP_NAME}? v{VERSION} booting...")
        self._log(f"{shield}admin privileges: {'OK' if admin else 'MISSING — restart as administrator'}")
        missing=[f for f in ("goodbyedpi.exe","WinDivert.dll","WinDivert64.sys")
                 if not (BIN_DIR/f).exists()]
        for f in missing: self._log(f"✗ missing: {f}")
        if not missing: self._log("✓ driver files: OK")
        try:
            socket.create_connection(("discord.com",443),timeout=3).close()
            self._log("Network: DNS check... OK")
        except: self._log("ERROR: Discord Voice RTC blocked.")
        self._log("Status: Awaiting Activation...")

    # ── Tunnel ─────────────────────────────────────────────────────────
    def _toggle(self):
        if self._on: self._tw.stop()
        else:
            key=list(PRESETS)[self._preset.currentIndex()]
            self._tw.launch(key,self._ks.isChecked())

    def _on_start(self):
        self._on=True; self._eye.set_active(True); self._vein.activate()
        self._tbar.set_status(True,self._ping); self._log("▶ ACTIVATED. enjoy your freedom.")

    def _on_stop(self):
        self._on=False; self._eye.set_active(False); self._vein.deactivate()
        self._tbar.set_status(False); self._log("■ deactivated.")

    def _on_err(self,msg): self._on_stop(); self._log(f"✗ error: {msg}")

    def _on_ping(self,ms):
        self._ping=ms
        if self._on: self._tbar.set_status(True,ms)

    # ── DNS actions ────────────────────────────────────────────────────
    def _dns_select(self,name:str):
        self._dns_sel=name
        for n,b in self._dns_btns.items(): b.set_selected(n==name)
        p,s=DNS_PRESETS[name]
        if p:
            self._dns_info.setText(f"primary:    {p}\nsecondary:  {s or '—'}")
        else:
            self._dns_info.setText("primary:    auto (DHCP)\nsecondary:  auto (DHCP)")

    def _dns_show_current(self):
        adapter=self._adapter.currentText()
        cur=get_current_dns(adapter)
        self._dns_cur.setText(f"current:  {cur}")

    def _dns_refresh(self):
        adapters=get_adapters()
        self._adapter.clear(); self._adapter.addItems(adapters)
        self._dns_show_current()
        self._dns_log.queue_line("✓ adapters refreshed")

    def _dns_activate(self):
        if not self._dns_sel:
            self._dns_log.queue_line("✗ select a preset first"); return
        adapter=self._adapter.currentText()
        p,s=DNS_PRESETS[self._dns_sel]
        if not p:
            self._dns_reset(); return
        self._dw.set_dns(adapter,p,s)

    def _dns_reset(self):
        adapter=self._adapter.currentText()
        self._dw.reset_dns(adapter)

    def _dns_done(self,ok,msg):
        self._dns_log.queue_line(msg)
        QTimer.singleShot(600,self._dns_show_current)

    # ── Close ──────────────────────────────────────────────────────────
    def closeEvent(self,e):
        if self._on: self._tw.stop()
        self._pw.stop()
        for t in (self._pt,self._tt,self._dt): t.quit(); t.wait(2000)
        e.accept()

# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
def main():
    if sys.platform=="win32" and not is_admin():
        relaunch_admin()

    app=QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("0bx0d?")
    app.setStyleSheet(GLOBAL_QSS)

    from PySide6.QtGui import QPalette
    pal=QPalette()
    pal.setColor(QPalette.ColorRole.Window,     QColor(C_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C_RED2))
    pal.setColor(QPalette.ColorRole.Base,       QColor("#0a0b0c"))
    pal.setColor(QPalette.ColorRole.Text,       QColor(C_SILVER))
    pal.setColor(QPalette.ColorRole.Button,     QColor("#0c0000"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(C_RED2))
    pal.setColor(QPalette.ColorRole.Highlight,  QColor(C_RED))
    pal.setColor(QPalette.ColorRole.HighlightedText,QColor(C_SILVER))
    app.setPalette(pal)

    win=MainWindow(); win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
