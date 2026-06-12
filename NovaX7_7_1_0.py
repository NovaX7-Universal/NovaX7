# Version: 7.1.3
import sys as _sys
import os as _os

# ── Self-restart with correct env vars if not already set ──────────────────
# QT_OPENGL and QTWEBENGINE_CHROMIUM_FLAGS must exist before the Qt DLLs
# are loaded. Setting os.environ later (even before "from PyQt6 import ...")
# is too late on Windows because the DLL loader resolves them at import time.
# Solution: if the marker __NOVA_ENV_SET__ is absent we re-exec this script
# via subprocess with the vars pre-set in the child process environment.
if _os.environ.get("__NOVA_ENV_SET__") != "1":
    env = _os.environ.copy()
    if _os.name == "nt":
        env.setdefault("QT_OPENGL", "software")
    env["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--disable-features=PointerLockOptions "
        "--disable-gpu-sandbox "
        # Hide webdriver/automation detection (TikTok, Google sign-in)
        "--disable-blink-features=AutomationControlled "
        # Enable media autoplay without user gesture (TikTok, YouTube)
        "--autoplay-policy=no-user-gesture-required "
        # H.264 / AAC codec support via MediaFoundation (Windows)
        "--enable-features=MediaFoundationH264Encoding,PlatformHEVCDecoderSupport,"
        # Web Audio API + MIDI + AudioWorklet for online instruments (piano, synth, …)
        "WebAudioAPI,AudioWorkletRealtimeThread,WebMIDI "
        # Dedicated audio output channels for Web Audio
        "--audio-output-channels=2 "
        # Allow cross-origin media requests (TikTok CDN)
        "--disable-site-isolation-trials "
        "--allow-running-insecure-content "
        # Reduce CORS strictness for embedded video iframes
        "--reduce-security-for-testing "
        # Allow SharedArrayBuffer without COOP/COEP (needed for some Wasm games / AudioWorklet)
        "--enable-features=SharedArrayBuffer "
        # Disable audio process sandbox so Web Audio can access the audio device
        "--disable-audio-output-resampler "
        "--no-sandbox-and-elevated "
    )
    env["__NOVA_ENV_SET__"] = "1"
    import subprocess as _sp
    result = _sp.run([_sys.executable] + _sys.argv, env=env)
    _sys.exit(result.returncode)
# ───────────────────────────────────────────────────────────────────────────

del _sys, _os

import sys
import subprocess
import os
import sqlite3
import json
import shutil
import random
import math
import threading
import http.server
import urllib.parse
import urllib.request
import base64
import hashlib
import hmac
import secrets
import struct
import tempfile
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QFrame,
    QSpacerItem,
    QSizePolicy,
    QInputDialog,
    QMenu,
    QLineEdit,
    QLabel,
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QFileDialog,
    QSlider,
    QMessageBox,
    QListWidgetItem,
    QTabWidget,
    QComboBox,
    QFontComboBox,
    QCheckBox,
    QSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QScrollArea,
    QTextEdit,
    QGroupBox,
    QToolButton,
    QSplitter,
    QProgressBar,
    QStackedWidget,
    QRadioButton,
    QGridLayout,
    QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QPoint, QPointF, QUrl, QMimeData, QRect, QRectF, QElapsedTimer
from PyQt6.QtGui import QFont, QPixmap, QAction, QIcon, QColor, QPalette, QKeySequence, QShortcut, QBrush, QPen, QDesktopServices

# Optional: PyQtWebEngine for the YouTube browser panel
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import (
        QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
        QWebEngineFullScreenRequest, QWebEngineUrlRequestInterceptor,
        QWebEngineScript,
    )
    _WEBENGINE_AVAILABLE = True
    _WEBENGINE_ERROR = ""
except Exception as e:
    _WEBENGINE_AVAILABLE = False
    _WEBENGINE_ERROR = str(e)
    print(f"[Nova] WebEngine konnte nicht geladen werden: {e}")

def _try_load_webengine():
    """Compatibility wrapper — WebEngine is now loaded at startup like DEV8."""
    return _WEBENGINE_AVAILABLE

if os.name == "nt":
    import winreg

    def _add_vlc_to_path():
        for key in (
            r"SOFTWARE\VideoLAN\VLC",
            r"SOFTWARE\WOW6432Node\VideoLAN\VLC",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                    vlc_path = os.path.dirname(winreg.QueryValueEx(k, "InstallDir")[0])
                    os.add_dll_directory(vlc_path)
                    return
            except OSError:
                pass
        for path in (
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC",
        ):
            if os.path.isdir(path):
                os.add_dll_directory(path)
                return

    _add_vlc_to_path()

import vlc
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

# ── Optional: Discord Rich Presence via pypresence ──────────────────────────
try:
    from pypresence import Presence as _DiscordPresence
    _PYPRESENCE_AVAILABLE = True
except ImportError:
    _PYPRESENCE_AVAILABLE = False
    print("[Nova] pypresence nicht gefunden – Discord Rich Presence deaktiviert.")
    print("       Installieren mit: pip install pypresence")

# Discord Application Client-ID (öffentliche Nova-App-ID – kann angepasst werden)
_DISCORD_CLIENT_ID = "1504475285834432522"   # ← hier eigene App-ID eintragen


SUPPORTED_FORMATS = [".aac", ".mp3", ".ogg", ".wav", ".flac", ".m4a"]
SUPPORTED_VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".gif", ".webm", ".mov"]

# ──────────────────────────── BLOCK BLAST MINI-GAME ────────────────────────────

_BB_GRID_SIZE    = 8
_BB_CELL         = 60
_BB_GRID_PX      = _BB_GRID_SIZE * _BB_CELL
_BB_PREVIEW_CELL = 34
_BB_TRAY_SLOTS   = 3

_BB_BG_COLOR  = QColor("#0D0D1A")
_BB_GRID_BG   = QColor("#13132B")
_BB_GRID_LINE = QColor("#1E1E40")
_BB_EMPTY     = QColor("#1A1A35")
_BB_TEXT      = QColor("#E8E8FF")
_BB_SCORE_COL = QColor("#A78BFA")

_BB_BLOCK_COLORS = [
    ("#7C3AED", "#A855F7"),
    ("#0EA5E9", "#38BDF8"),
    ("#10B981", "#34D399"),
    ("#F59E0B", "#FCD34D"),
    ("#EF4444", "#F87171"),
    ("#EC4899", "#F472B6"),
    ("#6366F1", "#818CF8"),
    ("#14B8A6", "#2DD4BF"),
]

_BB_ALL_SHAPES = [
    [(0,0)],
    [(0,0),(0,1)], [(0,0),(1,0)],
    [(0,0),(0,1),(0,2)], [(0,0),(1,0),(2,0)],
    [(0,0),(0,1),(1,0),(1,1)],
    [(0,0),(1,0),(2,0),(2,1)], [(0,0),(0,1),(0,2),(1,0)],
    [(0,0),(0,1),(1,1),(2,1)], [(0,2),(1,0),(1,1),(1,2)],
    [(0,0),(1,0),(2,0),(2,-1)], [(0,0),(1,0),(1,1),(1,2)],
    [(0,1),(1,1),(2,0),(2,1)],
    [(0,0),(0,1),(0,2),(1,1)], [(0,0),(1,0),(1,1),(2,0)],
    [(0,1),(0,2),(1,0),(1,1)], [(0,0),(1,0),(1,1),(2,1)],
    [(0,0),(0,1),(1,1),(1,2)], [(0,1),(1,0),(1,1),(2,0)],
    [(0,0),(0,1),(0,2),(0,3)], [(0,0),(1,0),(2,0),(3,0)],
    [(0,0),(0,1),(0,2),(1,0),(2,0)], [(0,0),(1,0),(2,0),(2,1),(2,2)],
]

def _bb_normalize(shape):
    min_r = min(r for r,c in shape)
    min_c = min(c for r,c in shape)
    return [(r-min_r, c-min_c) for r,c in shape]

def _bb_random_block():
    shape = _bb_normalize(random.choice(_BB_ALL_SHAPES))
    color = random.choice(_BB_BLOCK_COLORS)
    return {"shape": shape, "color": color}


class _BBGameState:
    def __init__(self):
        self.best = 0
        self.reset()

    def reset(self):
        self.board     = [[None]*_BB_GRID_SIZE for _ in range(_BB_GRID_SIZE)]
        self.score     = 0
        self.tray      = [_bb_random_block() for _ in range(_BB_TRAY_SLOTS)]
        self.used      = [False]*_BB_TRAY_SLOTS
        self.game_over = False
        self.combo     = 0
        self.last_cleared_cells = set()

    def can_place(self, block, row, col):
        for r,c in block["shape"]:
            nr,nc = row+r, col+c
            if not (0<=nr<_BB_GRID_SIZE and 0<=nc<_BB_GRID_SIZE): return False
            if self.board[nr][nc] is not None: return False
        return True

    def place(self, block, row, col):
        for r,c in block["shape"]:
            self.board[row+r][col+c] = block["color"]
        cleared, self.last_cleared_cells = self._clear_lines()
        self.score += len(block["shape"])*2
        if cleared > 0:
            self.combo += 1
            self.score += int(cleared*10*(1+(self.combo-1)*0.5))
        else:
            self.combo = 0
        self.best = max(self.best, self.score)
        return cleared

    def _clear_lines(self):
        cleared = 0
        rows_to_clear = [r for r in range(_BB_GRID_SIZE) if all(self.board[r][c] is not None for c in range(_BB_GRID_SIZE))]
        cols_to_clear = [c for c in range(_BB_GRID_SIZE) if all(self.board[r][c] is not None for r in range(_BB_GRID_SIZE))]
        cells = set()
        for r in rows_to_clear:
            for c in range(_BB_GRID_SIZE): cells.add((r,c))
            cleared += 1
        for c in cols_to_clear:
            for r in range(_BB_GRID_SIZE): cells.add((r,c))
            cleared += 1
        for r,c in cells: self.board[r][c] = None
        return cleared, cells

    def refill_tray_if_needed(self):
        if all(self.used):
            self.tray  = [_bb_random_block() for _ in range(_BB_TRAY_SLOTS)]
            self.used  = [False]*_BB_TRAY_SLOTS

    def check_game_over(self):
        available = [self.tray[i] for i in range(_BB_TRAY_SLOTS) if not self.used[i]]
        for block in available:
            for r in range(_BB_GRID_SIZE):
                for c in range(_BB_GRID_SIZE):
                    if self.can_place(block, r, c): return False
        self.game_over = True
        return True


from PyQt6.QtCore import pyqtSignal as _pyqtSignal

class _BBGridWidget(QWidget):
    block_placed = _pyqtSignal(int)

    def __init__(self, state):
        super().__init__()
        self.state         = state
        self.hover_row     = -1
        self.hover_col     = -1
        self.drag_block    = None
        self.drag_tray_idx = -1
        self.drag_offset   = QPoint(0,0)
        self.drag_pos      = QPoint(0,0)
        self.flash_cells   = set()
        self.setFixedSize(_BB_GRID_PX+2, _BB_GRID_PX+2)
        self.setMouseTracking(True)

    def cell_rect(self, r, c):
        return QRect(c*_BB_CELL+1, r*_BB_CELL+1, _BB_CELL-1, _BB_CELL-1)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPainterPath, QLinearGradient, QBrush, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), _BB_GRID_BG)
        for r in range(_BB_GRID_SIZE):
            for c in range(_BB_GRID_SIZE):
                rect = self.cell_rect(r,c)
                cp = self.state.board[r][c]
                if cp:
                    self._draw_cell(p, rect, cp)
                elif (r,c) in self.flash_cells:
                    path = QPainterPath()
                    path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 5,5)
                    p.fillPath(path, QBrush(QColor(255,255,255,180)))
                else:
                    p.fillRect(rect, _BB_EMPTY)
        if self.drag_block and self.hover_row >= 0:
            ok = self.state.can_place(self.drag_block, self.hover_row, self.hover_col)
            for dr,dc in self.drag_block["shape"]:
                nr,nc = self.hover_row+dr, self.hover_col+dc
                if 0<=nr<_BB_GRID_SIZE and 0<=nc<_BB_GRID_SIZE:
                    rect = self.cell_rect(nr,nc)
                    cp = self.drag_block["color"]
                    c = QColor(cp[1] if ok else "#EF4444")
                    c.setAlpha(130)
                    path = QPainterPath()
                    path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 5,5)
                    p.fillPath(path, QBrush(c))
        pen = QPen(_BB_GRID_LINE, 1)
        p.setPen(pen)
        for i in range(_BB_GRID_SIZE+1):
            p.drawLine(i*_BB_CELL+1, 1, i*_BB_CELL+1, _BB_GRID_PX+1)
            p.drawLine(1, i*_BB_CELL+1, _BB_GRID_PX+1, i*_BB_CELL+1)
        p.setPen(QPen(QColor("#2D2D5E"), 2))
        p.drawRect(0, 0, _BB_GRID_PX+1, _BB_GRID_PX+1)
        if self.drag_block:
            for dr,dc in self.drag_block["shape"]:
                x = self.drag_pos.x()+dc*_BB_CELL-self.drag_offset.x()
                y = self.drag_pos.y()+dr*_BB_CELL-self.drag_offset.y()
                self._draw_cell(p, QRect(x,y,_BB_CELL-1,_BB_CELL-1), self.drag_block["color"], 200)

    def _draw_cell(self, p, rect, cp, alpha=255):
        from PyQt6.QtGui import QLinearGradient, QPainterPath, QBrush
        b = QColor(cp[0]); b.setAlpha(alpha)
        l = QColor(cp[1]); l.setAlpha(alpha)
        grad = QLinearGradient(float(rect.x()), float(rect.y()), float(rect.right()), float(rect.bottom()))
        grad.setColorAt(0, l); grad.setColorAt(1, b)
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 5,5)
        p.fillPath(path, QBrush(grad))
        p.fillRect(rect.x()+2, rect.y()+2, rect.width()-4, rect.height()//3, QColor(255,255,255,40))

    def mouseMoveEvent(self, event):
        if self.drag_block:
            self.drag_pos = event.pos()
            col = (event.pos().x()-self.drag_offset.x()+_BB_CELL//2)//_BB_CELL
            row = (event.pos().y()-self.drag_offset.y()+_BB_CELL//2)//_BB_CELL
            self.hover_row, self.hover_col = row, col
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_block and event.button() == Qt.MouseButton.LeftButton:
            self.releaseMouse()
            col = (event.pos().x()-self.drag_offset.x()+_BB_CELL//2)//_BB_CELL
            row = (event.pos().y()-self.drag_offset.y()+_BB_CELL//2)//_BB_CELL
            placed, cleared = False, 0
            if self.state.can_place(self.drag_block, row, col):
                cleared = self.state.place(self.drag_block, row, col)
                self.state.used[self.drag_tray_idx] = True
                self.state.refill_tray_if_needed()
                self.state.check_game_over()
                placed = True
                if cleared > 0:
                    self.flash_cells = set(self.state.last_cleared_cells)
                    self.update()
                    QTimer.singleShot(220, self._clear_flash)
            self.drag_block = None; self.drag_tray_idx = -1
            self.hover_row  = -1;   self.hover_col     = -1
            self.update()
            if placed: self.block_placed.emit(cleared)

    def _clear_flash(self):
        self.flash_cells = set(); self.update()

    def start_drag(self, block, idx, global_pos):
        self.drag_block = block; self.drag_tray_idx = idx
        self.drag_offset = QPoint(_BB_CELL//2, _BB_CELL//2)
        self.drag_pos = self.mapFromGlobal(global_pos)
        self.setMouseTracking(True)
        self.grabMouse()


class _BBTrayWidget(QWidget):
    drag_started = _pyqtSignal(dict, int, QPoint)

    def __init__(self, idx, state):
        super().__init__()
        self.idx = idx; self.state = state
        self.setFixedSize(130, 130)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPainterPath, QBrush, QPen, QLinearGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)
        p.fillPath(path, QBrush(QColor("#1A1A35")))
        p.setPen(QPen(QColor("#2D2D5E"), 1)); p.drawPath(path)
        if self.state.used[self.idx]: return
        block = self.state.tray[self.idx]
        shape, cp = block["shape"], block["color"]
        rows = [r for r,c in shape]; cols = [c for r,c in shape]
        h = (max(rows)-min(rows)+1)*_BB_PREVIEW_CELL
        w = (max(cols)-min(cols)+1)*_BB_PREVIEW_CELL
        ox = (self.width()-w)//2; oy = (self.height()-h)//2
        mr, mc = min(rows), min(cols)
        for r,c in shape:
            x = ox+(c-mc)*_BB_PREVIEW_CELL; y = oy+(r-mr)*_BB_PREVIEW_CELL
            rect = QRect(x, y, _BB_PREVIEW_CELL-2, _BB_PREVIEW_CELL-2)
            grad = QLinearGradient(float(rect.x()), float(rect.y()), float(rect.right()), float(rect.bottom()))
            grad.setColorAt(0, QColor(cp[1])); grad.setColorAt(1, QColor(cp[0]))
            path2 = QPainterPath()
            path2.addRoundedRect(x, y, _BB_PREVIEW_CELL-2, _BB_PREVIEW_CELL-2, 4, 4)
            p.fillPath(path2, QBrush(grad))
            p.fillRect(x+2, y+2, _BB_PREVIEW_CELL-6, (_BB_PREVIEW_CELL-2)//3, QColor(255,255,255,50))

    def mousePressEvent(self, event):
        if event.button()==Qt.MouseButton.LeftButton and not self.state.used[self.idx]:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_started.emit(self.state.tray[self.idx], self.idx, event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class BlockBlastWindow(QDialog):
    """Block Blast – eingebettetes Easter-Egg-Fenster für Nova Player."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎮  Block Blast  –  FFPM Edition")
        self.setFixedSize(_BB_GRID_PX+62, _BB_GRID_PX+310)
        self.setStyleSheet(f"background-color: {_BB_BG_COLOR.name()};")
        self.state = _BBGameState()
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20,15,20,15); main.setSpacing(12)

        title = QLabel("BLOCK BLAST")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#A78BFA; font-size:26px; font-weight:900; letter-spacing:4px; background:transparent;")
        main.addWidget(title)

        self.score_lbl = QLabel("SCORE  0        BEST  0")
        self.score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_lbl.setStyleSheet("color:#A78BFA; font-size:18px; font-weight:bold; background:transparent;")
        main.addWidget(self.score_lbl)

        grid_container = QWidget(); grid_container.setFixedSize(_BB_GRID_PX+2, _BB_GRID_PX+2)
        gh = QHBoxLayout(grid_container); gh.setContentsMargins(0,0,0,0)
        self.grid = _BBGridWidget(self.state)
        self.grid.block_placed.connect(self._on_placed)
        gh.addWidget(self.grid)
        main.addWidget(grid_container, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("NÄCHSTE BLÖCKE")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#6B7280; font-size:10px; letter-spacing:2px; background:transparent;")
        main.addWidget(lbl)

        tray_row = QHBoxLayout(); tray_row.setSpacing(15)
        self.tray_widgets = []
        for i in range(_BB_TRAY_SLOTS):
            tw = _BBTrayWidget(i, self.state)
            tw.drag_started.connect(self.grid.start_drag)
            tray_row.addWidget(tw); self.tray_widgets.append(tw)
        main.addLayout(tray_row)

        btn = QPushButton("Neu starten")
        btn.setFixedHeight(38)
        btn.setStyleSheet("QPushButton{background:#1A1A35;color:#6B7280;font-size:13px;border-radius:10px;border:1px solid #2D2D5E;}"
                          "QPushButton:hover{color:#A78BFA;border-color:#7C3AED;}")
        btn.clicked.connect(self._restart)
        main.addWidget(btn)

        # Game-Over-Overlay
        self.overlay = QWidget(self.grid)
        self.overlay.setGeometry(0, 0, _BB_GRID_PX+2, _BB_GRID_PX+2)
        self.overlay.hide()
        ov_layout = QVBoxLayout(self.overlay)
        ov_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        go_title = QLabel("GAME OVER")
        go_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        go_title.setStyleSheet("color:#EF4444; font-size:32px; font-weight:bold; background:transparent;")
        self._ov_score = QLabel("")
        self._ov_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ov_score.setStyleSheet("color:#A78BFA; font-size:18px; background:transparent;")
        ov_btn = QPushButton("🔄  Nochmal spielen")
        ov_btn.setFixedSize(200, 50)
        ov_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #4F46E5);"
                              "color:white;font-size:15px;font-weight:bold;border-radius:25px;border:none;}"
                              "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8B5CF6,stop:1 #6366F1);}")
        ov_btn.clicked.connect(self._restart)
        ov_layout.addWidget(go_title); ov_layout.addSpacing(10)
        ov_layout.addWidget(self._ov_score); ov_layout.addSpacing(20)
        ov_layout.addWidget(ov_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        def _ov_paint(event):
            from PyQt6.QtGui import QPainter
            p2 = QPainter(self.overlay)
            p2.fillRect(self.overlay.rect(), QColor(0,0,0,180))
        self.overlay.paintEvent = _ov_paint

        self._refresh()

    def _on_placed(self, cleared):
        self._refresh()
        if self.state.game_over:
            self._ov_score.setText(f"Score: {self.state.score:,}   |   Best: {self.state.best:,}")
            self.overlay.show()

    def _refresh(self):
        self.score_lbl.setText(
            f"SCORE  {self.state.score:,}        BEST  {self.state.best:,}"
            + (f"   🔥 ×{self.state.combo}" if self.state.combo >= 2 else "")
        )
        for tw in self.tray_widgets: tw.update()
        self.grid.update()

    def _restart(self):
        self.overlay.hide(); self.state.reset(); self._refresh()

# ──────────────────────────── TRANSLATIONS ────────────────────────────

_TRANSLATIONS = {
    "en": {
        # Sidebar / nav
        "LIBRARY": "LIBRARY",
        "PLAYLISTS": "PLAYLISTS",
        "All Songs": "All Songs",
        "Videos": "Videos",
        "Media Browser": "Media Browser",
        "Favourites": "Favourites",
        "Recently Played": "Recently Played",
        "Most Played": "Most Played",
        "Settings": "Settings",
        "New Playlist": "New Playlist",
        # Top bar buttons
        "+ Import Files": "＋ Import Files",
        "Folder": "📁 Folder",
        "Audio": "♫ Audio",
        "Video": "🎬 Video",
        "Web Player": "🌐 Web Player",
        "Convert": "🔄 Convert",
        # Column headers
        "Title / Artist": "Title / Artist",
        "Album": "Album",
        "Duration": "Duration",
        "Plays": "Plays",
        # Player panel
        "No song playing": "No song playing",
        "Toggle Favourite": "Toggle Favourite",
        "Fullscreen": "⛶  Fullscreen",
        "Fullscreen tooltip": "Open fullscreen (or double-click image/video)",
        "Sleep": "☾ Sleep",
        "Queue": "☰ Queue",
        "Ready": "Ready",
        # Context menu – songs
        "▶  Play Now": "▶  Play Now",
        "♥  Toggle Favourite": "♥  Toggle Favourite",
        "📁  Open Folder": "📁  Open Folder",
        "➕  Add to Playlist": "➕  Add to Playlist",
        "🗑  Remove from Library": "🗑  Remove from Library",
        "✏  Edit": "✏  Edit",
        "🖼  Edit Image & Name": "🖼  Edit Image & Name",
        "✂  Remove from This Playlist": "✂  Remove from This Playlist",
        "No playlists — click + to create one": "No playlists — click + to create one",
        # Context menu – playlists
        "▶  Open": "▶  Open",
        "✏  Edit Name & Cover": "✏  Edit Name & Cover",
        "🎵  Edit Contents": "🎵  Edit Contents",
        "🗑  Delete": "🗑  Delete",
        # Playlist banner buttons
        "▶  Play All": "▶  Play All",
        "⇀  Shuffle": "⇀  Shuffle",
        # Dialogs – remove song
        "Remove Song": "Remove Song",
        "Remove song from library?": "Remove this song from the library?\n(The file is not deleted.)",
        # Dialogs – delete playlist
        "Delete Playlist": "Delete Playlist",
        "Delete playlist?": "Delete playlist '{name}'?",
        # Dialogs – sleep timer
        "Sleep Timer": "Sleep Timer",
        "Cancel existing sleep timer?": "Cancel existing sleep timer?",
        "Sleep timer set": "Sleep timer set for {minutes} minutes.",
        "Stop after:": "Stop after:",
        "Fade out": "Fade out before stopping",
        # Dialogs – queue
        "Up Next": "Up Next",
        "Close": "Close",
        # Edit Song dialog
        "Edit Song": "Edit Song",
        "Title:": "Title:",
        "Artist:": "Artist:",
        "📁  Choose Image": "📁  Choose Image",
        "✕  Clear Cover": "✕  Clear Cover",
        "Missing Title": "Missing Title",
        "Please enter a title.": "Please enter a title.",
        # Playlist dialog
        "Playlist": "Playlist",
        "Edit Playlist": "Edit Playlist",
        "Name:": "Name:",
        "Description:": "Description:",
        "📁  Choose Cover": "📁  Choose Cover",
        "✕  Remove": "✕  Remove",
        "Select Cover Image": "Select Cover Image",
        # EditPlaylistContentDialog
        "Edit Playlist Contents": "Edit Playlist Contents — {name}",
        "Drag & drop hint": "Drag & drop to reorder  ·  Right-click to remove",
        "▲  Move Up": "▲  Move Up",
        "▼  Move Down": "▼  Move Down",
        "🗑  Remove": "🗑  Remove",
        "🗑  Remove from Playlist": "🗑  Remove from Playlist",
        # PlaylistContentDialog
        "Library": "Library",
        "🔍  Search…": "🔍  Search…",
        "➕  Add →": "➕  Add →",
        "Playlist Contents": "Playlist Contents",
        "▲  Up": "▲  Up",
        "▼  Down": "▼  Down",
        "✂  Remove": "✂  Remove",
        "✔  Done": "✔  Done",
        # Browser panel
        "Home tooltip": "Home (YouTube)",
        "Save folder tooltip": "Save folder: {folder}",
        "Mode:": "Mode:",
        "🎬  Video": "🎬  Video",
        "🎵  Audio": "🎵  Audio",
        "Format:": "Format:",
        "Quality:": "Quality:",
        "⬇  Download": "⬇  Download",
        "⬇  Download Audio": "⬇  Download Audio",
        "⬇  Download Video": "⬇  Download Video",
        "Download tooltip": "Download current video / audio",
        "Ready (browser)": "Ready",
        "Loading…": "Loading…",
        "Load error": "Load error",
        "No URL title": "No URL",
        "No URL msg": "Please enter a URL in the address bar\nor open a YouTube video first.",
        "Download running": "A download is already in progress.",
        "Download running title": "Download Running",
        "Audio download starting": "⬇  Starting audio download ({fmt}, {qual}K)…",
        "Video download starting": "⬇  Starting video download ({fmt}, {qual})…",
        "Saved": "✔  Saved: {name}",
        "Error": "✗  Error: {error}",
        "Download done title": "Download Complete",
        "Download done msg": "Saved:\n{path}",
        "Download failed title": "Download Failed",
        "Download failed msg": "{error}",
        "Pick save folder": "Choose Save Folder",
        "Save folder set": "Save folder: {folder}",
        "URL no webengine": "URL: {url}  (WebEngine not available)",
        # WebEngine fallback
        "WebEngine not installed": (
            "<b>PyQt6-WebEngine not installed or broken</b><br><br>"
            "To use the media browser, run:<br><br>"
            "<code>pip install PyQt6-WebEngine</code><br><br>"
            "{error}"
            "Then restart Nova.<br><br>"
            "<small>If PyQt6-WebEngine is already installed, a system DLL may be missing<br>"
            "(e.g. Visual C++ Redistributable). Install it from:<br>"
            "https://aka.ms/vs/17/release/vc_redist.x64.exe</small>"
        ),
        "📋  Copy Command": "📋  Copy Command",
        # Settings dialog
        "Settings dialog title": "Settings",
        "Appearance": "Appearance",
        "Playback": "Playback",
        "Library tab": "Library",
        "Shortcuts": "Shortcuts",
        "Theme:": "Theme:",
        "Font:": "Font:",
        "Font Size:": "Font Size:",
        "UI Zoom:": "UI Zoom:",
        "Show Cover Thumbnails:": "Show Cover Thumbnails:",
        "Compact List Mode:": "Compact List Mode:",
        "Auto-play Next Song:": "Auto-play Next Song:",
        "Crossfade:": "Crossfade:",
        "Default Volume:": "Default Volume:",
        "Auto-extract Embedded Covers:": "Auto-extract Embedded Covers:",
        "Auto-import Folder:": "Auto-import Folder:",
        "Remember Playback Position:": "Remember Playback Position:",
        "Browse...": "Browse...",
        "Select Watch Folder": "Select Watch Folder",
        "Language:": "Language:",
        "shortcuts_text": (
            "Space        — Play / Pause\n"
            "Left         — Rewind 5 seconds\n"
            "Right        — Forward 5 seconds\n"
            "Ctrl+Right   — Next Song\n"
            "Ctrl+Left    — Previous Song\n"
            "Ctrl+Up      — Volume Up\n"
            "Ctrl+Down    — Volume Down\n"
            "Ctrl+L       — Toggle Loop\n"
            "Ctrl+S       — Toggle Shuffle\n"
            "Ctrl+F       — Focus Search\n"
            "Ctrl+I       — Import Files\n"
            "Delete       — Remove Song from View\n"
            "F5           — Refresh Library\n"
        ),
        # Status bar / misc
        "Media Browser status": "Media Browser  ·  YouTube, Vimeo, SoundCloud, Twitch, Bandcamp, …",
        "Playlist label": "Playlist",
        "Added to playlist": "Added to '{name}'",
        "Error duplicate playlist": "A playlist with that name already exists.",
        # Fullscreen hint
        "ESC hint": "ESC or double-click to close",
        # View titles
        "view_library": "♪  All Songs",
        "view_favourites": "♥  Favourites",
        "view_recently": "🕐  Recently Played",
        "view_mostplayed": "🔥  Most Played",
        "view_videos": "🎬  Videos",
        "view_ytbrowser": "🌐  Media Browser",
        "Search placeholder": "⌕  Search songs, artists, albums...",
        # Import tooltips
        "Audio import tooltip": "Import audio from YouTube, SoundCloud, and more via yt-dlp",
        "Video import tooltip": "Download video (mp4, mkv, gif, webm, mov, avi) via yt-dlp",
        "Convert tooltip": "Convert audio ↔ video using ffmpeg",
        # Discord Rich Presence
        "Discord RPC:": "Discord Rich Presence:",
        "discord_rpc_tooltip": "Show currently playing song in Discord status",
    },
    "de": {
        # Sidebar / nav
        "LIBRARY": "BIBLIOTHEK",
        "PLAYLISTS": "PLAYLISTS",
        "All Songs": "Alle Songs",
        "Videos": "Videos",
        "Media Browser": "Medienbrowser",
        "Favourites": "Favoriten",
        "Recently Played": "Zuletzt gespielt",
        "Most Played": "Meist gespielt",
        "Settings": "Einstellungen",
        "New Playlist": "Neue Playlist",
        # Top bar buttons
        "+ Import Files": "＋ Dateien",
        "Folder": "📁 Ordner",
        "Audio": "♫ Audio",
        "Video": "🎬 Video",
        "Web Player": "🌐 Web Player",
        "Convert": "🔄 Konvertieren",
        # Column headers
        "Title / Artist": "Titel / Künstler",
        "Album": "Album",
        "Duration": "Länge",
        "Plays": "Spiele",
        # Player panel
        "No song playing": "Kein Song aktiv",
        "Toggle Favourite": "Favorit umschalten",
        "Fullscreen": "⛶  Vollbild",
        "Fullscreen tooltip": "Vollbild öffnen (oder Doppelklick auf Bild/Video)",
        "Sleep": "☾ Sleep",
        "Queue": "☰ Warteschlange",
        "Ready": "Bereit",
        # Context menu – songs
        "▶  Play Now": "▶  Abspielen",
        "♥  Toggle Favourite": "♥  Favorit",
        "📁  Open Folder": "📁  Ordner öffnen",
        "➕  Add to Playlist": "➕  Zur Playlist",
        "🗑  Remove from Library": "🗑  Aus Bibliothek entfernen",
        "✏  Edit": "✏  Bearbeiten",
        "🖼  Edit Image & Name": "🖼  Bild & Name bearbeiten",
        "✂  Remove from This Playlist": "✂  Aus Playlist entfernen",
        "No playlists — click + to create one": "Keine Playlists — + drücken zum Erstellen",
        # Context menu – playlists
        "▶  Open": "▶  Öffnen",
        "✏  Edit Name & Cover": "✏  Name & Cover bearbeiten",
        "🎵  Edit Contents": "🎵  Inhalt bearbeiten",
        "🗑  Delete": "🗑  Löschen",
        # Playlist banner buttons
        "▶  Play All": "▶  Alle abspielen",
        "⇀  Shuffle": "⇀  Zufällig",
        # Dialogs – remove song
        "Remove Song": "Song entfernen",
        "Remove song from library?": "Song aus der Bibliothek entfernen?\n(Die Datei wird nicht gelöscht.)",
        # Dialogs – delete playlist
        "Delete Playlist": "Playlist löschen",
        "Delete playlist?": "Playlist '{name}' löschen?",
        # Dialogs – sleep timer
        "Sleep Timer": "Schlaf-Timer",
        "Cancel existing sleep timer?": "Bestehenden Schlaf-Timer abbrechen?",
        "Sleep timer set": "Schlaf-Timer gesetzt für {minutes} Minuten.",
        "Stop after:": "Stopp nach:",
        "Fade out": "Ausblenden vor dem Stopp",
        # Dialogs – queue
        "Up Next": "Als Nächstes",
        "Close": "Schließen",
        # Edit Song dialog
        "Edit Song": "Song bearbeiten",
        "Title:": "Titel:",
        "Artist:": "Künstler:",
        "📁  Choose Image": "📁  Bild wählen",
        "✕  Clear Cover": "✕  Cover entfernen",
        "Missing Title": "Kein Titel",
        "Please enter a title.": "Bitte einen Titel eingeben.",
        # Playlist dialog
        "Playlist": "Playlist",
        "Edit Playlist": "Playlist bearbeiten",
        "Name:": "Name:",
        "Description:": "Beschreibung:",
        "📁  Choose Cover": "📁  Cover wählen",
        "✕  Remove": "✕  Entfernen",
        "Select Cover Image": "Cover-Bild wählen",
        # EditPlaylistContentDialog
        "Edit Playlist Contents": "Playlist bearbeiten — {name}",
        "Drag & drop hint": "Reihenfolge per Drag & Drop ändern  ·  Rechtsklick zum Entfernen",
        "▲  Move Up": "▲  Nach oben",
        "▼  Move Down": "▼  Nach unten",
        "🗑  Remove": "🗑  Entfernen",
        "🗑  Remove from Playlist": "🗑  Aus Playlist entfernen",
        # PlaylistContentDialog
        "Library": "Bibliothek",
        "🔍  Search…": "🔍  Suchen…",
        "➕  Add →": "➕  Hinzufügen →",
        "Playlist Contents": "Playlist-Inhalt",
        "▲  Up": "▲  Hoch",
        "▼  Down": "▼  Runter",
        "✂  Remove": "✂  Entfernen",
        "✔  Done": "✔  Fertig",
        # Browser panel
        "Home tooltip": "Startseite (YouTube)",
        "Save folder tooltip": "Speicherordner: {folder}",
        "Mode:": "Modus:",
        "🎬  Video": "🎬  Video",
        "🎵  Audio": "🎵  Audio",
        "Format:": "Format:",
        "Quality:": "Qualität:",
        "⬇  Download": "⬇  Herunterladen",
        "⬇  Download Audio": "⬇  Audio laden",
        "⬇  Download Video": "⬇  Video laden",
        "Download tooltip": "Aktuelles Video / Audio herunterladen",
        "Ready (browser)": "Bereit",
        "Loading…": "Lädt...",
        "Load error": "Fehler beim Laden",
        "No URL title": "Keine URL",
        "No URL msg": "Bitte zuerst eine URL in die Adressleiste eingeben\noder ein YouTube-Video öffnen.",
        "Download running": "Es läuft bereits ein Download.",
        "Download running title": "Download läuft",
        "Audio download starting": "⬇  Audio-Download startet ({fmt}, {qual}K)…",
        "Video download starting": "⬇  Video-Download startet ({fmt}, {qual})…",
        "Saved": "✔  Gespeichert: {name}",
        "Error": "✗  Fehler: {error}",
        "Download done title": "Download abgeschlossen",
        "Download done msg": "Gespeichert:\n{path}",
        "Download failed title": "Download fehlgeschlagen",
        "Download failed msg": "{error}",
        "Pick save folder": "Speicherordner wählen",
        "Save folder set": "Speicherordner: {folder}",
        "URL no webengine": "URL: {url}  (WebEngine nicht verfügbar)",
        # WebEngine fallback
        "WebEngine not installed": (
            "<b>PyQt6-WebEngine nicht installiert oder fehlerhaft</b><br><br>"
            "Um den Medien-Browser zu nutzen, führe diesen Befehl aus:<br><br>"
            "<code>pip install PyQt6-WebEngine</code><br><br>"
            "{error}"
            "Danach Nova neu starten.<br><br>"
            "<small>Falls PyQt6-WebEngine bereits installiert ist, fehlt möglicherweise<br>"
            "ein System-DLL (z.B. Visual C++ Redistributable). Installiere es von:<br>"
            "https://aka.ms/vs/17/release/vc_redist.x64.exe</small>"
        ),
        "📋  Copy Command": "📋  Befehl kopieren",
        # Settings dialog
        "Settings dialog title": "Einstellungen",
        "Appearance": "Aussehen",
        "Playback": "Wiedergabe",
        "Library tab": "Bibliothek",
        "Shortcuts": "Tastenkürzel",
        "Theme:": "Theme:",
        "Font:": "Schrift:",
        "Font Size:": "Schriftgröße:",
        "UI Zoom:": "UI-Zoom:",
        "Show Cover Thumbnails:": "Cover-Vorschau anzeigen:",
        "Compact List Mode:": "Kompakter Listenmodus:",
        "Auto-play Next Song:": "Nächsten Song auto-abspielen:",
        "Crossfade:": "Überblendung:",
        "Default Volume:": "Standardlautstärke:",
        "Auto-extract Embedded Covers:": "Eingebettete Cover extrahieren:",
        "Auto-import Folder:": "Auto-Import-Ordner:",
        "Remember Playback Position:": "Wiedergabeposition merken:",
        "Browse...": "Durchsuchen...",
        "Select Watch Folder": "Ordner auswählen",
        "Language:": "Sprache:",
        "shortcuts_text": (
            "Leertaste    — Abspielen / Pause\n"
            "Links        — 5 Sekunden zurück\n"
            "Rechts       — 5 Sekunden vor\n"
            "Strg+Rechts  — Nächster Song\n"
            "Strg+Links   — Vorheriger Song\n"
            "Strg+Hoch    — Lautstärke erhöhen\n"
            "Strg+Runter  — Lautstärke senken\n"
            "Strg+L       — Wiederholen umschalten\n"
            "Strg+S       — Zufallswiedergabe\n"
            "Strg+F       — Suche fokussieren\n"
            "Strg+I       — Dateien importieren\n"
            "Entf         — Song aus Ansicht entfernen\n"
            "F5           — Bibliothek aktualisieren\n"
        ),
        # Status bar / misc
        "Media Browser status": "Medienbrowser  ·  YouTube, Vimeo, SoundCloud, Twitch, Bandcamp, …",
        "Playlist label": "Playlist",
        "Added to playlist": "Hinzugefügt zu '{name}'",
        "Error duplicate playlist": "Eine Playlist mit diesem Namen existiert bereits.",
        # Fullscreen hint
        "ESC hint": "ESC oder Doppelklick zum Schließen",
        # View titles
        "view_library": "♪  Alle Songs",
        "view_favourites": "♥  Favoriten",
        "view_recently": "🕐  Zuletzt gespielt",
        "view_mostplayed": "🔥  Meist gespielt",
        "view_videos": "🎬  Videos",
        "view_ytbrowser": "🌐  Medienbrowser",
        "Search placeholder": "⌕  Songs, Künstler, Alben suchen...",
        # Import tooltips
        "Audio import tooltip": "Audio von YouTube, SoundCloud u.v.m. via yt-dlp importieren",
        "Video import tooltip": "Video herunterladen (mp4, mkv, gif, webm, mov, avi) via yt-dlp",
        "Convert tooltip": "Audio ↔ Video konvertieren mit ffmpeg",
        # Discord Rich Presence
        "Discord RPC:": "Discord Rich Presence:",
        "discord_rpc_tooltip": "Aktuellen Song im Discord-Status anzeigen",
    },
}

# Active language — will be overwritten at startup from DB
_LANG = "en"

def tr(key, **kwargs):
    """Translate key into the current language, with optional format kwargs."""
    text = _TRANSLATIONS.get(_LANG, _TRANSLATIONS["en"]).get(key)
    if text is None:
        text = _TRANSLATIONS["en"].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text

def set_language(lang: str):
    """Switch the active language (call before building any UI)."""
    global _LANG
    if lang in _TRANSLATIONS:
        _LANG = lang

# ──────────────────────────── VIDEO CONTROLS OVERLAY ─────────────────────────
class VideoControlsOverlay(QFrame):
    """
    Overlay das den gesamten VLC-Frame abdeckt.

    - Oberer Bereich: vollständig transparent, Mausklick togglet die
      sichtbare Controls-Leiste unten.
    - Unterer Bereich (CONTROLS_H px): halbtransparente Leiste mit
      Seek-Slider, Buttons, Lautstärke.

    Durch die volle Ausdehnung fängt dieses Qt-Widget alle Mausereignisse
    ab, die VLC sonst "schlucken" würde (VLC übernimmt den nativen HWND
    des parent_frame — Children wie dieses Widget werden von Qt aber
    trotzdem über VLC gerendert und erhalten Events).
    """
    AUTO_HIDE_MS  = 3000
    FIRST_SHOW_MS = 5000
    CONTROLS_H    = 74

    def __init__(self, parent_frame: QFrame, player_ref):
        super().__init__(parent_frame)
        self._player = player_ref
        self._is_slider_dragging = False
        self._controls_visible = False

        self.setObjectName("vid_overlay")
        # Kein eigener Hintergrund auf dem äußeren Frame — wird im paintEvent gemacht
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        # ── Inneres Container-Widget für die Controls-Leiste ──────────────
        self._bar = QFrame(self)
        self._bar.setObjectName("vid_bar")
        self._bar.setStyleSheet(
            "QFrame#vid_bar {"
            "  background: qlineargradient("
            "    x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,210)"
            "  );"
            "  border: none;"
            "}"
            "QSlider::groove:horizontal {"
            "  background: rgba(255,255,255,40); height: 4px; border-radius: 2px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: rgba(255,255,255,200); border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "  background: white; width: 12px; height: 12px;"
            "  margin: -4px 0; border-radius: 6px;"
            "}"
            "QPushButton {"
            "  background: transparent; border: none;"
            "  color: white; font-size: 16px; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: rgba(255,255,255,30); }"
            "QLabel { color: rgba(255,255,255,200); font-size: 11px;"
            "  background: transparent; border: none; }"
        )

        # ── Layout der Controls-Leiste ────────────────────────────────────
        root = QVBoxLayout(self._bar)
        root.setContentsMargins(14, 8, 14, 10)
        root.setSpacing(4)

        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setFixedHeight(18)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)

        def _seek_click(e):
            if e.button() == Qt.MouseButton.LeftButton and self.seek_slider.maximum() > 0:
                val = int(e.position().x() / self.seek_slider.width() * self.seek_slider.maximum())
                self.seek_slider.setValue(val)
                self._player.player.set_time(val)
                self._player.progress_slider.setValue(val)
                self._player.bb_progress.setValue(val)
            QSlider.mousePressEvent(self.seek_slider, e)
        self.seek_slider.mousePressEvent = _seek_click
        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setFixedWidth(90)
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self.seek_slider, 1)
        seek_row.addWidget(self.time_lbl)
        root.addLayout(seek_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        def _btn(icon, size=28):
            b = QPushButton(icon)
            b.setFixedSize(size, size)
            return b

        self.shuffle_btn = _btn("⇄")
        self.prev_btn    = _btn("⏮")
        self.play_btn    = _btn("▶", 34)
        self.next_btn    = _btn("⏭")
        self.loop_btn    = _btn("↻")

        self.vol_icon = QLabel("🔈")
        self.vol_icon.setFixedWidth(20)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setFixedHeight(18)
        self.vol_slider.setValue(80)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        self.close_fs_btn = _btn("⛶", 28)
        self.close_fs_btn.setToolTip("Vollbild schließen")
        self.close_fs_btn.clicked.connect(self._on_close_fs)

        for w in [self.shuffle_btn, self.prev_btn, self.play_btn,
                  self.next_btn, self.loop_btn]:
            btn_row.addWidget(w)
        btn_row.addStretch()
        btn_row.addWidget(self.vol_icon)
        btn_row.addWidget(self.vol_slider)
        btn_row.addSpacing(12)
        btn_row.addWidget(self.close_fs_btn)
        root.addLayout(btn_row)

        self.shuffle_btn.clicked.connect(self._player.toggle_shuffle)
        self.prev_btn.clicked.connect(self._player.play_previous)
        self.play_btn.clicked.connect(self._player.toggle_play_pause)
        self.next_btn.clicked.connect(self._player.play_next)
        self.loop_btn.clicked.connect(self._player.toggle_loop)

        # ── Auto-hide: poll cursor position every 500 ms ─────────────────
        # mouseMoveEvent on the Tool-Window isn't reliable because VLC owns
        # the native HWND and swallows mouse events. Instead we poll
        # QCursor.pos() and show/hide based on movement + position.
        self._last_cursor = QPoint(-1, -1)
        self._idle_ms = 0
        self._was_clicked = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_cursor)
        self._poll_timer.start()

        self._bar.hide()

    def _poll_cursor(self):
        from PyQt6.QtGui import QCursor
        frame = getattr(self._player, "_vid_controls_frame", None)
        if frame is None:
            return

        # Hauptfenster oder Tool-Window selbst aktiv → weitermachen
        # Sonst (anderes Fenster vorne / minimiert) → sofort verstecken
        main_active = self._player.isActiveWindow() or self.isActiveWindow()
        minimized = self._player.isMinimized()
        if not main_active or minimized:
            if self.isVisible():
                self.hide()
                self._hide_bar()
            return

        # Hauptfenster ist aktiv → Tool-Window sichtbar halten
        if not self.isVisible():
            gp = frame.mapToGlobal(QPoint(0, 0))
            self.setGeometry(gp.x(), gp.y(), frame.width(), frame.height())
            self._bar.setGeometry(0, frame.height() - self.CONTROLS_H,
                                  frame.width(), self.CONTROLS_H)
            self.show()
            self.raise_()

        pos = QCursor.pos()
        gp = frame.mapToGlobal(QPoint(0, 0))
        over_frame = (gp.x() <= pos.x() <= gp.x() + frame.width() and
                      gp.y() <= pos.y() <= gp.y() + frame.height())

        if not over_frame:
            self._idle_ms += 500
            if self._idle_ms >= self.AUTO_HIDE_MS:
                self._hide_bar()
            return

        # Cursor über der Controls-Bar oder Slider wird gezogen → nie verstecken
        bar_top = gp.y() + frame.height() - self.CONTROLS_H
        over_bar = pos.y() >= bar_top
        if over_bar or self._is_slider_dragging:
            self._idle_ms = 0
            self._show_bar()
            self._last_cursor = pos
            return

        # Mausklick im Video-Bereich → Bar einblenden
        clicked = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if clicked and not self._was_clicked:
            self._idle_ms = 0
            self._show_bar()
        self._was_clicked = clicked

        self._last_cursor = pos
        if not clicked:
            self._idle_ms += 500
            if self._idle_ms >= self.AUTO_HIDE_MS:
                self._hide_bar()

    # ── Bar visibility ────────────────────────────────────────────────────
    def _hide_bar(self):
        self._bar.hide()
        self._controls_visible = False

    def _show_bar(self):
        self._bar.show()
        self._bar.raise_()
        self._controls_visible = True

    # ── Public API ────────────────────────────────────────────────────────
    def show_and_reset(self, first_time: bool = False):
        self._idle_ms = 0
        self._show_bar()

    def toggle(self):
        if self._controls_visible:
            self._idle_ms = self.AUTO_HIDE_MS  # force hide on next poll
            self._hide_bar()
        else:
            self.show_and_reset()

    def sync_progress(self, current_ms: int, length_ms: int):
        if length_ms > 0 and not self._is_slider_dragging:
            self.seek_slider.setMaximum(length_ms)
            self.seek_slider.setValue(current_ms)
            self.time_lbl.setText(
                f"{format_duration(current_ms)} / {format_duration(length_ms)}"
            )

    def sync_play_state(self, is_playing: bool):
        self.play_btn.setText("⏸" if is_playing else "▶")

    def sync_volume(self, value: int):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(value)
        self.vol_slider.blockSignals(False)

    def sync_loop(self, enabled: bool, accent: str, subtext: str, highlight: str):
        if enabled:
            self.loop_btn.setStyleSheet(
                f"QPushButton {{ background: {accent}33; color: {accent};"
                f"  border-radius: 4px; font-size: 16px; }}"
            )
        else:
            self.loop_btn.setStyleSheet("")

    def sync_shuffle(self, enabled: bool, accent: str, subtext: str, highlight: str):
        if enabled:
            self.shuffle_btn.setStyleSheet(
                f"QPushButton {{ background: {accent}33; color: {accent};"
                f"  border-radius: 4px; font-size: 16px; }}"
            )
        else:
            self.shuffle_btn.setStyleSheet("")

    def reposition(self, frame_w: int, frame_h: int):
        """Overlay auf gesamten Frame ausdehnen, Leiste unten positionieren."""
        frame = getattr(self._player, "_vid_controls_frame", None)
        if frame is not None and self.parent() is None:
            # Tool-Window: globale Bildschirmposition
            gp = frame.mapToGlobal(QPoint(0, 0))
            self.setGeometry(gp.x(), gp.y(), frame_w, frame_h)
        else:
            self.setGeometry(0, 0, frame_w, frame_h)
        self._bar.setGeometry(0, frame_h - self.CONTROLS_H, frame_w, self.CONTROLS_H)

    # ── Maus-Events ───────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        self._idle_ms = 0
        self._show_bar()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._idle_ms = 0
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        self.show_and_reset()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        pass  # transparent — _bar zeichnet sich selbst

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self._on_close_fs()
        elif k == Qt.Key.Key_Space:
            self._player.toggle_play_pause()
        elif k == Qt.Key.Key_Left:
            self._player._seek_relative(-5000)
        elif k == Qt.Key.Key_Right:
            self._player._seek_relative(5000)
        else:
            super().keyPressEvent(event)

    # ── Interne Slots ────────────────────────────────────────────────────
    def _on_seek_pressed(self):
        self._is_slider_dragging = True
        self._player.is_slider_pressed = True
        self._idle_ms = 0  # keep bar visible while dragging

    def _on_seek_released(self):
        self._is_slider_dragging = False
        self._player.is_slider_pressed = False
        self._player.player.set_time(self.seek_slider.value())
        self._player.progress_slider.setValue(self.seek_slider.value())
        self._player.bb_progress.setValue(self.seek_slider.value())
        self._idle_ms = 0

    def _on_volume_changed(self, value: int):
        self._player.change_volume(value)

    def _on_close_fs(self):
        if self._player._fs_win:
            self._player._close_video_fullscreen()
        elif getattr(self._player, "_popout_win", None) is not None:
            self._player._close_popout_window()


THEMES = {
    "Midnight": {
        "bg": "#0d1117", "sidebar": "#0b0f14", "panel": "#09090f",
        "card": "#161b22", "accent": "#1f6feb", "accent2": "#388bfd",
        "text": "#e6edf3", "subtext": "#8b949e", "border": "#1f2937",
        "green": "#1DB954", "red": "#f85149", "highlight": "#1f6feb33",
    },
    "Sunset": {
        "bg": "#1a0a00", "sidebar": "#150800", "panel": "#0f0500",
        "card": "#2a1200", "accent": "#ff6b35", "accent2": "#ff8c5a",
        "text": "#fff0e6", "subtext": "#cc8866", "border": "#3d1f00",
        "green": "#ff6b35", "red": "#ff3355", "highlight": "#ff6b3533",
    },
    "Forest": {
        "bg": "#0a120a", "sidebar": "#080e08", "panel": "#060a06",
        "card": "#111811", "accent": "#2ea043", "accent2": "#3fb950",
        "text": "#e6f0e6", "subtext": "#6e9f6e", "border": "#1a2e1a",
        "green": "#2ea043", "red": "#f85149", "highlight": "#2ea04333",
    },
    "Ocean": {
        "bg": "#040d1a", "sidebar": "#030b16", "panel": "#020810",
        "card": "#0a1628", "accent": "#0ea5e9", "accent2": "#38bdf8",
        "text": "#e0f2fe", "subtext": "#7cb9e8", "border": "#0f2744",
        "green": "#0ea5e9", "red": "#f43f5e", "highlight": "#0ea5e933",
    },
    "Rose": {
        "bg": "#1a0010", "sidebar": "#15000c", "panel": "#0f0008",
        "card": "#280018", "accent": "#e11d73", "accent2": "#f43f5e",
        "text": "#ffe4f0", "subtext": "#cc6699", "border": "#3d0020",
        "green": "#e11d73", "red": "#f43f5e", "highlight": "#e11d7333",
    },
    "Amoled": {
        "bg": "#000000", "sidebar": "#080808", "panel": "#000000",
        "card": "#111111", "accent": "#bb86fc", "accent2": "#ce93d8",
        "text": "#ffffff", "subtext": "#aaaaaa", "border": "#222222",
        "green": "#03dac6", "red": "#cf6679", "highlight": "#bb86fc33",
    },
    "Dracula": {
        "bg": "#282a36", "sidebar": "#21222c", "panel": "#1e1f29",
        "card": "#313244", "accent": "#bd93f9", "accent2": "#caa9fa",
        "text": "#f8f8f2", "subtext": "#6272a4", "border": "#44475a",
        "green": "#50fa7b", "red": "#ff5555", "highlight": "#bd93f933",
    },
    "Nord": {
        "bg": "#2e3440", "sidebar": "#272c36", "panel": "#242933",
        "card": "#3b4252", "accent": "#88c0d0", "accent2": "#81a1c1",
        "text": "#eceff4", "subtext": "#616e88", "border": "#434c5e",
        "green": "#a3be8c", "red": "#bf616a", "highlight": "#88c0d033",
    },
    "Catppuccin": {
        "bg": "#1e1e2e", "sidebar": "#181825", "panel": "#11111b",
        "card": "#313244", "accent": "#cba6f7", "accent2": "#b4befe",
        "text": "#cdd6f4", "subtext": "#6c7086", "border": "#45475a",
        "green": "#a6e3a1", "red": "#f38ba8", "highlight": "#cba6f733",
    },
    "Solarized": {
        "bg": "#002b36", "sidebar": "#00212b", "panel": "#001a22",
        "card": "#073642", "accent": "#268bd2", "accent2": "#2aa198",
        "text": "#839496", "subtext": "#586e75", "border": "#0d414e",
        "green": "#859900", "red": "#dc322f", "highlight": "#268bd233",
    },
    "Light": {
        "bg": "#f6f8fa", "sidebar": "#eaeef2", "panel": "#f0f2f5",
        "card": "#ffffff", "accent": "#0969da", "accent2": "#218bff",
        "text": "#1f2328", "subtext": "#57606a", "border": "#d0d7de",
        "green": "#1a7f37", "red": "#d1242f", "highlight": "#0969da22",
    },
    "Warm Sepia": {
        "bg": "#1c1510", "sidebar": "#16110c", "panel": "#120e0a",
        "card": "#261d15", "accent": "#d4a657", "accent2": "#e8c175",
        "text": "#f0e4cc", "subtext": "#9a7d5a", "border": "#3d2e1e",
        "green": "#7dba4e", "red": "#e05c4a", "highlight": "#d4a65733",
    },
    "Monochrome": {
        "bg": "#1a1a1a", "sidebar": "#141414", "panel": "#111111",
        "card": "#242424", "accent": "#888888", "accent2": "#aaaaaa",
        "text": "#e8e8e8", "subtext": "#888888", "border": "#333333",
        "green": "#999999", "red": "#bbbbbb", "highlight": "#88888822",
    },
    "Liquid Glass": {
        # Translucent light-on-dark frosted glass palette
        # bg/sidebar/panel are near-black so Qt solid widgets look right;
        # the glass effect is applied via the custom stylesheet below.
        "bg":       "#0c0c10",
        "sidebar":  "#10101a",
        "panel":    "#08080e",
        "card":     "#1a1a2a",
        "accent":   "#a0c4ff",
        "accent2":  "#c8b8ff",
        "text":     "#eef2ff",
        "subtext":  "#8892b0",
        "border":   "#ffffff18",
        "green":    "#64ffda",
        "red":      "#ff6b9d",
        "highlight":"#a0c4ff22",
        # Flag so apply_theme can detect this special theme
        "_liquid_glass": True,
    },
}

FONTS = [
    # ── Sans-Serif ──────────────────────────────────────────────────────────
    "Arial", "Arial Black", "Arial Narrow",
    "Segoe UI", "Segoe UI Light", "Segoe UI Semibold",
    "Helvetica", "Helvetica Neue",
    "Verdana", "Tahoma", "Trebuchet MS",
    "Calibri", "Candara", "Optima",
    "Roboto", "Roboto Light", "Roboto Condensed",
    "Open Sans", "Open Sans Light", "Open Sans Condensed",
    "Inter", "Inter Tight",
    "Lato", "Lato Light",
    "Nunito", "Nunito Light",
    "Poppins", "Poppins Light",
    "Raleway", "Raleway Light",
    "Ubuntu", "Ubuntu Light", "Ubuntu Condensed",
    "Noto Sans", "Noto Sans Light",
    "Source Sans Pro", "Source Sans 3",
    "Franklin Gothic Medium", "Century Gothic",
    "Gill Sans", "Gill Sans MT",
    # ── Serif ────────────────────────────────────────────────────────────────
    "Georgia", "Palatino Linotype", "Book Antiqua",
    "Times New Roman", "Garamond", "Garamond Premier Pro",
    "Merriweather", "Playfair Display",
    "Lora", "EB Garamond",
    "Cambria", "Constantia", "Cochin",
    "Noto Serif",
    # ── Monospace ────────────────────────────────────────────────────────────
    "Courier New", "Courier",
    "Consolas", "Lucida Console", "Lucida Sans Typewriter",
    "Monospace",
    "Cascadia Code", "Cascadia Mono",
    "Fira Code", "Fira Mono",
    "JetBrains Mono", "JetBrains Mono NL",
    "Source Code Pro", "Hack",
    "Inconsolata", "Anonymous Pro",
    "IBM Plex Mono", "IBM Plex Sans",
    # ── Display / Special ────────────────────────────────────────────────────
    "Impact", "Haettenschweiler",
    "Bahnschrift", "Bahnschrift Light", "Bahnschrift Condensed",
    "Exo 2", "Exo 2 Light",
    "Orbitron",
    "Oxanium",
    "Space Grotesk",
    "DM Sans", "DM Mono",
    "Quicksand", "Varela Round",
    # ── System Fallback ──────────────────────────────────────────────────────
    "MS UI Gothic", "Yu Gothic", "Meiryo",
    "Apple SD Gothic Neo", "SF Pro Display",
    "System Font",
]

ZOOM_LEVELS = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 150]


def _pm_b64decode(raw: str) -> bytes:
    """Decode url-safe base64 written by PasswordVault (adds missing padding)."""
    if not raw:
        return b""
    s = raw.strip()
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))


class MusicDatabase:
    def __init__(self, db_name="nova_library.db"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, db_name)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                channel TEXT,
                path TEXT UNIQUE,
                thumbnail_path TEXT,
                duration INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                format TEXT,
                resolution TEXT,
                date_added TEXT
            );

            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cover_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                path TEXT UNIQUE,
                duration INTEGER DEFAULT 0,
                play_count INTEGER DEFAULT 0,
                last_played TEXT,
                date_added TEXT,
                favourite INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                created_at TEXT,
                cover_path TEXT
            );

            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER,
                song_id INTEGER,
                position INTEGER,
                added_at TEXT,
                PRIMARY KEY (playlist_id, song_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER,
                played_at TEXT,
                FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        cols = [r[1] for r in self.cursor.execute("PRAGMA table_info(songs)").fetchall()]
        needed = {"duration": "INTEGER DEFAULT 0", "play_count": "INTEGER DEFAULT 0",
                  "last_played": "TEXT", "date_added": "TEXT",
                  "favourite": "INTEGER DEFAULT 0", "rating": "INTEGER DEFAULT 0",
                  "cover_path": "TEXT", "yt_url": "TEXT", "lyrics": "TEXT"}
        for col, typedef in needed.items():
            if col not in cols:
                self.cursor.execute(f"ALTER TABLE songs ADD COLUMN {col} {typedef}")
        # Migrate videos table: add yt_url and lyrics columns if missing
        vcols = [r[1] for r in self.cursor.execute("PRAGMA table_info(videos)").fetchall()]
        for col, typedef in [("yt_url", "TEXT"), ("lyrics", "TEXT")]:
            if col not in vcols:
                self.cursor.execute(f"ALTER TABLE videos ADD COLUMN {col} {typedef}")
        # Add playlist_videos table for video-in-playlist support
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_videos (
                playlist_id INTEGER,
                video_id INTEGER,
                position INTEGER,
                added_at TEXT,
                PRIMARY KEY (playlist_id, video_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

        # Password manager vault
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                username TEXT DEFAULT '',
                url TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                password_enc TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    # --- Password Manager ---
    def pm_is_initialized(self):
        return self.pm_vault_status() == "ok"

    def pm_vault_status(self):
        """Return 'unset', 'ok', or 'corrupt'."""
        salt_raw = self.get_setting("pm_salt", "")
        verifier = self.get_setting("pm_verifier", "")
        if not salt_raw or not verifier:
            return "unset"
        try:
            salt = _pm_b64decode(salt_raw)
            if len(salt) < 8:
                return "corrupt"
            return "ok"
        except Exception:
            return "corrupt"

    def pm_init(self, salt_b64, verifier):
        self.set_setting("pm_salt", salt_b64)
        self.set_setting("pm_verifier", verifier)

    def pm_get_salt(self):
        raw = self.get_setting("pm_salt", "")
        return _pm_b64decode(raw) if raw else b""

    def pm_reset_vault(self):
        self.cursor.execute("DELETE FROM password_entries")
        self.cursor.execute("DELETE FROM settings WHERE key IN ('pm_salt', 'pm_verifier')")
        self.conn.commit()

    def pm_get_verifier(self):
        return self.get_setting("pm_verifier", "")

    def pm_add_entry(self, title, username, url, notes, password_enc):
        now = datetime.now().isoformat()
        self.cursor.execute(
            "INSERT INTO password_entries(title,username,url,notes,password_enc,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (title, username or "", url or "", notes or "", password_enc, now, now),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def pm_update_entry(self, entry_id, title, username, url, notes, password_enc):
        now = datetime.now().isoformat()
        self.cursor.execute(
            "UPDATE password_entries SET title=?,username=?,url=?,notes=?,password_enc=?,updated_at=? WHERE id=?",
            (title, username or "", url or "", notes or "", password_enc, now, entry_id),
        )
        self.conn.commit()

    def pm_delete_entry(self, entry_id):
        self.cursor.execute("DELETE FROM password_entries WHERE id=?", (entry_id,))
        self.conn.commit()

    def pm_get_entries(self, search=""):
        q = ("SELECT id,title,username,url,notes,password_enc,created_at,updated_at "
             "FROM password_entries")
        if search:
            p = f"%{search}%"
            return self.cursor.execute(
                q + " WHERE title LIKE ? OR username LIKE ? OR url LIKE ? OR notes LIKE ? "
                    "ORDER BY title COLLATE NOCASE",
                (p, p, p, p),
            ).fetchall()
        return self.cursor.execute(q + " ORDER BY title COLLATE NOCASE").fetchall()

    def pm_get_entry(self, entry_id):
        return self.cursor.execute(
            "SELECT id,title,username,url,notes,password_enc,created_at,updated_at "
            "FROM password_entries WHERE id=?",
            (entry_id,),
        ).fetchone()

    # --- Songs ---
    def add_song(self, title, artist, album, path, cover_path=None, duration=0, yt_url=None):
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO songs(title,artist,album,path,cover_path,duration,date_added,yt_url) VALUES(?,?,?,?,?,?,?,?)",
                (title, artist, album, path, cover_path, duration, datetime.now().isoformat(), yt_url),
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def set_yt_url(self, song_id, yt_url):
        self.cursor.execute("UPDATE songs SET yt_url=? WHERE id=?", (yt_url, song_id))
        self.conn.commit()

    def get_yt_url(self, song_id):
        row = self.cursor.execute("SELECT yt_url FROM songs WHERE id=?", (song_id,)).fetchone()
        return row[0] if row else None

    def get_all_songs(self, search=""):
        q = "SELECT id,title,artist,album,path,cover_path,duration,favourite,rating,play_count FROM songs"
        if search:
            q += f" WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?"
            rows = self.cursor.execute(q, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
        else:
            rows = self.cursor.execute(q + " ORDER BY artist,title").fetchall()
        return rows

    def get_song_by_path(self, path):
        return self.cursor.execute(
            "SELECT id,title,artist,album,path,cover_path,duration,favourite,rating,play_count FROM songs WHERE path=?", (path,)
        ).fetchone()

    def toggle_favourite(self, song_id):
        self.cursor.execute("UPDATE songs SET favourite = 1 - favourite WHERE id=?", (song_id,))
        self.conn.commit()
        return self.cursor.execute("SELECT favourite FROM songs WHERE id=?", (song_id,)).fetchone()[0]

    def set_rating(self, song_id, rating):
        self.cursor.execute("UPDATE songs SET rating=? WHERE id=?", (rating, song_id))
        self.conn.commit()

    def increment_play_count(self, song_id):
        self.cursor.execute(
            "UPDATE songs SET play_count=play_count+1, last_played=? WHERE id=?",
            (datetime.now().isoformat(), song_id)
        )
        self.cursor.execute(
            "INSERT INTO play_history(song_id,played_at) VALUES(?,?)",
            (song_id, datetime.now().isoformat())
        )
        self.conn.commit()

    def delete_song(self, song_id):
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.cursor.execute("DELETE FROM play_history WHERE song_id=?", (song_id,))
        self.cursor.execute("DELETE FROM playlist_songs WHERE song_id=?", (song_id,))
        self.cursor.execute("DELETE FROM songs WHERE id=?", (song_id,))
        self.conn.commit()

    def get_favourites(self):
        return self.cursor.execute(
            "SELECT id,title,artist,album,path,cover_path,duration,favourite,rating,play_count FROM songs WHERE favourite=1 ORDER BY artist,title"
        ).fetchall()

    def get_recently_played(self, limit=50):
        return self.cursor.execute(
            """SELECT DISTINCT s.id,s.title,s.artist,s.album,s.path,s.cover_path,s.duration,s.favourite,s.rating,s.play_count
               FROM songs s JOIN play_history h ON s.id=h.song_id
               ORDER BY h.played_at DESC LIMIT ?""", (limit,)
        ).fetchall()

    def get_most_played(self, limit=50):
        return self.cursor.execute(
            "SELECT id,title,artist,album,path,cover_path,duration,favourite,rating,play_count FROM songs ORDER BY play_count DESC LIMIT ?", (limit,)
        ).fetchall()

    # --- Playlists ---
    def create_playlist(self, name, description=""):
        try:
            self.cursor.execute(
                "INSERT INTO playlists(name,description,created_at) VALUES(?,?,?)",
                (name, description, datetime.now().isoformat())
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(e)
            return None

    def get_all_playlists(self):
        return self.cursor.execute("SELECT id,name,description,created_at,cover_path FROM playlists ORDER BY name").fetchall()

    def get_playlist(self, playlist_id):
        return self.cursor.execute("SELECT id,name,description,created_at,cover_path FROM playlists WHERE id=?", (playlist_id,)).fetchone()

    def rename_playlist(self, playlist_id, new_name):
        self.cursor.execute("UPDATE playlists SET name=? WHERE id=?", (new_name, playlist_id))
        self.conn.commit()

    def update_playlist(self, playlist_id, name, description, cover_path=None):
        self.cursor.execute(
            "UPDATE playlists SET name=?, description=?, cover_path=? WHERE id=?",
            (name, description, cover_path, playlist_id)
        )
        self.conn.commit()

    def delete_playlist(self, playlist_id):
        self.cursor.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
        self.conn.commit()

    def reorder_playlist_songs(self, playlist_id, ordered_song_ids):
        """Update position for each song_id in playlist."""
        for pos, sid in enumerate(ordered_song_ids):
            self.cursor.execute(
                "UPDATE playlist_songs SET position=? WHERE playlist_id=? AND song_id=?",
                (pos, playlist_id, sid)
            )
        self.conn.commit()

    # --- Video playlists ---
    def add_video_to_playlist(self, playlist_id, video_id):
        pos = self.cursor.execute(
            "SELECT COUNT(*) FROM playlist_videos WHERE playlist_id=?", (playlist_id,)
        ).fetchone()[0]
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO playlist_videos(playlist_id,video_id,position,added_at) VALUES(?,?,?,?)",
                (playlist_id, video_id, pos, datetime.now().isoformat())
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def remove_video_from_playlist(self, playlist_id, video_id):
        self.cursor.execute(
            "DELETE FROM playlist_videos WHERE playlist_id=? AND video_id=?",
            (playlist_id, video_id)
        )
        self.conn.commit()

    def video_in_playlist(self, playlist_id, video_id):
        return bool(self.cursor.execute(
            "SELECT 1 FROM playlist_videos WHERE playlist_id=? AND video_id=?",
            (playlist_id, video_id)
        ).fetchone())

    def get_playlist_videos(self, playlist_id):
        return self.cursor.execute(
            """SELECT v.id,v.title,v.channel,v.path,v.thumbnail_path,v.duration,v.file_size,v.format,v.resolution
               FROM videos v JOIN playlist_videos pv ON v.id=pv.video_id
               WHERE pv.playlist_id=? ORDER BY pv.position,pv.added_at""",
            (playlist_id,)
        ).fetchall()

    def add_song_to_playlist(self, playlist_id, song_id):
        pos = (self.cursor.execute("SELECT COUNT(*) FROM playlist_songs WHERE playlist_id=?", (playlist_id,)).fetchone()[0])
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO playlist_songs(playlist_id,song_id,position,added_at) VALUES(?,?,?,?)",
                (playlist_id, song_id, pos, datetime.now().isoformat())
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def remove_song_from_playlist(self, playlist_id, song_id):
        self.cursor.execute("DELETE FROM playlist_songs WHERE playlist_id=? AND song_id=?", (playlist_id, song_id))
        self.conn.commit()

    def get_playlist_songs(self, playlist_id):
        return self.cursor.execute(
            """SELECT s.id,s.title,s.artist,s.album,s.path,s.cover_path,s.duration,s.favourite,s.rating,s.play_count
               FROM songs s JOIN playlist_songs ps ON s.id=ps.song_id
               WHERE ps.playlist_id=? ORDER BY ps.position,ps.added_at""",
            (playlist_id,)
        ).fetchall()

    def song_in_playlist(self, playlist_id, song_id):
        return bool(self.cursor.execute(
            "SELECT 1 FROM playlist_songs WHERE playlist_id=? AND song_id=?", (playlist_id, song_id)
        ).fetchone())

    # --- Settings ---
    def get_setting(self, key, default=None):
        row = self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
        self.conn.commit()

    # --- Videos ---
    def add_video(self, title, channel, path, thumbnail_path=None, duration=0, file_size=0, fmt="", resolution="", yt_url=None):
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO videos(title,channel,path,thumbnail_path,duration,file_size,format,resolution,date_added,yt_url) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (title, channel, path, thumbnail_path, duration, file_size, fmt, resolution, datetime.now().isoformat(), yt_url),
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def get_all_videos(self, search=""):
        q = "SELECT id,title,channel,path,thumbnail_path,duration,file_size,format,resolution FROM videos"
        if search:
            q += " WHERE title LIKE ? OR channel LIKE ?"
            rows = self.cursor.execute(q, (f"%{search}%", f"%{search}%")).fetchall()
        else:
            rows = self.cursor.execute(q + " ORDER BY date_added DESC").fetchall()
        return rows

    def get_video_by_path(self, path):
        return self.cursor.execute(
            "SELECT id,title,channel,path,thumbnail_path,duration,file_size,format,resolution,yt_url FROM videos WHERE path=?", (path,)
        ).fetchone()

    def get_video_yt_url(self, video_id):
        row = self.cursor.execute("SELECT yt_url FROM videos WHERE id=?", (video_id,)).fetchone()
        return row[0] if row else None

    def set_video_yt_url(self, video_id, yt_url):
        self.cursor.execute("UPDATE videos SET yt_url=? WHERE id=?", (yt_url, video_id))
        self.conn.commit()

    def delete_video(self, video_id):
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.cursor.execute("DELETE FROM playlist_videos WHERE video_id=?", (video_id,))
        self.cursor.execute("DELETE FROM videos WHERE id=?", (video_id,))
        self.conn.commit()

    def update_video(self, video_id, title, channel, yt_url=None):
        self.cursor.execute(
            "UPDATE videos SET title=?, channel=?, yt_url=? WHERE id=?",
            (title, channel, yt_url, video_id)
        )
        self.conn.commit()


def format_duration(ms):
    if not ms or ms <= 0:
        return "0:00"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def extract_cover_from_audio(path):
    """Extract embedded cover art, save to temp file, return path."""
    try:
        ext = Path(path).suffix.lower()
        out_path = os.path.join(os.path.dirname(path), ".nova_covers")
        os.makedirs(out_path, exist_ok=True)
        cover_file = os.path.join(out_path, Path(path).stem + "_cover.jpg")

        if ext == ".mp3":
            tags = ID3(path)
            for tag in tags.values():
                if isinstance(tag, APIC):
                    with open(cover_file, "wb") as f:
                        f.write(tag.data)
                    return cover_file
        elif ext == ".flac":
            audio = FLAC(path)
            if audio.pictures:
                with open(cover_file, "wb") as f:
                    f.write(audio.pictures[0].data)
                return cover_file
        elif ext == ".m4a":
            audio = MP4(path)
            covr = audio.tags.get("covr", [])
            if covr:
                with open(cover_file, "wb") as f:
                    f.write(bytes(covr[0]))
                return cover_file
    except Exception:
        pass
    return None


# ──────────────────────────── FFMPEG HELPER ────────────────────────────

def _get_ffmpeg_dir(python_executable, progress_signal=None):
    """
    Return a directory containing an executable named 'ffmpeg'.
    Checks (in order):
      1. System PATH
      2. imageio-ffmpeg package (copies/symlinks under a stable temp dir)
    Returns None if ffmpeg cannot be located.
    """
    # 1. Check system PATH first
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        if progress_signal:
            progress_signal.emit(f"Using system ffmpeg: {ffmpeg_in_path}")
        return os.path.dirname(ffmpeg_in_path)

    # 2. Try imageio-ffmpeg
    try:
        result = subprocess.run(
            [python_executable, "-c",
             "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            real_path = result.stdout.strip()
            if real_path and os.path.exists(real_path):
                staging_dir = os.path.join(
                    tempfile.gettempdir(), "nova_ffmpeg_shim"
                )
                os.makedirs(staging_dir, exist_ok=True)
                ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
                dest = os.path.join(staging_dir, ffmpeg_name)

                if not os.path.exists(dest):
                    if sys.platform == "win32":
                        shutil.copy2(real_path, dest)
                    else:
                        try:
                            os.symlink(real_path, dest)
                        except OSError:
                            shutil.copy2(real_path, dest)

                if progress_signal:
                    progress_signal.emit(f"Using imageio-ffmpeg: {real_path}")
                return staging_dir
    except Exception as e:
        if progress_signal:
            progress_signal.emit(f"imageio-ffmpeg probe failed: {e}")

    return None


# ──────────────────────────── CHROME EXTENSION API ────────────────────────────

NOVA_EXT_API_PORT = 8765


def nova_extension_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "NovaYtdlpExtension")


class _NovaExtApiHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP API for the Nova yt-dlp Chrome extension."""

    nova_ref = None

    def log_message(self, _format, *_args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/ping":
            self._send_json(200, {"ok": True, "app": "NovaX7", "version": 1})
            return
        if path == "/status":
            nova = self.nova_ref
            st = getattr(nova, "_ext_last_status", {"state": "idle"}) if nova else {"state": "offline"}
            self._send_json(200, st)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/download":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "invalid json"})
            return
        nova = self.nova_ref
        if not nova:
            self._send_json(503, {"error": "Nova not ready"})
            return
        url = (data.get("url") or "").strip()
        if not url.startswith("http"):
            self._send_json(400, {"error": "invalid url"})
            return
        nova.queue_extension_download(data)
        self._send_json(200, {"ok": True, "queued": True, "url": url})


class NovaExtensionServer(threading.Thread):
    """Background thread serving the Chrome extension on 127.0.0.1."""

    def __init__(self, nova, port=NOVA_EXT_API_PORT):
        super().__init__(daemon=True)
        self.nova = nova
        self.port = port
        self._httpd = None

    def run(self):
        _NovaExtApiHandler.nova_ref = self.nova
        try:
            self._httpd = http.server.HTTPServer(("127.0.0.1", self.port), _NovaExtApiHandler)
            print(f"[Nova] Chrome extension API listening on http://127.0.0.1:{self.port}")
            self._httpd.serve_forever()
        except OSError as e:
            print(f"[Nova] Extension API port {self.port} unavailable: {e}")

    def stop(self):
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass


# ──────────────────────────── YT-DLP DOWNLOAD THREAD ────────────────────────────

class YtdlpDownloadThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, str)  # success, filepath, error_msg

    def __init__(self, url, output_dir, audio_format="mp3", quality="192"):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.audio_format = audio_format
        self.quality = quality

    def run(self):
        try:
            python = sys.executable

            # Quick availability check
            check = subprocess.run(
                [python, "-m", "yt_dlp", "--version"],
                capture_output=True, text=True
            )
            if check.returncode != 0:
                self.finished_signal.emit(
                    False, "",
                    "yt-dlp is not installed in this Python environment.\n"
                    f"Run:  {python} -m pip install yt-dlp"
                )
                return

            self.progress_signal.emit(f"yt-dlp {check.stdout.strip()} ready.")

            # Locate ffmpeg
            ffmpeg_dir = _get_ffmpeg_dir(python, self.progress_signal)
            if ffmpeg_dir is None:
                self.finished_signal.emit(
                    False, "",
                    "ffmpeg not found.\n\n"
                    "Easiest fix — run once in your terminal:\n"
                    f"  {python} -m pip install imageio-ffmpeg\n\n"
                    "Or install system ffmpeg:\n"
                    "  Windows: winget install ffmpeg\n"
                    "  macOS:   brew install ffmpeg\n"
                    "  Linux:   sudo apt install ffmpeg"
                )
                return

            self.progress_signal.emit("Fetching video info...")

            # %(autonumber)s stellt sicher, dass yt-dlp beim zweiten Download
            # einer gleichen URL nie eine bereits vorhandene Datei überschreibt,
            # sondern immer eine neue nummerierte Datei anlegt.
            output_template = os.path.join(self.output_dir, "%(artist)s - %(title)s (%(autonumber)s).%(ext)s")

            # Lossless formats (flac, wav) don't use a bitrate quality flag
            _lossless = self.audio_format.lower() in ("flac", "wav")
            # --embed-thumbnail works well for mp3/m4a/ogg; skip for lossless to avoid errors
            _supports_thumb = self.audio_format.lower() in ("mp3", "m4a", "ogg", "aac")

            cmd = [
                python, "-m", "yt_dlp",
                "-x",
                "--audio-format", self.audio_format,
                "--ffmpeg-location", ffmpeg_dir,
            ]
            if not _lossless:
                cmd += ["--audio-quality", self.quality + "K" if self.quality.isdigit() else self.quality]
            if _supports_thumb:
                cmd += ["--embed-thumbnail"]
            cmd += [
                "--embed-metadata",
                "--add-metadata",
                "--output", output_template,
                "--no-playlist",
                "--no-mtime",
                "--newline",
                "--concurrent-fragments", "4",
                "--no-part",
                self.url
            ]

            self.progress_signal.emit(f"Downloading: {self.url}")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            last_file = None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    self.progress_signal.emit(line[:120])
                if "[ExtractAudio] Destination:" in line:
                    last_file = line.split("Destination:")[-1].strip()
                elif "Destination:" in line and any(line.endswith(f".{fmt}") for fmt in SUPPORTED_FORMATS):
                    last_file = line.split("Destination:")[-1].strip()
                elif line.startswith("[download] Destination:"):
                    candidate = line.replace("[download] Destination:", "").strip()
                    if any(candidate.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                        last_file = candidate

            proc.wait()

            if proc.returncode != 0:
                self.finished_signal.emit(False, "", f"yt-dlp exited with code {proc.returncode}")
                return

            if not last_file or not os.path.exists(last_file):
                candidates = []
                for f in os.listdir(self.output_dir):
                    if any(f.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                        full = os.path.join(self.output_dir, f)
                        candidates.append((os.path.getmtime(full), full))
                if candidates:
                    candidates.sort(reverse=True)
                    last_file = candidates[0][1]

            if last_file and os.path.exists(last_file):
                self.finished_signal.emit(True, last_file, "")
            else:
                self.finished_signal.emit(False, "", "Could not locate downloaded file.")

        except FileNotFoundError:
            self.finished_signal.emit(
                False, "",
                f"Could not launch Python interpreter.\nTried: {sys.executable}"
            )
        except Exception as e:
            self.finished_signal.emit(False, "", str(e))


class YtdlpBatchDownloadThread(QThread):
    """Downloads a playlist of URLs one by one."""
    progress_signal = pyqtSignal(str)
    item_done_signal = pyqtSignal(bool, str, str)
    all_done_signal = pyqtSignal(int, int)

    def __init__(self, urls, output_dir, audio_format="mp3", quality="192"):
        super().__init__()
        self.urls = urls
        self.output_dir = output_dir
        self.audio_format = audio_format
        self.quality = quality
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        success_count = 0
        fail_count = 0
        for i, url in enumerate(self.urls):
            if self._stop:
                break
            self.progress_signal.emit(f"[{i+1}/{len(self.urls)}] Downloading: {url[:80]}")
            worker = YtdlpDownloadThread(url, self.output_dir, self.audio_format, self.quality)
            worker.run()
        self.all_done_signal.emit(success_count, fail_count)


# ──────────────────────────── VIDEO DOWNLOAD THREAD ────────────────────────────

def _detect_hw_encoder(ffmpeg_path):
    """
    Probe which H.264 hardware encoder is available and return the
    matching ffmpeg -c:v codec name + any extra flags needed.

    Priority: NVENC (Nvidia) → AMF (AMD) → VideoToolbox (Apple) → libx264 CPU.
    Returns (codec, extra_flags_list) — extra_flags is [] for libx264.
    """
    candidates = [
        # (codec_name,  test_flags,                            extra_flags)
        ("h264_nvenc",   ["-f", "lavfi", "-i", "nullsrc",
                          "-t", "0.1", "-c:v", "h264_nvenc",
                          "-f", "null", "-"],
                         ["-rc", "vbr", "-cq", "18", "-preset", "p1",
                          "-tune", "hq", "-b:v", "0"]),
        ("h264_amf",     ["-f", "lavfi", "-i", "nullsrc",
                          "-t", "0.1", "-c:v", "h264_amf",
                          "-f", "null", "-"],
                         ["-quality", "speed", "-rc", "cqp", "-qp_i", "18",
                          "-qp_p", "18", "-qp_b", "20"]),
        ("h264_videotoolbox",
                         ["-f", "lavfi", "-i", "nullsrc",
                          "-t", "0.1", "-c:v", "h264_videotoolbox",
                          "-f", "null", "-"],
                         ["-q:v", "50", "-allow_sw", "1"]),
    ]
    for codec, test_flags, extra in candidates:
        try:
            r = subprocess.run(
                [ffmpeg_path] + test_flags,
                capture_output=True, timeout=8
            )
            if r.returncode == 0:
                return codec, extra
        except Exception:
            pass
    # CPU fallback
    return "libx264", ["-preset", "veryfast"]


class YtdlpVideoDownloadThread(QThread):
    progress_signal = pyqtSignal(str)
    percent_signal  = pyqtSignal(int)   # 0-100 download; 200-299 merging (pct-200); -1 = unknown
    finished_signal = pyqtSignal(bool, str, str)  # success, filepath, error_msg

    def __init__(self, url, output_dir, video_format="mp4", quality="bestvideo+bestaudio"):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.video_format = video_format
        self.quality = quality

    def run(self):
        try:
            python = sys.executable

            check = subprocess.run(
                [python, "-m", "yt_dlp", "--version"],
                capture_output=True, text=True
            )
            if check.returncode != 0:
                self.finished_signal.emit(False, "", "yt-dlp not installed.\n"
                    f"Run: {python} -m pip install yt-dlp")
                return

            self.progress_signal.emit(f"yt-dlp {check.stdout.strip()} ready.")

            ffmpeg_dir = _get_ffmpeg_dir(python, self.progress_signal)
            if ffmpeg_dir is None:
                self.finished_signal.emit(False, "",
                    "ffmpeg not found.\n\nInstall via:\n"
                    f"  {python} -m pip install imageio-ffmpeg\n"
                    "or: winget install ffmpeg / brew install ffmpeg / apt install ffmpeg")
                return

            self.progress_signal.emit("Fetching video info...")

            # %(autonumber)s → neue Datei bei jedem Download, kein Überschreiben.
            output_template = os.path.join(self.output_dir, "%(title)s (%(autonumber)s).%(ext)s")

            # Build format selector.
            # Priorität: H.264 (avc1) MP4-Video + M4A/AAC-Audio → reines Muxing,
            # kein Re-encoding → sofort fertig, nativ in Adobe Premiere Pro importierbar.
            # AV1 (av01) und VP9 werden ausgeschlossen — Premiere Pro unterstützt
            # diese Codecs nicht nativ (Stand 2024/25).
            # Bei 4K wird [height<=2160] gesetzt, damit kein 8K-Stream gewählt wird
            # und YouTube-4K-Streams (meist avc1 oder vp9) korrekt gefiltert werden.
            _h = {
                "bestvideo+bestaudio": "[height<=2160]",  # 4K: max 2160p, H.264 bevorzugt
                "1080p": "[height<=1080]",
                "720p":  "[height<=720]",
                "480p":  "[height<=480]",
                "360p":  "[height<=360]",
                "worst": "",
            }
            h = _h.get(self.quality, "[height<=2160]")
            if self.quality == "worst":
                fmt_sel = (
                    f"worstvideo{h}[ext=mp4][vcodec!*=av01][vcodec!*=vp9]+worstaudio[ext=m4a]"
                    f"/worstvideo{h}[vcodec!*=av01][vcodec!*=vp9]+worstaudio[ext=m4a]"
                    f"/worst"
                )
            else:
                if self.quality == "bestvideo+bestaudio":
                    # 4K-Modus: YouTube liefert 4K AUSSCHLIESSLICH als VP9 oder AV1 —
                    # H.264 (avc1) existiert auf YouTube nur bis 1080p.
                    # Strategie: besten 4K-Stream laden (VP9 bevorzugt, kein AV1) +
                    # M4A/AAC-Audio, dann via ffmpeg zu H.264 re-encoden.
                    # Re-encoding dauert länger, ist aber die einzige Möglichkeit,
                    # eine echte 4K-H.264-MP4-Datei für Adobe Premiere Pro zu erhalten.
                    # AV1 wird weiterhin ausgeschlossen (zu langsames Decoding beim Re-encode).
                    fmt_sel = (
                        f"bestvideo{h}[ext=webm][vcodec^=vp9]+bestaudio[ext=m4a]"
                        f"/bestvideo{h}[vcodec^=vp9]+bestaudio[ext=m4a]"
                        f"/bestvideo{h}[vcodec!*=av01]+bestaudio[ext=m4a]"
                        f"/bestvideo{h}+bestaudio[ext=m4a]"
                        f"/best{h}"
                    )
                else:
                    # 1080p und darunter: H.264 direkt verfügbar → reines Muxing,
                    # kein Re-encoding nötig, maximale Premiere-Pro-Kompatibilität.
                    fmt_sel = (
                        f"bestvideo{h}[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]"
                        f"/bestvideo{h}[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]"
                        f"/bestvideo{h}[ext=mp4][vcodec!*=av01][vcodec!*=vp9]+bestaudio[ext=m4a]"
                        f"/bestvideo{h}[vcodec!*=av01][vcodec!*=vp9]+bestaudio[ext=m4a]"
                        f"/best{h}"
                    )

            if self.video_format == "gif":
                cmd = [
                    python, "-m", "yt_dlp",
                    "--format", "bestvideo[ext=mp4]/bestvideo/best",
                    "--ffmpeg-location", ffmpeg_dir,
                    "--output", output_template,
                    "--no-playlist", "--no-mtime", "--newline",
                    "--concurrent-fragments", "4",
                    "--recode-video", "gif",
                    self.url
                ]
            elif self.video_format in ("webm",):
                # webm: prefer native webm streams; merge into webm container
                fmt_sel_webm = (
                    f"bestvideo{h}[ext=webm]+bestaudio[ext=webm]"
                    f"/bestvideo{h}[ext=webm]+bestaudio"
                    f"/bestvideo{h}+bestaudio"
                    f"/best{h}"
                )
                cmd = [
                    python, "-m", "yt_dlp",
                    "--format", fmt_sel_webm,
                    "--ffmpeg-location", ffmpeg_dir,
                    "--output", output_template,
                    "--no-playlist", "--no-mtime", "--newline",
                    "--merge-output-format", "webm",
                    "--concurrent-fragments", "4",
                    "--no-part",
                    self.url
                ]
            elif self.video_format in ("mkv", "avi", "mov"):
                # mkv/avi/mov: download best streams and remux/re-encode into target format
                cmd = [
                    python, "-m", "yt_dlp",
                    "--format", fmt_sel,
                    "--ffmpeg-location", ffmpeg_dir,
                    "--output", output_template,
                    "--no-playlist", "--no-mtime", "--newline",
                    "--merge-output-format", self.video_format,
                    "--recode-video", self.video_format,
                    "--concurrent-fragments", "4",
                    "--no-part",
                    self.url
                ]
            else:
                if self.quality == "bestvideo+bestaudio":
                    # 4K needs VP9→H.264 re-encode for Premiere Pro compatibility.
                    # Auto-detect fastest available encoder: NVENC > AMF > VideoToolbox > libx264.
                    ffmpeg_exe = os.path.join(
                        ffmpeg_dir,
                        "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
                    )
                    hw_codec, hw_extra = _detect_hw_encoder(ffmpeg_exe)
                    self.progress_signal.emit(f"🎬 Encoder: {hw_codec}")

                    # Build the ffmpeg postprocessor argument string
                    # -c:v <hw_codec> [extra hw flags] -c:a aac -b:a 320k -movflags +faststart
                    ff_args = (
                        f"-c:v {hw_codec} "
                        + " ".join(hw_extra)
                        + " -pix_fmt yuv420p -c:a aac -b:a 320k -movflags +faststart"
                    )
                    cmd = [
                        python, "-m", "yt_dlp",
                        "--format", fmt_sel,
                        "--ffmpeg-location", ffmpeg_dir,
                        "--output", output_template,
                        "--no-playlist", "--no-mtime", "--newline",
                        "--merge-output-format", "mp4",
                        "--concurrent-fragments", "8",
                        "--no-part",
                        "--recode-video", "mp4",
                        "--postprocessor-args", f"ffmpeg:{ff_args}",
                        self.url
                    ]
                else:
                    # ≤1080p: H.264 streams available directly → pure remux, no re-encode
                    cmd = [
                        python, "-m", "yt_dlp",
                        "--format", fmt_sel,
                        "--ffmpeg-location", ffmpeg_dir,
                        "--output", output_template,
                        "--no-playlist", "--no-mtime", "--newline",
                        "--merge-output-format", "mp4",
                        "--concurrent-fragments", "8",
                        "--no-part",
                        "--postprocessor-args", "ffmpeg:-c copy -movflags +faststart",
                        self.url
                    ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )

            import re as _re
            # yt-dlp download progress:  "[download]  42.3% of ..."
            _dl_pct_re  = _re.compile(r"\[download\]\s+([\d.]+)%")
            # ffmpeg merge/encode progress:  "time=00:01:23.45"
            _ff_time_re = _re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")
            # ffmpeg duration line (comes early in stderr):  "Duration: 00:05:12.34"
            _ff_dur_re  = _re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")

            last_file = None
            total_secs = 0.0
            in_merge = False
            all_formats = SUPPORTED_VIDEO_FORMATS + SUPPORTED_FORMATS

            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue

                self.progress_signal.emit(line[:120])

                # ── Detect merge phase ────────────────────────────────────
                if "[ffmpeg]" in line or "[Merger]" in line or "Merging formats" in line:
                    in_merge = True
                    self.progress_signal.emit("🔀 Merging streams (ffmpeg)…")
                    self.percent_signal.emit(-1)  # indeterminate until time= arrives

                # ── Parse ffmpeg Duration (comes once at merge start) ────
                m_dur = _ff_dur_re.search(line)
                if m_dur:
                    h, mn, s, cs = int(m_dur.group(1)), int(m_dur.group(2)), int(m_dur.group(3)), int(m_dur.group(4))
                    total_secs = h * 3600 + mn * 60 + s + cs / 100.0

                # ── Parse ffmpeg time= (encoding / merging progress) ─────
                m_ff = _ff_time_re.search(line)
                if m_ff and total_secs > 0:
                    h, mn, s, cs = int(m_ff.group(1)), int(m_ff.group(2)), int(m_ff.group(3)), int(m_ff.group(4))
                    elapsed = h * 3600 + mn * 60 + s + cs / 100.0
                    pct = min(int(elapsed / total_secs * 100), 99)
                    # Use 200+ range to signal "merge phase" to the dialog
                    self.percent_signal.emit(200 + pct)
                    continue  # already emitted via progress_signal above

                # ── Parse yt-dlp download percentage ─────────────────────
                if not in_merge:
                    m_dl = _dl_pct_re.search(line)
                    if m_dl:
                        pct = min(int(float(m_dl.group(1))), 99)
                        self.percent_signal.emit(pct)

                # ── Track output file path ────────────────────────────────
                if "Destination:" in line:
                    candidate = line.split("Destination:")[-1].strip()
                    if any(candidate.lower().endswith(ext) for ext in all_formats):
                        last_file = candidate
                elif "has already been downloaded" in line:
                    candidate = line.replace("[download]", "").replace("has already been downloaded", "").strip()
                    if os.path.exists(candidate) and any(candidate.lower().endswith(ext) for ext in all_formats):
                        last_file = candidate

            proc.wait()

            if proc.returncode != 0:
                self.finished_signal.emit(False, "", f"yt-dlp exited with code {proc.returncode}")
                return

            if not last_file or not os.path.exists(last_file):
                candidates = []
                for f in os.listdir(self.output_dir):
                    if any(f.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS):
                        full = os.path.join(self.output_dir, f)
                        candidates.append((os.path.getmtime(full), full))
                if candidates:
                    candidates.sort(reverse=True)
                    last_file = candidates[0][1]

            if last_file and os.path.exists(last_file):
                self.finished_signal.emit(True, last_file, "")
            else:
                self.finished_signal.emit(False, "", "Could not locate downloaded video file.")

        except Exception as e:
            self.finished_signal.emit(False, "", str(e))


# ──────────────────────────── DRAG & DROP MIXIN ────────────────────────────

class DropAcceptMixin:
    """
    Mixin that adds drag-and-drop file import to any QDialog.
    Subclasses must set self._drop_input_widget to a QLineEdit or QTextEdit
    that should receive the dropped path/paths.
    _drop_mode: 'single' (first file only → QLineEdit)
                'multi'  (all files, one per line → QTextEdit)
    """
    _drop_input_widget = None
    _drop_mode = "single"

    def _init_drop(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        event.acceptProposedAction()
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        if not paths:
            return
        w = self._drop_input_widget
        if w is None:
            return
        if self._drop_mode == "multi":
            existing = w.toPlainText().strip()
            new_block = "\n".join(paths)
            w.setPlainText((existing + "\n" + new_block).strip())
        else:
            w.setText(paths[0])
            # Trigger auto-output-path update if available
            if hasattr(self, "_auto_output_path"):
                self._auto_output_path()


# ──────────────────────────── VIDEO DOWNLOAD DIALOG ────────────────────────────

class VideoDownloadDialog(DropAcceptMixin, QDialog):
    def __init__(self, parent, db, download_dir):
        super().__init__(parent)
        self.db = db
        self.download_dir = download_dir
        self.downloaded_files = []
        self.worker = None
        self._drop_mode = "multi"

        self.setWindowTitle("Download Video")
        self.setFixedSize(600, 580)
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Header
        header = QLabel("🎬  Download Video from YouTube / Web")
        header.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel(
            "Paste one or more URLs (one per line). Downloads full video with audio.\n"
            "Supports YouTube, Vimeo, Twitter/X, Reddit, and 1000+ sites via yt-dlp.\n"
            "GIF export: converts first ~30s to an animated GIF (480px wide, 15fps)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # URL input
        url_label = QLabel("URLs (one per line):")
        layout.addWidget(url_label)
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\n"
            "https://vimeo.com/...\n"
            "https://twitter.com/.../status/..."
        )
        self.url_input.setFixedHeight(110)
        layout.addWidget(self.url_input)
        # Enable drag & drop: dropped local files are added as paths
        self._drop_input_widget = self.url_input
        self._init_drop()

        # Options
        opt1 = QHBoxLayout()
        fmt_label = QLabel("Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["mp4", "mkv", "avi", "webm", "mov", "gif"])
        self.fmt_combo.setCurrentText("mp4")
        self.fmt_combo.setFixedWidth(85)
        self.fmt_combo.currentTextChanged.connect(self._on_format_changed)

        qual_label = QLabel("Quality:")
        self.qual_combo = QComboBox()
        self.qual_combo.addItems(["Best (4K+)", "1080p", "720p", "480p", "360p", "Worst (smallest)"])
        self.qual_combo.setFixedWidth(160)

        opt1.addWidget(fmt_label)
        opt1.addWidget(self.fmt_combo)
        opt1.addSpacing(14)
        opt1.addWidget(qual_label)
        opt1.addWidget(self.qual_combo)
        opt1.addStretch()
        layout.addLayout(opt1)

        opt2 = QHBoxLayout()
        dir_label = QLabel("Save to:")
        self.dir_edit = QLineEdit(self.download_dir)
        self.dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self.browse_dir)
        opt2.addWidget(dir_label)
        opt2.addWidget(self.dir_edit, 1)
        opt2.addWidget(browse_btn)
        layout.addLayout(opt2)

        # GIF note label
        self.gif_note = QLabel("⚠  GIF mode: resolution capped at 480px, 15fps. Large files may take a while.")
        self.gif_note.setWordWrap(True)
        self.gif_note.setObjectName("time_label")
        self.gif_note.setVisible(False)
        layout.addWidget(self.gif_note)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(140)
        self.log.setPlaceholderText("Download log will appear here...")
        layout.addWidget(self.log)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("🎬  Download Video")
        self.download_btn.setFixedHeight(38)
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.setFixedHeight(38)
        self.cancel_btn.clicked.connect(self.cancel_or_close)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def _on_format_changed(self, fmt):
        self.gif_note.setVisible(fmt == "gif")
        self.qual_combo.setEnabled(fmt != "gif")

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_dir)
        if folder:
            self.download_dir = folder
            self.dir_edit.setText(folder)

    def log_message(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _qual_string(self):
        txt = self.qual_combo.currentText()
        if "4K" in txt:
            return "bestvideo+bestaudio"
        elif "1080" in txt:
            return "1080p"
        elif "720" in txt:
            return "720p"
        elif "480" in txt:
            return "480p"
        elif "360" in txt:
            return "360p"
        else:
            return "worst"

    def start_download(self):
        raw = self.url_input.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "No URLs", "Please enter at least one URL.")
            return
        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        if not urls:
            return

        os.makedirs(self.download_dir, exist_ok=True)
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.downloaded_files = []

        fmt = self.fmt_combo.currentText()
        qual = self._qual_string()

        self.log.clear()
        self.log_message(f"Starting download of {len(urls)} URL(s)...")
        self.log_message(f"Format: {fmt.upper()}  Quality: {qual}  →  {self.download_dir}")
        self.log_message("─" * 60)

        self._urls_remaining = list(urls)
        self._fmt = fmt
        self._qual = qual
        self._success = 0
        self._fail = 0
        self._download_next()

    def _download_next(self):
        if not self._urls_remaining:
            self._all_done()
            return
        url = self._urls_remaining.pop(0)
        self._current_url = url  # remember for yt_url storage
        total_orig = len(self.url_input.toPlainText().strip().splitlines())
        done = total_orig - len(self._urls_remaining) - 1
        self.status_label.setText(f"Downloading {done + 1} / {total_orig}...")

        self.worker = YtdlpVideoDownloadThread(url, self.download_dir, self._fmt, self._qual)
        self.worker.progress_signal.connect(self.log_message)
        self.worker.percent_signal.connect(self._on_dl_percent)
        self.worker.finished_signal.connect(self._on_one_done)
        self.worker.start()

    def _on_dl_percent(self, pct):
        if pct == -1:
            # Indeterminate — merging started but no time= yet
            self.progress_bar.setRange(0, 0)
            self.status_label.setText("🔀 Merging streams…")
        elif pct >= 200:
            # Merge/encode phase: 200+actual_pct
            real = pct - 200
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(real)
            self.status_label.setText(f"🔀 Merging… {real}%")
        else:
            # Normal download phase
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
            total_orig = len(self.url_input.toPlainText().strip().splitlines())
            done = total_orig - len(self._urls_remaining) - 1
            self.status_label.setText(f"Downloading {done + 1} / {total_orig}… {pct}%")

    def _on_one_done(self, success, filepath, error):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        if success and filepath:
            self.downloaded_files.append((filepath, getattr(self, "_current_url", "")))
            self._success += 1
            self.log_message(f"Saved: {os.path.basename(filepath)}")
        else:
            self._fail += 1
            self.log_message(f"Failed: {error}")
        self.log_message("─" * 60)
        self._download_next()

    def _all_done(self):
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"Done — {self._success} downloaded, {self._fail} failed.")
        self.log_message(f"\nComplete: {self._success} succeeded, {self._fail} failed.")

        if self.downloaded_files:
            added = 0
            for fp, src_url in self.downloaded_files:
                if any(fp.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS):
                    fname = os.path.basename(fp)
                    title = Path(fname).stem
                    fmt = Path(fname).suffix.lstrip(".")
                    file_size = os.path.getsize(fp) if os.path.exists(fp) else 0
                    if not self.db.get_video_by_path(fp):
                        self.db.add_video(title, "Unknown", fp, None, 0, file_size, fmt, "", yt_url=src_url)
                        added += 1
                    else:
                        # Already in library – update yt_url if missing
                        row = self.db.get_video_by_path(fp)
                        if row and src_url and not self.db.get_video_yt_url(row[0]):
                            self.db.set_video_yt_url(row[0], src_url)

            self.log_message(f"Saved {added} video(s) to library.")
            QMessageBox.information(
                self, "Download Complete",
                f"Downloaded {self._success} video(s).\n{added} added to the video library.\n\nSaved to:\n{self.download_dir}"
            )
            self.accept()

    def cancel_or_close(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.log_message("Download cancelled.")
            self.progress_bar.setVisible(False)
            self.download_btn.setEnabled(True)
            self._urls_remaining = []
        else:
            self.reject()


# ──────────────────────────── YT-DLP IMPORT DIALOG ────────────────────────────

class YtdlpImportDialog(DropAcceptMixin, QDialog):
    def __init__(self, parent, db, download_dir):
        super().__init__(parent)
        self.db = db
        self.download_dir = download_dir
        self.downloaded_files = []
        self.worker = None
        self._drop_mode = "multi"

        self.setWindowTitle("Import from YouTube / Web")
        self.setFixedSize(560, 520)
        layout = QVBoxLayout()
        layout.setSpacing(12)

        header = QLabel("⬇  Import from YouTube / SoundCloud / Web")
        header.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel(
            "Paste one or more URLs (one per line). Supports YouTube, SoundCloud, Bandcamp, and "
            "any site supported by yt-dlp.\n\n"
            f"Requires yt-dlp — install with:  {sys.executable} -m pip install yt-dlp"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        url_label = QLabel("URLs (one per line):")
        layout.addWidget(url_label)
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\n"
            "https://soundcloud.com/...\n"
        )
        self.url_input.setFixedHeight(110)
        layout.addWidget(self.url_input)
        # Enable drag & drop: dropped local files are added as paths
        self._drop_input_widget = self.url_input
        self._init_drop()

        options_row = QHBoxLayout()

        fmt_label = QLabel("Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["mp3", "m4a", "flac", "wav", "ogg"])
        self.fmt_combo.setCurrentText("mp3")
        self.fmt_combo.setFixedWidth(80)

        qual_label = QLabel("Quality:")
        self.qual_combo = QComboBox()
        self.qual_combo.addItems(["320", "256", "192", "128", "96"])
        self.qual_combo.setCurrentText("192")
        self.qual_combo.setFixedWidth(70)

        dir_label = QLabel("Save to:")
        self.dir_edit = QLineEdit(self.download_dir)
        self.dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self.browse_dir)

        options_row.addWidget(fmt_label)
        options_row.addWidget(self.fmt_combo)
        options_row.addSpacing(10)
        options_row.addWidget(qual_label)
        options_row.addWidget(self.qual_combo)
        options_row.addSpacing(10)
        options_row.addWidget(dir_label)
        options_row.addWidget(self.dir_edit, 1)
        options_row.addWidget(browse_btn)
        layout.addLayout(options_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)
        self.log.setPlaceholderText("Download log will appear here...")
        layout.addWidget(self.log)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("⬇  Download & Import")
        self.download_btn.setFixedHeight(38)
        self.download_btn.clicked.connect(self.start_download)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(38)
        self.cancel_btn.clicked.connect(self.cancel_or_close)

        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_dir)
        if folder:
            self.download_dir = folder
            self.dir_edit.setText(folder)

    def log_message(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def start_download(self):
        raw = self.url_input.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "No URLs", "Please enter at least one URL.")
            return

        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        if not urls:
            return

        os.makedirs(self.download_dir, exist_ok=True)
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.downloaded_files = []

        fmt = self.fmt_combo.currentText()
        qual = self.qual_combo.currentText()

        self.log.clear()
        self.log_message(f"Starting download of {len(urls)} URL(s)...")
        self.log_message(f"Format: {fmt.upper()}  Quality: {qual}K  →  {self.download_dir}")
        self.log_message("─" * 60)

        self._urls_remaining = list(urls)
        self._fmt = fmt
        self._qual = qual
        self._success = 0
        self._fail = 0
        self._download_next()

    def _download_next(self):
        if not self._urls_remaining:
            self._all_done()
            return

        url = self._urls_remaining.pop(0)
        self._current_url = url  # remember for yt_url storage
        total_orig = len(self.url_input.toPlainText().strip().splitlines())
        done = total_orig - len(self._urls_remaining) - 1
        self.status_label.setText(f"Downloading {done + 1} / {total_orig}...")

        self.worker = YtdlpDownloadThread(url, self.download_dir, self._fmt, self._qual)
        self.worker.progress_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self._on_one_done)
        self.worker.start()

    def _on_one_done(self, success, filepath, error):
        if success and filepath:
            self.downloaded_files.append((filepath, getattr(self, "_current_url", "")))
            self._success += 1
            self.log_message(f"✓ Saved: {os.path.basename(filepath)}")
        else:
            self._fail += 1
            self.log_message(f"✗ Failed: {error}")
        self.log_message("─" * 60)
        self._download_next()

    def _all_done(self):
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"Done — {self._success} downloaded, {self._fail} failed.")
        self.log_message(f"\n✓ Complete: {self._success} succeeded, {self._fail} failed.")

        if self.downloaded_files:
            added = 0
            for fp, src_url in self.downloaded_files:
                if any(fp.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                    fname = os.path.basename(fp)
                    title = Path(fname).stem
                    artist = "Unknown Artist"
                    album = "Unknown Album"
                    duration = 0
                    cover_path = None
                    try:
                        audio = MutagenFile(fp, easy=True)
                        if audio:
                            title = audio.get("title", [title])[0]
                            artist = audio.get("artist", [artist])[0]
                            album = audio.get("album", [album])[0]
                            if hasattr(audio, "info") and hasattr(audio.info, "length"):
                                duration = int(audio.info.length * 1000)
                    except Exception as e:
                        print(f"Metadata read error: {e}")
                    cover_path = extract_cover_from_audio(fp)
                    if not self.db.get_song_by_path(fp):
                        self.db.add_song(title, artist, album, fp, cover_path, duration, yt_url=src_url)
                        added += 1
                    else:
                        # Already in library – update yt_url if missing
                        row = self.db.get_song_by_path(fp)
                        if row and src_url and not self.db.get_yt_url(row[0]):
                            self.db.set_yt_url(row[0], src_url)

            self.log_message(f"→ Imported {added} song(s) into library.")
            QMessageBox.information(
                self, "Import Complete",
                f"Downloaded {self._success} file(s).\nImported {added} new song(s) into library."
            )
            self.accept()

    def cancel_or_close(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.log_message("Download cancelled.")
            self.progress_bar.setVisible(False)
            self.download_btn.setEnabled(True)
            self._urls_remaining = []
        else:
            self.reject()


class FullscreenOverlay(QWidget):
    """Fullscreen overlay for cover art or video preview."""
    def __init__(self, parent=None, pixmap=None, video_path=None, vlc_instance=None):
        super().__init__(None)
        self.setWindowTitle("Nova – Fullscreen")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet("background: #000000;")

        self._vlc_player = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        close_hint = QLabel("Press Esc or double-click to close")
        close_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_hint.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px; background: transparent; padding: 6px;")

        if video_path and vlc_instance:
            self.video_frame = QFrame(self)
            self.video_frame.setStyleSheet("background: #000000;")
            layout.addWidget(self.video_frame, 1)
            layout.addWidget(close_hint)
            self._vlc_player = vlc_instance.media_player_new()
            media = vlc_instance.media_new(video_path)
            self._vlc_player.set_media(media)
            self.showFullScreen()
            wid = int(self.video_frame.winId())
            if sys.platform == "win32":
                self._vlc_player.set_hwnd(wid)
            elif sys.platform == "darwin":
                self._vlc_player.set_nsobject(wid)
            else:
                self._vlc_player.set_xwindow(wid)
            self._vlc_player.play()
        elif pixmap:
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setStyleSheet("background: #000000;")
            layout.addWidget(img_label, 1)
            layout.addWidget(close_hint)
            self.showFullScreen()
            screen = QApplication.primaryScreen().size()
            img_label.setPixmap(pixmap.scaled(
                screen.width(), screen.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            self.showFullScreen()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close_fs()
        elif self._vlc_player:
            if key == Qt.Key.Key_Space:
                state = self._vlc_player.get_state()
                if state == vlc.State.Playing:
                    self._vlc_player.pause()
                else:
                    self._vlc_player.play()
                event.accept()
                return
            elif key == Qt.Key.Key_Left:
                t = max(0, self._vlc_player.get_time() - 5000)
                self._vlc_player.set_time(t)
                event.accept()
                return
            elif key == Qt.Key.Key_Right:
                length = self._vlc_player.get_length()
                t = min(length, self._vlc_player.get_time() + 5000) if length > 0 else self._vlc_player.get_time() + 5000
                self._vlc_player.set_time(t)
                event.accept()
                return
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._close_fs()

    def _close_fs(self):
        if self._vlc_player:
            self._vlc_player.stop()
        self.close()


class EditSongDialog(QDialog):
    """Edit song title, artist, cover art, YouTube URL and lyrics."""
    def __init__(self, parent, db, song_id, title, artist, cover_path):
        super().__init__(parent)
        self.db = db
        self.song_id = song_id
        self.new_cover_path = cover_path
        self.setWindowTitle("Edit Song")
        self.setFixedSize(480, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.title_edit = QLineEdit(title or "")
        self.artist_edit = QLineEdit(artist or "")
        yt_url_current = db.get_yt_url(song_id) or ""
        self.yt_url_edit = QLineEdit(yt_url_current)
        self.yt_url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…")
        form.addRow("Title:", self.title_edit)
        form.addRow("Artist:", self.artist_edit)
        form.addRow("YouTube-URL:", self.yt_url_edit)
        layout.addLayout(form)

        cover_row = QHBoxLayout()
        self.cover_preview = QLabel()
        self.cover_preview.setFixedSize(90, 90)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setStyleSheet("border-radius: 10px; background: #1a1a1a; border: 1px solid #333;")
        if cover_path and os.path.exists(cover_path):
            px = QPixmap(cover_path).scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_preview.setPixmap(px)
        else:
            self.cover_preview.setText("🎵")
            self.cover_preview.setFont(QFont("Arial", 28))

        cover_btns_layout = QVBoxLayout()
        pick_btn = QPushButton("📁  Choose Image")
        pick_btn.setFixedHeight(34)
        pick_btn.clicked.connect(self._pick_cover)
        clear_btn = QPushButton("✕  Clear Cover")
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(self._clear_cover)
        cover_btns_layout.addWidget(pick_btn)
        cover_btns_layout.addWidget(clear_btn)
        cover_btns_layout.addStretch()
        cover_row.addWidget(self.cover_preview)
        cover_row.addSpacing(14)
        cover_row.addLayout(cover_btns_layout)
        cover_row.addStretch()
        layout.addLayout(cover_row)

        # ── Lyrics field ──────────────────────────────────────────────────
        layout.addWidget(QLabel("Lyrics:"))

        search_row = QHBoxLayout()
        self.lyrics_search = QLineEdit()
        self.lyrics_search.setPlaceholderText(f"{artist or 'Artist'} - {title or 'Title'}")
        self.lyrics_search.setText(f"{artist} - {title}" if artist and title else "")
        self.lyrics_search.setToolTip("Format: Artist - Title  (e.g.  Eminem - Slim Shady)")
        self._lyrics_fetch_btn = QPushButton("🔍 Fetch")
        self._lyrics_fetch_btn.setFixedWidth(70)
        self._lyrics_fetch_btn.clicked.connect(self._fetch_lyrics)
        search_row.addWidget(self.lyrics_search)
        search_row.addWidget(self._lyrics_fetch_btn)
        layout.addLayout(search_row)

        self._lyrics_status = QLabel("Format: Artist - Title")
        self._lyrics_status.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._lyrics_status)

        existing_lyrics = db.cursor.execute(
            "SELECT lyrics FROM songs WHERE id=?", (song_id,)
        ).fetchone()
        existing_lyrics = (existing_lyrics[0] or "") if existing_lyrics else ""
        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlainText(existing_lyrics)
        self.lyrics_edit.setPlaceholderText("Lyrics appear here after fetching, or paste manually…")
        self.lyrics_edit.setFixedHeight(130)
        layout.addWidget(self.lyrics_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _fetch_lyrics(self):
        query = self.lyrics_search.text().strip()
        if not query:
            self._lyrics_status.setText("⚠  Enter  Artist - Title  first.")
            return
        if " - " in query:
            artist, _, title = query.partition(" - ")
        else:
            artist, title = "", query
        artist, title = artist.strip(), title.strip()
        self._lyrics_fetch_btn.setEnabled(False)
        self._lyrics_status.setText("Searching…")
        self._fetcher = LyricsFetcher(artist, title)
        self._fetcher.lyrics_ready.connect(self._on_fetched)
        self._fetcher.lyrics_failed.connect(self._on_fetch_failed)
        self._fetcher.start()

    def _on_fetched(self, raw: str, _lines):
        self.lyrics_edit.setPlainText(raw)
        self._lyrics_status.setText("✓ Lyrics loaded — save to keep them.")
        self._lyrics_status.setStyleSheet("color: #4caf50; font-size: 11px;")
        self._lyrics_fetch_btn.setEnabled(True)

    def _on_fetch_failed(self, msg: str):
        self._lyrics_status.setText(f"✗ {msg}")
        self._lyrics_status.setStyleSheet("color: #e57373; font-size: 11px;")
        self._lyrics_fetch_btn.setEnabled(True)

    def _pick_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Cover Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.new_cover_path = path
            px = QPixmap(path).scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_preview.setPixmap(px)
            self.cover_preview.setText("")

    def _clear_cover(self):
        self.new_cover_path = None
        self.cover_preview.clear()
        self.cover_preview.setText("🎵")

    def _save(self):
        title = self.title_edit.text().strip()
        artist = self.artist_edit.text().strip()
        yt_url = self.yt_url_edit.text().strip() or None
        lyrics = self.lyrics_edit.toPlainText().strip() or None
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return
        self.db.cursor.execute(
            "UPDATE songs SET title=?, artist=?, cover_path=?, yt_url=?, lyrics=? WHERE id=?",
            (title, artist, self.new_cover_path, yt_url, lyrics, self.song_id)
        )
        self.db.conn.commit()
        self.accept()


class SleepTimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sleep Timer")
        self.setFixedSize(300, 180)
        layout = QFormLayout()
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 480)
        self.minutes_spin.setValue(30)
        self.minutes_spin.setSuffix(" minutes")
        layout.addRow("Stop after:", self.minutes_spin)
        self.fade_check = QCheckBox("Fade out before stopping")
        layout.addRow(self.fade_check)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)
        self.setLayout(layout)


class PlaylistDialog(QDialog):
    """Create or edit a playlist — name, description, cover art."""
    def __init__(self, parent=None, name="", description="", cover_path=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist")
        self.setFixedSize(400, 310)
        self.new_cover_path = cover_path

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.desc_edit = QLineEdit(description)
        form.addRow("Name:", self.name_edit)
        form.addRow("Description:", self.desc_edit)
        layout.addLayout(form)

        cover_row = QHBoxLayout()
        self.cover_preview = QLabel()
        self.cover_preview.setFixedSize(64, 64)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setStyleSheet("border-radius: 8px; background: #1a1a1a; border: 1px solid #333;")
        cover_row.addWidget(self.cover_preview)
        cover_row.addSpacing(10)
        pick_btn = QPushButton("📁  Cover wählen")
        pick_btn.setFixedHeight(32)
        pick_btn.clicked.connect(self._pick_cover)
        clear_btn = QPushButton("✕  Entfernen")
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self._clear_cover)
        vb = QVBoxLayout()
        vb.addWidget(pick_btn)
        vb.addWidget(clear_btn)
        vb.addStretch()
        cover_row.addLayout(vb)
        cover_row.addStretch()
        layout.addLayout(cover_row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Refresh preview AFTER the widget is fully in the layout to avoid
        # a font/pixmap assignment crash under pythonw on Windows
        self._refresh_cover_preview()

    def _refresh_cover_preview(self):
        if self.new_cover_path and os.path.exists(self.new_cover_path):
            px = QPixmap(self.new_cover_path).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.cover_preview.setPixmap(px)
            self.cover_preview.setText("")
        else:
            self.cover_preview.clear()
            self.cover_preview.setText("♪")
            self.cover_preview.setFont(QFont("Arial", 24))

    def _pick_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cover-Bild wählen", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.new_cover_path = path
            self._refresh_cover_preview()

    def _clear_cover(self):
        self.new_cover_path = None
        self._refresh_cover_preview()


class EditPlaylistContentDialog(QDialog):
    """
    Full playlist editor: reorder songs/videos via drag-and-drop,
    remove entries, view cover.
    """
    def __init__(self, parent, db, playlist_id):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        pl = db.get_playlist(playlist_id)
        self.setWindowTitle(f"Playlist bearbeiten — {pl[1]}")
        self.setMinimumSize(560, 520)
        self.resize(600, 580)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel(f"♪  {pl[1]}")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        if pl[2]:
            desc_lbl = QLabel(pl[2])
            desc_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
            layout.addWidget(desc_lbl)

        # Hint
        hint = QLabel("Reihenfolge per Drag & Drop ändern  ·  Rechtsklick zum Entfernen")
        hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        layout.addWidget(hint)

        # Song list (drag & drop)
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._item_context_menu)
        self.list_widget.setSpacing(2)
        self.list_widget.setIconSize(QSize(40, 40))
        layout.addWidget(self.list_widget)

        # Buttons
        btn_row = QHBoxLayout()
        move_up_btn = QPushButton("▲  Nach oben")
        move_up_btn.clicked.connect(self._move_up)
        move_down_btn = QPushButton("▼  Nach unten")
        move_down_btn.clicked.connect(self._move_down)
        remove_btn = QPushButton("🗑  Entfernen")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(move_up_btn)
        btn_row.addWidget(move_down_btn)
        btn_row.addStretch()
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)

        save_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btns.accepted.connect(self._save)
        save_btns.rejected.connect(self.reject)
        layout.addWidget(save_btns)

        self._load_items()

    def _load_items(self):
        self.list_widget.clear()
        # Songs
        songs = self.db.get_playlist_songs(self.playlist_id)
        for s in songs:
            sid, title, artist, album, path, cover_path, duration, fav, rating, plays = s
            dur = format_duration(duration)
            text = f"{title}\n{artist}  ·  {album}  [{dur}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, ("song", sid, path))
            if cover_path and os.path.exists(cover_path):
                px = QPixmap(cover_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            else:
                item.setIcon(QIcon())
            self.list_widget.addItem(item)
        # Videos
        videos = self.db.get_playlist_videos(self.playlist_id)
        for v in videos:
            vid_id, title, channel, path, thumb_path, duration, file_size, fmt, resolution = v
            dur = format_duration(duration)
            text = f"🎬  {title}\n{channel}  ·  {resolution}  [{dur}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, ("video", vid_id, path))
            if thumb_path and os.path.exists(thumb_path):
                px = QPixmap(thumb_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            self.list_widget.addItem(item)

    def _item_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        rm = QAction("🗑  Aus Playlist entfernen", self)
        rm.triggered.connect(lambda: self._remove_item(item))
        menu.addAction(rm)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _remove_item(self, item):
        kind, eid, path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "song":
            self.db.remove_song_from_playlist(self.playlist_id, eid)
        else:
            self.db.remove_video_from_playlist(self.playlist_id, eid)
        self._load_items()

    def _remove_selected(self):
        item = self.list_widget.currentItem()
        if item:
            self._remove_item(item)

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def _save(self):
        song_ids = []
        video_ids = []
        for i in range(self.list_widget.count()):
            kind, eid, _ = self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            if kind == "song":
                song_ids.append((i, eid))
            else:
                video_ids.append((i, eid))
        for pos, sid in song_ids:
            self.db.cursor.execute(
                "UPDATE playlist_songs SET position=? WHERE playlist_id=? AND song_id=?",
                (pos, self.playlist_id, sid)
            )
        for pos, vid in video_ids:
            self.db.cursor.execute(
                "UPDATE playlist_videos SET position=? WHERE playlist_id=? AND video_id=?",
                (pos, self.playlist_id, vid)
            )
        self.db.conn.commit()
        self.accept()


class WebPlayerDialog(QDialog):
    """Dialog that generates and shows a standalone HTML player."""
    def __init__(self, parent, songs, current_song=None, theme=None):
        super().__init__(parent)
        self.setWindowTitle("Web Player Export")
        self.setFixedSize(500, 340)
        self.songs = songs
        self.current_song = current_song
        self.theme = theme or THEMES["Midnight"]
        layout = QVBoxLayout()

        info = QLabel(
            f"Generate a standalone HTML music player with {len(songs)} songs.\n"
            "Songs are linked by file path (must stay accessible).\n"
            "Includes download button for each track."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.include_covers = QCheckBox("Embed cover art as base64 (larger file)")
        self.include_covers.setChecked(False)
        layout.addWidget(self.include_covers)

        self.open_after = QCheckBox("Open in browser after saving")
        self.open_after.setChecked(True)
        layout.addWidget(self.open_after)

        btns = QDialogButtonBox()
        save_btn = btns.addButton("Save HTML File", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = btns.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        save_btn.clicked.connect(self.save_html)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btns)

        self.setLayout(layout)

    def save_html(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Web Player", "nova_player.html", "HTML Files (*.html)")
        if not path:
            return
        html = self.generate_html()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if self.open_after.isChecked():
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(path)}")
        self.accept()

    def generate_html(self):
        accent = self.theme["accent"]
        bg = self.theme["bg"]
        card = self.theme["card"]
        text = self.theme["text"]
        subtext = self.theme["subtext"]

        songs_json = []
        for s in self.songs:
            sid, title, artist, album, path, cover_path, duration, fav, rating, plays = s
            cover_data = ""
            if self.include_covers.isChecked() and cover_path and os.path.exists(cover_path):
                try:
                    with open(cover_path, "rb") as f:
                        cover_data = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
                except Exception:
                    pass
            songs_json.append({
                "title": title, "artist": artist, "album": album,
                "path": path, "duration": duration, "cover": cover_data,
                "favourite": bool(fav)
            })

        songs_js = json.dumps(songs_json, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NovaX7</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;800&display=swap');
  :root {{
    --bg: {bg}; --card: {card}; --accent: {accent};
    --text: {text}; --sub: {subtext}; --border: {self.theme["border"]};
    --green: {self.theme["green"]}; --red: {self.theme["red"]};
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Space Mono', monospace; min-height: 100vh; }}
  .app {{ display: grid; grid-template-columns: 1fr 340px; grid-template-rows: auto 1fr; height: 100vh; overflow: hidden; }}
  .header {{ grid-column: 1/-1; padding: 20px 32px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid var(--border); background: var(--card); }}
  .logo {{ font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.6rem; color: var(--accent); letter-spacing: -0.04em; }}
  .search {{ flex: 1; max-width: 360px; padding: 10px 16px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 24px; color: var(--text); font-family: inherit; font-size: 0.85rem; outline: none; transition: border 0.2s; }}
  .search:focus {{ border-color: var(--accent); }}
  .library {{ overflow-y: auto; padding: 16px; }}
  .song-item {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; cursor: pointer; transition: background 0.15s; border: 1px solid transparent; margin-bottom: 4px; }}
  .song-item:hover {{ background: rgba(255,255,255,0.05); border-color: var(--border); }}
  .song-item.playing {{ background: var(--accent)22; border-color: var(--accent)66; }}
  .song-num {{ width: 28px; text-align: center; color: var(--sub); font-size: 0.8rem; flex-shrink: 0; }}
  .song-cover {{ width: 48px; height: 48px; border-radius: 8px; object-fit: cover; background: rgba(255,255,255,0.08); flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; }}
  .song-cover img {{ width: 100%; height: 100%; border-radius: 8px; object-fit: cover; }}
  .song-info {{ flex: 1; min-width: 0; }}
  .song-title {{ font-size: 0.9rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .song-artist {{ font-size: 0.78rem; color: var(--sub); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .song-dur {{ font-size: 0.78rem; color: var(--sub); flex-shrink: 0; }}
  .fav-btn {{ background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 4px; opacity: 0.5; transition: opacity 0.2s, transform 0.15s; }}
  .fav-btn:hover {{ opacity: 1; transform: scale(1.2); }}
  .fav-btn.active {{ opacity: 1; }}
  .dl-btn {{ background: none; border: 1px solid var(--border); color: var(--sub); padding: 4px 10px; border-radius: 20px; font-size: 0.7rem; cursor: pointer; font-family: inherit; transition: all 0.2s; text-decoration: none; white-space: nowrap; }}
  .dl-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .player-panel {{ background: var(--card); border-left: 1px solid var(--border); display: flex; flex-direction: column; padding: 32px 24px; gap: 24px; overflow-y: auto; }}
  .cover-art {{ width: 100%; aspect-ratio: 1; border-radius: 18px; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; font-size: 4rem; overflow: hidden; }}
  .cover-art img {{ width: 100%; height: 100%; object-fit: cover; border-radius: 18px; }}
  .now-playing {{ text-align: center; }}
  .np-title {{ font-family: 'Syne', sans-serif; font-size: 1.1rem; font-weight: 800; margin-bottom: 4px; }}
  .np-artist {{ font-size: 0.82rem; color: var(--sub); }}
  .progress-area {{ display: flex; flex-direction: column; gap: 8px; }}
  .progress-bar {{ -webkit-appearance: none; appearance: none; width: 100%; height: 4px; border-radius: 2px; background: rgba(255,255,255,0.1); outline: none; cursor: pointer; }}
  .progress-bar::-webkit-slider-thumb {{ -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--accent); cursor: pointer; }}
  .time-row {{ display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--sub); }}
  .controls {{ display: flex; align-items: center; justify-content: center; gap: 16px; }}
  .ctrl-btn {{ background: none; border: none; color: var(--text); font-size: 1.4rem; cursor: pointer; padding: 8px; border-radius: 50%; transition: background 0.15s, transform 0.1s; }}
  .ctrl-btn:hover {{ background: rgba(255,255,255,0.08); transform: scale(1.1); }}
  .play-btn {{ background: var(--accent) !important; width: 52px; height: 52px; border-radius: 50%; font-size: 1.2rem; display: flex; align-items: center; justify-content: center; }}
  .play-btn:hover {{ filter: brightness(1.15); }}
  .vol-row {{ display: flex; align-items: center; gap: 10px; }}
  .vol-icon {{ font-size: 1rem; color: var(--sub); }}
  .volume-bar {{ -webkit-appearance: none; appearance: none; flex: 1; height: 4px; border-radius: 2px; background: rgba(255,255,255,0.1); outline: none; cursor: pointer; }}
  .volume-bar::-webkit-slider-thumb {{ -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%; background: var(--sub); cursor: pointer; }}
  .shuffle-btn, .loop-btn {{ background: none; border: none; color: var(--sub); font-size: 1rem; cursor: pointer; padding: 6px; border-radius: 6px; transition: color 0.2s; }}
  .shuffle-btn.active, .loop-btn.active {{ color: var(--accent); }}
  .empty {{ text-align: center; color: var(--sub); padding: 60px 20px; }}
  ::-webkit-scrollbar {{ width: 6px; }} ::-webkit-scrollbar-track {{ background: transparent; }} ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 3px; }}
  @media (max-width: 700px) {{ .app {{ grid-template-columns: 1fr; grid-template-rows: auto 1fr auto; }} .player-panel {{ border-left: none; border-top: 1px solid var(--border); }} .cover-art {{ display: none; }} }}
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <div class="logo">⬡ NovaX7 </div>
    <input class="search" type="text" placeholder="Search songs, artists..." id="searchInput" oninput="filterSongs(this.value)">
    <button class="shuffle-btn" id="shuffleBtn" onclick="toggleShuffle()" title="Shuffle">⇄</button>
    <button class="loop-btn" id="loopBtn" onclick="toggleLoop()" title="Loop">↻</button>
  </div>
  <div class="library" id="library"></div>
  <div class="player-panel">
    <div class="cover-art" id="coverArt">🎵</div>
    <div class="now-playing">
      <div class="np-title" id="npTitle">No song selected</div>
      <div class="np-artist" id="npArtist">—</div>
    </div>
    <div class="progress-area">
      <input type="range" class="progress-bar" id="progressBar" value="0" min="0" max="100" step="0.1" oninput="seekTo(this.value)">
      <div class="time-row"><span id="timeElapsed">0:00</span><span id="timeDuration">0:00</span></div>
    </div>
    <div class="controls">
      <button class="ctrl-btn" onclick="playPrev()" title="Previous">⏮</button>
      <button class="ctrl-btn play-btn" id="playBtn" onclick="togglePlay()" title="Play/Pause">▶</button>
      <button class="ctrl-btn" onclick="playNext()" title="Next">⏭</button>
    </div>
    <div class="vol-row">
      <span class="vol-icon">🔈</span>
      <input type="range" class="volume-bar" id="volumeBar" value="80" min="0" max="100" oninput="setVolume(this.value)">
      <span class="vol-icon">🔊</span>
    </div>
  </div>
</div>
<audio id="audioEl" preload="none"></audio>
<script>
const SONGS = {songs_js};
let currentIdx = -1, isPlaying = false, shuffleOn = false, loopOn = false;
let filteredSongs = [...SONGS];
const audio = document.getElementById('audioEl');

function fmtTime(sec) {{
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec/60), s = Math.floor(sec%60);
  return m + ':' + String(s).padStart(2,'0');
}}

function fmtMs(ms) {{
  if (!ms) return '0:00';
  return fmtTime(ms/1000);
}}

function renderLibrary(songs) {{
  const lib = document.getElementById('library');
  if (!songs.length) {{ lib.innerHTML = '<div class="empty">No songs found.</div>'; return; }}
  lib.innerHTML = songs.map((s,i) => `
    <div class="song-item" id="song-${{i}}" onclick="playSong(${{SONGS.indexOf(s)}})">
      <span class="song-num">${{i+1}}</span>
      <div class="song-cover">${{s.cover ? `<img src="${{s.cover}}" alt="">` : '🎵'}}</div>
      <div class="song-info">
        <div class="song-title">${{esc(s.title)}}</div>
        <div class="song-artist">${{esc(s.artist)}} · ${{esc(s.album)}}</div>
      </div>
      <span class="song-dur">${{fmtMs(s.duration)}}</span>
      <button class="fav-btn ${{s.favourite?'active':''}}" onclick="event.stopPropagation();toggleFav(${{SONGS.indexOf(s)}})" title="Favourite">${{s.favourite?'♥':'♡'}}</button>
      <a class="dl-btn" href="${{s.path}}" download="${{esc(s.title)}}" onclick="event.stopPropagation()">↓ DL</a>
    </div>
  `).join('');
}}

function esc(s) {{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}

function filterSongs(q) {{
  q = q.toLowerCase();
  filteredSongs = q ? SONGS.filter(s => (s.title+s.artist+s.album).toLowerCase().includes(q)) : [...SONGS];
  renderLibrary(filteredSongs);
}}

function playSong(globalIdx) {{
  currentIdx = globalIdx;
  const s = SONGS[globalIdx];
  audio.src = s.path;
  audio.load();
  audio.play().then(()=>{{isPlaying=true;updateUI();}}).catch(()=>{{}});
  document.getElementById('npTitle').textContent = s.title;
  document.getElementById('npArtist').textContent = s.artist + (s.album ? ' · ' + s.album : '');
  document.getElementById('coverArt').innerHTML = s.cover ? `<img src="${{s.cover}}" alt="">` : '🎵';
  document.querySelectorAll('.song-item').forEach(el=>el.classList.remove('playing'));
  const li = filteredSongs.indexOf(s);
  if(li>=0) document.getElementById('song-'+li)?.classList.add('playing');
}}

function togglePlay() {{
  if(currentIdx<0 && SONGS.length) {{ playSong(0); return; }}
  if(audio.paused) {{ audio.play(); isPlaying=true; }} else {{ audio.pause(); isPlaying=false; }}
  updateUI();
}}

function playNext() {{
  if(!SONGS.length) return;
  if(shuffleOn) {{ const r=Math.floor(Math.random()*SONGS.length); playSong(r); }}
  else playSong((currentIdx+1)%SONGS.length);
}}

function playPrev() {{
  if(!SONGS.length) return;
  if(audio.currentTime>3) {{ audio.currentTime=0; return; }}
  playSong((currentIdx-1+SONGS.length)%SONGS.length);
}}

function seekTo(v) {{ if(audio.duration) audio.currentTime = v/100*audio.duration; }}
function setVolume(v) {{ audio.volume = v/100; }}
function toggleShuffle() {{ shuffleOn=!shuffleOn; document.getElementById('shuffleBtn').classList.toggle('active',shuffleOn); }}
function toggleLoop() {{ loopOn=!loopOn; audio.loop=loopOn; document.getElementById('loopBtn').classList.toggle('active',loopOn); }}
function toggleFav(i) {{
  SONGS[i].favourite=!SONGS[i].favourite;
  renderLibrary(filteredSongs);
}}

function updateUI() {{
  document.getElementById('playBtn').textContent = isPlaying ? '⏸' : '▶';
}}

audio.addEventListener('timeupdate', ()=>{{
  const pct = audio.duration ? (audio.currentTime/audio.duration*100) : 0;
  document.getElementById('progressBar').value = pct;
  document.getElementById('timeElapsed').textContent = fmtTime(audio.currentTime);
  document.getElementById('timeDuration').textContent = fmtTime(audio.duration);
}});
audio.addEventListener('ended', ()=>{{ if(!loopOn) playNext(); isPlaying=!audio.paused; updateUI(); }});
audio.addEventListener('play', ()=>{{isPlaying=true;updateUI();}});
audio.addEventListener('pause', ()=>{{isPlaying=false;updateUI();}});

document.addEventListener('keydown', e=>{{
  if(e.target.tagName==='INPUT') return;
  if(e.code==='Space') {{ e.preventDefault(); togglePlay(); }}
  if(e.code==='ArrowRight') {{ audio.currentTime=Math.min(audio.duration,audio.currentTime+10); }}
  if(e.code==='ArrowLeft') {{ audio.currentTime=Math.max(0,audio.currentTime-10); }}
  if(e.code==='ArrowUp') {{ const vb=document.getElementById('volumeBar'); vb.value=Math.min(100,+vb.value+5); setVolume(vb.value); }}
  if(e.code==='ArrowDown') {{ const vb=document.getElementById('volumeBar'); vb.value=Math.max(0,+vb.value-5); setVolume(vb.value); }}
  if(e.code==='KeyN') playNext();
  if(e.code==='KeyP') playPrev();
}});

renderLibrary(SONGS);
</script>
</body>
</html>"""


# ──────────────────────────── SNAKE EASTER EGG ────────────────────────────

import math as _math

class SnakeWindow(QDialog):
    """Snake-Minispiel – Liquid Glass Stil. Trigger: Code 'DIPPEN' in Settings."""

    _CELL       = 24
    _COLS       = 26
    _ROWS       = 22
    _W          = 26 * 24
    _H          = 22 * 24
    _HEADER     = 58
    _SNAKE_R    = 24 * 0.42
    _FOOD_R     = 24 * 0.36
    _SPEED_NORM = 7.0
    _SPEED_MED  = 11.0
    _SPEED_FAST = 16.0
    _RENDER_HZ  = 16   # ms (~60fps)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🐍  Snake — Dippen Edition")
        self.setFixedSize(self._W, self._H + self._HEADER)
        self.setModal(True)

        from PyQt6.QtCore import QElapsedTimer
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._last_ms  = self._elapsed.elapsed()
        self._anim     = 0.0
        self._acc      = 0.0
        self._interp   = 0.0
        self._sps      = 1.0 / self._SPEED_NORM   # secs per step
        self._paused   = False
        self._hi       = 0
        self._food_pop = 0.0
        self._swipe_start = None

        self._reset_game()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(False)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._frame)
        self._timer.start(self._RENDER_HZ)

    # ── Game state ────────────────────────────────────────────────────────────

    def _reset_game(self):
        cx, cy = self._COLS // 2, self._ROWS // 2
        self._snake  = [(cx,cy),(cx-1,cy),(cx-2,cy),(cx-3,cy),(cx-4,cy)]
        self._dir    = (1, 0)
        self._queued = []
        self._food   = self._spawn_food()
        self._score  = 0
        self._alive  = True
        self._acc    = 0.0
        self._interp = 0.0
        self._prev_head = self._cpt(*self._snake[0])

    def _spawn_food(self):
        s = set(self._snake)
        while True:
            p = (random.randint(0, self._COLS-1), random.randint(0, self._ROWS-1))
            if p not in s:
                return p

    def _cpt(self, cx, cy):
        return QPointF(cx * self._CELL + self._CELL / 2,
                       cy * self._CELL + self._CELL / 2)

    def _steer(self, dx, dy):
        last = self._queued[-1] if self._queued else self._dir
        if (dx,dy) != (-last[0],-last[1]) and (dx,dy) != last:
            if len(self._queued) < 2:
                self._queued.append((dx,dy))

    def _step(self):
        if not self._alive: return
        if self._queued:
            self._dir = self._queued.pop(0)
        hx, hy = self._snake[0]
        nx, ny = hx + self._dir[0], hy + self._dir[1]
        if not (0 <= nx < self._COLS and 0 <= ny < self._ROWS) \
                or (nx, ny) in self._snake[1:]:
            self._alive = False
            self._hi = max(self._hi, self._score)
            return
        self._snake.insert(0, (nx, ny))
        if (nx, ny) == self._food:
            self._score += 1
            self._food   = self._spawn_food()
            self._food_pop = 1.0
        else:
            self._snake.pop()

    def _game_speed(self):
        if self._score >= 25: return self._SPEED_FAST
        if self._score >= 10: return self._SPEED_MED
        return self._SPEED_NORM

    # ── Frame loop ────────────────────────────────────────────────────────────

    def _frame(self):
        now = self._elapsed.elapsed()
        dt  = min((now - self._last_ms) / 1000.0, 0.1)
        self._last_ms = now
        self._anim   += dt

        if not self._paused and self._alive:
            self._sps = 1.0 / self._game_speed()
            self._acc += dt
            while self._acc >= self._sps:
                self._acc -= self._sps
                self._prev_head = self._cpt(*self._snake[0])
                self._step()
                if not self._alive: break
            self._interp = min(self._acc / self._sps, 1.0)
            if self._food_pop > 0:
                self._food_pop = max(0.0, self._food_pop - dt * 6)
        self.update()

    # ── Input ─────────────────────────────────────────────────────────────────

    _KEY_DIR = {
        Qt.Key.Key_Up:(0,-1),    Qt.Key.Key_W:(0,-1),
        Qt.Key.Key_Down:(0,1),   Qt.Key.Key_S:(0,1),
        Qt.Key.Key_Left:(-1,0),  Qt.Key.Key_A:(-1,0),
        Qt.Key.Key_Right:(1,0),  Qt.Key.Key_D:(1,0),
    }

    def keyPressEvent(self, e):
        k = e.key()
        if k in self._KEY_DIR:     self._steer(*self._KEY_DIR[k])
        elif k == Qt.Key.Key_P:    self._paused = not self._paused
        elif k == Qt.Key.Key_R:    self._reset_game()
        elif k == Qt.Key.Key_Escape: self._timer.stop(); self.reject()

    def mousePressEvent(self, e):
        if not self._alive:
            self._reset_game(); return
        if e.button() == Qt.MouseButton.RightButton:
            self._paused = not self._paused; return
        if e.button() == Qt.MouseButton.LeftButton:
            self._swipe_start = e.position()

    def mouseMoveEvent(self, e):
        if self._swipe_start is None: return
        dx = e.position().x() - self._swipe_start.x()
        dy = e.position().y() - self._swipe_start.y()
        if _math.hypot(dx, dy) >= 18:
            self._apply_swipe(dx, dy)
            self._swipe_start = e.position()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._swipe_start is None:
            return
        dx = e.position().x() - self._swipe_start.x()
        dy = e.position().y() - self._swipe_start.y()
        if _math.hypot(dx, dy) >= 10:
            self._apply_swipe(dx, dy)
        self._swipe_start = None

    def _apply_swipe(self, dx, dy):
        if not self._alive or self._paused: return
        if abs(dx) >= abs(dy): self._steer(1 if dx>0 else -1, 0)
        else:                  self._steer(0, 1 if dy>0 else -1)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        from PyQt6.QtGui import QPainter, QPainterPath, QLinearGradient, QRadialGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._ph_draw_header(p)
        p.translate(0, self._HEADER)
        self._ph_draw_bg(p)
        self._ph_draw_food(p)
        self._ph_draw_snake(p)
        if not self._alive:
            self._ph_overlay(p, "GAME OVER", f"Score  {self._score}",
                             ["Klick / R → Neu", "Esc → Schließen"])
        elif self._paused:
            self._ph_overlay(p, "PAUSE", "", ["Rechtsklick / P → Weiter"])
        p.end()

    def _ph_draw_bg(self, p):
        from PyQt6.QtGui import QPainter, QLinearGradient, QRadialGradient
        g = QLinearGradient(0,0,0,self._H)
        g.setColorAt(0, QColor("#0b0c1e")); g.setColorAt(1, QColor("#10172a"))
        p.fillRect(0, 0, self._W, self._H, QBrush(g))
        p.setPen(QPen(QColor(255,255,255,8), 1))
        for x in range(0, self._W+1, self._CELL): p.drawLine(x,0,x,self._H)
        for y in range(0, self._H+1, self._CELL): p.drawLine(0,y,self._W,y)
        vig = QRadialGradient(self._W/2, self._H/2, max(self._W,self._H)*0.7)
        vig.setColorAt(0, QColor(0,0,0,0)); vig.setColorAt(1, QColor(0,0,0,100))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(vig))
        p.drawRect(0, 0, self._W, self._H)

    def _ph_draw_header(self, p):
        from PyQt6.QtGui import QLinearGradient, QFontMetrics
        g = QLinearGradient(0,0,0,self._HEADER)
        g.setColorAt(0, QColor(255,255,255,22)); g.setColorAt(1, QColor(255,255,255,6))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
        p.drawRect(0, 0, self._W, self._HEADER)
        p.setPen(QPen(QColor(255,255,255,45), 1))
        p.drawLine(0, self._HEADER-1, self._W, self._HEADER-1)

        fl = QFont("SF Pro Display,Segoe UI,Arial", 8)
        fl.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        fv = QFont("SF Pro Display,Segoe UI,Arial", 20, QFont.Weight.Bold)
        ft = QFont("SF Pro Display,Segoe UI,Arial", 13, QFont.Weight.Bold)
        ft.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)

        p.setFont(fl); p.setPen(QColor(180,190,220,140))
        p.drawText(20, 16, "SCORE"); p.drawText(self._W-105, 16, "BEST")
        p.setFont(fv); p.setPen(QColor(255,255,255,230))
        p.drawText(20, 48, str(self._score))
        p.drawText(self._W-105, 48, str(self._hi))

        title = "🐍  SNAKE"
        p.setFont(ft)
        hue = int(self._anim * 60) % 360
        p.setPen(QColor.fromHsv(hue, 110, 255, 210))
        fm = QFontMetrics(ft)
        tw = fm.horizontalAdvance(title)
        p.drawText((self._W - tw)//2, 40, title)

        fh = QFont("SF Pro Display,Segoe UI,Arial", 7)
        p.setFont(fh); p.setPen(QColor(180,190,220,130))
        hint = "Swipe / WASD  ·  P Pause  ·  Esc Schließen"
        fmh = QFontMetrics(fh)
        p.drawText((self._W - fmh.horizontalAdvance(hint))//2, self._HEADER-5, hint)

    def _ph_draw_food(self, p):
        from PyQt6.QtGui import QRadialGradient
        fx, fy = self._food
        cx = fx*self._CELL + self._CELL/2
        cy = fy*self._CELL + self._CELL/2
        pulse = 0.5 + 0.5*_math.sin(self._anim*5)
        pop   = _math.sin(self._food_pop*_math.pi)*0.35 if self._food_pop>0 else 0
        r = self._FOOD_R*(1 + 0.12*pulse + pop)

        g1 = QRadialGradient(cx, cy, r*3.5)
        g1.setColorAt(0, QColor(255,79,139,70)); g1.setColorAt(1, QColor(255,79,139,0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g1))
        p.drawEllipse(QRectF(cx-r*3.5, cy-r*3.5, r*7, r*7))

        gb = QRadialGradient(cx-r*0.2, cy-r*0.3, r*1.3)
        gb.setColorAt(0, QColor(255,160,180,210))
        gb.setColorAt(0.6, QColor("#ff4f8b"))
        gb.setColorAt(1, QColor(200,30,90,200))
        p.setBrush(QBrush(gb)); p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,70),1))
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        sg = QRadialGradient(cx-r*0.35, cy-r*0.4, r*0.5)
        sg.setColorAt(0, QColor(255,255,255,180)); sg.setColorAt(1, QColor(255,255,255,0))
        p.setBrush(QBrush(sg)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

    def _ph_smooth_pts(self):
        s = self._snake; t = self._interp
        cur_head = self._cpt(*s[0])
        pts = [QPointF(self._prev_head.x()+(cur_head.x()-self._prev_head.x())*t,
                       self._prev_head.y()+(cur_head.y()-self._prev_head.y())*t)]
        for i in range(1, len(s)):
            prev = self._cpt(*s[i-1]); cur = self._cpt(*s[i])
            pts.append(QPointF(prev.x()+(cur.x()-prev.x())*t,
                               prev.y()+(cur.y()-prev.y())*t))
        return pts

    def _ph_tube_path(self, pts, radius):
        from PyQt6.QtGui import QPainterPath
        n = len(pts)
        if n < 2:
            path = QPainterPath()
            path.addEllipse(QRectF(pts[0].x()-radius, pts[0].y()-radius, radius*2, radius*2))
            return path

        def sn(a, b):
            dx=b.x()-a.x(); dy=b.y()-a.y(); L=_math.hypot(dx,dy) or 1e-9
            return QPointF(-dy/L, dx/L)

        segs = [sn(pts[i], pts[i+1]) for i in range(n-1)]

        def avg(i):
            if i==0: return segs[0]
            if i==n-1: return segs[-1]
            ax=(segs[i-1].x()+segs[i].x())/2; ay=(segs[i-1].y()+segs[i].y())/2
            L=_math.hypot(ax,ay) or 1e-9; return QPointF(ax/L,ay/L)

        ns = [avg(i) for i in range(n)]
        lft = [QPointF(pts[i].x()+ns[i].x()*radius, pts[i].y()+ns[i].y()*radius) for i in range(n)]
        rgt = [QPointF(pts[i].x()-ns[i].x()*radius, pts[i].y()-ns[i].y()*radius) for i in range(n)]

        path = QPainterPath()
        path.moveTo(lft[0])
        for pt in lft[1:]: path.lineTo(pt)
        tl=pts[-1]; tn=ns[-1]
        path.arcTo(QRectF(tl.x()-radius,tl.y()-radius,radius*2,radius*2),
                   _math.degrees(_math.atan2(-tn.y(),-tn.x()))-90, 180)
        for pt in reversed(rgt): path.lineTo(pt)
        hl=pts[0]; hn=ns[0]
        path.arcTo(QRectF(hl.x()-radius,hl.y()-radius,radius*2,radius*2),
                   _math.degrees(_math.atan2(-hn.y(),-hn.x()))+90, 180)
        path.closeSubpath()
        return path

    def _ph_draw_snake(self, p):
        from PyQt6.QtGui import QPainterPath, QLinearGradient, QRadialGradient
        pts = self._ph_smooth_pts()
        if len(pts) < 2: return

        sp = self._ph_tube_path(pts, self._SNAKE_R+5)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(0,0,0,55))); p.drawPath(sp)

        bp = self._ph_tube_path(pts, self._SNAKE_R)
        bg = QLinearGradient(pts[0].x(),pts[0].y(), pts[-1].x(),pts[-1].y())
        bg.setColorAt(0, QColor("#38f5c8")); bg.setColorAt(0.5, QColor("#22d4f5")); bg.setColorAt(1, QColor("#9b6aff"))
        p.setBrush(QBrush(bg)); p.drawPath(bp)

        shine = self._ph_tube_path(pts, self._SNAKE_R*0.52)
        sg = QLinearGradient(pts[0].x(), pts[0].y()-self._SNAKE_R, pts[0].x(), pts[0].y())
        sg.setColorAt(0, QColor(255,255,255,80)); sg.setColorAt(1, QColor(255,255,255,0))
        p.setBrush(QBrush(sg)); p.drawPath(shine)

        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,45),1))
        p.drawPath(bp)

        h = pts[0]
        gl = QRadialGradient(h.x(), h.y(), self._SNAKE_R*2.6)
        gl.setColorAt(0, QColor(56,245,200,100)); gl.setColorAt(1, QColor(56,245,200,0))
        p.setBrush(QBrush(gl)); p.setPen(Qt.PenStyle.NoPen)
        r = self._SNAKE_R*2.6; p.drawEllipse(QRectF(h.x()-r, h.y()-r, r*2, r*2))

        dx,dy = self._dir; ox,oy = -dy,dx; er=3.8
        for sign in (+1,-1):
            ex=h.x()+dx*5+sign*ox*5.5; ey=h.y()+dy*5+sign*oy*5.5
            p.setBrush(QBrush(QColor(240,255,250,230))); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(ex-er,ey-er,er*2,er*2))
            p.setBrush(QBrush(QColor(10,20,40,255)))
            p.drawEllipse(QRectF(ex-er*0.5+dx*1.2,ey-er*0.5+dy*1.2,er,er))
            p.setBrush(QBrush(QColor(255,255,255,200)))
            p.drawEllipse(QRectF(ex-1+dx,ey-2+dy,2,2))

    def _ph_overlay(self, p, title, subtitle, hints):
        from PyQt6.QtGui import QPainterPath, QLinearGradient, QFontMetrics
        pw=320; ph=170; px=(self._W-pw)//2; py=(self._H-ph)//2
        bg=QLinearGradient(px,py,px,py+ph)
        bg.setColorAt(0,QColor(15,20,45,215)); bg.setColorAt(1,QColor(10,14,35,235))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(px,py,pw,ph),16,16)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255,255,255,55),1))
        p.drawRoundedRect(QRectF(px,py,pw,ph),16,16)
        sg=QLinearGradient(px,py,px,py+32); sg.setColorAt(0,QColor(255,255,255,28)); sg.setColorAt(1,QColor(255,255,255,0))
        path=QPainterPath(); path.addRoundedRect(QRectF(px,py,pw,32),16,16)
        p.setBrush(QBrush(sg)); p.setPen(Qt.PenStyle.NoPen); p.drawPath(path)

        ft=QFont("SF Pro Display,Segoe UI,Arial",24,QFont.Weight.Bold)
        fs=QFont("SF Pro Display,Segoe UI,Arial",12)
        fh=QFont("SF Pro Display,Segoe UI,Arial",9)
        fh.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,1.5)

        p.setFont(ft); p.setPen(QColor("#f0c040"))
        fm=QFontMetrics(ft); tw=fm.horizontalAdvance(title)
        p.drawText(px+(pw-tw)//2, py+48, title)
        if subtitle:
            p.setFont(fs); p.setPen(QColor(255,255,255,230))
            fm2=QFontMetrics(fs); tw2=fm2.horizontalAdvance(subtitle)
            p.drawText(px+(pw-tw2)//2, py+76, subtitle)
        p.setFont(fh); p.setPen(QColor(180,190,220,140))
        for i,h in enumerate(hints):
            fm3=QFontMetrics(fh); tw3=fm3.horizontalAdvance(h)
            p.drawText(px+(pw-tw3)//2, py+104+i*17, h)

    def closeEvent(self, e):
        self._timer.stop(); super().closeEvent(e)


# ──────────────────────────── PASSWORD MANAGER ────────────────────────────

class PasswordVault:
    """Local vault crypto using PBKDF2 + HMAC keystream (stdlib only)."""

    _MAGIC = b"nova-pm-v1"

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000, dklen=32)

    @classmethod
    def make_verifier(cls, key: bytes) -> str:
        return hmac.new(key, cls._MAGIC, hashlib.sha256).hexdigest()

    @classmethod
    def verify_key(cls, key: bytes, verifier: str) -> bool:
        expected = cls.make_verifier(key)
        return hmac.compare_digest(expected, verifier)

    @staticmethod
    def encrypt(plaintext: str, key: bytes) -> str:
        nonce = secrets.token_bytes(16)
        data = plaintext.encode("utf-8")
        keystream = b""
        counter = 0
        while len(keystream) < len(data):
            keystream += hmac.new(key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
            counter += 1
        out = bytes(data[i] ^ keystream[i] for i in range(len(data)))
        return base64.urlsafe_b64encode(nonce + out).decode("ascii")

    @staticmethod
    def decrypt(ciphertext: str, key: bytes) -> str:
        raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        nonce, enc = raw[:16], raw[16:]
        keystream = b""
        counter = 0
        while len(keystream) < len(enc):
            keystream += hmac.new(key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
            counter += 1
        out = bytes(enc[i] ^ keystream[i] for i in range(len(enc)))
        return out.decode("utf-8")

    @staticmethod
    def generate_password(length=16) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(max(8, length)))


class PasswordEntryDialog(QDialog):
    """Add or edit a vault entry."""

    def __init__(self, parent, title="", username="", url="", notes="", password=""):
        super().__init__(parent)
        self.setWindowTitle("Password Entry")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("e.g. GitHub")
        form.addRow("Title:", self.title_edit)

        self.user_edit = QLineEdit(username)
        self.user_edit.setPlaceholderText("Username or email")
        form.addRow("Username:", self.user_edit)

        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("https://…")
        form.addRow("URL:", self.url_edit)

        pass_row = QHBoxLayout()
        self.pass_edit = QLineEdit(password)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("toolbar_btn")
        gen_btn.setFixedHeight(30)
        gen_btn.clicked.connect(lambda: self.pass_edit.setText(PasswordVault.generate_password()))
        show_btn = QPushButton("Show")
        show_btn.setObjectName("toolbar_btn")
        show_btn.setFixedHeight(30)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda on: self.pass_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        pass_row.addWidget(self.pass_edit, 1)
        pass_row.addWidget(gen_btn)
        pass_row.addWidget(show_btn)
        form.addRow("Password:", pass_row)

        self.notes_edit = QTextEdit(notes)
        self.notes_edit.setMaximumHeight(90)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return (
            self.title_edit.text().strip(),
            self.user_edit.text().strip(),
            self.url_edit.text().strip(),
            self.notes_edit.toPlainText().strip(),
            self.pass_edit.text(),
        )

    def accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Password Entry", "Title is required.")
            return
        if not self.pass_edit.text():
            QMessageBox.warning(self, "Password Entry", "Password cannot be empty.")
            return
        super().accept()


class PasswordManagerPanel(QWidget):
    """Encrypted local password vault integrated into the main library view."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self._db = db
        self._key = None
        self._entries = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        self._stack = QStackedWidget()

        # ── Setup ──
        setup = QWidget()
        sl = QVBoxLayout(setup)
        sl.addStretch()
        st = QLabel("Create Password Vault")
        st.setFont(QFont("", 16, QFont.Weight.Bold))
        st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sd = QLabel(
            "Choose a master password to encrypt your saved logins.\n"
            "It cannot be recovered if forgotten."
        )
        sd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sd.setWordWrap(True)
        sf = QFormLayout()
        sf.setContentsMargins(80, 0, 80, 0)
        self._setup_pass = QLineEdit()
        self._setup_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_confirm = QLineEdit()
        self._setup_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_pass.returnPressed.connect(self._setup_confirm.setFocus)
        self._setup_confirm.returnPressed.connect(self._create_vault)
        sf.addRow("Master password:", self._setup_pass)
        sf.addRow("Confirm:", self._setup_confirm)
        create_btn = QPushButton("Create Vault")
        create_btn.setObjectName("toolbar_btn")
        create_btn.setFixedHeight(36)
        create_btn.clicked.connect(self._create_vault)
        sl.addWidget(st)
        sl.addWidget(sd)
        sl.addSpacing(12)
        sl.addLayout(sf)
        sl.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        sl.addStretch()
        self._stack.addWidget(setup)

        # ── Unlock ──
        unlock = QWidget()
        ul = QVBoxLayout(unlock)
        ul.addStretch()
        ut = QLabel("Unlock Password Vault")
        ut.setFont(QFont("", 16, QFont.Weight.Bold))
        ut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        uf = QFormLayout()
        uf.setContentsMargins(80, 0, 80, 0)
        self._unlock_pass = QLineEdit()
        self._unlock_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._unlock_pass.returnPressed.connect(self._unlock)
        uf.addRow("Master password:", self._unlock_pass)
        self._unlock_status = QLabel("")
        self._unlock_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._unlock_status.setStyleSheet("color: #e05c4a;")
        unlock_btn = QPushButton("Unlock")
        unlock_btn.setObjectName("toolbar_btn")
        unlock_btn.setFixedHeight(36)
        unlock_btn.clicked.connect(self._unlock)
        ul.addWidget(ut)
        ul.addSpacing(12)
        ul.addLayout(uf)
        ul.addWidget(self._unlock_status)
        ul.addWidget(unlock_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        reset_btn = QPushButton("Reset vault…")
        reset_btn.setObjectName("toolbar_btn")
        reset_btn.setFlat(True)
        reset_btn.setStyleSheet("color: #e05c4a;")
        reset_btn.clicked.connect(self._reset_vault)
        ul.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        ul.addStretch()
        self._stack.addWidget(unlock)

        # ── Main vault ──
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("⌕  Search entries…")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._load_entries)
        add_btn = QPushButton("+  Add")
        add_btn.setObjectName("toolbar_btn")
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_entry)
        lock_btn = QPushButton("⛨  Lock")
        lock_btn.setObjectName("toolbar_btn")
        lock_btn.setFixedHeight(34)
        lock_btn.clicked.connect(self.lock)
        toolbar.addWidget(self._search, 1)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(lock_btn)
        ml.addLayout(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._list = SmoothListWidget()
        self._list.setSpacing(2)
        self._list.currentRowChanged.connect(self._show_entry)
        split.addWidget(self._list)

        detail = QFrame()
        detail.setObjectName("right_panel")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(16, 16, 16, 16)
        dl.setSpacing(8)
        self._d_title = QLabel("Select an entry")
        self._d_title.setFont(QFont("", 14, QFont.Weight.Bold))
        self._d_title.setWordWrap(True)
        self._d_user = QLabel("")
        self._d_url = QLabel("")
        self._d_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._d_url.setOpenExternalLinks(True)
        self._d_pass = QLineEdit()
        self._d_pass.setReadOnly(True)
        self._d_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._d_notes = QTextEdit()
        self._d_notes.setReadOnly(True)
        self._d_notes.setMaximumHeight(120)
        dl.addWidget(self._d_title)
        dl.addWidget(self._d_user)
        dl.addWidget(self._d_url)
        dl.addWidget(QLabel("Password:"))
        dl.addWidget(self._d_pass)
        dl.addWidget(QLabel("Notes:"))
        dl.addWidget(self._d_notes)

        btn_row = QHBoxLayout()
        self._show_pass_btn = QPushButton("Show")
        self._show_pass_btn.setObjectName("toolbar_btn")
        self._show_pass_btn.setCheckable(True)
        self._show_pass_btn.toggled.connect(self._toggle_pass_visibility)
        copy_user = QPushButton("Copy User")
        copy_user.setObjectName("toolbar_btn")
        copy_user.clicked.connect(lambda: self._copy_field("user"))
        copy_pass = QPushButton("Copy Pass")
        copy_pass.setObjectName("toolbar_btn")
        copy_pass.clicked.connect(lambda: self._copy_field("pass"))
        open_url = QPushButton("Open URL")
        open_url.setObjectName("toolbar_btn")
        open_url.clicked.connect(self._open_url)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("toolbar_btn")
        edit_btn.clicked.connect(self._edit_entry)
        del_btn = QPushButton("Delete")
        del_btn.setObjectName("toolbar_btn")
        del_btn.clicked.connect(self._delete_entry)
        for b in (self._show_pass_btn, copy_user, copy_pass, open_url, edit_btn, del_btn):
            btn_row.addWidget(b)
        dl.addLayout(btn_row)
        dl.addStretch()
        split.addWidget(detail)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        ml.addWidget(split, 1)
        self._stack.addWidget(main)

        root.addWidget(self._stack)

    def refresh(self):
        status = self._db.pm_vault_status()
        if status == "unset":
            self._stack.setCurrentIndex(0)
        elif status == "corrupt":
            self._key = None
            self._unlock_status.setText(
                "Vault data is corrupted. Reset the vault to start over."
            )
            self._stack.setCurrentIndex(1)
        elif not self._key:
            self._unlock_status.setText("")
            self._unlock_pass.clear()
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(2)
            self._load_entries()

    def lock(self):
        self._key = None
        self._selected_id = None
        self._unlock_pass.clear()
        self._unlock_status.setText("")
        self.refresh()

    def is_unlocked(self):
        return self._key is not None

    def _create_vault(self):
        p1 = self._setup_pass.text()
        p2 = self._setup_confirm.text()
        if len(p1) < 8:
            QMessageBox.warning(self, "Password Vault", "Master password must be at least 8 characters.")
            return
        if p1 != p2:
            QMessageBox.warning(self, "Password Vault", "Passwords do not match.")
            return
        salt = secrets.token_bytes(16)
        key = PasswordVault.derive_key(p1, salt)
        self._db.pm_init(
            base64.urlsafe_b64encode(salt).decode("ascii"),
            PasswordVault.make_verifier(key),
        )
        self._key = key
        self._setup_pass.clear()
        self._setup_confirm.clear()
        self.refresh()

    def _unlock(self):
        password = self._unlock_pass.text()
        if not password:
            self._unlock_status.setText("Enter your master password.")
            return
        if self._db.pm_vault_status() == "corrupt":
            self._unlock_status.setText(
                "Vault data is corrupted. Use «Reset vault…» below."
            )
            return
        try:
            salt = self._db.pm_get_salt()
        except Exception:
            self._unlock_status.setText(
                "Vault data is corrupted. Use «Reset vault…» below."
            )
            return
        key = PasswordVault.derive_key(password, salt)
        if not PasswordVault.verify_key(key, self._db.pm_get_verifier()):
            self._unlock_status.setText("Incorrect master password.")
            return
        self._key = key
        self._unlock_pass.clear()
        self._unlock_status.setText("")
        self.refresh()

    def _reset_vault(self):
        if QMessageBox.warning(
            self,
            "Reset Password Vault",
            "Delete the vault and all saved passwords?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._db.pm_reset_vault()
        self._key = None
        self._selected_id = None
        self._setup_pass.clear()
        self._setup_confirm.clear()
        self._unlock_pass.clear()
        self._unlock_status.setText("")
        self.refresh()

    def _load_entries(self):
        if not self._key:
            return
        query = self._search.text().strip()
        self._entries = self._db.pm_get_entries(query)
        self._list.blockSignals(True)
        self._list.clear()
        for row in self._entries:
            eid, title, username, *_ = row
            sub = f"  ·  {username}" if username else ""
            item = QListWidgetItem(f"{title}{sub}")
            item.setData(Qt.ItemDataRole.UserRole, eid)
            self._list.addItem(item)
        self._list.blockSignals(False)
        if self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._clear_detail()

    def _entry_by_id(self, eid):
        for row in self._entries:
            if row[0] == eid:
                return row
        return self._db.pm_get_entry(eid)

    def _decrypt_password(self, enc):
        try:
            return PasswordVault.decrypt(enc, self._key)
        except Exception:
            return ""

    def _show_entry(self, row):
        if row < 0 or row >= len(self._entries):
            self._clear_detail()
            return
        entry = self._entries[row]
        eid, title, username, url, notes, enc, created, updated = entry
        self._selected_id = eid
        self._d_title.setText(title)
        self._d_user.setText(f"Username: {username}" if username else "Username: —")
        if url:
            safe = url.replace('"', "%22")
            self._d_url.setText(f'<a href="{safe}">{url}</a>')
        else:
            self._d_url.setText("")
        self._d_pass.setText(self._decrypt_password(enc))
        self._d_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._show_pass_btn.setChecked(False)
        self._d_notes.setPlainText(notes or "")

    def _clear_detail(self):
        self._selected_id = None
        self._d_title.setText("Select an entry")
        self._d_user.setText("")
        self._d_url.setText("")
        self._d_pass.clear()
        self._d_notes.clear()

    def _toggle_pass_visibility(self, show):
        self._d_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        )

    def _copy_field(self, field):
        if field == "user":
            text = self._d_user.text().replace("Username: ", "", 1)
            if text == "—":
                text = ""
        else:
            text = self._d_pass.text()
        if text:
            QApplication.clipboard().setText(text)

    def _open_url(self):
        row = self._entry_by_id(self._selected_id) if self._selected_id else None
        if not row or not row[3]:
            return
        url = row[3]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        QDesktopServices.openUrl(QUrl(url))

    def _add_entry(self):
        dlg = PasswordEntryDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        title, username, url, notes, password = dlg.values()
        enc = PasswordVault.encrypt(password, self._key)
        self._db.pm_add_entry(title, username, url, notes, enc)
        self._load_entries()

    def _edit_entry(self):
        if not self._selected_id:
            return
        row = self._entry_by_id(self._selected_id)
        if not row:
            return
        eid, title, username, url, notes, enc, *_ = row
        dlg = PasswordEntryDialog(
            self, title, username, url, notes, self._decrypt_password(enc)
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        title, username, url, notes, password = dlg.values()
        self._db.pm_update_entry(
            eid, title, username, url, notes, PasswordVault.encrypt(password, self._key)
        )
        self._load_entries()

    def _delete_entry(self):
        if not self._selected_id:
            return
        row = self._entry_by_id(self._selected_id)
        if not row:
            return
        if QMessageBox.question(
            self, "Delete Entry", f"Delete «{row[1]}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._db.pm_delete_entry(self._selected_id)
        self._selected_id = None
        self._load_entries()


# ──────────────────────────────────────────────────────────────────────────────


# ─────────────────────── AUTO-UPDATER HELPERS ───────────────────────────────

import hashlib as _hashlib
import urllib.request as _urllib_req

_NOVA_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_config.json")
_NOVA_VERSION = "7.1.3"
_NOVA_UPDATE_URL = (
    "https://raw.githubusercontent.com/NovaX7-Universal/NovaX7/main/NovaX7_7_1_0.py"
)


def _get_nova_script_path():
    """Absolute path to the .py file the user started — updated in-place on update."""
    if sys.argv:
        candidate = os.path.abspath(sys.argv[0])
        if candidate.lower().endswith(".py") and os.path.isfile(candidate):
            return candidate
    return os.path.abspath(__file__)


def _apply_script_update(script_path, new_content):
    """Replace the contents of an existing .py file (no new file with another name)."""
    import tempfile
    script_path = os.path.abspath(script_path)
    if not script_path.lower().endswith(".py"):
        raise ValueError(f"Kein Python-Skript: {script_path}")
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Datei nicht gefunden: {script_path}")

    backup_path = script_path + ".backup"
    shutil.copy2(script_path, backup_path)

    dir_name = os.path.dirname(script_path) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=dir_name, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        os.replace(tmp_path, script_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        # Fallback: direct overwrite of the running file
        with open(script_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)

    return script_path, backup_path


def _load_nova_config():
    if os.path.exists(_NOVA_CONFIG):
        try:
            with open(_NOVA_CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_nova_config(cfg):
    with open(_NOVA_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _file_hash(path):
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_github_raw(raw_url, token):
    import time
    base = raw_url.split("?")[0]
    url = f"{base}?t={int(time.time())}"
    req = _urllib_req.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw",
            "User-Agent": "NovaX7-Updater/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    with _urllib_req.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def _fetch_public_update(url=None):
    """Download latest NovaX7 from the public GitHub repo (no token required)."""
    import time
    base = (url or _NOVA_UPDATE_URL).split("?")[0]
    req = _urllib_req.Request(
        f"{base}?t={int(time.time())}",
        headers={
            "User-Agent": "NovaX7-Updater/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with _urllib_req.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def _parse_semver(text):
    import re
    if not text:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(text))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _format_semver(parts):
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def _compare_semver(a, b):
    """Return -1 if a<b, 0 if equal, 1 if a>b."""
    if a == b:
        return 0
    return 1 if a > b else -1


def _parse_version_from_source(source):
    import re
    for line in source.splitlines()[:20]:
        if line.startswith("# Version:"):
            raw = line.split(":", 1)[1].strip()
            parts = _parse_semver(raw)
            return _format_semver(parts) if parts else raw
    m = re.search(r'_NOVA_VERSION\s*=\s*["\']([^"\']+)["\']', source)
    if m:
        parts = _parse_semver(m.group(1))
        return _format_semver(parts) if parts else m.group(1).strip()
    return ""


def _get_installed_version():
    """Read semver from the running script file (falls back to _NOVA_VERSION)."""
    try:
        path = _get_nova_script_path()
        with open(path, encoding="utf-8") as f:
            chunk = f.read(12000)
        ver = _parse_version_from_source(chunk)
        if ver:
            parts = _parse_semver(ver)
            if parts:
                return _format_semver(parts)
    except Exception:
        pass
    parts = _parse_semver(_NOVA_VERSION)
    return _format_semver(parts) if parts else _NOVA_VERSION


def _fetch_update_source():
    """Fetch latest Nova script from GitHub (always cache-busted)."""
    cfg = _load_nova_config()
    raw_url = cfg.get("github_raw_url", "").strip()
    token = cfg.get("github_token", "").strip()
    # Public repo: always use cache-busted raw URL (avoids stale CDN copies).
    if not raw_url or "NovaX7-Universal/NovaX7" in raw_url:
        return _fetch_public_update(_NOVA_UPDATE_URL)
    if token:
        return _fetch_github_raw(raw_url, token)
    return _fetch_public_update(_NOVA_UPDATE_URL)


# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent, db, current_theme):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings")
        self.setMinimumSize(560, 560)
        self.resize(580, 620)
        layout = QVBoxLayout()

        tabs = QTabWidget()

        # ── Appearance ────────────────────────────────────────────────────────
        appear_scroll = QScrollArea()
        appear_scroll.setWidgetResizable(True)
        appear_scroll.setFrameShape(QFrame.Shape.NoFrame)
        appear_inner = QWidget()
        appear_layout = QFormLayout(appear_inner)
        appear_layout.setSpacing(10)
        appear_layout.setContentsMargins(8, 8, 8, 8)

        # ── Theme combo ──────────────────────────────────────────────────────
        self.theme_combo = QComboBox()
        for t in THEMES:
            self.theme_combo.addItem(t)
        self.theme_combo.addItem("✏  Custom …")
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        appear_layout.addRow("Theme:", self.theme_combo)

        # ── Liquid Glass toggle button ────────────────────────────────────────
        _lg_active = (current_theme == "Liquid Glass")
        self._lg_btn = QPushButton(
            "✨  Liquid Glass  —  aktiv" if _lg_active else "✨  Liquid Glass aktivieren"
        )
        self._lg_btn.setCheckable(True)
        self._lg_btn.setChecked(_lg_active)
        self._lg_btn.setFixedHeight(32)
        _lg_on_style  = (
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(91,141,238,200), stop:1 rgba(160,100,255,180));"
            "color: #eef2ff; border: 1px solid rgba(255,255,255,60);"
            "border-radius: 10px; font-weight: 700; font-size: 12px; padding: 4px 14px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(111,161,255,220), stop:1 rgba(180,120,255,200)); }"
        )
        _lg_off_style = (
            "QPushButton { background: rgba(255,255,255,10);"
            "color: #8892b0; border: 1px solid rgba(255,255,255,28);"
            "border-radius: 10px; font-weight: 600; font-size: 12px; padding: 4px 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,20); color: #eef2ff; }"
        )
        self._lg_btn.setStyleSheet(_lg_on_style if _lg_active else _lg_off_style)

        def _toggle_lg(checked):
            if checked:
                self.theme_combo.setCurrentText("Liquid Glass")
                self._lg_btn.setText("✨  Liquid Glass  —  aktiv")
                self._lg_btn.setStyleSheet(_lg_on_style)
            else:
                # Switch back to Midnight when toggled off
                self.theme_combo.setCurrentText("Midnight")
                self._lg_btn.setText("✨  Liquid Glass aktivieren")
                self._lg_btn.setStyleSheet(_lg_off_style)

        self._lg_btn.toggled.connect(_toggle_lg)
        # Keep button in sync if user changes combo manually
        def _combo_changed_lg(name):
            self._lg_btn.blockSignals(True)
            if name == "Liquid Glass":
                self._lg_btn.setChecked(True)
                self._lg_btn.setText("✨  Liquid Glass  —  aktiv")
                self._lg_btn.setStyleSheet(_lg_on_style)
            else:
                self._lg_btn.setChecked(False)
                self._lg_btn.setText("✨  Liquid Glass aktivieren")
                self._lg_btn.setStyleSheet(_lg_off_style)
            self._lg_btn.blockSignals(False)
        self.theme_combo.currentTextChanged.connect(_combo_changed_lg)
        appear_layout.addRow("", self._lg_btn)

        # ── Font combo with live preview ────────────────────────────────────
        font_row = QHBoxLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setMaxVisibleItems(20)
        self.font_combo.setEditable(False)
        cur_font = db.get_setting("ui_font", "Arial")
        self.font_combo.setCurrentFont(QFont(cur_font))
        self._font_preview = QLabel("Aa – Nova Player 123")
        self._font_preview.setMinimumWidth(150)
        self._font_preview.setMaximumWidth(180)
        self._font_preview.setStyleSheet(
            "border:1px solid #444; border-radius:4px; padding:3px 6px;"
        )
        self._update_font_preview()
        self.font_combo.currentFontChanged.connect(self._update_font_preview)
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(self._font_preview)
        appear_layout.addRow("Font:", font_row)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 28)
        self.font_size_spin.setValue(int(db.get_setting("font_size", "13")))
        self.font_size_spin.setSuffix(" pt")
        appear_layout.addRow("Font Size:", self.font_size_spin)

        self.zoom_combo = QComboBox()
        for z in ZOOM_LEVELS:
            self.zoom_combo.addItem(f"{z}%", z)
        cur_zoom = int(db.get_setting("ui_zoom", "100"))
        idx = self.zoom_combo.findData(cur_zoom)
        if idx >= 0:
            self.zoom_combo.setCurrentIndex(idx)
        appear_layout.addRow("UI Zoom:", self.zoom_combo)

        self.show_covers = QCheckBox()
        self.show_covers.setChecked(db.get_setting("show_covers", "1") == "1")
        appear_layout.addRow("Show Cover Thumbnails:", self.show_covers)

        self.compact_mode = QCheckBox()
        self.compact_mode.setChecked(db.get_setting("compact_mode", "0") == "1")
        appear_layout.addRow("Compact List Mode:", self.compact_mode)

        # ── Divider ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        appear_layout.addRow(sep)

        # ── Custom Color Overrides ───────────────────────────────────────────
        _color_label = QLabel("🎨  Custom Color Overrides")
        _color_label.setStyleSheet("font-weight:bold; margin-top:4px;")
        appear_layout.addRow(_color_label)

        # Helper: build a color-picker button row
        def _make_color_row(setting_key, fallback_color):
            btn = QPushButton()
            btn.setFixedSize(32, 22)
            btn.setToolTip("Click to pick a color")
            reset = QPushButton("✕")
            reset.setFixedSize(24, 22)
            reset.setToolTip("Reset to theme default")
            saved = db.get_setting(setting_key, "")
            color = saved if saved else fallback_color
            btn.setStyleSheet(f"background:{color}; border:1px solid #555; border-radius:3px;")
            btn._current_color = color

            def _pick(checked=False, b=btn, key=setting_key):
                from PyQt6.QtWidgets import QColorDialog
                c = QColorDialog.getColor(QColor(b._current_color), self, "Pick Color")
                if c.isValid():
                    b._current_color = c.name()
                    b.setStyleSheet(
                        f"background:{c.name()}; border:1px solid #555; border-radius:3px;"
                    )

            def _reset(checked=False, b=btn, fb=fallback_color):
                b._current_color = fb
                b.setStyleSheet(f"background:{fb}; border:1px solid #555; border-radius:3px;")

            btn.clicked.connect(_pick)
            reset.clicked.connect(_reset)
            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(btn)
            row.addWidget(reset)
            row.addStretch()
            return row, btn

        theme_now = THEMES.get(current_theme, THEMES["Midnight"])

        self._color_accent_row, self._color_accent_btn = _make_color_row(
            "custom_accent", theme_now["accent"])
        appear_layout.addRow("Accent Color:", self._color_accent_row)

        self._color_accent2_row, self._color_accent2_btn = _make_color_row(
            "custom_accent2", theme_now["accent2"])
        appear_layout.addRow("Accent 2 Color:", self._color_accent2_row)

        self._color_bg_row, self._color_bg_btn = _make_color_row(
            "custom_bg", theme_now["bg"])
        appear_layout.addRow("Background:", self._color_bg_row)

        self._color_sidebar_row, self._color_sidebar_btn = _make_color_row(
            "custom_sidebar", theme_now["sidebar"])
        appear_layout.addRow("Sidebar Color:", self._color_sidebar_row)

        self._color_card_row, self._color_card_btn = _make_color_row(
            "custom_card", theme_now["card"])
        appear_layout.addRow("Card / Panel:", self._color_card_row)

        self._color_panel_row, self._color_panel_btn = _make_color_row(
            "custom_panel", theme_now.get("panel", theme_now["bg"]))
        appear_layout.addRow("Bottom Bar / Panel:", self._color_panel_row)

        self._color_text_row, self._color_text_btn = _make_color_row(
            "custom_text", theme_now["text"])
        appear_layout.addRow("Text Color:", self._color_text_row)

        self._color_subtext_row, self._color_subtext_btn = _make_color_row(
            "custom_subtext", theme_now["subtext"])
        appear_layout.addRow("Subtext Color:", self._color_subtext_row)

        # ── Reset all custom colors ──────────────────────────────────────────
        reset_all_btn = QPushButton("↺  Reset all custom colors to theme default")
        reset_all_btn.setFixedHeight(26)

        def _reset_all_colors():
            t = THEMES.get(self.theme_combo.currentText(), THEMES["Midnight"])
            pairs = [
                (self._color_accent_btn,  t["accent"]),
                (self._color_accent2_btn, t["accent2"]),
                (self._color_bg_btn,      t["bg"]),
                (self._color_sidebar_btn, t["sidebar"]),
                (self._color_panel_btn,   t.get("panel", t["bg"])),
                (self._color_card_btn,    t["card"]),
                (self._color_text_btn,    t["text"]),
                (self._color_subtext_btn, t["subtext"]),
            ]
            for btn, col in pairs:
                btn._current_color = col
                btn.setStyleSheet(f"background:{col}; border:1px solid #555; border-radius:3px;")

        reset_all_btn.clicked.connect(_reset_all_colors)
        appear_layout.addRow("", reset_all_btn)

        # ── Divider ─────────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        appear_layout.addRow(sep2)

        # ── Border Radius ────────────────────────────────────────────────────
        self.border_radius_spin = QSpinBox()
        self.border_radius_spin.setRange(0, 20)
        self.border_radius_spin.setValue(int(db.get_setting("border_radius", "6")))
        self.border_radius_spin.setSuffix(" px")
        self.border_radius_spin.setToolTip("Border radius for buttons, cards, etc.")
        appear_layout.addRow("Border Radius:", self.border_radius_spin)

        # ── Sidebar Width ────────────────────────────────────────────────────
        self.sidebar_width_spin = QSpinBox()
        self.sidebar_width_spin.setRange(140, 320)
        self.sidebar_width_spin.setValue(int(db.get_setting("sidebar_width", "200")))
        self.sidebar_width_spin.setSuffix(" px")
        self.sidebar_width_spin.setToolTip("Width of the left sidebar")
        appear_layout.addRow("Sidebar Width:", self.sidebar_width_spin)

        # ── Player Panel Width ────────────────────────────────────────────────
        self.player_width_spin = QSpinBox()
        self.player_width_spin.setRange(200, 460)
        self.player_width_spin.setValue(int(db.get_setting("player_width", "290")))
        self.player_width_spin.setSuffix(" px")
        self.player_width_spin.setToolTip("Width of the right player panel")
        appear_layout.addRow("Player Panel Width:", self.player_width_spin)

        # ── Show statusbar ────────────────────────────────────────────────────
        self.show_statusbar = QCheckBox()
        self.show_statusbar.setChecked(db.get_setting("show_statusbar", "1") == "1")
        appear_layout.addRow("Show Status Bar:", self.show_statusbar)

        appear_inner.setLayout(appear_layout)
        appear_scroll.setWidget(appear_inner)
        tabs.addTab(appear_scroll, "Appearance")

        # --- Playback ---
        play_tab = QWidget()
        play_layout = QFormLayout()

        self.auto_next = QCheckBox()
        self.auto_next.setChecked(db.get_setting("auto_next", "1") == "1")
        play_layout.addRow("Auto-play Next Song:", self.auto_next)

        self.crossfade_spin = QSpinBox()
        self.crossfade_spin.setRange(0, 10)
        self.crossfade_spin.setValue(int(db.get_setting("crossfade", "0")))
        self.crossfade_spin.setSuffix("s")
        play_layout.addRow("Crossfade:", self.crossfade_spin)

        self.default_vol = QSpinBox()
        self.default_vol.setRange(0, 100)
        self.default_vol.setValue(int(db.get_setting("default_volume", "80")))
        self.default_vol.setSuffix("%")
        play_layout.addRow("Default Volume:", self.default_vol)

        self.extract_covers = QCheckBox()
        self.extract_covers.setChecked(db.get_setting("extract_covers", "1") == "1")
        play_layout.addRow("Auto-extract Embedded Covers:", self.extract_covers)

        # Discord Rich Presence
        self.discord_rpc = QCheckBox()
        self.discord_rpc.setChecked(db.get_setting("discord_rpc", "0") == "1")
        self.discord_rpc.setToolTip(
            "Zeigt den aktuell spielenden Song in deinem Discord-Status an.\n"
            "Benötigt: pip install pypresence"
            + ("" if _PYPRESENCE_AVAILABLE else "\n⚠ pypresence ist nicht installiert!")
        )
        if not _PYPRESENCE_AVAILABLE:
            self.discord_rpc.setEnabled(False)
            self.discord_rpc.setToolTip("pypresence nicht installiert – führe aus:\npip install pypresence")
        play_layout.addRow("Discord Rich Presence:", self.discord_rpc)

        play_tab.setLayout(play_layout)
        tabs.addTab(play_tab, "Playback")

        # --- Library ---
        lib_tab = QWidget()
        lib_layout = QFormLayout()

        self.watch_folder = QLineEdit(db.get_setting("watch_folder", ""))
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self.browse_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.watch_folder)
        folder_row.addWidget(browse_btn)
        lib_layout.addRow("Auto-import Folder:", folder_row)

        self.remember_pos = QCheckBox()
        self.remember_pos.setChecked(db.get_setting("remember_pos", "0") == "1")
        lib_layout.addRow("Remember Playback Position:", self.remember_pos)

        # Browser start URL
        self.browser_home_url = QLineEdit(db.get_setting("browser_home_url", "https://www.google.com"))
        self.browser_home_url.setPlaceholderText("https://www.google.com")
        lib_layout.addRow("Browser-Startseite:", self.browser_home_url)

        lib_tab.setLayout(lib_layout)
        tabs.addTab(lib_tab, "Library")

        # --- Keyboard Shortcuts ---
        kb_tab = QWidget()
        kb_layout = QVBoxLayout()
        shortcuts_text = QTextEdit()
        shortcuts_text.setReadOnly(True)
        shortcuts_text.setPlainText(
            "Space        — Play / Pause\n"
            "Left         — Rewind 5 seconds\n"
            "Right        — Forward 5 seconds\n"
            "Ctrl+Right   — Next Song\n"
            "Ctrl+Left    — Previous Song\n"
            "Ctrl+Up      — Volume Up\n"
            "Ctrl+Down    — Volume Down\n"
            "Ctrl+L       — Toggle Loop\n"
            "Ctrl+S       — Toggle Shuffle\n"
            "Ctrl+F       — Focus Search\n"
            "Ctrl+I       — Import Files\n"
            "Delete       — Remove Song from View\n"
            "F5           — Refresh Library\n"
            "F11          — Fenster Vollbild ein/aus\n"
        )
        kb_layout.addWidget(shortcuts_text)
        kb_tab.setLayout(kb_layout)
        tabs.addTab(kb_tab, "Shortcuts")

        # --- Extras (Code eingeben) ---
        extras_tab = QWidget()
        extras_layout = QVBoxLayout()
        extras_layout.setContentsMargins(16, 20, 16, 16)
        extras_layout.setSpacing(12)

        extras_title = QLabel("🔑  Code einlösen")
        extras_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        extras_layout.addWidget(extras_title)

        extras_desc = QLabel("Gib hier einen Code ein, um zusätzliche Funktionen freizuschalten.")
        extras_desc.setWordWrap(True)
        extras_desc.setStyleSheet("color: #888; font-size: 12px;")
        extras_layout.addWidget(extras_desc)

        code_row = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Code eingeben …")
        self.code_input.setMaxLength(64)
        self.code_input.setFixedHeight(36)
        self.code_input.setStyleSheet(
            "QLineEdit { border: 1px solid #555; border-radius: 6px; padding: 4px 10px; font-size: 14px; }"
            "QLineEdit:focus { border-color: #7c6af7; }"
        )
        self.code_input.returnPressed.connect(self._redeem_code)

        redeem_btn = QPushButton("Einlösen")
        redeem_btn.setFixedHeight(36)
        redeem_btn.setFixedWidth(100)
        redeem_btn.setStyleSheet(
            "QPushButton { border-radius: 6px; padding: 4px 14px; font-weight: bold; }"
            "QPushButton:hover { opacity: 0.85; }"
        )
        redeem_btn.clicked.connect(self._redeem_code)

        code_row.addWidget(self.code_input)
        code_row.addWidget(redeem_btn)
        extras_layout.addLayout(code_row)

        self._code_status = QLabel("")
        self._code_status.setWordWrap(True)
        self._code_status.setStyleSheet("font-size: 12px; min-height: 20px;")
        extras_layout.addWidget(self._code_status)

        extras_layout.addStretch()
        extras_tab.setLayout(extras_layout)
        tabs.addTab(extras_tab, "Extras")

        # --- Update Tab ---
        update_tab = QWidget()
        update_layout = QVBoxLayout()
        update_layout.setContentsMargins(16, 20, 16, 16)
        update_layout.setSpacing(10)

        upd_title = QLabel("🔄  NovaX7 Updater")
        upd_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        update_layout.addWidget(upd_title)

        _cfg = _load_nova_config()
        _uses_private = bool(_cfg.get("github_token") and _cfg.get("github_raw_url"))
        upd_desc = QLabel(
            f"Installierte Version: <b>{_get_installed_version()}</b><br>"
            "Updates werden direkt aus Nova geladen — kein <code>nova_updater.py</code> "
            "oder <code>nova_upload.py</code> nötig."
            + ("<br><small>Privates GitHub-Repo aus nova_config.json wird verwendet.</small>"
               if _uses_private else
               "<br><small>Quelle: NovaX7-Universal/NovaX7 auf GitHub</small>")
        )
        upd_desc.setWordWrap(True)
        upd_desc.setTextFormat(Qt.TextFormat.RichText)
        upd_desc.setStyleSheet("font-size:12px; color:#8892b0;")
        update_layout.addWidget(upd_desc)

        self._upd_status = QLabel("")
        self._upd_status.setWordWrap(True)
        self._upd_status.setStyleSheet("font-size:12px; min-height:20px;")
        update_layout.addWidget(self._upd_status)

        upd_btn = QPushButton("🔄  Jetzt updaten")
        upd_btn.setFixedHeight(42)
        upd_btn.setStyleSheet(
            "QPushButton { border-radius:8px; padding:6px 18px; font-weight:bold; font-size:14px; }"
        )
        upd_btn.clicked.connect(self._check_and_apply_update)
        update_layout.addWidget(upd_btn)

        update_layout.addStretch()
        update_tab.setLayout(update_layout)
        tabs.addTab(update_tab, "Update")

        layout.addWidget(tabs)

        # ── Bottom button row: Reset All  |  spacer  |  Save  Cancel ─────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)

        reset_all_settings_btn = QPushButton("↺  Reset All Settings")
        reset_all_settings_btn.setToolTip(
            "Resets every setting to its factory default.\n"
            "The dialog stays open so you can review before saving."
        )
        reset_all_settings_btn.setStyleSheet(
            "QPushButton { color: #e05c4a; border: 1px solid #e05c4a55; "
            "border-radius: 6px; padding: 5px 14px; }"
            "QPushButton:hover { background: #e05c4a22; }"
        )
        reset_all_settings_btn.clicked.connect(self._reset_all_settings)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)

        btn_row.addWidget(reset_all_settings_btn)
        btn_row.addStretch()
        btn_row.addWidget(btns)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _update_font_preview(self, *_):
        font = self.font_combo.currentFont()
        font.setPointSize(11)
        self._font_preview.setFont(font)
        self._font_preview.setText(f"Aa – {font.family()[:14]}")

    def _on_theme_changed(self, name):
        """When a base theme is selected, update the color picker buttons to match."""
        t = THEMES.get(name)
        if not t:
            return
        pairs = [
            (self._color_accent_btn,  t["accent"]),
            (self._color_accent2_btn, t["accent2"]),
            (self._color_bg_btn,      t["bg"]),
            (self._color_sidebar_btn, t["sidebar"]),
            (self._color_panel_btn,   t.get("panel", t["bg"])),
            (self._color_card_btn,    t["card"]),
            (self._color_text_btn,    t["text"]),
            (self._color_subtext_btn, t["subtext"]),
        ]
        for btn, col in pairs:
            btn._current_color = col
            btn.setStyleSheet(f"background:{col}; border:1px solid #555; border-radius:3px;")

    def _check_and_apply_update(self):
        self._upd_status.setStyleSheet("font-size:12px; color:#8892b0;")
        self._upd_status.setText("⏳ Suche nach Updates…")
        QApplication.processEvents()

        try:
            remote_code = _fetch_update_source()
        except Exception as e:
            self._upd_status.setStyleSheet("font-size:12px; color:#e05c4a;")
            self._upd_status.setText(f"✗ Download fehlgeschlagen: {e}")
            return

        if not remote_code.strip().startswith("# Version:"):
            self._upd_status.setStyleSheet("font-size:12px; color:#e05c4a;")
            self._upd_status.setText("✗ Ungültige Update-Datei vom Server erhalten.")
            return

        current_hash = _file_hash(_get_nova_script_path())
        remote_hash  = _hashlib.sha256(remote_code.encode("utf-8")).hexdigest()
        local_ver = _get_installed_version()
        remote_ver = _parse_version_from_source(remote_code) or "?"
        local_parts = _parse_semver(local_ver)
        remote_parts = _parse_semver(remote_ver)

        if current_hash == remote_hash:
            self._upd_status.setStyleSheet("font-size:12px; color:#38f5c8;")
            self._upd_status.setText(f"✓ Bereits aktuell (Version {local_ver}).")
            return

        if local_parts and remote_parts and _compare_semver(remote_parts, local_parts) <= 0:
            self._upd_status.setStyleSheet("font-size:12px; color:#38f5c8;")
            self._upd_status.setText(
                f"✓ Bereits aktuell — installiert: {local_ver}, "
                f"Server: {remote_ver} (kein Downgrade)."
            )
            return

        script_path = _get_nova_script_path()
        reply = QMessageBox.question(
            self, "Update verfügbar",
            f"Neue Version gefunden: {remote_ver}\n"
            f"Aktuell installiert: {local_ver}\n\n"
            f"Die bestehende Datei wird ersetzt:\n{script_path}\n\n"
            "Nova wird aktualisiert und neu gestartet.\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._upd_status.setStyleSheet("font-size:12px; color:#8892b0;")
            self._upd_status.setText("Update abgebrochen.")
            return

        self._upd_status.setText(f"⏳ Ersetze Inhalt von {os.path.basename(script_path)}…")
        QApplication.processEvents()

        try:
            updated_path, backup_path = _apply_script_update(script_path, remote_code)
        except Exception as e:
            self._upd_status.setStyleSheet("font-size:12px; color:#e05c4a;")
            self._upd_status.setText(f"✗ Schreibfehler: {e}")
            return

        self._upd_status.setStyleSheet("font-size:12px; color:#38f5c8;")
        self._upd_status.setText(
            f"✓ {os.path.basename(updated_path)} aktualisiert "
            f"(Backup: {os.path.basename(backup_path)}). Nova startet neu…"
        )
        QApplication.processEvents()
        import subprocess as _sp
        _sp.Popen([sys.executable, updated_path])
        QApplication.quit()

    def _reset_all_settings(self):
        """Reset every control in the dialog to its factory default (no DB write yet)."""
        if QMessageBox.question(
            self, "Reset All Settings",
            "Reset all settings to factory defaults?\n\nChanges are not saved until you click Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        # ── Appearance ────────────────────────────────────────────────────────
        self.theme_combo.setCurrentText("Midnight")
        self.font_combo.setCurrentFont(QFont("Arial"))
        self.font_size_spin.setValue(13)
        zoom_idx = self.zoom_combo.findData(100)
        if zoom_idx >= 0:
            self.zoom_combo.setCurrentIndex(zoom_idx)
        self.show_covers.setChecked(True)
        self.compact_mode.setChecked(False)
        self.border_radius_spin.setValue(6)
        self.sidebar_width_spin.setValue(200)
        self.player_width_spin.setValue(290)
        self.show_statusbar.setChecked(True)
        # Reset all color pickers to Midnight defaults
        self._on_theme_changed("Midnight")

        # ── Playback ──────────────────────────────────────────────────────────
        self.auto_next.setChecked(True)
        self.crossfade_spin.setValue(0)
        self.default_vol.setValue(80)
        self.extract_covers.setChecked(True)
        if self.discord_rpc.isEnabled():
            self.discord_rpc.setChecked(False)

        # ── Library ───────────────────────────────────────────────────────────
        self.watch_folder.setText("")
        self.remember_pos.setChecked(False)
        self.browser_home_url.setText("https://www.google.com")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Watch Folder")
        if folder:
            self.watch_folder.setText(folder)

    def save(self):
        self.db.set_setting("theme", self.theme_combo.currentText())
        self.db.set_setting("ui_font", self.font_combo.currentFont().family())
        self.db.set_setting("font_size", self.font_size_spin.value())
        self.db.set_setting("ui_zoom", self.zoom_combo.currentData())
        self.db.set_setting("show_covers", "1" if self.show_covers.isChecked() else "0")
        self.db.set_setting("compact_mode", "1" if self.compact_mode.isChecked() else "0")
        # Custom color overrides
        self.db.set_setting("custom_accent",  self._color_accent_btn._current_color)
        self.db.set_setting("custom_accent2", self._color_accent2_btn._current_color)
        self.db.set_setting("custom_bg",      self._color_bg_btn._current_color)
        self.db.set_setting("custom_sidebar", self._color_sidebar_btn._current_color)
        self.db.set_setting("custom_panel",   self._color_panel_btn._current_color)
        self.db.set_setting("custom_card",    self._color_card_btn._current_color)
        self.db.set_setting("custom_text",    self._color_text_btn._current_color)
        self.db.set_setting("custom_subtext", self._color_subtext_btn._current_color)
        # Layout tweaks
        self.db.set_setting("border_radius",  self.border_radius_spin.value())
        self.db.set_setting("sidebar_width",  self.sidebar_width_spin.value())
        self.db.set_setting("player_width",   self.player_width_spin.value())
        self.db.set_setting("show_statusbar", "1" if self.show_statusbar.isChecked() else "0")
        self.db.set_setting("auto_next", "1" if self.auto_next.isChecked() else "0")
        self.db.set_setting("crossfade", self.crossfade_spin.value())
        self.db.set_setting("default_volume", self.default_vol.value())
        self.db.set_setting("extract_covers", "1" if self.extract_covers.isChecked() else "0")
        self.db.set_setting("discord_rpc", "1" if self.discord_rpc.isChecked() else "0")
        self.db.set_setting("watch_folder", self.watch_folder.text())
        self.db.set_setting("remember_pos", "1" if self.remember_pos.isChecked() else "0")
        url = self.browser_home_url.text().strip()
        if url and not url.startswith("http"):
            url = "https://" + url
        self.db.set_setting("browser_home_url", url or "https://www.google.com")
        self.accept()

    def _redeem_code(self):
        """Code einlösen."""
        code = self.code_input.text().strip()
        if not code:
            self._code_status.setStyleSheet("color: #e05c4a; font-size: 12px;")
            self._code_status.setText("⚠  Bitte einen Code eingeben.")
            return

        # ── DIPPEN → Snake Easter Egg ────────────────────────────────────────
        if code.upper() == "DIPPEN":
            self.code_input.clear()
            self._code_status.setStyleSheet("color: #38f5c8; font-size: 12px;")
            self._code_status.setText("🐍  Snake freigeschaltet!")
            game = SnakeWindow(self)
            game.exec()
            return

        # ── FFPM → Block Blast Easter Egg ─────────────────────────────────────
        if code.upper() == "FFPM":
            self.code_input.clear()
            self._code_status.setStyleSheet("color: #A78BFA; font-size: 12px;")
            self._code_status.setText("🎮  Block Blast freigeschaltet!")
            game = BlockBlastWindow(self)
            game.exec()
            return

        # ── Unbekannter Code ──────────────────────────────────────────────────
        self.code_input.clear()
        self._code_status.setStyleSheet("color: #e05c4a; font-size: 12px;")
        self._code_status.setText(f"✗  Unbekannter Code: «{code}»")


        # ── Unbekannter Code ──────────────────────────────────────────────────
        self.code_input.clear()
        self._code_status.setStyleSheet("color: #e05c4a; font-size: 12px;")
        self._code_status.setText(f"✗  Unbekannter Code: «{code}»")


# ──────────────────────────── GLOBAL HOTKEY THREAD ────────────────────────────

class GlobalHotkeyThread(QThread):
    triggered = pyqtSignal()

    def __init__(self, key_code):
        super().__init__()
        self.key_code = key_code
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        import ctypes
        from ctypes import wintypes
        HOTKEY_ID = 2026
        # Unregister just in case
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        # Register VK key code (0 is no modifiers)
        res = ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, 0, self.key_code)
        
        msg = wintypes.MSG()
        while self.running:
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1): # PM_REMOVE = 1
                if msg.message == 0x0312: # WM_HOTKEY
                    if msg.wParam == HOTKEY_ID:
                        self.triggered.emit()
                elif msg.message == 0x0012: # WM_QUIT
                    break
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            self.msleep(20)
            
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)


# ──────────────────────────── AUTOCLICKER THREAD ────────────────────────────

class AutoclickerThread(QThread):
    click_sent = pyqtSignal(int)
    stopped = pyqtSignal()

    def __init__(self, interval_ms, button, click_type):
        super().__init__()
        self.interval = interval_ms / 1000.0
        self.button = button
        self.click_type = click_type
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        import ctypes
        import time
        
        clicks = 0
        btn_str = self.button.lower()
        if 'left' in btn_str:
            down = 0x0002
            up = 0x0004
        elif 'right' in btn_str:
            down = 0x0008
            up = 0x0010
        else:
            down = 0x0020
            up = 0x0040

        while self.running:
            if 'double' in self.click_type.lower():
                ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
                time.sleep(0.01)
                ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
            else:
                ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
                
            clicks += 1
            self.click_sent.emit(clicks)
            
            sleep_left = self.interval
            while sleep_left > 0 and self.running:
                step = min(0.01, sleep_left)
                time.sleep(step)
                sleep_left -= step
                
        self.stopped.emit()


# ──────────────────────────── AUTOCLICKER PANEL ────────────────────────────

class AutoclickerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_thread = None
        self.hotkey_thread = None
        self.clicks_count = 0
        self.coords = None
        self._build_ui()
        self.start_hotkey_listener()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(16)
        
        title_box = QHBoxLayout()
        title_icon = QLabel("🖱")
        title_icon.setFont(QFont("Segoe UI", 20))
        title_lbl = QLabel("Auto Clicker")
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_box.addWidget(title_icon)
        title_box.addWidget(title_lbl)
        title_box.addStretch()
        self.main_layout.addLayout(title_box)
        
        desc = QLabel("Automate repetitive mouse clicks. Configure the options below and toggle the state with the global hotkey.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8892b0; font-size: 13px;")
        self.main_layout.addWidget(desc)
        
        # Click Interval
        interval_card = QFrame()
        interval_card.setObjectName("extra_card")
        interval_layout = QVBoxLayout(interval_card)
        interval_layout.setSpacing(10)
        
        int_title = QLabel("⏱  Click Interval")
        int_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        interval_layout.addWidget(int_title)
        
        spin_row = QHBoxLayout()
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setSuffix(" h")
        self.mins_spin = QSpinBox()
        self.mins_spin.setRange(0, 59)
        self.mins_spin.setSuffix(" m")
        self.secs_spin = QSpinBox()
        self.secs_spin.setRange(0, 59)
        self.secs_spin.setSuffix(" s")
        self.ms_spin = QSpinBox()
        self.ms_spin.setRange(1, 999999)
        self.ms_spin.setValue(100)
        self.ms_spin.setSuffix(" ms")
        
        spin_row.addWidget(self.hours_spin)
        spin_row.addWidget(self.mins_spin)
        spin_row.addWidget(self.secs_spin)
        spin_row.addWidget(self.ms_spin)
        interval_layout.addLayout(spin_row)
        self.main_layout.addWidget(interval_card)
        
        # Click Options
        options_card = QFrame()
        options_card.setObjectName("extra_card")
        options_layout = QFormLayout(options_card)
        options_layout.setSpacing(12)
        
        opt_title = QLabel("⚙  Click Options")
        opt_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        options_layout.addRow(opt_title, QLabel(""))
        
        self.btn_combo = QComboBox()
        self.btn_combo.addItems(["Left Click", "Right Click", "Middle Click"])
        options_layout.addRow("Mouse Button:", self.btn_combo)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Single Click", "Double Click"])
        options_layout.addRow("Click Type:", self.type_combo)
        
        self.main_layout.addWidget(options_card)
        
        # Hotkey Setup
        hotkey_card = QFrame()
        hotkey_card.setObjectName("extra_card")
        hotkey_layout = QHBoxLayout(hotkey_card)
        
        hk_title = QLabel("⌨  Toggle Hotkey:")
        hk_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.hk_combo = QComboBox()
        self.hk_combo.addItems([f"F{i}" for i in range(1, 13)])
        self.hk_combo.setCurrentText("F2")
        self.hk_combo.currentTextChanged.connect(self.start_hotkey_listener)
        
        hotkey_layout.addWidget(hk_title)
        hotkey_layout.addWidget(self.hk_combo)
        hotkey_layout.addStretch()
        self.main_layout.addWidget(hotkey_card)
        
        # Control Card
        control_card = QFrame()
        control_card.setObjectName("extra_card")
        control_layout = QHBoxLayout(control_card)
        
        self.status_lbl = QLabel("Status: Idle")
        self.status_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        
        self.toggle_btn = QPushButton("▶  Start (F2)")
        self.toggle_btn.setObjectName("action_btn")
        self.toggle_btn.setFixedSize(140, 36)
        self.toggle_btn.clicked.connect(self.toggle_clicking)
        
        control_layout.addWidget(self.status_lbl)
        control_layout.addStretch()
        control_layout.addWidget(self.toggle_btn)
        self.main_layout.addWidget(control_card)
        self.main_layout.addStretch()
        
        self.apply_theme_styles()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def apply_theme_styles(self):
        t = self.window().theme if hasattr(self.window(), "theme") else {
            "card": "#181824", "border": "#27273a", "accent": "#5b8dee", "text": "#e8ecf4"
        }
        card_style = f"""
            QFrame#extra_card {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 12px;
                padding: 12px;
            }}
            QLabel {{
                background: transparent;
            }}
        """
        self.setStyleSheet(card_style)
        self.update_toggle_btn_style()

    def update_toggle_btn_style(self):
        t = self.window().theme if hasattr(self.window(), "theme") else {
            "accent": "#5b8dee", "border": "#27273a", "text": "#e8ecf4"
        }
        is_running = self.active_thread is not None
        if is_running:
            style = """
                QPushButton#action_btn {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ef4444, stop:1 #b91c1c);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton#action_btn:hover {
                    filter: brightness(1.1);
                }
            """
        else:
            style = f"""
                QPushButton#action_btn {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t['accent']}, stop:1 {t.get('accent2', t['accent'])});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }}
                QPushButton#action_btn:hover {{
                    filter: brightness(1.1);
                }}
            """
        self.toggle_btn.setStyleSheet(style)

    def toggle_clicking(self):
        if self.active_thread:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        if self.active_thread:
            return
            
        interval_ms = (
            self.hours_spin.value() * 3600000 +
            self.mins_spin.value() * 60000 +
            self.secs_spin.value() * 1000 +
            self.ms_spin.value()
        )
        
        button = self.btn_combo.currentText()
        click_type = self.type_combo.currentText()
        
        self.clicks_count = 0
        self.status_lbl.setText("Status: Running (0 clicks)")
        
        self.active_thread = AutoclickerThread(interval_ms, button, click_type)
        self.active_thread.click_sent.connect(self.on_click_sent)
        self.active_thread.stopped.connect(self.stop_clicking)
        self.active_thread.start()
        
        hk = self.hk_combo.currentText()
        self.toggle_btn.setText(f"■  Stop ({hk})")
        self.update_toggle_btn_style()

    def stop_clicking(self):
        if not self.active_thread:
            return
        self.active_thread.stop()
        self.active_thread.wait()
        self.active_thread = None
        
        self.status_lbl.setText(f"Status: Stopped (Total: {self.clicks_count} clicks)")
        hk = self.hk_combo.currentText()
        self.toggle_btn.setText(f"▶  Start ({hk})")
        self.update_toggle_btn_style()

    def on_click_sent(self, count):
        self.clicks_count = count
        self.status_lbl.setText(f"Status: Running ({count} clicks)")

    def start_hotkey_listener(self, *args):
        if self.hotkey_thread:
            self.hotkey_thread.stop()
            self.hotkey_thread.wait()
            self.hotkey_thread = None
            
        hk = self.hk_combo.currentText()
        HOTKEYS = {
            "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
            "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B
        }
        vk = HOTKEYS.get(hk, 0x71)
        
        self.toggle_btn.setText(f"▶  Start ({hk})" if not self.active_thread else f"■  Stop ({hk})")
        
        self.hotkey_thread = GlobalHotkeyThread(vk)
        self.hotkey_thread.triggered.connect(self.toggle_clicking)
        self.hotkey_thread.start()

    def closeEvent(self, event):
        if self.active_thread:
            self.active_thread.stop()
            self.active_thread.wait()
        if self.hotkey_thread:
            self.hotkey_thread.stop()
            self.hotkey_thread.wait()
        super().closeEvent(event)


# ──────────────────────────── EXTRAS PANEL ────────────────────────────

class ExtrasPanel(QWidget):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.parent_player = parent
        self.db = db
        self._build_ui()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(10)

        # Navigation Bar
        self.top_bar = QHBoxLayout()
        self.back_btn = QPushButton("←  Back")
        self.back_btn.setObjectName("toolbar_btn")
        self.back_btn.setFixedWidth(80)
        self.back_btn.setFixedHeight(30)
        self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self.show_dashboard)
        
        self.title_label = QLabel("⚡  Extras")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        self.top_bar.addWidget(self.back_btn)
        self.top_bar.addWidget(self.title_label)
        self.top_bar.addStretch()
        self.layout.addLayout(self.top_bar)

        self.stack = QStackedWidget()
        
        # Dashboard View
        self.dashboard = QWidget()
        self.dash_layout = QVBoxLayout(self.dashboard)
        self.dash_layout.setContentsMargins(0, 10, 0, 0)
        
        grid = QGridLayout()
        grid.setSpacing(16)
        
        self.card_autoclicker = self._create_card(
            "🖱", "Auto Clicker",
            "Automate repetitive mouse clicks with high speed. Toggle globally with F2 or hotkeys.",
            self.open_autoclicker
        )
        self.card_password = self._create_card(
            "⛨", "Password Vault",
            "Store, edit, and fill your logins and passwords securely using local AES-256 encryption.",
            self.open_password_vault
        )
        self.card_coming = self._create_card(
            "⚙", "More Coming Soon",
            "Future updates will bring more productivity and automation tools right here.",
            None, disabled=True
        )
        
        grid.addWidget(self.card_autoclicker, 0, 0)
        grid.addWidget(self.card_password, 0, 1)
        grid.addWidget(self.card_coming, 1, 0)
        
        self.dash_layout.addLayout(grid)
        self.dash_layout.addStretch()
        
        self.stack.addWidget(self.dashboard)
        
        # Autoclicker View
        self.autoclicker_view = AutoclickerPanel(self)
        self.stack.addWidget(self.autoclicker_view)
        
        # Password Vault View
        self.password_vault_view = PasswordManagerPanel(self.parent_player, self.db)
        self.stack.addWidget(self.password_vault_view)
        
        self.layout.addWidget(self.stack)
        
    def _create_card(self, icon, title, desc, callback, disabled=False):
        card = QFrame()
        card.setObjectName("extras_card")
        
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(8)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI", 24))
        lay.addWidget(icon_lbl)
        
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lay.addWidget(title_lbl)
        
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #8892b0; font-size: 12px;")
        lay.addWidget(desc_lbl)
        
        lay.addStretch()
        
        t = self.parent_player.theme if hasattr(self.parent_player, "theme") else {
            "card": "#181824", "border": "#27273a", "accent": "#5b8dee", "text": "#e8ecf4"
        }
        
        if disabled:
            card.setStyleSheet(f"""
                QFrame#extras_card {{
                    background-color: {t['card']};
                    border: 1px solid {t['border']};
                    border-radius: 12px;
                    opacity: 0.5;
                }}
            """)
        else:
            card.setStyleSheet(f"""
                QFrame#extras_card {{
                    background-color: {t['card']};
                    border: 1px solid {t['border']};
                    border-radius: 12px;
                }}
                QFrame#extras_card:hover {{
                    border-color: {t['accent']};
                    background-color: {t['highlight']};
                }}
            """)
            if callback:
                card.mouseReleaseEvent = lambda event: callback()
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                
        return card

    def show_dashboard(self):
        self.top_bar.setContentsMargins(0, 0, 0, 0)
        self.back_btn.setVisible(False)
        self.title_label.setText("⚡  Extras")
        
        if self.stack.currentIndex() == 2:
            self.password_vault_view.lock()
            
        self.stack.setCurrentIndex(0)
        self.parent_player.status_label.setText("Extras  ·  Utility tools")

    def open_autoclicker(self):
        self.back_btn.setVisible(True)
        self.title_label.setText("🖱  Auto Clicker")
        self.stack.setCurrentIndex(1)
        self.parent_player.status_label.setText("Auto Clicker  ·  Automate clicking tasks")
        self.autoclicker_view.apply_theme_styles()

    def open_password_vault(self):
        self.back_btn.setVisible(True)
        self.title_label.setText("⛨  Password Vault")
        self.stack.setCurrentIndex(2)
        self.password_vault_view.refresh()
        self.parent_player.status_label.setText("Password Manager  ·  Encrypted local vault")


# ──────────────────────────── THUMBNAIL WORKER ────────────────────────────

class ThumbnailWorker(QThread):
    """Generates missing video thumbnails in a background thread."""
    thumbnail_ready = pyqtSignal(int, str)   # (list_row_index, thumb_path)
    thumbnail_saved = pyqtSignal(int, str)   # (vid_id, thumb_path) — for DB update

    def __init__(self, tasks):
        super().__init__()
        # tasks: list of (row_index, vid_id, video_path)
        self.tasks = tasks
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for row, vid_id, path in self.tasks:
            if self._stop:
                break
            if not os.path.exists(path):
                continue
            thumb = extract_video_thumbnail(path)
            if thumb:
                self.thumbnail_ready.emit(row, thumb)
                self.thumbnail_saved.emit(vid_id, thumb)


def extract_video_thumbnail(video_path, out_dir=None):
    """Extract a single frame from a video as thumbnail. Returns path or None."""
    # On Windows, hide the console window for every subprocess call
    _no_window = {}
    if os.name == "nt":
        _no_window = {"creationflags": subprocess.CREATE_NO_WINDOW}

    try:
        if out_dir is None:
            out_dir = os.path.join(os.path.dirname(video_path), ".nova_covers")
        os.makedirs(out_dir, exist_ok=True)
        thumb_path = os.path.join(out_dir, Path(video_path).stem + "_thumb.jpg")
        if os.path.exists(thumb_path):
            return thumb_path
        # Try ffmpeg first
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True,
                    **_no_window
                )
                if result.returncode == 0:
                    ffmpeg = result.stdout.strip()
            except Exception:
                pass
        if ffmpeg and os.path.exists(ffmpeg):
            subprocess.run(
                [ffmpeg, "-y", "-i", video_path, "-ss", "00:00:03", "-vframes", "1",
                 "-vf", "scale=240:-1", thumb_path],
                capture_output=True,
                **_no_window
            )
            if os.path.exists(thumb_path):
                return thumb_path
    except Exception as e:
        print(f"Thumbnail error: {e}")
    return None


# ──────────────────────────── CONVERT THREAD ────────────────────────────

class ConvertThread(QThread):
    progress_signal = pyqtSignal(str)
    percent_signal  = pyqtSignal(int)   # 0-100; -1 = unknown
    finished_signal = pyqtSignal(bool, str, str)

    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path

    def run(self):
        try:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                try:
                    result = subprocess.run(
                        [sys.executable, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        ffmpeg = result.stdout.strip()
                except Exception:
                    pass

            if not ffmpeg or not os.path.exists(ffmpeg):
                self.finished_signal.emit(False, "",
                    "ffmpeg not found.\n\nInstall via:\n"
                    f"  {sys.executable} -m pip install imageio-ffmpeg\n"
                    "or: winget install ffmpeg / brew install ffmpeg / apt install ffmpeg")
                return

            self.progress_signal.emit(f"Converting: {os.path.basename(self.input_path)}")
            self.progress_signal.emit(f"→ {os.path.basename(self.output_path)}")

            # ── Probe total duration for progress calculation ──────────
            total_secs = 0.0
            try:
                ffprobe = shutil.which("ffprobe") or os.path.join(
                    os.path.dirname(ffmpeg), "ffprobe" + (".exe" if sys.platform == "win32" else "")
                )
                if ffprobe and os.path.exists(ffprobe):
                    probe = subprocess.run(
                        [ffprobe, "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", self.input_path],
                        capture_output=True, text=True, timeout=15
                    )
                    total_secs = float(probe.stdout.strip()) if probe.returncode == 0 else 0.0
            except Exception:
                total_secs = 0.0

            in_ext  = Path(self.input_path).suffix.lower()
            out_ext = Path(self.output_path).suffix.lower()

            in_is_video = in_ext in SUPPORTED_VIDEO_FORMATS
            out_is_video = out_ext in SUPPORTED_VIDEO_FORMATS
            in_is_audio = in_ext in SUPPORTED_FORMATS
            out_is_audio = out_ext in SUPPORTED_FORMATS

            # ── Audio codec for output format ──────────────────────────
            def _audio_codec(ext):
                """Return -c:a flags for the given output extension."""
                if ext == ".mp3":
                    return ["-c:a", "libmp3lame", "-b:a", "192k", "-q:a", "2"]
                elif ext in (".m4a", ".mp4", ".mov", ".m4v"):
                    return ["-c:a", "aac", "-b:a", "192k"]
                elif ext == ".flac":
                    return ["-c:a", "flac"]
                elif ext == ".wav":
                    return ["-c:a", "pcm_s16le"]
                elif ext in (".ogg", ".webm"):
                    return ["-c:a", "libopus", "-b:a", "128k"]
                elif ext == ".aac":
                    return ["-c:a", "aac", "-b:a", "192k"]
                elif ext in (".mkv", ".avi"):
                    return ["-c:a", "aac", "-b:a", "192k"]
                else:
                    return ["-c:a", "aac", "-b:a", "192k"]

            # ── Detect best available H.264 encoder once ──────────────
            hw_codec, hw_extra = _detect_hw_encoder(ffmpeg)
            self.progress_signal.emit(f"🎬 Encoder: {hw_codec}")

            def _h264_flags(out_ext, codec=None, extra=None):
                """H.264 video flags using best available encoder.
                -profile:v / -level are libx264-only; HW encoders reject them."""
                c = codec or hw_codec
                e = extra if extra is not None else hw_extra
                flags = ["-c:v", c] + e + ["-pix_fmt", "yuv420p"]
                if c == "libx264":
                    flags += ["-crf", "18", "-profile:v", "high", "-level", "4.0"]
                if out_ext in (".mp4", ".mov", ".m4v"):
                    flags += ["-movflags", "+faststart"]
                return flags

            def _h264_flags_cpu(out_ext):
                """Always use libx264 CPU fallback — used when HW encoder fails."""
                return _h264_flags(out_ext, codec="libx264", extra=["-preset", "veryfast"])

            # ── Build command ──────────────────────────────────────────
            # All paths use -threads 0 (auto CPU threads) for speed.
            # video→video always maps v+a explicitly so audio is never dropped
            # regardless of input container (webm, mkv, avi, etc.).

            if in_is_video and out_is_audio:
                # video → audio: extract audio, drop video
                cmd = [ffmpeg, "-y", "-i", self.input_path,
                       "-map", "0:a:0",
                       "-vn"]
                cmd += _audio_codec(out_ext)
                cmd += ["-threads", "0", self.output_path]

            elif in_is_audio and out_is_video:
                # audio → video: black 1280×720 canvas + H.264+AAC
                cmd = [ffmpeg, "-y",
                       "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=25",
                       "-i", self.input_path,
                       "-map", "0:v", "-map", "1:a"]
                cmd += _h264_flags(out_ext)
                cmd += ["-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-threads", "0",
                        self.output_path]

            elif in_is_video and out_is_video:
                # video → video
                # -map 0:v:0  → first video stream
                # -map 0:a:0  → first audio stream (hard, not optional)
                cmd = [ffmpeg, "-y", "-i", self.input_path,
                       "-map", "0:v:0",
                       "-map", "0:a:0"]
                if out_ext == ".webm":
                    cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "33",
                            "-deadline", "realtime", "-cpu-used", "8",
                            "-c:a", "libopus", "-b:a", "128k"]
                elif out_ext == ".avi":
                    cmd += ["-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-vtag", "xvid",
                            "-c:a", "libmp3lame", "-b:a", "192k"]
                else:
                    # mp4 / mkv / mov — hardware H.264 + AAC
                    cmd += _h264_flags(out_ext)
                    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
                cmd += ["-threads", "0", self.output_path]

                # Fallback: if the input has no audio stream at all, retry without audio map
                self._cmd_fallback = [ffmpeg, "-y", "-i", self.input_path,
                                      "-map", "0:v:0", "-an"]
                if out_ext == ".webm":
                    self._cmd_fallback += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "33",
                                           "-deadline", "realtime", "-cpu-used", "8"]
                elif out_ext == ".avi":
                    self._cmd_fallback += ["-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-vtag", "xvid"]
                else:
                    self._cmd_fallback += _h264_flags(out_ext)
                self._cmd_fallback += ["-threads", "0", self.output_path]

            else:
                # audio → audio
                cmd = [ffmpeg, "-y", "-i", self.input_path,
                       "-map", "0:a:0"]
                cmd += _audio_codec(out_ext)
                cmd += ["-threads", "0", self.output_path]

            # ── Run ───────────────────────────────────────────────────
            import re as _re
            _time_re = _re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")

            # ffmpeg writes progress to stderr; stdout is separate.
            # Use stderr=PIPE so we can parse time= lines for progress.
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace"
            )

            def _read_stderr():
                for raw in proc.stderr:
                    line = raw.rstrip()
                    if not line:
                        continue
                    # Parse  time=HH:MM:SS.xx  for progress
                    m = _time_re.search(line)
                    if m and total_secs > 0:
                        h, mn, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                        elapsed = h * 3600 + mn * 60 + s + cs / 100.0
                        pct = min(int(elapsed / total_secs * 100), 99)
                        self.percent_signal.emit(pct)
                        self.progress_signal.emit(f"[{pct:3d}%] {line[:100]}")
                    else:
                        self.progress_signal.emit(line[:120])

            import threading as _threading
            stderr_thread = _threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            # stdout is usually empty for ffmpeg but drain it anyway
            for raw in proc.stdout:
                pass

            proc.wait()
            stderr_thread.join(timeout=5)

            def _run_cmd(cmd_to_run, label=""):
                """Run an ffmpeg command, stream stderr for progress, return returncode."""
                p = subprocess.Popen(
                    cmd_to_run,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace"
                )
                def _drain():
                    for raw in p.stderr:
                        line = raw.rstrip()
                        if not line:
                            continue
                        m = _time_re.search(line)
                        if m and total_secs > 0:
                            h2, mn2, s2, cs2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                            elapsed2 = h2 * 3600 + mn2 * 60 + s2 + cs2 / 100.0
                            pct2 = min(int(elapsed2 / total_secs * 100), 99)
                            self.percent_signal.emit(pct2)
                            self.progress_signal.emit(f"[{pct2:3d}%] {line[:100]}")
                        else:
                            self.progress_signal.emit(line[:120])
                t = _threading.Thread(target=_drain, daemon=True)
                t.start()
                for _ in p.stdout:
                    pass
                p.wait()
                t.join(timeout=5)
                return p.returncode

            rc = _run_cmd(cmd)

            # ── Fallback chain ─────────────────────────────────────────
            if rc != 0 and hw_codec != "libx264" and in_is_video and out_is_video:
                # HW encoder failed (e.g. unsupported profile/format for this container).
                # Rebuild command with CPU libx264 and retry.
                self.progress_signal.emit(f"⚠ {hw_codec} failed (code {rc}) — retrying with libx264…")
                self.percent_signal.emit(-1)
                cpu_cmd = [ffmpeg, "-y", "-i", self.input_path,
                           "-map", "0:v:0", "-map", "0:a:0"]
                if out_ext == ".webm":
                    cpu_cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "33",
                                "-deadline", "realtime", "-cpu-used", "8",
                                "-c:a", "libopus", "-b:a", "128k"]
                elif out_ext == ".avi":
                    cpu_cmd += ["-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-vtag", "xvid",
                                "-c:a", "libmp3lame", "-b:a", "192k"]
                else:
                    cpu_cmd += _h264_flags_cpu(out_ext)
                    cpu_cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
                cpu_cmd += ["-threads", "0", self.output_path]
                rc = _run_cmd(cpu_cmd)

            if rc != 0 and hasattr(self, "_cmd_fallback"):
                # Audio-stream fallback: input has no audio track → retry without -map 0:a:0
                self.progress_signal.emit("⚠ No audio stream found — retrying without audio…")
                self.percent_signal.emit(-1)
                rc = _run_cmd(self._cmd_fallback)

            if rc == 0 and os.path.exists(self.output_path):
                self.finished_signal.emit(True, self.output_path, "")
            else:
                self.finished_signal.emit(False, "", f"ffmpeg exited with code {rc}")
        except Exception as e:
            self.finished_signal.emit(False, "", str(e))


# ──────────────────────────── CONVERT DIALOG ────────────────────────────

# ──────────────────────────── QUICK-TABS EDITOR ────────────────────────────

DEFAULT_QUICK_TABS = [
    ("▶ YouTube",    "https://www.youtube.com"),
    ("♪ SoundCloud", "https://soundcloud.com"),
    ("🎵 Spotify",   "https://open.spotify.com"),
    ("📱 TikTok",    "https://www.tiktok.com"),
    ("🎮 Twitch",    "https://www.twitch.tv"),
    ("🎸 Bandcamp",  "https://bandcamp.com"),
    ("🎬 Vimeo",     "https://vimeo.com"),
]

QUICK_TABS_DB_KEY = "browser_quick_tabs"


def load_quick_tabs(db):
    """Load quick-tabs from DB; fall back to defaults if not set."""
    raw = db.get_setting(QUICK_TABS_DB_KEY, "") if db else ""
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and all(isinstance(i, list) and len(i) == 2 for i in data):
                return [tuple(i) for i in data]
        except Exception:
            pass
    return list(DEFAULT_QUICK_TABS)


def save_quick_tabs(db, tabs):
    """Persist quick-tabs to DB."""
    if db:
        db.set_setting(QUICK_TABS_DB_KEY, json.dumps(tabs, ensure_ascii=False))


class QuickTabsEditorDialog(QDialog):
    """Edit, add, remove, and reorder browser quick-tabs."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("⚙  Schnell-Tabs bearbeiten")
        self.setMinimumSize(500, 420)

        self._tabs = list(load_quick_tabs(db))  # [(label, url), …]

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("Schnell-Tabs — Reihenfolge, Labels und URLs anpassen")
        hdr.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(hdr)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.list_widget, 1)

        self._refresh_list()

        # Buttons row
        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕  Hinzufügen")
        add_btn.clicked.connect(self._add)
        edit_btn = QPushButton("✏  Bearbeiten")
        edit_btn.clicked.connect(self._edit_selected)
        remove_btn = QPushButton("🗑  Entfernen")
        remove_btn.clicked.connect(self._remove)
        up_btn = QPushButton("▲")
        up_btn.setFixedWidth(36)
        up_btn.clicked.connect(self._move_up)
        down_btn = QPushButton("▼")
        down_btn.setFixedWidth(36)
        down_btn.clicked.connect(self._move_down)
        reset_btn = QPushButton("↺  Standard")
        reset_btn.clicked.connect(self._reset)
        for b in (add_btn, edit_btn, remove_btn, up_btn, down_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        # OK / Cancel
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._save_and_accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    # ── helpers ──────────────────────────────────────────────────────────

    def _refresh_list(self):
        self.list_widget.clear()
        for label, url in self._tabs:
            item = QListWidgetItem(f"{label}   —   {url}")
            item.setData(Qt.ItemDataRole.UserRole, (label, url))
            self.list_widget.addItem(item)

    def _sync_from_list(self):
        """Read current order from list_widget (handles drag-drop)."""
        self._tabs = [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
        ]

    def _selected_row(self):
        rows = self.list_widget.selectedIndexes()
        return rows[0].row() if rows else -1

    # ── actions ──────────────────────────────────────────────────────────

    def _add(self):
        dlg = _QuickTabEntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._sync_from_list()
            self._tabs.append((dlg.label, dlg.url))
            self._refresh_list()

    def _edit_selected(self, _item=None):
        row = self._selected_row()
        if row < 0:
            return
        self._sync_from_list()
        label, url = self._tabs[row]
        dlg = _QuickTabEntryDialog(self, label, url)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._tabs[row] = (dlg.label, dlg.url)
            self._refresh_list()
            self.list_widget.setCurrentRow(row)

    def _remove(self):
        row = self._selected_row()
        if row < 0:
            return
        self._sync_from_list()
        self._tabs.pop(row)
        self._refresh_list()

    def _move_up(self):
        row = self._selected_row()
        if row <= 0:
            return
        self._sync_from_list()
        self._tabs.insert(row - 1, self._tabs.pop(row))
        self._refresh_list()
        self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._selected_row()
        self._sync_from_list()
        if row < 0 or row >= len(self._tabs) - 1:
            return
        self._tabs.insert(row + 1, self._tabs.pop(row))
        self._refresh_list()
        self.list_widget.setCurrentRow(row + 1)

    def _reset(self):
        if QMessageBox.question(
            self, "Zurücksetzen", "Standard-Tabs wiederherstellen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._tabs = list(DEFAULT_QUICK_TABS)
            self._refresh_list()

    def _save_and_accept(self):
        self._sync_from_list()
        save_quick_tabs(self.db, self._tabs)
        self.accept()


class _QuickTabEntryDialog(QDialog):
    """Single-tab label + URL input."""

    def __init__(self, parent, label="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Tab bearbeiten")
        self.setFixedSize(420, 160)
        self.label = label
        self.url = url

        form = QFormLayout(self)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._label_edit = QLineEdit(label)
        self._label_edit.setPlaceholderText("z.B.  ▶ YouTube")
        form.addRow("Bezeichnung:", self._label_edit)

        self._url_edit = QLineEdit(url)
        self._url_edit.setPlaceholderText("https://www.youtube.com")
        form.addRow("URL:", self._url_edit)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def _accept(self):
        self.label = self._label_edit.text().strip() or self._url_edit.text().strip()
        self.url = self._url_edit.text().strip()
        if not self.url:
            return
        if not self.url.startswith(("http://", "https://")):
            self.url = "https://" + self.url
        self.accept()



class ConvertDialog(DropAcceptMixin, QDialog):
    def __init__(self, parent, db, input_path=None):
        super().__init__(parent)
        self.db = db
        self.worker = None
        self._drop_mode = "single"
        self.setWindowTitle("Convert Audio / Video")
        self.setFixedSize(580, 500)
        layout = QVBoxLayout()
        layout.setSpacing(12)

        header = QLabel("🔄  Convert Audio ↔ Video")
        header.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel("Convert between audio and video formats using ffmpeg.\n"
                      "Video → Audio: extracts audio track.\n"
                      "Audio → Video: wraps audio in a black-screen video container.\n"
                      "Video → Video / Audio → Audio: re-encodes.")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Input
        in_row = QHBoxLayout()
        in_label = QLabel("Input file:")
        in_label.setFixedWidth(80)
        self.in_edit = QLineEdit(input_path or "")
        self.in_edit.setReadOnly(True)
        self.in_edit.setPlaceholderText("Select or drag a file…")
        in_browse = QPushButton("Browse")
        in_browse.setFixedWidth(70)
        in_browse.clicked.connect(self.browse_input)
        in_row.addWidget(in_label)
        in_row.addWidget(self.in_edit, 1)
        in_row.addWidget(in_browse)
        layout.addLayout(in_row)
        # Enable drag & drop: dropped files go to the input field
        self._drop_input_widget = self.in_edit
        self._init_drop()

        # Output format
        fmt_row = QHBoxLayout()
        fmt_label = QLabel("Output format:")
        fmt_label.setFixedWidth(100)
        self.fmt_combo = QComboBox()
        all_fmts = [".mp3", ".m4a", ".flac", ".wav", ".ogg", ".mp4", ".mkv", ".avi", ".webm", ".mov"]
        self.fmt_combo.addItems([f.lstrip(".") for f in all_fmts])
        self.fmt_combo.setCurrentText("mp3")
        self.fmt_combo.setFixedWidth(100)
        fmt_row.addWidget(fmt_label)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # Output path
        out_row = QHBoxLayout()
        out_label = QLabel("Save to:")
        out_label.setFixedWidth(80)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Auto-set from input + format")
        self.out_edit.textChanged.connect(lambda _: None)  # allow manual edits
        out_browse = QPushButton("Browse")
        out_browse.setFixedWidth(70)
        out_browse.clicked.connect(self.browse_output)
        out_row.addWidget(out_label)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        layout.addLayout(out_row)

        self.fmt_combo.currentTextChanged.connect(self._auto_output_path)
        if input_path:
            self._auto_output_path()

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(130)
        self.log.setPlaceholderText("Conversion log…")
        layout.addWidget(self.log)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.convert_btn = QPushButton("🔄  Convert")
        self.convert_btn.setFixedHeight(38)
        self.convert_btn.clicked.connect(self.start_convert)
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(38)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.convert_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def browse_input(self):
        all_exts = SUPPORTED_FORMATS + SUPPORTED_VIDEO_FORMATS
        filter_str = "Media Files (" + " ".join(f"*{e}" for e in all_exts) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", filter_str)
        if path:
            self.in_edit.setText(path)
            self._auto_output_path()

    def browse_output(self):
        fmt = self.fmt_combo.currentText()
        # Suggest the auto-path as default, but let the user override it
        default = self.out_edit.text() or ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output File", default,
            f"{fmt.upper()} Files (*.{fmt});;All Files (*.*)"
        )
        if path:
            # Ensure the chosen path has the correct extension
            if not path.lower().endswith(f".{fmt}"):
                path = str(Path(path).with_suffix(f".{fmt}"))
            self.out_edit.setText(path)

    def _auto_output_path(self):
        inp = self.in_edit.text()
        if not inp:
            return
        fmt = self.fmt_combo.currentText()
        out = str(Path(inp).with_suffix(f".converted.{fmt}"))
        # Always overwrite if the current value looks like a previously auto-generated path
        current = self.out_edit.text()
        if not current or ".converted." in current:
            self.out_edit.setText(out)

    def log_message(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def start_convert(self):
        inp = self.in_edit.text().strip()
        out = self.out_edit.text().strip()
        if not inp or not os.path.exists(inp):
            QMessageBox.warning(self, "No Input", "Please select a valid input file.")
            return
        if not out:
            QMessageBox.warning(self, "No Output", "Please set an output path.")
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)   # indeterminate until ffprobe gives duration
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.log.clear()
        self.status_label.setText("Converting…")

        self.worker = ConvertThread(inp, out)
        self.worker.progress_signal.connect(self.log_message)
        self.worker.percent_signal.connect(self._on_percent)
        self.worker.finished_signal.connect(self._on_done)
        self.worker.start()

    def _on_percent(self, pct):
        if pct < 0:
            # Unknown duration — keep indeterminate
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
            self.status_label.setText(f"Converting… {pct}%")

    def _on_done(self, success, filepath, error):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        if success:
            self.status_label.setText(f"✓ Done: {os.path.basename(filepath)}")
            self.log_message(f"\n✓ Saved: {filepath}")
            out_ext = Path(filepath).suffix.lower()
            if out_ext in SUPPORTED_FORMATS:
                try:
                    audio = MutagenFile(filepath, easy=True)
                    title = Path(filepath).stem
                    artist = "Unknown Artist"
                    album = "Unknown Album"
                    duration = 0
                    if audio:
                        title = audio.get("title", [title])[0]
                        artist = audio.get("artist", [artist])[0]
                        album = audio.get("album", [album])[0]
                        if hasattr(audio.info, "length"):
                            duration = int(audio.info.length * 1000)
                except Exception:
                    pass
                if not self.db.get_song_by_path(filepath):
                    self.db.add_song(title, artist, "Unknown Album", filepath, None, duration)
                    self.log_message("→ Added to music library.")
            elif out_ext in SUPPORTED_VIDEO_FORMATS:
                if not self.db.get_video_by_path(filepath):
                    title = Path(filepath).stem
                    fmt = out_ext.lstrip(".")
                    size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    self.db.add_video(title, "Converted", filepath, None, 0, size, fmt, "")
                    self.log_message("→ Added to video library.")
            QMessageBox.information(self, "Done", f"Conversion complete!\n\n{filepath}")
        else:
            self.status_label.setText("✗ Failed")
            self.log_message(f"\n✗ Error: {error}")
            QMessageBox.critical(self, "Conversion Failed", error)


# ──────────────────────────── UNIVERSAL MEDIA BROWSER PANEL ────────────────────────────

# ── WebAssembly / SharedArrayBuffer header interceptor ──────────────────────
# Unity, Unreal and other Wasm games require SharedArrayBuffer, which Chrome
# only enables when the page is "cross-origin isolated".  That requires:
#   Cross-Origin-Opener-Policy: same-origin
#   Cross-Origin-Embedder-Policy: require-corp
# Most game-hosting sites don't send them, so we inject them on every request.
if _WEBENGINE_AVAILABLE:
    class _CoepCoopInterceptor(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            try:
                info.setHttpHeader(b"Cross-Origin-Opener-Policy",  b"same-origin")
                info.setHttpHeader(b"Cross-Origin-Embedder-Policy", b"require-corp")
            except Exception:
                pass
else:
    _CoepCoopInterceptor = None

# Global registry that keeps strong Python references to all popup views alive.
# Must outlive any individual page or view — module-level guarantees that.
_NOVA_POPUP_REGISTRY: list = []


class _NovaPopupWindow(QWidget if _WEBENGINE_AVAILABLE else object):
    """
    A proper top-level window that hosts a QWebEngineView for popups.
    Using a QWidget container (not the view itself as the window) ensures
    Qt can render the page correctly.
    """
    def __init__(self, profile):
        if not _WEBENGINE_AVAILABLE:
            return
        super().__init__(None, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Inner view + page
        self._view = QWebEngineView(self)
        self._page = _NovaWebPage(profile, self._view)

        # Apply all the same settings as the main browser
        try:
            ps = self._page.settings()
            ps.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            try:
                ps.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            except Exception:
                pass
        except Exception as e:
            print(f"[Nova] Popup settings error: {e}")

        self._view.setPage(self._page)
        self._page.setBackgroundColor(QColor("#0d1117"))

        # Sync window title with page title
        self._page.titleChanged.connect(
            lambda t: self.setWindowTitle(t or "Nova – Pop-up")
        )
        # Debug: print load errors to console
        self._view.loadFinished.connect(
            lambda ok: print(f"[Nova] Popup loadFinished ok={ok} url={self._page.url().toString()}")
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self.resize(960, 640)
        self.setWindowTitle("Nova – Pop-up")
        _NOVA_POPUP_REGISTRY.append(self)

    def page(self):
        """Return the inner QWebEnginePage for use by createWindow."""
        return self._page

    def closeEvent(self, event):
        super().closeEvent(event)
        try:
            _NOVA_POPUP_REGISTRY.remove(self)
        except ValueError:
            pass


# Keep old name as alias so nothing else breaks
_NovaPopupView = _NovaPopupWindow


if _WEBENGINE_AVAILABLE:
    class _NovaWebPage(QWebEnginePage):
        """
        Custom page that:
        - Auto-grants ALL feature permissions (pointer lock, microphone, camera, …)
        - Creates child windows for popups (TikTok, Google sign-in, …)
        - Suppresses JS dialogs silently
        """
        def __init__(self, profile, parent=None):
            super().__init__(profile, parent)
            self.featurePermissionRequested.connect(self._grant)

        def _grant(self, origin, feature):
            self.setFeaturePermission(
                origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )

        def createWindow(self, _type):
            """
            Called by Qt when a site opens window.open() or target=_blank.
            Must return a QWebEnginePage. We build a full QWidget window that
            hosts the view — a bare QWebEngineView as a top-level window does
            not render in all cases (e.g. WebAssembly game popups).
            """
            try:
                popup = _NovaPopupWindow(self.profile())
                popup.show()
                return popup.page()
            except Exception as e:
                print(f"[Nova] Popup-Fehler: {e}")
                return None

        def javaScriptAlert(self, _url, msg):
            QMessageBox.information(None, "Nova – Seite", msg)

        def javaScriptConfirm(self, _url, msg):
            result = QMessageBox.question(
                None, "Nova – Seite", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return result == QMessageBox.StandardButton.Yes

        def javaScriptPrompt(self, _url, msg, default):
            text, ok = QInputDialog.getText(None, "Nova – Seite", msg, text=default)
            return ok, text if ok else default
else:
    _NovaWebPage = None


class YouTubeBrowserPanel(QWidget):
    """
    Universeller eingebetteter Browser für alle Medien-Seiten
    (YouTube, Vimeo, SoundCloud, Twitch, Bandcamp, …).
    Erfordert PyQt6-WebEngine: pip install PyQt6-WebEngine
    """
    download_requested = pyqtSignal(str)  # emits URL when user clicks Download

    # Default homepage shown when the Home button is pressed
    HOME_URL = "https://www.google.com"

    def __init__(self, parent=None, db=None, download_dir=None):
        super().__init__(parent)
        self._nova = parent
        self.db = db
        self.download_dir = download_dir or os.path.expanduser("~/Downloads")
        self.worker = None
        # Load configurable start URL from DB (falls back to HOME_URL class default)
        if db is not None:
            saved = db.get_setting("browser_home_url", "")
            if saved:
                self.HOME_URL = saved
        self._setup_ui()

    # ── shared WebEngine profile (created once, reused across all tabs) ──
    _shared_profile = None

    @classmethod
    def _get_profile(cls):
        if cls._shared_profile is None and _WEBENGINE_AVAILABLE:
            _profile_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), ".nova_browser_profile"
            )
            os.makedirs(_profile_path, exist_ok=True)
            try:
                p = QWebEngineProfile("NovaProfile")
                p.setPersistentStoragePath(_profile_path)
                p.setCachePath(os.path.join(_profile_path, "cache"))
                p.setPersistentCookiesPolicy(
                    QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
                )
            except Exception:
                p = QWebEngineProfile.defaultProfile()
            p.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
            # Inject COOP/COEP headers so WebAssembly games can use SharedArrayBuffer
            if _CoepCoopInterceptor is not None:
                interceptor = _CoepCoopInterceptor(p)
                p.setUrlRequestInterceptor(interceptor)
                p._interceptor = interceptor  # keep a strong reference

            # ── Stealth script: injected at DocumentCreation so it runs BEFORE
            # any page JS — defeats Cloudflare, Xbox, reCAPTCHA bot detection ──
            _STEALTH_JS = r"""
(function() {
    // 1) Remove webdriver flag entirely
    try {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    } catch(e) {}

    // 2) window.chrome object expected by many anti-bot checks
    if (!window.chrome) {
        window.chrome = {
            runtime: {
                id: undefined,
                connect: function(){},
                sendMessage: function(){},
                onMessage: { addListener: function(){} }
            },
            loadTimes: function() { return {}; },
            csi: function() { return {}; },
            app: { isInstalled: false }
        };
    }

    // 3) navigator properties
    try { Object.defineProperty(navigator, 'vendor',   { get: () => 'Google Inc.' }); } catch(e) {}
    try { Object.defineProperty(navigator, 'platform', { get: () => 'Win32' }); } catch(e) {}
    try { Object.defineProperty(navigator, 'languages',{ get: () => ['de-DE','de','en-US','en'] }); } catch(e) {}

    // 4) Realistic plugin list
    try {
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                var arr = [
                    { name: 'Chrome PDF Plugin',  filename: 'internal-pdf-viewer',           description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',description: '' },
                    { name: 'Native Client',      filename: 'internal-nacl-plugin',           description: '' }
                ];
                arr.__proto__ = PluginArray.prototype;
                return arr;
            }
        });
    } catch(e) {}

    // 5) Permissions API — bot detectors query notification permission
    if (navigator.permissions && navigator.permissions.query) {
        var _origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = function(desc) {
            if (desc && desc.name === 'notifications') {
                return Promise.resolve({ state: 'denied', onchange: null });
            }
            return _origQuery(desc);
        };
    }

    // 6) Hide automation in toString checks
    var _origFnToString = Function.prototype.toString;
    Function.prototype.toString = function() {
        if (this === navigator.permissions.query) {
            return 'function query() { [native code] }';
        }
        return _origFnToString.call(this);
    };

    // 7) Web Audio API – auto-resume suspended AudioContext on first user interaction.
    //    Online instruments (piano, synth, …) create an AudioContext on page load but
    //    browsers suspend it until a user gesture. In QtWebEngine the gesture is often
    //    not recognised, so we force-resume every AudioContext on the first click/keydown.
    //    We also store all contexts in window.__novaAudioContexts so the Audio-unlock
    //    button (_unlock_browser_audio) can find and resume them reliably.
    (function() {
        if (!window.__novaAudioContexts) window.__novaAudioContexts = [];
        var _OrigAC = window.AudioContext || window.webkitAudioContext;
        if (!_OrigAC) return;
        var _PatchedAC = function() {
            var ctx = new (Function.prototype.bind.apply(_OrigAC, [null].concat(Array.prototype.slice.call(arguments))))();
            window.__novaAudioContexts.push(ctx);
            return ctx;
        };
        // Copy static properties and set prototype correctly
        _PatchedAC.prototype = _OrigAC.prototype;
        Object.setPrototypeOf(_PatchedAC, _OrigAC);
        try {
            Object.defineProperty(window, 'AudioContext',       { value: _PatchedAC, writable: true, configurable: true });
            Object.defineProperty(window, 'webkitAudioContext', { value: _PatchedAC, writable: true, configurable: true });
        } catch(e) {
            window.AudioContext = window.webkitAudioContext = _PatchedAC;
        }
        function _resumeAll() {
            (window.__novaAudioContexts || []).forEach(function(c) {
                try { if (c.state === 'suspended') c.resume(); } catch(e) {}
            });
        }
        ['click','keydown','pointerdown','touchstart'].forEach(function(evt) {
            document.addEventListener(evt, _resumeAll, { once: false, capture: true });
        });
    })();

    // 8) Web MIDI – stub navigator.requestMIDIAccess if it is missing so sites don't crash
    if (!navigator.requestMIDIAccess) {
        try {
            Object.defineProperty(navigator, 'requestMIDIAccess', {
                value: function() {
                    return Promise.resolve({
                        inputs:  new Map(),
                        outputs: new Map(),
                        onstatechange: null,
                        sysexEnabled: false
                    });
                },
                writable: true, configurable: true
            });
        } catch(e) {}
    }
})();
"""
            script = QWebEngineScript()
            script.setName("nova_stealth")
            script.setSourceCode(_STEALTH_JS)
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setRunsOnSubFrames(True)
            p.scripts().insert(script)

            cls._shared_profile = p
        return cls._shared_profile

    def _make_web_view(self):
        """Create a fully configured QWebEngineView for one browser tab."""
        view = QWebEngineView()
        profile = self._get_profile()
        page = _NovaWebPage(profile, view)
        view.setPage(page)
        try:
            ps = page.settings()
            ps.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            try:
                ps.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            except Exception:
                pass
            try:
                ps.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, False)
            except Exception:
                pass
            page.fullScreenRequested.connect(self._handle_fullscreen_request)
        except Exception as e:
            print(f"[Nova] WebEngine settings error: {e}")

        # ── Keyboard-fix for online instruments ──────────────────────────────
        # When the web view receives focus (e.g. user clicks on a virtual piano),
        # disable Nova's global Qt shortcuts so keys like A-L reach the web page.
        # When focus leaves the view, re-enable them.
        def _on_focus_in(_event=None):
            try:
                top = self.window()
                if hasattr(top, "set_browser_shortcuts_enabled"):
                    top.set_browser_shortcuts_enabled(False)
            except Exception:
                pass

        def _on_focus_out(_event=None):
            try:
                top = self.window()
                if hasattr(top, "set_browser_shortcuts_enabled"):
                    top.set_browser_shortcuts_enabled(True)
            except Exception:
                pass

        # Install event filter on the view to catch FocusIn / FocusOut
        class _FocusFilter(object):
            def eventFilter(self_, obj, event):
                from PyQt6.QtCore import QEvent
                if event.type() == QEvent.Type.FocusIn:
                    _on_focus_in()
                elif event.type() == QEvent.Type.FocusOut:
                    _on_focus_out()
                return False  # don't consume the event

        from PyQt6.QtCore import QObject as _QObject
        class _FocusFilterQObject(_QObject):
            def eventFilter(self_, obj, event):
                from PyQt6.QtCore import QEvent
                if event.type() == QEvent.Type.FocusIn:
                    _on_focus_in()
                elif event.type() == QEvent.Type.FocusOut:
                    _on_focus_out()
                return False

        _filter = _FocusFilterQObject(view)
        view.installEventFilter(_filter)
        view._nova_focus_filter = _filter  # keep strong reference
        # ─────────────────────────────────────────────────────────────────────

        return view

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top toolbar (navigation + URL) ──
        toolbar = QFrame()
        toolbar.setObjectName("yt_browser_toolbar")
        toolbar.setFixedHeight(52)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        self.back_btn = QPushButton("◀")
        self.back_btn.setFixedSize(32, 32)
        self.back_btn.setObjectName("nav_btn")
        self.fwd_btn = QPushButton("▶")
        self.fwd_btn.setFixedSize(32, 32)
        self.fwd_btn.setObjectName("nav_btn")
        self.reload_btn = QPushButton("↺")
        self.reload_btn.setFixedSize(32, 32)
        self.reload_btn.setObjectName("nav_btn")
        self.home_btn = QPushButton("🏠")
        self.home_btn.setFixedSize(32, 32)
        self.home_btn.setObjectName("nav_btn")
        self.home_btn.setToolTip("Startseite")

        # New-tab button
        new_tab_btn = QPushButton("＋")
        new_tab_btn.setFixedSize(32, 32)
        new_tab_btn.setObjectName("nav_btn")
        new_tab_btn.setToolTip("Neuen Tab öffnen")
        new_tab_btn.clicked.connect(lambda: self._add_tab())

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("URL oder Suche eingeben …")
        self.url_bar.setFixedHeight(32)
        self.url_bar.returnPressed.connect(self._navigate_from_bar)

        self.dir_btn = QPushButton("📁")
        self.dir_btn.setFixedSize(32, 32)
        self.dir_btn.setObjectName("toolbar_btn")
        self.dir_btn.setToolTip(f"Speicherordner: {self.download_dir}")
        self.dir_btn.clicked.connect(self._pick_dir)

        # Open current URL in the real system browser (Chrome/Edge/Firefox)
        # Useful for CAPTCHAs / logins that block embedded browsers
        self.ext_btn = QPushButton("🌍")
        self.ext_btn.setFixedSize(32, 32)
        self.ext_btn.setObjectName("nav_btn")
        self.ext_btn.setToolTip(
            "Im echten Browser öffnen\n"
            "Nützlich für CAPTCHAs & Logins (z.B. Xbox, Google)\n"
            "Nach dem Login hier neu laden"
        )
        self.ext_btn.clicked.connect(self._open_in_system_browser)

        self.ext_dl_btn = QPushButton("⬡")
        self.ext_dl_btn.setFixedSize(32, 32)
        self.ext_dl_btn.setObjectName("nav_btn")
        self.ext_dl_btn.setToolTip(
            "Nova Chrome Extension installieren\n"
            "Lädt YouTube-Videos/Audio via yt-dlp in Nova"
        )
        self.ext_dl_btn.clicked.connect(self._open_extension_installer)

        tb.addWidget(self.back_btn)
        tb.addWidget(self.fwd_btn)
        tb.addWidget(self.reload_btn)
        tb.addWidget(self.home_btn)
        tb.addWidget(new_tab_btn)
        tb.addWidget(self.url_bar, 1)
        tb.addWidget(self.ext_dl_btn)
        tb.addWidget(self.ext_btn)
        tb.addWidget(self.dir_btn)
        layout.addWidget(toolbar)

        # ── Quick-access site buttons ──
        self._tabs_bar = QFrame()
        self._tabs_bar.setObjectName("yt_browser_toolbar")
        self._tabs_bar.setFixedHeight(36)
        self._tabs_lay = QHBoxLayout(self._tabs_bar)
        self._tabs_lay.setContentsMargins(10, 4, 10, 4)
        self._tabs_lay.setSpacing(6)
        self._rebuild_quick_tabs_bar()
        layout.addWidget(self._tabs_bar)

        # ── Download toolbar ──
        dl_toolbar = QFrame()
        dl_toolbar.setObjectName("yt_browser_toolbar")
        dl_toolbar.setFixedHeight(44)
        dt = QHBoxLayout(dl_toolbar)
        dt.setContentsMargins(12, 6, 12, 6)
        dt.setSpacing(8)

        mode_lbl = QLabel("Modus:")
        mode_lbl.setObjectName("time_label")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["🎬  Video", "🎵  Audio"])
        self.mode_combo.setFixedWidth(110)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        fmt_lbl = QLabel("Format:")
        fmt_lbl.setObjectName("time_label")
        self.dl_fmt_combo = QComboBox()
        self.dl_fmt_combo.addItems(["mp4", "mkv", "webm", "mov", "avi"])
        self.dl_fmt_combo.setFixedWidth(75)

        qual_lbl = QLabel("Qualität:")
        qual_lbl.setObjectName("time_label")
        self.dl_qual_combo = QComboBox()
        self.dl_qual_combo.addItems(["Best (4K+)", "1080p", "720p", "480p", "360p", "Smallest"])
        self.dl_qual_combo.setCurrentText("1080p")
        self.dl_qual_combo.setFixedWidth(105)

        self.dl_btn = QPushButton("⬇  Herunterladen")
        self.dl_btn.setObjectName("yt_dl_btn")
        self.dl_btn.setFixedHeight(30)
        self.dl_btn.setToolTip("Aktuelles Video / Audio herunterladen")
        self.dl_btn.clicked.connect(self._start_download)

        dt.addWidget(mode_lbl)
        dt.addWidget(self.mode_combo)
        dt.addSpacing(6)
        dt.addWidget(fmt_lbl)
        dt.addWidget(self.dl_fmt_combo)
        dt.addSpacing(6)
        dt.addWidget(qual_lbl)
        dt.addWidget(self.dl_qual_combo)
        dt.addStretch()
        dt.addWidget(self.dl_btn)
        layout.addWidget(dl_toolbar)

        # ── Status bar ──
        self.status_frame = QFrame()
        self.status_frame.setObjectName("yt_status_bar")
        self.status_frame.setFixedHeight(28)
        sf = QHBoxLayout(self.status_frame)
        sf.setContentsMargins(12, 0, 12, 0)
        sf.setSpacing(8)
        self.status_lbl = QLabel("Bereit")
        self.status_lbl.setObjectName("time_label")
        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 0)
        self.dl_progress.setFixedHeight(10)
        self.dl_progress.setVisible(False)
        sf.addWidget(self.status_lbl, 1)
        sf.addWidget(self.dl_progress)
        layout.addWidget(self.status_frame)

        # ── Tab widget holding the actual web views ──
        if _try_load_webengine():
            self._browser_fs_window = None
            self._yt_fs_active = False   # YouTube-internes Vollbild (Ebene 2)
            self._mouse_locked = False

            self.tab_widget = QTabWidget()
            self.tab_widget.setTabsClosable(True)
            self.tab_widget.setMovable(True)
            self.tab_widget.tabCloseRequested.connect(self._close_tab)
            self.tab_widget.currentChanged.connect(self._on_tab_switched)
            self.tab_widget.setStyleSheet("""
                QTabWidget::pane { border: none; }
                QTabBar::tab {
                    padding: 5px 14px;
                    min-width: 80px;
                    max-width: 200px;
                }
                QTabBar::tab:selected { font-weight: bold; }
                QTabBar::close-button { subcontrol-position: right; }
            """)
            layout.addWidget(self.tab_widget, 1)

            # Pre-build a native fullscreen window that will host tab_widget.
            # Created here (hidden) so the window handle exists before any GPU
            # surface is set up; moving tab_widget into it later does NOT destroy
            # Chromium's rendering surface because tab_widget itself is not a
            # QWebEngineView.
            self._fs_container = QWidget(None, Qt.WindowType.Window)
            self._fs_container.setWindowTitle("Nova – Browser Vollbild")
            self._fs_container.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self._fs_container.setStyleSheet("background:#000;")
            _fsl = QVBoxLayout(self._fs_container)
            _fsl.setContentsMargins(0, 0, 0, 0)
            _fsl.setSpacing(0)
            esc_sc = QShortcut(QKeySequence("Escape"), self._fs_container)
            esc_sc.activated.connect(self._on_fs_win_esc)
            self._fs_esc_shortcut = esc_sc

            # Extra buttons row
            extra_row = QFrame()
            extra_row.setObjectName("yt_browser_toolbar")
            extra_row.setFixedHeight(36)
            er = QHBoxLayout(extra_row)
            er.setContentsMargins(12, 4, 12, 4)
            er.setSpacing(8)
            self.fs_win_btn = QPushButton("⛶  Vollbild-Fenster")
            self.fs_win_btn.setObjectName("toolbar_btn")
            self.fs_win_btn.setFixedHeight(26)
            self.fs_win_btn.setToolTip("Browser als eigenes Vollbild-Fenster öffnen")
            self.fs_win_btn.clicked.connect(self._toggle_browser_fullscreen_window)
            self.mouse_lock_btn = QPushButton("🖱  Maus einrasten")
            self.mouse_lock_btn.setObjectName("toolbar_btn")
            self.mouse_lock_btn.setFixedHeight(26)
            self.mouse_lock_btn.setToolTip("Mauszeiger im Browser einrasten / lösen")
            self.mouse_lock_btn.clicked.connect(self._toggle_mouse_lock)
            er.addWidget(self.fs_win_btn)
            er.addWidget(self.mouse_lock_btn)
            er.addStretch()

            # ── Browser Audio Controls ────────────────────────────────────────
            # Mute toggle button
            self._browser_muted = False
            self.browser_mute_btn = QPushButton("🔊")
            self.browser_mute_btn.setObjectName("toolbar_btn")
            self.browser_mute_btn.setFixedSize(28, 26)
            self.browser_mute_btn.setToolTip("Browser-Audio stummschalten / einschalten")
            self.browser_mute_btn.clicked.connect(self._toggle_browser_mute)

            # Volume label
            browser_vol_lbl = QLabel("🔉")
            browser_vol_lbl.setObjectName("time_label")
            browser_vol_lbl.setFixedWidth(18)

            # Volume slider (0–150, default 100)
            self._browser_volume = 100
            self.browser_vol_slider = QSlider(Qt.Orientation.Horizontal)
            self.browser_vol_slider.setRange(0, 150)
            self.browser_vol_slider.setValue(100)
            self.browser_vol_slider.setFixedWidth(100)
            self.browser_vol_slider.setFixedHeight(20)
            self.browser_vol_slider.setToolTip("Browser-Lautstärke (0–150%)")
            self.browser_vol_slider.valueChanged.connect(self._on_browser_volume_changed)

            self.browser_vol_pct_lbl = QLabel("100%")
            self.browser_vol_pct_lbl.setObjectName("time_label")
            self.browser_vol_pct_lbl.setFixedWidth(38)

            # Audio-unlock button — resumes suspended AudioContext for virtual instruments
            self.audio_unlock_btn = QPushButton("🎹 Audio")
            self.audio_unlock_btn.setObjectName("toolbar_btn")
            self.audio_unlock_btn.setFixedHeight(26)
            self.audio_unlock_btn.setToolTip(
                "Audio entsperren / AudioContext aufwecken\n"
                "Drücken wenn virtuelle Instrumente (Piano, Synth…) stumm sind"
            )
            self.audio_unlock_btn.clicked.connect(self._unlock_browser_audio)

            er.addWidget(self.audio_unlock_btn)
            er.addSpacing(4)
            er.addWidget(self.browser_mute_btn)
            er.addWidget(browser_vol_lbl)
            er.addWidget(self.browser_vol_slider)
            er.addWidget(self.browser_vol_pct_lbl)
            # ─────────────────────────────────────────────────────────────────

            layout.addWidget(extra_row)

            # Open first tab
            self._add_tab(self.HOME_URL)

            # Convenience alias so old code that references self.web still works
            self.web = self._current_web()

        else:
            self.tab_widget = None
            self.web = None
            # Fallback: show install instructions
            fallback = QFrame()
            fallback.setObjectName("cover_container")
            fl = QVBoxLayout(fallback)
            fl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fl.setSpacing(12)
            icon_lbl = QLabel("🌐")
            icon_lbl.setFont(QFont("Arial", 40))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg = QLabel(
                "<b>PyQt6-WebEngine nicht installiert oder fehlerhaft</b><br><br>"
                "Um den Medien-Browser zu nutzen, führe diesen Befehl aus:<br><br>"
                "<code>pip install PyQt6-WebEngine</code><br><br>"
                + (f"<small><b>Fehler:</b> {_WEBENGINE_ERROR}</small><br><br>" if _WEBENGINE_ERROR else "")
                + "Danach Nova neu starten.<br><br>"
                "<small>Falls PyQt6-WebEngine bereits installiert ist, fehlt möglicherweise<br>"
                "ein System-DLL (z.B. Visual C++ Redistributable). Installiere es von:<br>"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe</small>"
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setWordWrap(True)
            msg.setTextFormat(Qt.TextFormat.RichText)
            copy_btn = QPushButton("📋  Befehl kopieren")
            copy_btn.setFixedWidth(220)
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(
                "pip install PyQt6-WebEngine"
            ))
            fl.addWidget(icon_lbl)
            fl.addWidget(msg)
            fl.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(fallback, 1)
            # URL bar still works as manual URL copy tool
            self.back_btn.setEnabled(False)
            self.fwd_btn.setEnabled(False)
            self.reload_btn.setEnabled(False)
            self.home_btn.setEnabled(False)
            self.web = None

    def _on_page_loaded(self, ok: bool):
        self.status_lbl.setText("Fertig" if ok else "Fehler beim Laden")
        if not ok or self.web is None:
            return

        # ── TikTok / Google: spoof navigator so the site treats us as real Chrome ──
        spoof_js = r"""
(function() {
    // 1) Hide webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // 2) window.chrome — TikTok player won't init without this
    if (!window.chrome) {
        window.chrome = {
            runtime: { id: undefined, connect: function(){}, sendMessage: function(){} },
            loadTimes: function() { return {}; },
            csi: function() { return {}; },
            app: { isInstalled: false, InstallState: {}, RunningState: {} }
        };
    }

    // 3) navigator properties
    Object.defineProperty(navigator, 'vendor',   { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    Object.defineProperty(navigator, 'languages',{ get: () => ['de-DE','de','en-US','en'] });

    // 4) Plugins — empty list = detected as bot
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            var arr = [
                { name: 'Chrome PDF Plugin',  filename: 'internal-pdf-viewer',          description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client',      filename: 'internal-nacl-plugin',          description: '' }
            ];
            arr.__proto__ = PluginArray.prototype;
            return arr;
        }
    });

    // 5) canPlayType spoofing — TikTok falls back to unsupported path if H.264 reports ''
    //    QtWebEngine often has H.264 but canPlayType returns '' due to missing license string.
    var _origCPT = HTMLVideoElement.prototype.canPlayType;
    HTMLVideoElement.prototype.canPlayType = function(type) {
        var result = _origCPT.call(this, type);
        // If engine already says 'probably' or 'maybe', keep it
        if (result) return result;
        // Force 'probably' for known-supported codec strings
        var t = (type || '').toLowerCase();
        if (t.indexOf('avc1') !== -1 || t.indexOf('h264') !== -1 ||
            t.indexOf('mp4') !== -1  || t.indexOf('aac')  !== -1 ||
            t.indexOf('mp2t') !== -1 || t.indexOf('hvc1') !== -1) {
            return 'probably';
        }
        return result;
    };

    // 6) MediaSource isTypeSupported — same fix
    if (window.MediaSource) {
        var _origITS = MediaSource.isTypeSupported;
        MediaSource.isTypeSupported = function(type) {
            if (_origITS.call(this, type)) return true;
            var t = (type || '').toLowerCase();
            if (t.indexOf('avc1') !== -1 || t.indexOf('h264') !== -1 ||
                t.indexOf('mp4a') !== -1 || t.indexOf('hvc1') !== -1) {
                return true;
            }
            return false;
        };
    }

    // 7) Pointer-lock passthrough
    var _origRPL = Element.prototype.requestPointerLock;
    Element.prototype.requestPointerLock = function() {
        try { return _origRPL.call(this); } catch(e) {}
    };
})();
"""
        self.web.page().runJavaScript(spoof_js)

        # Inject JS that listens for the page acquiring / releasing pointer lock
        # and sends a message back via Qt's channel so we can sync the button.
        js = """
(function(){
    function _syncLock(){
        var locked = !!document.pointerLockElement;
        window._nova_pointer_locked = locked;
    }
    document.addEventListener('pointerlockchange', function(){
        _syncLock();
        // Signal Nova via title trick (fastest cross-origin-safe channel)
        document.title = '__nova_pl__' + (document.pointerLockElement ? '1' : '0')
                         + '__' + document.title.replace(/^__nova_pl__[01]__/, '');
    });
})();
"""
        self.web.page().runJavaScript(js)
        # Also listen for title changes to pick up the lock/unlock signal
        try:
            self.web.titleChanged.disconnect(self._on_title_changed)
        except Exception:
            pass
        self.web.titleChanged.connect(self._on_title_changed)
        # Re-apply browser volume settings to the freshly loaded page
        QTimer.singleShot(500, self._apply_browser_volume_js)

    def _on_title_changed(self, title: str):
        """Detect auto pointer-lock signals injected by _on_page_loaded."""
        if title.startswith("__nova_pl__"):
            locked = title[len("__nova_pl__"):len("__nova_pl__")+1] == "1"
            if locked != self._mouse_locked:
                self._mouse_locked = locked
                if locked:
                    self.mouse_lock_btn.setText("🔓  Maus lösen")
                    self.status_lbl.setText("Maus eingerastet (automatisch) — Klick auf 'Maus lösen' oder Esc")
                else:
                    self.mouse_lock_btn.setText("🖱  Maus einrasten")
                    self.status_lbl.setText("Maus-Lock aufgehoben")



    def _current_web(self):
        """Return the QWebEngineView of the currently active tab, or None."""
        if not self.tab_widget:
            return None
        return self.tab_widget.currentWidget()

    def _add_tab(self, url=None):
        """Open a new browser tab, optionally loading url."""
        if not _WEBENGINE_AVAILABLE:
            return
        view = self._make_web_view()
        url = url or self.HOME_URL

        # Tab title updates
        def _update_title(ok, v=view):
            title = v.page().title() or "Neuer Tab"
            idx = self.tab_widget.indexOf(v)
            if idx >= 0:
                short = title[:22] + "…" if len(title) > 24 else title
                self.tab_widget.setTabText(idx, short)
                self.tab_widget.setTabToolTip(idx, title)

        def _on_url(u, v=view):
            if self.tab_widget.currentWidget() is v:
                self.url_bar.setText(u.toString())
                self.dl_btn.setEnabled(True)
                self.dl_btn.setToolTip(f"Herunterladen: {u.toString()}")

        def _on_load_start(v=view):
            if self.tab_widget.currentWidget() is v:
                self.status_lbl.setText("Lädt…")

        def _on_load_finish(ok, v=view):
            _update_title(ok, v)
            if self.tab_widget.currentWidget() is v:
                self._on_page_loaded(ok)

        view.urlChanged.connect(_on_url)
        view.loadStarted.connect(_on_load_start)
        view.loadFinished.connect(_on_load_finish)

        idx = self.tab_widget.addTab(view, "Neuer Tab")
        self.tab_widget.setCurrentIndex(idx)
        view.load(QUrl(url))

        # Keep self.web alias pointing to current tab
        self.web = view

        # Nav buttons wired to the current active tab
        self._rewire_nav_buttons()

    def _close_tab(self, index):
        """Close a tab; always keep at least one open."""
        if self.tab_widget.count() <= 1:
            # Reset to home instead of closing
            w = self.tab_widget.widget(0)
            if w:
                w.load(QUrl(self.HOME_URL))
            return
        widget = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        if widget:
            widget.deleteLater()
        self.web = self._current_web()
        self._rewire_nav_buttons()

    def _on_tab_switched(self, index):
        """Sync URL bar and nav buttons when the user clicks a tab."""
        view = self.tab_widget.widget(index) if self.tab_widget else None
        if view:
            self.url_bar.setText(view.url().toString())
            self.web = view
        self._rewire_nav_buttons()
        # Re-apply current volume to the newly visible tab
        QTimer.singleShot(300, self._apply_browser_volume_js)

    def _rewire_nav_buttons(self):
        """Disconnect nav buttons from any previous view and reconnect to current."""
        try:
            self.back_btn.clicked.disconnect()
            self.fwd_btn.clicked.disconnect()
            self.reload_btn.clicked.disconnect()
            self.home_btn.clicked.disconnect()
        except Exception:
            pass
        view = self._current_web()
        if view:
            self.back_btn.clicked.connect(view.back)
            self.fwd_btn.clicked.connect(view.forward)
            self.reload_btn.clicked.connect(view.reload)
            self.home_btn.clicked.connect(lambda: view.load(QUrl(self.HOME_URL)))

    def _rebuild_quick_tabs_bar(self):
        """Clear and repopulate the quick-tabs bar from DB (or defaults)."""
        lay = self._tabs_lay
        # Remove all existing widgets from the layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tabs = load_quick_tabs(self.db)
        for label, url in tabs:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setFixedHeight(26)
            btn.setStyleSheet("QPushButton { font-size: 11px; padding: 2px 10px; border-radius: 6px; }")
            btn.clicked.connect(lambda _, u=url: self._current_web() and self._current_web().load(QUrl(u)))
            lay.addWidget(btn)

        lay.addStretch()

        # Edit button at the far right
        edit_btn = QPushButton("⚙")
        edit_btn.setObjectName("nav_btn")
        edit_btn.setFixedSize(26, 26)
        edit_btn.setToolTip("Schnell-Tabs anpassen")
        edit_btn.setStyleSheet("QPushButton { font-size: 13px; padding: 0px; border-radius: 6px; }")
        edit_btn.clicked.connect(self._open_quick_tabs_editor)
        lay.addWidget(edit_btn)

    def _open_quick_tabs_editor(self):
        """Open the editor dialog and rebuild the bar if changes were saved."""
        dlg = QuickTabsEditorDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._rebuild_quick_tabs_bar()

    def _handle_fullscreen_request(self, request: QWebEngineFullScreenRequest):
        """
        Called when a website (e.g. YouTube) requests or exits fullscreen.

        Zwei Ebenen:
          Ebene 1 – Nova FS-Fenster  (_browser_fs_window)
          Ebene 2 – YouTube-internes Vollbild innerhalb von Ebene 1

        Wenn Nova's FS-Fenster bereits offen ist und YouTube noch mal
        fullscreen anfordert, akzeptieren wir den Request (damit Chromium
        intern umschaltet) aber wir öffnen kein zweites Fenster und
        schließen das bestehende beim Exit-Signal nicht.
        """
        request.accept()
        if request.toggleOn():
            if self._browser_fs_window is None:
                # Ebene 1: Nova FS-Fenster öffnen
                self._show_browser_fullscreen_overlay()
            else:
                # Ebene 2: YouTube-Vollbild innerhalb des FS-Fensters – nichts tun
                self._yt_fs_active = True
        else:
            if getattr(self, "_yt_fs_active", False):
                # Ebene 2 wird beendet (ESC aus YouTube-Vollbild) – FS-Fenster bleibt offen
                self._yt_fs_active = False
            else:
                # Ebene 1 wird beendet
                self._hide_browser_fullscreen_overlay()

    def _show_browser_fullscreen_overlay(self):
        """Move tab_widget (NOT the WebEngineView) into the pre-built fullscreen
        window.  The WebEngineViews inside tab_widget never change their parent,
        so Chromium's GPU surface is never destroyed: no black screen, no delay.
        """
        if self._browser_fs_window is not None:
            return

        # Detach tab_widget from our embedded layout and reparent into fs_container
        self.layout().removeWidget(self.tab_widget)
        fs_lay = self._fs_container.layout()
        fs_lay.addWidget(self.tab_widget, 1)
        self.tab_widget.show()

        self._browser_fs_window = self._fs_container
        self._fs_esc_shortcut.setEnabled(True)
        self._fs_container.showFullScreen()

        view = self._current_web()
        if view:
            view.setFocus()


    def _on_fs_win_esc(self):
        """ESC: exit YouTube-internal fullscreen (Ebene 2) first, then Nova FS."""
        if getattr(self, "_yt_fs_active", False):
            view = self._current_web()
            if view:
                try:
                    view.triggerPageAction(QWebEnginePage.WebAction.ExitFullScreen)
                except Exception:
                    pass
        else:
            self._hide_browser_fullscreen_overlay()

    def _hide_browser_fullscreen_overlay(self):
        """Move tab_widget back into the embedded panel and hide the FS window."""
        if self._browser_fs_window is None:
            return
        self._yt_fs_active = False
        self._browser_fs_window = None
        self._fs_esc_shortcut.setEnabled(False)

        # Tell Chromium to exit any internal fullscreen state
        view = self._current_web()
        if view:
            try:
                view.triggerPageAction(QWebEnginePage.WebAction.ExitFullScreen)
            except Exception:
                pass

        # Detach tab_widget from fs_container and put it back into our layout
        fs_lay = self._fs_container.layout()
        fs_lay.removeWidget(self.tab_widget)
        # Re-insert before extra_row (last item) — same position as during init
        own_lay = self.layout()
        own_lay.insertWidget(own_lay.count() - 1, self.tab_widget, 1)
        self.tab_widget.show()

        # Hide the FS window (don't close – we reuse it next time)
        self._fs_container.hide()

        # Make sure the browser view inside Nova is on screen
        nova = None
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "center_stack") and hasattr(w, "yt_browser"):
                nova = w
                break
        if nova is not None:
            nova.center_stack.setCurrentWidget(nova.yt_browser)
            nova.yt_browser.show()
        if view:
            view.setFocus()


    def _toggle_browser_fullscreen_window(self):
        if self._browser_fs_window is None:
            self._show_browser_fullscreen_overlay()
        else:
            self._hide_browser_fullscreen_overlay()

    def _restore_browser_view(self):
        """No-op kept for compatibility."""
        pass

    # ──────────────────────────── MOUSE LOCK ────────────────────────────

    def _toggle_mouse_lock(self):
        view = self._current_web()
        if view is None:
            return
        if not self._mouse_locked:
            js = """
(function(){
    var el = document.activeElement && document.activeElement !== document.body
             ? document.activeElement : document.body;
    el.requestPointerLock();
    document.addEventListener('pointerlockchange', function _plc(){
        document.removeEventListener('pointerlockchange', _plc);
    }, {once:true});
})();
"""
            view.page().runJavaScript(js)
            self._mouse_locked = True
            self.mouse_lock_btn.setText("🔓  Maus lösen")
            self.status_lbl.setText("Maus eingerastet — Klick auf 'Maus lösen' oder Esc")
        else:
            view.page().runJavaScript("document.exitPointerLock();")
            self._mouse_locked = False
            self.mouse_lock_btn.setText("🖱  Maus einrasten")
            self.status_lbl.setText("Maus-Lock aufgehoben")

    # ── Browser Audio Controls ────────────────────────────────────────────────

    def _apply_browser_volume_js(self):
        """Inject JS into the active tab to set volume on all media elements
        and the Web Audio API master gain (for virtual instruments / synths)."""
        view = self._current_web()
        if view is None:
            return
        vol = 0.0 if self._browser_muted else (self._browser_volume / 100.0)
        js = f"""
(function() {{
    var vol = {vol:.4f};

    // 1) All <video> and <audio> elements
    document.querySelectorAll('video, audio').forEach(function(el) {{
        try {{ el.volume = Math.min(vol, 1.0); el.muted = (vol === 0); }} catch(e) {{}}
    }});

    // 2) Web Audio API — create / reuse a GainNode on the AudioContext
    //    Works for virtual pianos, synths, Web Audio instruments, etc.
    try {{
        if (!window.__novaGainNode && window.AudioContext) {{
            // Patch AudioContext.prototype so future contexts get the gain too
            var _origAC = window.AudioContext;
            window.AudioContext = function(opts) {{
                var ctx = new _origAC(opts);
                var g = ctx.createGain();
                g.gain.value = window.__novaBrowserVol !== undefined ? window.__novaBrowserVol : 1.0;
                var _origDest = ctx.destination;
                // Re-route all future connections through the gain node
                var _origConnect = AudioNode.prototype.connect;
                // Store on context for later access
                ctx.__novaGain = g;
                g.connect(_origDest);
                return ctx;
            }};
        }}
    }} catch(e) {{}}

    // 3) Adjust gain on any already-existing AudioContexts via __novaGain
    window.__novaBrowserVol = vol;
    try {{
        // Some pages expose their AudioContext; adjust if we patched it
        if (window.AudioContext && AudioContext.prototype.__novaContextList) {{
            AudioContext.prototype.__novaContextList.forEach(function(ctx) {{
                if (ctx.__novaGain) ctx.__novaGain.gain.setTargetAtTime(vol, ctx.currentTime, 0.01);
            }});
        }}
    }} catch(e) {{}}

    // 4) Tone.js / Howler.js support
    try {{
        if (window.Tone && Tone.getDestination) {{
            Tone.getDestination().volume.value = vol === 0 ? -Infinity : 20 * Math.log10(vol);
        }}
    }} catch(e) {{}}
    try {{
        if (window.Howler) {{ Howler.volume(vol); }}
    }} catch(e) {{}}
}})();
"""
        view.page().runJavaScript(js)

    def _on_browser_volume_changed(self, value):
        self._browser_volume = value
        self.browser_vol_pct_lbl.setText(f"{value}%")
        if value == 0:
            self.browser_mute_btn.setText("🔇")
            self._browser_muted = True
        else:
            self._browser_muted = False
            self.browser_mute_btn.setText("🔊")
        self._apply_browser_volume_js()

    def _toggle_browser_mute(self):
        self._browser_muted = not self._browser_muted
        self.browser_mute_btn.setText("🔇" if self._browser_muted else "🔊")
        # Visual feedback: red background when muted so state is always visible
        if self._browser_muted:
            self.browser_mute_btn.setStyleSheet(
                "background-color: #c0392b; color: white; border-radius: 4px;"
            )
        else:
            self.browser_mute_btn.setStyleSheet("")
        self._apply_browser_volume_js()

    def _unlock_browser_audio(self):
        """Resume suspended AudioContext — essential for virtual instruments that
        need a user-gesture before the Web Audio API allows sound output."""
        view = self._current_web()
        if view is None:
            return
        vol = self._browser_volume / 100.0
        js = f"""
(function() {{
    var vol = {vol:.4f};

    // Ensure the tracking array exists (stealth script may have already filled it)
    if (!window.__novaAudioContexts) window.__novaAudioContexts = [];

    // Resume all tracked contexts (collected by the stealth injection script)
    (window.__novaAudioContexts || []).forEach(function(ctx) {{
        try {{
            if (ctx.state === 'suspended') ctx.resume();
        }} catch(e) {{}}
    }});

    // Also try to resume any context attached to known global objects
    ['Tone', 'TONE', 'ac', 'audioContext', 'ctx', 'audioCtx'].forEach(function(k) {{
        try {{
            var obj = window[k];
            if (!obj) return;
            // Tone.js
            if (obj.context && obj.context.resume) obj.context.resume();
            // Raw AudioContext
            if (obj.resume && obj.state === 'suspended') obj.resume();
        }} catch(e) {{}}
    }});

    // Re-apply volume to all media elements
    document.querySelectorAll('video, audio').forEach(function(el) {{
        try {{ el.volume = Math.min(vol, 1.0); el.muted = false; }} catch(e) {{}}
    }});

    // Tone.js destination
    try {{
        if (window.Tone && Tone.start) {{ Tone.start(); }}
        if (window.Tone && Tone.getDestination) {{
            Tone.getDestination().volume.value = vol === 0 ? -Infinity : 20 * Math.log10(vol);
        }}
    }} catch(e) {{}}

    // Howler
    try {{ if (window.Howler) {{ Howler.volume(vol); }} }} catch(e) {{}}
}})();
"""
        view.page().runJavaScript(js)
        self.status_lbl.setText("🎹 AudioContext aufgeweckt — Instrumente sollten jetzt klingen")

    # ─────────────────────────────────────────────────────────────────────────

    def _on_mode_changed(self, index):
        """Switch format/quality options between Video and Audio mode."""
        is_audio = index == 1  # 0 = Video, 1 = Audio
        self.dl_fmt_combo.blockSignals(True)
        self.dl_fmt_combo.clear()
        if is_audio:
            self.dl_fmt_combo.addItems(["mp3", "m4a", "flac", "wav", "ogg"])
            self.dl_fmt_combo.setCurrentText("mp3")
            self.dl_qual_combo.clear()
            self.dl_qual_combo.addItems(["320 kbps", "256 kbps", "192 kbps", "128 kbps", "96 kbps"])
            self.dl_qual_combo.setCurrentText("192 kbps")
            self.dl_btn.setText("⬇  Audio laden")
        else:
            self.dl_fmt_combo.addItems(["mp4", "mkv", "webm", "mov", "avi"])
            self.dl_fmt_combo.setCurrentText("mp4")
            self.dl_qual_combo.clear()
            self.dl_qual_combo.addItems(["Best (4K+)", "1080p", "720p", "480p", "360p", "Smallest"])
            self.dl_qual_combo.setCurrentText("1080p")
            self.dl_btn.setText("⬇  Video laden")
        self.dl_fmt_combo.blockSignals(False)

    def _on_url_changed(self, url: QUrl):
        self.url_bar.setText(url.toString())
        # Keep button always enabled — user can also paste URLs manually
        self.dl_btn.setEnabled(True)
        self.dl_btn.setToolTip(f"Herunterladen: {url.toString()}")

    def _navigate_from_bar(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        import urllib.parse as _up
        looks_like_url = (
            text.startswith("http://") or
            text.startswith("https://") or
            text.startswith("ftp://") or
            ("." in text and " " not in text and "/" in text) or
            ("." in text and " " not in text)
        )
        if not looks_like_url:
            text = "https://www.youtube.com/results?search_query=" + _up.quote(text)
        elif not text.startswith("http"):
            text = "https://" + text
        view = self._current_web()
        if view:
            view.load(QUrl(text))
        else:
            self.status_lbl.setText(f"URL: {text}  (WebEngine nicht verfügbar)")

    def _pick_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Speicherordner wählen", self.download_dir)
        if folder:
            self.download_dir = folder
            self.dir_btn.setToolTip(f"Speicherordner: {folder}")
            if self.db:
                self.db.set_setting("yt_browser_download_dir", folder)
            self.status_lbl.setText(f"Speicherordner: {folder}")

    def _open_extension_installer(self):
        if self._nova and hasattr(self._nova, "open_chrome_extension_dialog"):
            self._nova.open_chrome_extension_dialog()

    def _open_in_system_browser(self):
        """Open current URL in the system default browser (safe, non-blocking)."""
        url = self._get_current_url()
        if not url or url in ("", "about:blank"):
            QMessageBox.information(self, "Kein URL", "Es ist keine URL geladen.")
            return
        try:
            import webbrowser
            webbrowser.open(url)
            self.status_lbl.setText(f"Im Browser geöffnet: {url}")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Browser konnte nicht geöffnet werden:\n{e}")

    def _find_browser_exe(self):
        """Find Chrome or Edge executable path."""
        import shutil
        local  = os.environ.get("LOCALAPPDATA", "")
        prog   = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        prog86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidates = []
        for base in (local, prog, prog86):
            if not base:
                continue
            candidates += [
                os.path.join(base, "Google",        "Chrome",       "Application", "chrome.exe"),
                os.path.join(base, "Microsoft",     "Edge",         "Application", "msedge.exe"),
                os.path.join(base, "BraveSoftware", "Brave-Browser","Application", "brave.exe"),
            ]
        # macOS
        for p in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ):
            candidates.append(p)
        for p in candidates:
            if os.path.exists(p):
                return p
        return shutil.which("google-chrome") or shutil.which("chromium-browser")

    def _find_browser_user_data(self, exe):
        """Return the user-data-dir for the given browser exe."""
        local = os.environ.get("LOCALAPPDATA", "")
        if "chrome" in exe.lower():
            path = os.path.join(local, "Google", "Chrome", "User Data")
        elif "brave" in exe.lower():
            path = os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")
        else:
            path = os.path.join(local, "Microsoft", "Edge", "User Data")
        return path if os.path.isdir(path) else ""

    def _launch_browser_for_login(self, url):
        """
        Launch browser with --remote-debugging-port pointing at its real profile
        so cookies are available. Show a dialog to import after login.
        """
        DEBUG_PORT = 9222
        exe = self._find_browser_exe()
        if not exe:
            # Fallback: just open normally
            import webbrowser
            webbrowser.open(url)
            QMessageBox.information(
                self, "Browser geöffnet",
                "Bitte einloggen, dann Cookies manuell importieren\n"
                "über den 🍪-Button."
            )
            return

        user_data = self._find_browser_user_data(exe)

        # Kill any existing instance on this debug port first
        import urllib.request, time
        def _debug_alive():
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1)
                return True
            except Exception:
                return False

        cmd = [exe,
               f"--remote-debugging-port={DEBUG_PORT}",
               "--remote-allow-origins=*",
               "--no-first-run",
               "--no-default-browser-check",
               url]
        if user_data:
            cmd.insert(1, f"--user-data-dir={user_data}")

        try:
            self._debug_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            import webbrowser
            webbrowser.open(url)
            QMessageBox.warning(self, "Hinweis",
                f"Browser konnte nicht mit Debug-Port gestartet werden:\n{e}\n\n"
                "Die Seite wurde normal geöffnet.\n"
                "Cookie-Import ist in dieser Sitzung nicht verfügbar.")
            return

        # Wait up to 5s for debug port
        for _ in range(25):
            if _debug_alive():
                break
            time.sleep(0.2)

        self.status_lbl.setText("Browser geöffnet — bitte einloggen, dann 🍪 drücken")

        # Show non-blocking info; import button is always in toolbar
        msg = QMessageBox(self)
        msg.setWindowTitle("Im Browser einloggen")
        msg.setText(
            "Chrome/Edge wurde geöffnet.\n\n"
            "1️⃣  Logge dich dort ein\n"
            "2️⃣  Komm hierher zurück\n"
            "3️⃣  Drücke den 🍪 Button in der Toolbar"
        )
        msg.setIcon(QMessageBox.Icon.Information)
        msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

    def _import_cookies_from_browser(self, current_url=""):
        """
        Connect to the running browser via CDP WebSocket and import all cookies
        for the current domain into Nova's cookie store.
        """
        import urllib.request, json, time, socket, struct, base64

        DEBUG_PORT = 9222
        url = current_url or self._get_current_url()

        # Domain filter
        domain_filter = ""
        if url.startswith("http"):
            from urllib.parse import urlparse
            host = urlparse(url).hostname or ""
            parts = host.split(".")
            domain_filter = ".".join(parts[-2:]) if len(parts) >= 2 else host

        # Check debug port is alive
        try:
            raw = urllib.request.urlopen(
                f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2
            ).read()
            targets = json.loads(raw)
        except Exception:
            QMessageBox.warning(
                self, "Browser nicht verbunden",
                "Kein Browser mit Debug-Port gefunden.\n\n"
                "Bitte zuerst 🌍 drücken um den Browser zu öffnen,\n"
                "dann einloggen, dann 🍪 drücken."
            )
            return

        page_targets = [t for t in targets if t.get("type") == "page"]
        if not page_targets:
            QMessageBox.warning(self, "Fehler", "Keine Browser-Seite gefunden.")
            return

        ws_url = page_targets[0]["webSocketDebuggerUrl"]
        # Parse ws://host:port/path
        ws_path = ws_url[len(f"ws://127.0.0.1:{DEBUG_PORT}"):]

        # Raw WebSocket handshake + send/recv
        def _ws_connect():
            s = socket.create_connection(("127.0.0.1", DEBUG_PORT), timeout=5)
            key = base64.b64encode(os.urandom(16)).decode()
            s.sendall((
                f"GET {ws_path} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{DEBUG_PORT}\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode())
            # Consume HTTP headers
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = s.recv(256)
                if not chunk:
                    raise ConnectionError("WebSocket handshake failed")
                buf += chunk
            return s

        def _ws_send(s, msg):
            data = msg.encode()
            hdr = bytearray([0x81])
            l = len(data)
            if l < 126:   hdr.append(0x80 | l)
            elif l < 65536:
                hdr += bytes([0x80 | 126]) + struct.pack(">H", l)
            else:
                hdr += bytes([0x80 | 127]) + struct.pack(">Q", l)
            mask = os.urandom(4)
            hdr += mask
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            s.sendall(bytes(hdr) + payload)

        def _ws_recv(s):
            def _read(n):
                buf = b""
                while len(buf) < n:
                    chunk = s.recv(n - len(buf))
                    if not chunk:
                        raise ConnectionError("Socket closed")
                    buf += chunk
                return buf
            b0, b1 = _read(2)
            length = b1 & 0x7f
            if length == 126:  length = struct.unpack(">H", _read(2))[0]
            elif length == 127: length = struct.unpack(">Q", _read(8))[0]
            return _read(length).decode("utf-8", errors="replace")

        try:
            sock = _ws_connect()
            _ws_send(sock, json.dumps({"id": 1, "method": "Network.getAllCookies"}))
            # Read frames until we get our response (id=1)
            cookies_data = []
            for _ in range(10):
                frame = _ws_recv(sock)
                obj = json.loads(frame)
                if obj.get("id") == 1:
                    cookies_data = obj.get("result", {}).get("cookies", [])
                    break
            sock.close()
        except Exception as e:
            QMessageBox.warning(self, "Verbindungsfehler",
                f"Konnte nicht mit Browser kommunizieren:\n{e}\n\n"
                "Stelle sicher dass der Browser noch geöffnet ist.")
            return

        # Filter by domain
        if domain_filter:
            cookies_data = [c for c in cookies_data
                            if domain_filter in c.get("domain", "")]

        if not cookies_data:
            QMessageBox.information(
                self, "Keine Cookies",
                f"Keine Cookies für \"{domain_filter}\" gefunden.\n\n"
                "Bitte erst auf der Seite einloggen,\ndann nochmal 🍪 drücken."
            )
            return

        from PyQt6.QtNetwork import QNetworkCookie
        from PyQt6.QtCore import QDateTime
        store = self._get_profile().cookieStore()
        imported = 0
        for c in cookies_data:
            try:
                qc = QNetworkCookie()
                qc.setName(c["name"].encode())
                qc.setValue(c["value"].encode())
                qc.setDomain(c["domain"])
                qc.setPath(c.get("path", "/"))
                qc.setSecure(c.get("secure", False))
                qc.setHttpOnly(c.get("httpOnly", False))
                exp = c.get("expires", 0)
                if exp and exp > 0:
                    qc.setExpirationDate(QDateTime.fromSecsSinceEpoch(int(exp)))
                store.setCookie(qc)
                imported += 1
            except Exception:
                continue

        QMessageBox.information(
            self, "✔ Cookies importiert",
            f"{imported} Cookies für \"{domain_filter}\" importiert.\n\n"
            "Die Seite wird neu geladen — du solltest jetzt eingeloggt sein."
        )
        view = self._current_web()
        if view:
            view.reload()

    def _get_current_url(self):
        view = self._current_web()
        if view:
            return view.url().toString()
        return self.url_bar.text().strip()

    def start_download_from_extension(self, data):
        """Queue a download requested by the Nova Chrome extension."""
        url = (data.get("url") or "").strip()
        if not url.startswith("http"):
            return False, "invalid url"
        if self.worker and self.worker.isRunning():
            return False, "download already running"

        mode = (data.get("mode") or "video").lower()
        fmt = (data.get("format") or ("mp3" if mode == "audio" else "mp4")).lower()
        quality = data.get("quality") or ("192" if mode == "audio" else "1080p")

        os.makedirs(self.download_dir, exist_ok=True)
        self.dl_btn.setEnabled(False)
        self.dl_progress.setVisible(True)
        self._current_dl_url = url

        if mode == "audio":
            qual = str(quality).split()[0]
            self.mode_combo.setCurrentIndex(1)
            idx = self.dl_fmt_combo.findText(fmt, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.dl_fmt_combo.setCurrentIndex(idx)
            qtext = f"{qual} kbps"
            qidx = self.dl_qual_combo.findText(qtext, Qt.MatchFlag.MatchStartsWith)
            if qidx >= 0:
                self.dl_qual_combo.setCurrentIndex(qidx)
            self.status_lbl.setText(f"⬇  Extension: audio ({fmt.upper()}, {qual}K)…")
            self.worker = YtdlpDownloadThread(
                url=url, output_dir=self.download_dir, audio_format=fmt, quality=qual
            )
            self.worker.finished_signal.connect(self._on_finished_audio)
        else:
            qual_map = {
                "bestvideo+bestaudio": "Best (4K+)",
                "1080p": "1080p", "720p": "720p", "480p": "480p",
                "360p": "360p", "worst": "Smallest",
            }
            self.mode_combo.setCurrentIndex(0)
            idx = self.dl_fmt_combo.findText(fmt, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.dl_fmt_combo.setCurrentIndex(idx)
            qlabel = qual_map.get(quality, quality)
            qidx = self.dl_qual_combo.findText(qlabel, Qt.MatchFlag.MatchFixedString)
            if qidx >= 0:
                self.dl_qual_combo.setCurrentIndex(qidx)
            ytdlp_qual = quality if quality in qual_map else "1080p"
            self.status_lbl.setText(f"⬇  Extension: video ({fmt.upper()}, {qlabel})…")
            self.worker = YtdlpVideoDownloadThread(
                url=url, output_dir=self.download_dir, video_format=fmt, quality=ytdlp_qual
            )
            self.worker.finished_signal.connect(self._on_finished)

        self.worker.progress_signal.connect(self._on_progress)
        self.worker.start()
        return True, "queued"

    def _start_download(self):
        url = self._get_current_url()
        if not url or not url.startswith("http"):
            QMessageBox.warning(self, "Keine URL",
                "Bitte zuerst eine URL in die Adressleiste eingeben\noder ein YouTube-Video öffnen.")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Download läuft", "Es läuft bereits ein Download.")
            return

        os.makedirs(self.download_dir, exist_ok=True)
        self.dl_btn.setEnabled(False)
        self.dl_progress.setVisible(True)
        self._current_dl_url = url  # remember for yt_url storage in callbacks

        is_audio = self.mode_combo.currentIndex() == 1
        fmt = self.dl_fmt_combo.currentText()

        if is_audio:
            qual_raw = self.dl_qual_combo.currentText()
            qual = qual_raw.split()[0]  # "192 kbps" → "192"
            self.status_lbl.setText(f"⬇  Audio-Download startet ({fmt.upper()}, {qual}K)...")
            self.worker = YtdlpDownloadThread(
                url=url,
                output_dir=self.download_dir,
                audio_format=fmt,
                quality=qual
            )
            self.worker.finished_signal.connect(self._on_finished_audio)
        else:
            qual_map = {
                "Best (4K+)": "bestvideo+bestaudio",
                "1080p": "1080p",
                "720p": "720p",
                "480p": "480p",
                "360p": "360p",
                "Smallest": "worst",
            }
            qual = qual_map.get(self.dl_qual_combo.currentText(), "1080p")
            self.status_lbl.setText(f"⬇  Video-Download startet ({fmt.upper()}, {qual})...")
            self.worker = YtdlpVideoDownloadThread(
                url=url,
                output_dir=self.download_dir,
                video_format=fmt,
                quality=qual
            )
            self.worker.finished_signal.connect(self._on_finished)

        self.worker.progress_signal.connect(self._on_progress)
        self.worker.start()

    def _on_progress(self, msg):
        self.status_lbl.setText(msg[:90])

    def _on_finished(self, success, filepath, error):
        self.dl_progress.setVisible(False)
        self.dl_btn.setEnabled(True)
        if success:
            fname = os.path.basename(filepath)
            self.status_lbl.setText(f"✔  Gespeichert: {fname}")
            # Add to video library if db is available
            if self.db and filepath and os.path.exists(filepath):
                title = Path(filepath).stem
                fmt = Path(filepath).suffix.lstrip(".")
                size = os.path.getsize(filepath)
                qual = self.dl_qual_combo.currentText()
                src_url = getattr(self, "_current_dl_url", "")
                if not self.db.get_video_by_path(filepath):
                    self.db.add_video(title, "YouTube", filepath, None, 0, size, fmt, qual, yt_url=src_url)
                else:
                    row = self.db.get_video_by_path(filepath)
                    if row and src_url and not self.db.get_video_yt_url(row[0]):
                        self.db.set_video_yt_url(row[0], src_url)
            QMessageBox.information(self, "Download abgeschlossen",
                f"Video gespeichert:\n{filepath}")
        else:
            self.status_lbl.setText(f"✗  Fehler: {error[:80]}")
            QMessageBox.critical(self, "Download fehlgeschlagen", error)

    def _on_finished_audio(self, success, filepath, error):
        self.dl_progress.setVisible(False)
        self.dl_btn.setEnabled(True)
        if success:
            fname = os.path.basename(filepath)
            self.status_lbl.setText(f"✔  Gespeichert: {fname}")
            # Add to music library if db is available
            if self.db and filepath and os.path.exists(filepath):
                try:
                    audio = MutagenFile(filepath, easy=True)
                    title = Path(filepath).stem
                    artist = "Unknown Artist"
                    album = "Unknown Album"
                    duration = 0
                    if audio:
                        title = audio.get("title", [title])[0]
                        artist = audio.get("artist", [artist])[0]
                        album = audio.get("album", [album])[0]
                        if hasattr(audio.info, "length"):
                            duration = int(audio.info.length * 1000)
                except Exception:
                    title = Path(filepath).stem
                    artist = "Unknown Artist"
                    album = "Unknown Album"
                    duration = 0
                src_url = getattr(self, "_current_dl_url", "")
                if not self.db.get_song_by_path(filepath):
                    self.db.add_song(title, artist, album, filepath, None, duration, yt_url=src_url)
                else:
                    row = self.db.get_song_by_path(filepath)
                    if row and src_url and not self.db.get_yt_url(row[0]):
                        self.db.set_yt_url(row[0], src_url)
            QMessageBox.information(self, "Download abgeschlossen",
                f"Audio gespeichert:\n{filepath}")
        else:
            self.status_lbl.setText(f"✗  Fehler: {error[:80]}")
            QMessageBox.critical(self, "Download fehlgeschlagen", error)


# ──────────────────────────── SMOOTH SCROLL LIST ────────────────────────────

class SmoothListWidget(QListWidget):
    """
    QListWidget with true pixel-level smooth scrolling.

    Key fixes vs. the naive approach:
    - ScrollPerPixel policy so the scrollbar moves in single-pixel steps.
    - wheelEvent calls event.accept() AND does NOT call super() — this
      completely suppresses Qt's built-in item-unit snap jump.
    - A 16 ms QTimer drives kinetic deceleration at ~60 fps.
    """

    # Tweak these to taste:
    _IMPULSE_SCALE = 2.5   # pixels of velocity added per 15° wheel notch
    _FRICTION      = 0.88  # velocity multiplied each frame (lower = shorter glide)
    _MIN_VEL       = 0.3   # velocity below which we stop the timer

    def __init__(self, parent=None):
        super().__init__(parent)
        # CRITICAL: pixel-level scrollbar so setValue(n) moves exactly n pixels
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        self._velocity = 0.0
        self._remainder = 0.0   # sub-pixel accumulator to avoid rounding snap
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(16)          # ~60 fps
        self._scroll_timer.timeout.connect(self._tick)

    def wheelEvent(self, event):
        # angleDelta().y() is typically ±120 per notch (15°).
        # We intentionally do NOT call super().wheelEvent() — that would
        # apply Qt's own item-unit scroll on top of ours, causing the snap.
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        # Add a proportional impulse (negative because scroll-down = positive bar)
        self._velocity -= delta * self._IMPULSE_SCALE / 15.0

        if not self._scroll_timer.isActive():
            self._remainder = 0.0
            self._scroll_timer.start()

        event.accept()   # swallow the event completely

    def _tick(self):
        if abs(self._velocity) < self._MIN_VEL:
            self._velocity = 0.0
            self._remainder = 0.0
            self._scroll_timer.stop()
            return

        bar = self.verticalScrollBar()

        # Sub-pixel accumulation: carry fractional pixels across frames
        # so slow deceleration never gets stuck at 0-pixel steps.
        move = self._velocity + self._remainder
        pixels = int(move)
        self._remainder = move - pixels

        new_val = bar.value() + pixels
        clamped = max(bar.minimum(), min(bar.maximum(), new_val))
        bar.setValue(clamped)

        # Kill momentum at edges to prevent stuck timer
        if clamped == bar.minimum() or clamped == bar.maximum():
            self._velocity = 0.0
            self._remainder = 0.0
            self._scroll_timer.stop()
            return

        self._velocity *= self._FRICTION


class SmoothScrollArea(QScrollArea):
    """
    QScrollArea with kinetic smooth scrolling for manual mouse-wheel use.
    No auto-scroll — the user controls position entirely.
    """
    _IMPULSE_SCALE = 0.8
    _FRICTION      = 0.75
    _MIN_VEL       = 0.3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._velocity  = 0.0
        self._remainder = 0.0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(16)   # ~60 fps
        self._scroll_timer.timeout.connect(self._tick)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self._velocity -= delta * self._IMPULSE_SCALE / 15.0
        if not self._scroll_timer.isActive():
            self._remainder = 0.0
            self._scroll_timer.start()
        event.accept()

    def _tick(self):
        if abs(self._velocity) < self._MIN_VEL:
            self._velocity  = 0.0
            self._remainder = 0.0
            self._scroll_timer.stop()
            return
        bar  = self.verticalScrollBar()
        move = self._velocity + self._remainder
        pixels = int(move)
        self._remainder = move - pixels
        new_val = bar.value() + pixels
        clamped = max(bar.minimum(), min(bar.maximum(), new_val))
        bar.setValue(clamped)
        if clamped in (bar.minimum(), bar.maximum()):
            self._velocity  = 0.0
            self._remainder = 0.0
            self._scroll_timer.stop()
            return
        self._velocity *= self._FRICTION


class LyricsFullscreenOverlay(QFrame):
    """Full-window lyrics overlay with zoom (Ctrl+wheel, +/- keys, toolbar buttons)."""

    _FONT_MIN = 12
    _FONT_MAX = 80
    _FONT_DEFAULT = 18

    def __init__(self, parent, theme, title_text, lines):
        super().__init__(parent)
        self._theme = theme
        self._font_size = self._FONT_DEFAULT
        self.setStyleSheet(f"background: {theme['bg']}; border: none;")
        self.setGeometry(parent.rect())
        self.raise_()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        title_lbl = QLabel(title_text)
        title_lbl.setFont(QFont("", 15, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {theme['text']}; background: transparent;")

        zoom_out = QPushButton("−")
        zoom_out.setObjectName("toolbar_btn")
        zoom_out.setFixedSize(30, 30)
        zoom_out.setToolTip("Zoom out (−)")

        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setFixedWidth(44)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_lbl.setObjectName("time_label")

        zoom_in = QPushButton("+")
        zoom_in.setObjectName("toolbar_btn")
        zoom_in.setFixedSize(30, 30)
        zoom_in.setToolTip("Zoom in (+)")

        reset_btn = QPushButton("100%")
        reset_btn.setObjectName("toolbar_btn")
        reset_btn.setFixedHeight(30)
        reset_btn.setToolTip("Reset zoom (0)")

        close_btn = QPushButton("✕  Close")
        close_btn.setObjectName("toolbar_btn")
        close_btn.setFixedHeight(30)

        zoom_out.clicked.connect(lambda: self._zoom_by(-2))
        zoom_in.clicked.connect(lambda: self._zoom_by(2))
        reset_btn.clicked.connect(self._zoom_reset)
        close_btn.clicked.connect(self.close)

        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(zoom_out)
        hdr.addWidget(self._zoom_lbl)
        hdr.addWidget(zoom_in)
        hdr.addWidget(reset_btn)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        self._scroll = SmoothScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._lyrics_lbl = QLabel("\n".join(lines))
        self._lyrics_lbl.setWordWrap(True)
        self._lyrics_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._lyrics_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._lyrics_lbl.setMargin(8)
        self._scroll.setWidget(self._lyrics_lbl)
        layout.addWidget(self._scroll, 1)

        hint = QLabel("Ctrl + scroll  ·  + / −  ·  0 reset  ·  Esc close")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setObjectName("time_label")
        layout.addWidget(hint)

        self._apply_font_size()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def _zoom_pct(self):
        return int(round(self._font_size / self._FONT_DEFAULT * 100))

    def _apply_font_size(self):
        t = self._theme
        self._lyrics_lbl.setStyleSheet(
            f"color: {t['text']}; background: transparent; "
            f"font-size: {self._font_size}px; line-height: 1.8;"
        )
        self._zoom_lbl.setText(f"{self._zoom_pct()}%")

    def _zoom_by(self, delta):
        self._font_size = max(self._FONT_MIN, min(self._FONT_MAX, self._font_size + delta))
        self._apply_font_size()

    def _zoom_reset(self):
        self._font_size = self._FONT_DEFAULT
        self._apply_font_size()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            dy = event.angleDelta().y()
            if dy > 0:
                self._zoom_by(2)
            elif dy < 0:
                self._zoom_by(-2)
            event.accept()
            return
        self._scroll.wheelEvent(event)

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self.close()
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_by(2)
        elif k == Qt.Key.Key_Minus:
            self._zoom_by(-2)
        elif k == Qt.Key.Key_0:
            self._zoom_reset()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        parent = self.parentWidget()
        if parent:
            self.setGeometry(parent.rect())

    def closeEvent(self, event):
        self.deleteLater()
        super().closeEvent(event)


class PlaylistContentDialog(QDialog):
    """Dialog for adding, removing, and reordering songs/videos in a playlist."""

    def __init__(self, parent, db, playlist_id, playlist_name):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.setWindowTitle(f"Playlist bearbeiten – {playlist_name}")
        self.setMinimumSize(860, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        title_lbl = QLabel(f"🎵  {playlist_name}")
        title_lbl.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        main_layout.addWidget(title_lbl)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: library (all songs + videos) ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_header = QLabel("Bibliothek")
        left_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        left_layout.addWidget(left_header)

        self.lib_search = QLineEdit()
        self.lib_search.setPlaceholderText("🔍  Suchen…")
        self.lib_search.textChanged.connect(self._refresh_library)
        left_layout.addWidget(self.lib_search)

        self.lib_list = QListWidget()
        self.lib_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.lib_list.setIconSize(QSize(40, 40))
        left_layout.addWidget(self.lib_list)

        add_btn = QPushButton("➕  Hinzufügen →")
        add_btn.clicked.connect(self._add_selected)
        left_layout.addWidget(add_btn)

        splitter.addWidget(left)

        # ── RIGHT: current playlist contents ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_header = QLabel("Playlist-Inhalt")
        right_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        right_layout.addWidget(right_header)

        self.pl_list = QListWidget()
        self.pl_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.pl_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.pl_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.pl_list.setIconSize(QSize(40, 40))
        # Connect after the widget is fully constructed to avoid model() crash on some Qt builds
        self.pl_list.model().rowsMoved.connect(self._on_rows_moved)
        right_layout.addWidget(self.pl_list)

        btn_row = QHBoxLayout()
        move_up_btn = QPushButton("▲  Hoch")
        move_up_btn.clicked.connect(self._move_up)
        move_dn_btn = QPushButton("▼  Runter")
        move_dn_btn.clicked.connect(self._move_down)
        remove_btn = QPushButton("✂  Entfernen")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(move_up_btn)
        btn_row.addWidget(move_dn_btn)
        btn_row.addStretch()
        btn_row.addWidget(remove_btn)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([400, 400])
        main_layout.addWidget(splitter)

        close_btn = QPushButton("✔  Fertig")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn)

        self._refresh_library()
        self._refresh_playlist()

    # ── helpers ──────────────────────────────────────────────────────

    def _refresh_library(self):
        search = self.lib_search.text().strip()
        self.lib_list.clear()

        songs = self.db.get_all_songs(search)
        for song in songs:
            sid, title, artist, album, path, cover_path, duration, fav, rating, plays = song
            label = f"♪  {title}\n    {artist}  ·  {album}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("song", sid, path))
            if cover_path and os.path.exists(cover_path):
                px = QPixmap(cover_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            self.lib_list.addItem(item)

        videos = self.db.get_all_videos(search)
        for vid in videos:
            vid_id, title, channel, path, thumb_path, duration, file_size, fmt, resolution = vid
            label = f"🎬  {title}\n    {channel}  {resolution}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("video", vid_id, path))
            if thumb_path and os.path.exists(thumb_path):
                px = QPixmap(thumb_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            self.lib_list.addItem(item)

    def _refresh_playlist(self):
        self.pl_list.clear()

        songs = self.db.get_playlist_songs(self.playlist_id)
        for song in songs:
            sid, title, artist, album, path, cover_path, duration, fav, rating, plays = song
            label = f"♪  {title}\n    {artist}  ·  {album}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("song", sid, path))
            if cover_path and os.path.exists(cover_path):
                px = QPixmap(cover_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            self.pl_list.addItem(item)

        videos = self.db.get_playlist_videos(self.playlist_id)
        for vid in videos:
            vid_id, title, channel, path, thumb_path, duration, file_size, fmt, resolution = vid
            label = f"🎬  {title}\n    {channel}  {resolution}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("video", vid_id, path))
            if thumb_path and os.path.exists(thumb_path):
                px = QPixmap(thumb_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(px))
            self.pl_list.addItem(item)

    def _add_selected(self):
        for item in self.lib_list.selectedItems():
            kind, item_id, path = item.data(Qt.ItemDataRole.UserRole)
            if kind == "song":
                if not self.db.song_in_playlist(self.playlist_id, item_id):
                    self.db.add_song_to_playlist(self.playlist_id, item_id)
            else:
                if not self.db.video_in_playlist(self.playlist_id, item_id):
                    self.db.add_video_to_playlist(self.playlist_id, item_id)
        self._refresh_playlist()

    def _remove_selected(self):
        rows = sorted(
            {self.pl_list.row(i) for i in self.pl_list.selectedItems()},
            reverse=True
        )
        for row in rows:
            item = self.pl_list.item(row)
            if item:
                kind, item_id, path = item.data(Qt.ItemDataRole.UserRole)
                if kind == "song":
                    self.db.remove_song_from_playlist(self.playlist_id, item_id)
                else:
                    self.db.remove_video_from_playlist(self.playlist_id, item_id)
        self._refresh_playlist()

    def _move_up(self):
        row = self.pl_list.currentRow()
        if row > 0:
            item = self.pl_list.takeItem(row)
            self.pl_list.insertItem(row - 1, item)
            self.pl_list.setCurrentRow(row - 1)
            self._save_order()

    def _move_down(self):
        row = self.pl_list.currentRow()
        if row < self.pl_list.count() - 1:
            item = self.pl_list.takeItem(row)
            self.pl_list.insertItem(row + 1, item)
            self.pl_list.setCurrentRow(row + 1)
            self._save_order()

    def _on_rows_moved(self, *args):
        self._save_order()

    def _save_order(self):
        """Persist the current visual order of songs to the DB."""
        song_ids = []
        for i in range(self.pl_list.count()):
            item = self.pl_list.item(i)
            kind, item_id, path = item.data(Qt.ItemDataRole.UserRole)
            if kind == "song":
                song_ids.append(item_id)
        if song_ids:
            self.db.reorder_playlist_songs(self.playlist_id, song_ids)




# ══════════════════════════════════════════════════════════════════════════════
#  PLAYLIST SHARE / REDEEM  (paste.rs — no API key needed)
# ══════════════════════════════════════════════════════════════════════════════

def _paste_rs_upload(payload: str) -> str:
    """Upload text to paste.rs and return the paste ID (the path component)."""
    import urllib.request
    data = payload.encode("utf-8")
    req = urllib.request.Request(
        "https://paste.rs/",
        data=data,
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        url = resp.read().decode().strip()   # e.g. https://paste.rs/aBcD
    return url.split("/")[-1]               # "aBcD"


def _paste_rs_fetch(paste_id: str) -> str:
    """Fetch raw text from paste.rs by ID."""
    import urllib.request
    url = f"https://paste.rs/{paste_id}"
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


class _ShareUploadThread(QThread):
    done_signal  = pyqtSignal(bool, str)   # success, paste_id or error

    def __init__(self, payload: str):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            paste_id = _paste_rs_upload(self.payload)
            self.done_signal.emit(True, paste_id)
        except Exception as e:
            self.done_signal.emit(False, str(e))


class _RedeemFetchThread(QThread):
    done_signal = pyqtSignal(bool, str)   # success, raw JSON or error

    def __init__(self, paste_id: str):
        super().__init__()
        self.paste_id = paste_id

    def run(self):
        try:
            text = _paste_rs_fetch(self.paste_id)
            self.done_signal.emit(True, text)
        except Exception as e:
            self.done_signal.emit(False, str(e))


class SharePlaylistDialog(QDialog):
    """Build a shareable code for a playlist using paste.rs."""

    def __init__(self, parent, db, playlist_id):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.setWindowTitle("🔗  Playlist teilen")
        self.setFixedSize(520, 420)
        self._thread = None

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        pl = db.get_playlist(playlist_id)
        pl_name = pl[1] if pl else "Playlist"

        hdr = QLabel(f"🔗  Playlist teilen: <b>{pl_name}</b>")
        hdr.setFont(QFont("Arial", 13))
        layout.addWidget(hdr)

        info = QLabel(
            "Generiert einen kurzen Code. Dein Freund gibt ihn in Nova ein und die\n"
            "Medien werden automatisch via yt-dlp heruntergeladen.\n\n"
            "⚠  Nur Einträge mit gespeicherter YouTube-URL werden einbezogen.\n"
            "   (URL kann über Rechtsklick → Bearbeiten gesetzt werden.)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Songs mit URL
        songs = db.get_playlist_songs(playlist_id)
        self._entries = []
        missing = 0
        for s in songs:
            sid, title, artist = s[0], s[1], s[2]
            yt_url = db.get_yt_url(sid) or ""
            if yt_url:
                self._entries.append({"type": "song", "title": title, "artist": artist, "yt_url": yt_url})
            else:
                missing += 1

        # Videos mit URL
        videos = db.get_playlist_videos(playlist_id)
        missing_videos = 0
        for v in videos:
            vid_id, title, channel = v[0], v[1], v[2]
            yt_url = db.get_video_yt_url(vid_id) or ""
            if yt_url:
                self._entries.append({"type": "video", "title": title, "artist": channel, "yt_url": yt_url})
            else:
                missing_videos += 1

        total_missing = missing + missing_videos
        total_lbl = QLabel(
            f"✓ {len(self._entries)} Eintrag/Einträge mit URL  |  "
            f"⚠ {total_missing} ohne URL (werden übersprungen)"
        )
        total_lbl.setWordWrap(True)
        layout.addWidget(total_lbl)

        # Code-Anzeige
        self.code_edit = QLineEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setPlaceholderText("Code erscheint hier nach dem Hochladen…")
        self.code_edit.setFont(QFont("Courier New", 16))
        self.code_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.code_edit)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.share_btn = QPushButton("☁  Code generieren")
        self.share_btn.setFixedHeight(36)
        self.share_btn.clicked.connect(self._upload)
        self.copy_btn = QPushButton("📋  Kopieren")
        self.copy_btn.setFixedHeight(36)
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy)
        close_btn = QPushButton("Schließen")
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.share_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

        if not self._entries:
            self.share_btn.setEnabled(False)
            self.status_lbl.setText("Keine Einträge mit YouTube-URL vorhanden.")

    def _upload(self):
        pl = self.db.get_playlist(self.playlist_id)
        payload = json.dumps({
            "nova_playlist": True,
            "version": 2,
            "name": pl[1] if pl else "Shared Playlist",
            "songs": self._entries,   # each entry has a "type" field: "song" or "video"
        }, ensure_ascii=False, indent=2)

        self.share_btn.setEnabled(False)
        self.status_lbl.setText("⏳  Wird hochgeladen…")

        self._thread = _ShareUploadThread(payload)
        self._thread.done_signal.connect(self._on_done)
        self._thread.start()

    def _on_done(self, success, result):
        if success:
            self.code_edit.setText(result)
            self.copy_btn.setEnabled(True)
            self.status_lbl.setText("✅  Code fertig! Teile ihn mit deinem Freund.")
        else:
            self.status_lbl.setText(f"❌  Fehler: {result}")
            self.share_btn.setEnabled(True)

    def _copy(self):
        QApplication.clipboard().setText(self.code_edit.text())
        self.status_lbl.setText("📋  In Zwischenablage kopiert!")


class RedeemCodeDialog(QDialog):
    """Enter a share code, fetch the playlist JSON, download songs via yt-dlp."""

    def __init__(self, parent, db, download_dir):
        super().__init__(parent)
        self.db = db
        self.download_dir = download_dir
        self.setWindowTitle("🎁  Playlist-Code einlösen")
        self.setFixedSize(560, 520)
        self._fetch_thread = None
        self._dl_worker = None
        self._pending_songs = []
        self._downloaded = []   # (filepath, yt_url)
        self._success = 0
        self._fail = 0
        self._pl_name = "Shared Playlist"

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QLabel("🎁  Playlist-Code einlösen")
        hdr.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        layout.addWidget(hdr)

        info = QLabel(
            "Gib den Code ein, den dein Freund mit dir geteilt hat.\n"
            "Die Songs werden automatisch von YouTube heruntergeladen und\n"
            "als neue Playlist in deine Bibliothek importiert."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        code_row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("z.B.  aBcD3f")
        self.code_edit.setFont(QFont("Courier New", 14))
        self.code_edit.setFixedHeight(36)
        self.fetch_btn = QPushButton("🔍  Laden")
        self.fetch_btn.setFixedHeight(36)
        self.fetch_btn.clicked.connect(self._fetch)
        code_row.addWidget(self.code_edit, 1)
        code_row.addWidget(self.fetch_btn)
        layout.addLayout(code_row)

        self.preview_lbl = QLabel("")
        self.preview_lbl.setWordWrap(True)
        layout.addWidget(self.preview_lbl)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(160)
        self.log.setPlaceholderText("Fortschritt erscheint hier…")
        layout.addWidget(self.log)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.dl_btn = QPushButton("⬇  Herunterladen & importieren")
        self.dl_btn.setFixedHeight(36)
        self.dl_btn.setEnabled(False)
        self.dl_btn.clicked.connect(self._start_download)
        self.close_btn = QPushButton("Schließen")
        self.close_btn.setFixedHeight(36)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.dl_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _log(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _fetch(self):
        code = self.code_edit.text().strip()
        if not code:
            return
        self.fetch_btn.setEnabled(False)
        self.preview_lbl.setText("⏳  Wird geladen…")
        self._fetch_thread = _RedeemFetchThread(code)
        self._fetch_thread.done_signal.connect(self._on_fetched)
        self._fetch_thread.start()

    def _on_fetched(self, success, raw):
        self.fetch_btn.setEnabled(True)
        if not success:
            self.preview_lbl.setText(f"❌  Fehler: {raw}")
            return
        try:
            data = json.loads(raw)
            if not data.get("nova_playlist"):
                raise ValueError("Kein gültiger Nova-Playlist-Code.")
            self._pl_name = data.get("name", "Shared Playlist")
            self._pending_songs = data.get("songs", [])
            self.preview_lbl.setText(
                f"✅  <b>{self._pl_name}</b>  —  {len(self._pending_songs)} Song(s) gefunden.\n"
                f"Klicke 'Herunterladen' um alle zu importieren."
            )
            self.dl_btn.setEnabled(bool(self._pending_songs))
        except Exception as e:
            self.preview_lbl.setText(f"❌  Ungültiger Code: {e}")

    def _start_download(self):
        if not self._pending_songs:
            return
        self.dl_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._downloaded = []
        self._success = 0
        self._fail = 0
        self._queue = list(self._pending_songs)
        self._log(f"Starte Download von {len(self._queue)} Song(s)…")
        self._log("─" * 50)
        self._download_next()

    def _download_next(self):
        if not self._queue:
            self._all_done()
            return
        song = self._queue.pop(0)
        url = song.get("yt_url", "")
        title = song.get("title", "?")
        entry_type = song.get("type", "song")
        self._current_song_meta = song
        self._log(f"⬇  {'🎬' if entry_type == 'video' else '♫'}  {title}  ({url})")
        if entry_type == "video":
            self._dl_worker = YtdlpVideoDownloadThread(url, self.download_dir, "mp4", "bestvideo+bestaudio")
        else:
            self._dl_worker = YtdlpDownloadThread(url, self.download_dir)
        self._dl_worker.progress_signal.connect(lambda m: None)  # suppress verbose log
        self._dl_worker.finished_signal.connect(self._on_one_done)
        self._dl_worker.start()

    def _on_one_done(self, success, filepath, error):
        meta = self._current_song_meta
        if success and filepath:
            self._downloaded.append((filepath, meta.get("yt_url", ""), meta))
            self._success += 1
            self._log(f"  ✓ {os.path.basename(filepath)}")
        else:
            self._fail += 1
            self._log(f"  ✗ Fehler: {error}")
        self._log("─" * 50)
        self._download_next()

    def _all_done(self):
        self.progress_bar.setVisible(False)
        self._log(f"\n✅  Fertig: {self._success} erfolgreich, {self._fail} fehlgeschlagen.")

        # Import into library — handle songs and videos separately
        added_songs = 0
        added_videos = 0
        imported_song_ids = []
        imported_video_ids = []

        for fp, yt_url, meta in self._downloaded:
            entry_type = meta.get("type", "song")

            if entry_type == "video" and any(fp.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS):
                fname = os.path.basename(fp)
                title = meta.get("title", Path(fname).stem)
                channel = meta.get("artist", "")
                fmt = Path(fname).suffix.lstrip(".")
                file_size = os.path.getsize(fp) if os.path.exists(fp) else 0
                if not self.db.get_video_by_path(fp):
                    self.db.add_video(title, channel, fp, None, 0, file_size, fmt, "", yt_url=yt_url)
                    added_videos += 1
                row = self.db.get_video_by_path(fp)
                if row:
                    imported_video_ids.append(row[0])

            elif entry_type != "video" and any(fp.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                title = meta.get("title", Path(fp).stem)
                artist = meta.get("artist", "Unknown Artist")
                album = meta.get("album", "Unknown Album")
                duration = 0
                cover_path = None
                try:
                    audio = MutagenFile(fp, easy=True)
                    if audio:
                        title = audio.get("title", [title])[0]
                        artist = audio.get("artist", [artist])[0]
                        album = audio.get("album", [album])[0]
                        if hasattr(audio, "info") and hasattr(audio.info, "length"):
                            duration = int(audio.info.length * 1000)
                except Exception:
                    pass
                cover_path = extract_cover_from_audio(fp)
                if not self.db.get_song_by_path(fp):
                    self.db.add_song(title, artist, album, fp, cover_path, duration, yt_url=yt_url)
                    added_songs += 1
                row = self.db.get_song_by_path(fp)
                if row:
                    imported_song_ids.append(row[0])

        # Create playlist and add all imported items
        if imported_song_ids or imported_video_ids:
            pl_name = self._pl_name
            existing = [p[1] for p in self.db.get_all_playlists()]
            base = pl_name
            counter = 2
            while pl_name in existing:
                pl_name = f"{base} ({counter})"
                counter += 1
            pid = self.db.create_playlist(pl_name)
            if pid:
                for sid in imported_song_ids:
                    self.db.add_song_to_playlist(pid, sid)
                for vid in imported_video_ids:
                    self.db.add_video_to_playlist(pid, vid)

        self._log(f"→ {added_songs} neue Song(s), {added_videos} neue Video(s) importiert.")
        self._log(f"→ Playlist '{self._pl_name}' angelegt.")
        QMessageBox.information(
            self, "Import abgeschlossen",
            f"✅  {self._success} Eintrag/Einträge heruntergeladen.\n"
            f"{added_songs} Song(s) + {added_videos} Video(s) in Bibliothek importiert.\n"
            f"Playlist '{self._pl_name}' wurde angelegt."
        )
        self.close_btn.setText("Fertig")
        self.close_btn.clicked.disconnect()
        self.close_btn.clicked.connect(self.accept)


# ──────────────────────────── DISCORD RICH PRESENCE ────────────────────────────

class DiscordRPC:
    """
    Thin wrapper around pypresence.Presence.
    Alle Fehler werden still abgefangen, damit Discord-Probleme
    die App nie abstürzen lassen.
    """
    APP_ID = _DISCORD_CLIENT_ID

    def __init__(self):
        self._rpc: "_DiscordPresence | None" = None
        self._connected = False
        self._enabled = False          # wird per Einstellung gesetzt
        self._last_state: dict = {}
        self._last_details: str = ""   # für schnellen Vergleich ohne Timestamps

    # ── Verbindung ──────────────────────────────────────────────────────
    def connect(self):
        """Versucht, eine Verbindung zum lokalen Discord-Client herzustellen."""
        if not _PYPRESENCE_AVAILABLE or self._connected:
            return
        try:
            self._rpc = _DiscordPresence(self.APP_ID)
            self._rpc.connect()
            self._connected = True
            print("[Nova] Discord Rich Presence verbunden.")
        except Exception as e:
            self._rpc = None
            self._connected = False
            print(f"[Nova] Discord RPC Verbindungsfehler: {e}")

    def disconnect(self):
        """Trennt die Verbindung sauber."""
        if not self._connected or self._rpc is None:
            return
        try:
            self._rpc.clear()
            self._rpc.close()
        except Exception:
            pass
        finally:
            self._rpc = None
            self._connected = False
            print("[Nova] Discord Rich Presence getrennt.")

    # ── Status setzen ────────────────────────────────────────────────────
    def set_playing(self, title: str, artist: str, album: str = "",
                    duration_ms: int = 0, elapsed_ms: int = 0,
                    is_video: bool = False):
        """Setzt den 'Spielt gerade'-Status in Discord."""
        if not self._enabled:
            return
        if not self._connected:
            self.connect()
        if not self._connected:
            return

        import time
        state_line = artist if artist else "Unknown Artist"
        if album:
            state_line += f"  ·  {album}"

        details = title[:128] if title else "Unknown"
        state_line = state_line[:128]

        # Timestamps: nur start setzen → Discord zählt vorwärts (vergangene Zeit).
        # end weglassen, sonst zählt Discord rückwärts.
        start_ts = int(time.time()) - (elapsed_ms // 1000)

        large_image = "nova_logo"          # Asset-Name in der Discord Dev-App
        large_text = "NovaX7"
        # Hinweis: small_image-Assets ("video"/"music") müssen in der Discord Dev-App
        # als Bild-Assets hochgeladen sein. Falls nicht vorhanden, werden sie weggelassen.
        small_text = "Video" if is_video else "Musik"

        new_state = {
            "details": details,
            "state": state_line,
            "large_image": large_image,
            "large_text": large_text,
            "small_text": small_text,
            "start": start_ts,
        }

        # Wenn sich der Medientyp (Audio ↔ Video) geändert hat, _last_state leeren,
        # damit der Update garantiert durchgeführt wird.
        last_type = self._last_state.get("small_text")
        if last_type is not None and last_type != small_text:
            self._last_state = {}

        # Aktualisieren wenn sich Details, State (Position) oder Typ geändert hat.
        # start-Timestamp wird ignoriert da er sich jede Sekunde ändert.
        def _cmp(s):
            return (s.get("details"), s.get("state"), s.get("small_text"))

        if _cmp(new_state) == _cmp(self._last_state):
            return
        self._last_state = new_state

        try:
            self._rpc.update(**new_state)
        except Exception as e:
            print(f"[Nova] Discord RPC Update-Fehler: {e}")
            # Verbindung verloren → zurücksetzen, beim nächsten Aufruf neu verbinden
            self._connected = False
            self._rpc = None
            self._last_state = {}

    def set_paused(self, title: str, artist: str):
        """Setzt den 'Pausiert'-Status in Discord."""
        if not self._enabled:
            return
        if not self._connected:
            self.connect()
        if not self._connected:
            return

        details = (title[:125] + " ⏸") if title else "⏸ Pausiert"
        state_line = (artist[:128] if artist else "Nova Music Player")

        new_state = {
            "details": details,
            "state": state_line,
            "large_image": "nova_logo",
            "large_text": "Nova Music Player",
            "small_image": "pause",
            "small_text": "Pausiert",
        }
        if new_state == self._last_state:
            return
        self._last_state = new_state

        try:
            self._rpc.update(**new_state)
        except Exception as e:
            print(f"[Nova] Discord RPC Pause-Fehler: {e}")
            self._connected = False
            self._rpc = None
            self._last_state = {}

    def clear(self):
        """Entfernt den Status aus Discord (z.B. wenn nichts läuft)."""
        if not self._connected or self._rpc is None:
            return
        try:
            self._rpc.clear()
            self._last_state = {}
        except Exception:
            pass

    # ── Enable / Disable ─────────────────────────────────────────────────
    def enable(self):
        self._enabled = True
        if not self._connected:
            self.connect()

    def disable(self):
        self._enabled = False
        self.disconnect()


# ──────────────────────────── LYRICS FETCHER ────────────────────────────

class LyricsFetcher(QThread):
    """Fetches lyrics with multiple APIs and smart title cleaning."""
    lyrics_ready   = pyqtSignal(str, list)
    lyrics_failed  = pyqtSignal(str)

    def __init__(self, artist: str, title: str, parent=None):
        super().__init__(parent)
        self.artist = artist
        self.title  = title

    @staticmethod
    def _clean(text: str) -> str:
        """Strip common noise from artist/title strings."""
        import re
        # Remove feat./ft. and everything after
        text = re.sub(r'\s*[\(\[]?(?:feat|ft)\.?[^\)\]]*[\)\]]?', '', text, flags=re.IGNORECASE)
        # Remove parenthetical suffixes like (Official Video), [Lyrics], (Radio Edit)
        text = re.sub(r'\s*[\(\[][^\)\]]{0,40}[\)\]]', '', text)
        # Remove trailing dash-separated extras: "Title - Remastered 2020"
        text = re.sub(r'\s*-\s*(remaster|remix|live|acoustic|radio|edit|version|extended|official).*$',
                      '', text, flags=re.IGNORECASE)
        return text.strip()

    def _try_lyrics_ovh(self, artist: str, title: str):
        a = urllib.parse.quote(artist)
        t = urllib.parse.quote(title)
        url = f"https://api.lyrics.ovh/v1/{a}/{t}"
        req = urllib.request.Request(url, headers={"User-Agent": "NovaX7/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        return data.get("lyrics", "").strip()

    def _try_lrclib(self, artist: str, title: str):
        """lrclib.net — free, no key, returns plain lyrics or synced LRC."""
        params = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
        url = f"https://lrclib.net/api/get?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "NovaX7/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        # Prefer plain lyrics; fall back to synced (strip timestamps)
        plain = (data.get("plainLyrics") or "").strip()
        if plain:
            return plain
        synced = (data.get("syncedLyrics") or "").strip()
        if synced:
            import re
            # Strip [mm:ss.xx] timestamps
            plain = re.sub(r'^\[\d+:\d+\.\d+\]\s*', '', synced, flags=re.MULTILINE)
            return plain.strip()
        return ""

    def _try_lrclib_search(self, artist: str, title: str):
        """lrclib search endpoint — broader fuzzy match."""
        params = urllib.parse.urlencode({"q": f"{artist} {title}".strip()})
        url = f"https://lrclib.net/api/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "NovaX7/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            results = json.loads(resp.read().decode())
        if not isinstance(results, list):
            return ""
        for item in results[:5]:
            plain = (item.get("plainLyrics") or "").strip()
            if plain:
                return plain
            synced = (item.get("syncedLyrics") or "").strip()
            if synced:
                import re
                plain = re.sub(r'^\[\d+:\d+\.\d+\]\s*', '', synced, flags=re.MULTILINE)
                return plain.strip()
        return ""

    def _try_genius(self, artist: str, title: str):
        """Genius search scrape — no API key needed."""
        import re
        query = urllib.parse.quote(f"{artist} {title}".strip())
        url = f"https://genius.com/api/search/multi?per_page=3&q={query}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        # Find the first song result
        song_url = ""
        for section in data.get("response", {}).get("sections", []):
            if section.get("type") == "song":
                hits = section.get("hits", [])
                if hits:
                    song_url = hits[0].get("result", {}).get("url", "")
                    break
        if not song_url:
            return ""
        # Scrape the lyrics page
        req2 = urllib.request.Request(song_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            html = resp2.read().decode("utf-8", errors="replace")
        # Extract text from data-lyrics-container divs
        containers = re.findall(r'data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not containers:
            return ""
        lines = []
        for block in containers:
            # Replace <br> tags with newlines
            block = re.sub(r'<br\s*/?>', "\n", block, flags=re.IGNORECASE)
            # Remove all other HTML tags
            block = re.sub(r'<[^>]+>', '', block)
            # Decode HTML entities
            block = block.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'").replace("&quot;", '"')
            lines.append(block.strip())
        return "\n".join(lines).strip()

    def run(self):
        raw   = ""
        tried = []

        print(f"[Lyrics] Searching for: artist={self.artist!r}  title={self.title!r}")

        import re as _re2

        def _strip_artist_from_title(artist: str, title: str) -> str:
            """Remove artist name from the start of the title if it appears there."""
            if not artist:
                return title
            # Match "Artist - Title", "Artist: Title", "Artist — Title"
            pattern = r'^' + _re2.escape(artist) + r'\s*[-:—]\s*'
            cleaned = _re2.sub(pattern, '', title, flags=_re2.IGNORECASE).strip()
            return cleaned if cleaned else title

        artist_clean = self._clean(self.artist)
        title_clean  = self._clean(self.title)

        # Build a de-duplicated list of (artist, title) attempts
        _t0 = _strip_artist_from_title(self.artist, self.title)
        _t1 = _strip_artist_from_title(artist_clean, title_clean)
        _t2 = _t1.title()          # "lot of me" → "Lot Of Me"
        _t3 = _t1.capitalize()     # "LOT OF ME" → "Lot of me"

        _seen = set()
        _attempts = []
        for _a, _t in [
            (self.artist,  _t0),
            (artist_clean, _t1),
            (artist_clean, _t2),
            (artist_clean, _t3),
            ("",           _t1),   # title-only as last resort
        ]:
            key = (_a.lower(), _t.lower())
            if _t and key not in _seen:
                _seen.add(key)
                _attempts.append((_a, _t))

        for attempt_artist, attempt_title in _attempts:
            if not attempt_title:
                continue

            print(f"[Lyrics] Trying: {attempt_artist!r} / {attempt_title!r}")

            # 1. lrclib exact
            try:
                raw = self._try_lrclib(attempt_artist, attempt_title)
                if raw:
                    print(f"[Lyrics] Found via lrclib ({len(raw)} chars)")
                    break
            except Exception as e:
                tried.append(f"lrclib: {e}")
                print(f"[Lyrics]   lrclib failed: {e}")

            # 2. lrclib search (fuzzy)
            try:
                raw = self._try_lrclib_search(attempt_artist, attempt_title)
                if raw:
                    print(f"[Lyrics] Found via lrclib/search ({len(raw)} chars)")
                    break
            except Exception as e:
                tried.append(f"lrclib_search: {e}")
                print(f"[Lyrics]   lrclib_search failed: {e}")

            # 3. lyrics.ovh
            try:
                raw = self._try_lyrics_ovh(attempt_artist, attempt_title)
                if raw:
                    print(f"[Lyrics] Found via lyrics.ovh ({len(raw)} chars)")
                    break
            except Exception as e:
                tried.append(f"lyrics.ovh: {e}")
                print(f"[Lyrics]   lyrics.ovh failed: {e}")

            # 4. Genius scrape
            try:
                raw = self._try_genius(attempt_artist, attempt_title)
                if raw:
                    print(f"[Lyrics] Found via Genius ({len(raw)} chars)")
                    break
            except Exception as e:
                tried.append(f"genius: {e}")
                print(f"[Lyrics]   genius failed: {e}")

        if not raw:
            print(f"[Lyrics] Not found. Errors: {tried}")
            self.lyrics_failed.emit("No lyrics found.")
            return

        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        while "\n\n\n" in raw:
            raw = raw.replace("\n\n\n", "\n\n")
        lines = raw.split("\n")
        self.lyrics_ready.emit(raw, lines)


class NovaPlayer(QWidget):
    _ext_download_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._ext_download_signal.connect(self._run_extension_download)
        self.setWindowTitle("NovaX7")
        self.setGeometry(80, 80, 1340, 800)
        self.setMinimumSize(720, 480)

        self.db = MusicDatabase()
        self.instance = vlc.Instance("--quiet", "--no-video-title-show", "--log-verbose=-1")
        self.player = self.instance.media_player_new()
        self._crossfade_active = False
        self._crossfade_phase = None          # "out" | "in"
        self._crossfade_triggered = False
        self._crossfade_pending_item = None
        self._crossfade_elapsed = 0
        self._crossfade_out_ms = 0
        self._crossfade_in_ms = 0
        self._crossfade_target_vol = 80
        self._crossfade_last_vol = -1
        self._crossfade_clock = QElapsedTimer()
        self._crossfade_timer = QTimer()
        self._crossfade_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._crossfade_timer.timeout.connect(self._tick_crossfade)

        self.current_song_path = None
        self.current_index = -1
        self.current_song_id = None
        self.is_slider_pressed = False
        self.loop_enabled = False
        self.shuffle_enabled = False
        self.shuffle_queue = []
        self.current_view = "library"
        self.current_playlist_id = None
        self.sleep_timer = None
        self.sleep_minutes = 0
        self.sleep_elapsed = 0
        self._end_handled = False   # Guard: verhindert Doppel-Trigger bei Track-Ende
        self._thumb_worker = None    # Background thumbnail generator for video library

        # ── Lyrics ────────────────────────────────────────────────────────────
        self._lyrics_lines        = []     # list[str] — all lines
        self._lyrics_timestamps   = []     # list[float] — ms offset per line (estimated)
        self._lyrics_current_line = -1     # index of highlighted line
        self._lyrics_fetcher      = None   # active LyricsFetcher thread
        self._lyrics_cache        = {}     # {(artist.lower(), title.lower()): lines} in-memory cache
        self._lyrics_current_key  = None   # cache key for currently displayed lyrics
        self._lyrics_song_id      = None   # song DB id for the currently loading lyrics
        self._lyrics_video_id     = None   # video DB id for the currently loading lyrics

        # ── Discord Rich Presence ──────────────────────────────────────────
        self._discord = DiscordRPC()
        if self.db.get_setting("discord_rpc", "0") == "1" and _PYPRESENCE_AVAILABLE:
            self._discord.enable()

        self.current_theme_name = self.db.get_setting("theme", "Midnight")
        self.theme = THEMES.get(self.current_theme_name, THEMES["Midnight"])
        self.is_video_mode = False     # True when Videos view is active
        self._fs_overlay = None        # In-window cover fullscreen overlay
        self._fs_win = None            # Top-level video fullscreen window
        self.current_cover_path = None # Full-res cover path for fullscreen
        self._vid_controls = None      # VideoControlsOverlay (FS + Pop-out)
        self._vid_controls_frame = None  # Der VLC-Frame zu dem das Overlay gehört

        self.init_ui()
        self.apply_theme()
        self.load_library()
        self.refresh_sidebar()
        self.setAcceptDrops(True)

        vol = int(self.db.get_setting("default_volume", "80"))
        self.volume_slider.setValue(vol)
        self.bb_volume.setValue(vol)
        self.player.audio_set_volume(vol)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(400)

        # Separater 1-Sekunden-Timer für Discord Rich Presence (Position/Dauer-Update)
        self._discord_timer = QTimer()
        self._discord_timer.timeout.connect(self._update_discord_progress)
        self._discord_timer.start(1000)

        self._shortcuts_active = True
        self._setup_shortcuts()

        self._ext_last_status = {"state": "idle"}
        self._ext_server = NovaExtensionServer(self)
        self._ext_server.start()

        # Auto-generate extension folder on every start so it's always present
        try:
            self._ensure_extension_files(nova_extension_dir())
        except Exception:
            pass

    # ──────────────────────────── CHROME EXTENSION ────────────────────────────

    def queue_extension_download(self, data):
        """Called from the local HTTP API thread — marshal to the UI thread."""
        self._ext_download_signal.emit(data)

    def _run_extension_download(self, data):
        self._ext_last_status = {"state": "queued", "url": data.get("url", "")}
        if hasattr(self, "yt_browser") and self.yt_browser:
            ok, msg = self.yt_browser.start_download_from_extension(data)
            self._ext_last_status = {
                "state": "downloading" if ok else "error",
                "message": msg,
                "url": data.get("url", ""),
            }
            if ok:
                self.switch_view("ytbrowser")
            return
        self._ext_last_status = {"state": "error", "message": "Media browser not available"}

    def _ensure_extension_files(self, ext_dir):
        """Auto-generate the Chrome extension folder and files if missing."""
        import base64
        try:
            os.makedirs(ext_dir, exist_ok=True)
            
            manifest_path = os.path.join(ext_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                manifest_json = """{
  "manifest_version": 3,
  "name": "Nova yt-dlp Downloader",
  "version": "1.0",
  "description": "Download videos and audio using the Nova media browser via yt-dlp",
  "permissions": [
    "activeTab"
  ],
  "host_permissions": [
    "http://127.0.0.1:8765/*"
  ],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icon16.png",
      "48": "icon48.png",
      "128": "icon128.png"
    }
  },
  "icons": {
    "16": "icon16.png",
    "48": "icon48.png",
    "128": "icon128.png"
  }
}"""
                with open(manifest_path, "w", encoding="utf-8") as f:
                    f.write(manifest_json)

            popup_html_path = os.path.join(ext_dir, "popup.html")
            if not os.path.exists(popup_html_path):
                popup_html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    :root {
      --bg-dark: #0d1117;
      --bg-card: #161b22;
      --border-color: #30363d;
      --text-main: #c9d1d9;
      --text-muted: #8b949e;
      --accent-purple: #9d4edd;
      --accent-purple-glow: rgba(157, 78, 221, 0.4);
      --accent-green: #2ea44f;
      --accent-red: #da3633;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-dark);
      color: var(--text-main);
      margin: 0;
      padding: 16px;
      width: 290px;
      user-select: none;
    }

    /* Header */
    .header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
    }
    .header h1 {
      font-size: 16px;
      font-weight: 700;
      margin: 0;
      letter-spacing: 0.5px;
      background: linear-gradient(90deg, #c77dff, #e0aaff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header .logo-symbol {
      color: var(--accent-purple);
      font-size: 18px;
      font-weight: bold;
    }

    /* Mode Segmented Control */
    .segmented-control {
      display: flex;
      background-color: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 2px;
      margin-bottom: 16px;
    }
    .segmented-control button {
      flex: 1;
      background: none;
      border: none;
      color: var(--text-muted);
      padding: 8px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .segmented-control button.active {
      background-color: var(--accent-purple);
      color: #fff;
      box-shadow: 0 2px 8px var(--accent-purple-glow);
    }

    /* Options Panel */
    .options-group {
      background-color: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
    }
    .option-row {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 12px;
    }
    .option-row:last-child {
      margin-bottom: 0;
    }
    .option-row label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .option-row select {
      background-color: var(--bg-dark);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
      outline: none;
      transition: border-color 0.2s ease;
    }
    .option-row select:focus {
      border-color: var(--accent-purple);
    }

    /* Download Button */
    .dl-btn {
      display: block;
      width: 100%;
      background: linear-gradient(135deg, #7b2cbf, #9d4edd);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 10px 16px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px var(--accent-purple-glow);
      text-align: center;
    }
    .dl-btn:hover {
      opacity: 0.95;
      box-shadow: 0 4px 16px rgba(157, 78, 221, 0.6);
    }
    .dl-btn:active {
      transform: scale(0.98);
    }
    .dl-btn:disabled {
      background: var(--border-color);
      color: var(--text-muted);
      box-shadow: none;
      cursor: not-allowed;
      transform: none;
    }

    /* Footer Connection Status */
    .status-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--border-color);
      font-size: 12px;
    }
    .status-left {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-muted);
    }
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: var(--accent-red);
      box-shadow: 0 0 4px var(--accent-red);
    }
    .status-indicator.online {
      background-color: var(--accent-green);
      box-shadow: 0 0 6px var(--accent-green);
    }
    .download-progress {
      font-weight: 600;
      color: var(--accent-purple);
    }
  </style>
</head>
<body>

  <div class="header">
    <span class="logo-symbol">⬡</span>
    <h1>Nova Downloader</h1>
  </div>

  <div class="segmented-control">
    <button id="modeVideoBtn" class="active">Video</button>
    <button id="modeAudioBtn">Audio</button>
  </div>

  <!-- Options for Video Mode -->
  <div id="videoOptions" class="options-group">
    <div class="option-row">
      <label for="videoFormat">Format</label>
      <select id="videoFormat">
        <option value="mp4" selected>MP4</option>
        <option value="mkv">MKV</option>
        <option value="webm">WebM</option>
      </select>
    </div>
    <div class="option-row">
      <label for="videoQuality">Quality</label>
      <select id="videoQuality">
        <option value="Best (4K+)">Best (4K+)</option>
        <option value="1080p" selected>1080p (Full HD)</option>
        <option value="720p">720p (HD)</option>
        <option value="480p">480p (SD)</option>
        <option value="360p">360p (Low)</option>
        <option value="Smallest">Smallest</option>
      </select>
    </div>
  </div>

  <!-- Options for Audio Mode -->
  <div id="audioOptions" class="options-group" style="display: none;">
    <div class="option-row">
      <label for="audioFormat">Format</label>
      <select id="audioFormat">
        <option value="mp3" selected>MP3</option>
        <option value="m4a">M4A</option>
        <option value="flac">FLAC</option>
        <option value="wav">WAV</option>
        <option value="ogg">OGG</option>
      </select>
    </div>
    <div class="option-row">
      <label for="audioQuality">Bitrate</label>
      <select id="audioQuality">
        <option value="320">320 kbps (Best)</option>
        <option value="256">256 kbps</option>
        <option value="192" selected>192 kbps (Standard)</option>
        <option value="128">128 kbps (Small)</option>
      </select>
    </div>
  </div>

  <button id="downloadBtn" class="dl-btn">⬇ Download Video</button>

  <div class="status-bar">
    <div class="status-left">
      <div id="statusIndicator" class="status-indicator"></div>
      <span id="statusText">Connecting...</span>
    </div>
    <span id="progressText" class="download-progress"></span>
  </div>

  <script src="popup.js"></script>
</body>
</html>"""
                with open(popup_html_path, "w", encoding="utf-8") as f:
                    f.write(popup_html)

            popup_js_path = os.path.join(ext_dir, "popup.js")
            if not os.path.exists(popup_js_path):
                popup_js = """const API_BASE = "http://127.0.0.1:8765";

// DOM elements
const modeVideoBtn = document.getElementById("modeVideoBtn");
const modeAudioBtn = document.getElementById("modeAudioBtn");
const videoOptions = document.getElementById("videoOptions");
const audioOptions = document.getElementById("audioOptions");
const videoFormat = document.getElementById("videoFormat");
const videoQuality = document.getElementById("videoQuality");
const audioFormat = document.getElementById("audioFormat");
const audioQuality = document.getElementById("audioQuality");
const downloadBtn = document.getElementById("downloadBtn");
const statusIndicator = document.getElementById("statusIndicator");
const statusText = document.getElementById("statusText");
const progressText = document.getElementById("progressText");

let currentMode = "video"; // "video" or "audio"
let isNovaOnline = false;

// Toggle Mode
modeVideoBtn.addEventListener("click", () => {
  if (currentMode === "video") return;
  currentMode = "video";
  modeVideoBtn.classList.add("active");
  modeAudioBtn.classList.remove("active");
  videoOptions.style.display = "block";
  audioOptions.style.display = "none";
  updateDownloadBtnText();
});

modeAudioBtn.addEventListener("click", () => {
  if (currentMode === "audio") return;
  currentMode = "audio";
  modeAudioBtn.classList.add("active");
  modeVideoBtn.classList.remove("active");
  audioOptions.style.display = "block";
  videoOptions.style.display = "none";
  updateDownloadBtnText();
});

function updateDownloadBtnText() {
  if (currentMode === "video") {
    downloadBtn.innerText = "⬇ Download Video";
  } else {
    downloadBtn.innerText = "⬇ Download Audio";
  }
}

// Check if Nova is online
async function checkNovaStatus() {
  try {
    const res = await fetch(`${API_BASE}/ping`, { method: "GET", signal: AbortSignal.timeout(1000) });
    if (res.ok) {
      const data = await res.json();
      if (data.ok && data.app === "NovaX7") {
        setOnline(true);
        // Also fetch current download status if online
        await fetchAppStatus();
        return;
      }
    }
    setOnline(false);
  } catch (err) {
    setOnline(false);
  }
}

async function fetchAppStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`, { method: "GET", signal: AbortSignal.timeout(1000) });
    if (res.ok) {
      const status = await res.json();
      if (status && status.state) {
        let stateStr = status.state;
        if (stateStr === "downloading") {
          progressText.innerText = "Downloading...";
          progressText.style.color = "var(--accent-purple)";
        } else if (stateStr === "queued") {
          progressText.innerText = "Queued...";
          progressText.style.color = "var(--text-muted)";
        } else if (stateStr === "error") {
          progressText.innerText = "Error";
          progressText.style.color = "var(--accent-red)";
        } else {
          progressText.innerText = ""; // Idle or offline
        }
      }
    }
  } catch (e) {
    // Ignore error
  }
}

function setOnline(online) {
  isNovaOnline = online;
  if (online) {
    statusIndicator.classList.add("online");
    statusText.innerText = "Nova Connected";
    downloadBtn.removeAttribute("disabled");
  } else {
    statusIndicator.classList.remove("online");
    statusText.innerText = "Nova Offline";
    progressText.innerText = "";
    downloadBtn.setAttribute("disabled", "true");
  }
}

// Initiate download via Nova
downloadBtn.addEventListener("click", async () => {
  if (!isNovaOnline) return;

  // Get active tab URL
  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    if (!tabs || !tabs[0] || !tabs[0].url) {
      alert("No active tab URL found.");
      return;
    }

    const tabUrl = tabs[0].url;
    if (!tabUrl.startsWith("http")) {
      alert("Invalid page URL. Open a video page first (e.g. YouTube).");
      return;
    }

    // Prepare payload
    let format, quality;
    if (currentMode === "video") {
      format = videoFormat.value;
      quality = videoQuality.value;
    } else {
      format = audioFormat.value;
      quality = audioQuality.value;
    }

    const payload = {
      url: tabUrl,
      mode: currentMode,
      format: format,
      quality: quality
    };

    // Disable button to prevent double-click
    downloadBtn.disabled = true;
    downloadBtn.innerText = "Queuing...";

    try {
      const res = await fetch(`${API_BASE}/download`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const result = await res.json();
        if (result.ok) {
          progressText.innerText = "Queued!";
          progressText.style.color = "var(--accent-green)";
          setTimeout(() => {
            progressText.innerText = "Downloading...";
            progressText.style.color = "var(--accent-purple)";
          }, 1500);
        } else {
          alert(`Failed to queue download: ${result.error}`);
        }
      } else {
        alert("Failed to queue download: Server returned error status.");
      }
    } catch (err) {
      alert(`Error connecting to Nova: ${err.message}`);
    } finally {
      setTimeout(() => {
        updateDownloadBtnText();
        if (isNovaOnline) {
          downloadBtn.removeAttribute("disabled");
        }
      }, 2000);
    }
  });
});

// Periodic status checks
checkNovaStatus();
const intervalId = setInterval(checkNovaStatus, 1500);

window.addEventListener("unload", () => {
  clearInterval(intervalId);
});"""
                with open(popup_js_path, "w", encoding="utf-8") as f:
                    f.write(popup_js)

            # Write icons from base64
            icons = {
                "icon16.png": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAf0lEQVR4nGNgoBAw4pKY63f3P7pY8iZlDPWM+DQmbVSCi8/zv4fVICZCthJyHROpmtHVMzFQCJjIsR3ZFUyUuoAFXQA55HGJI8cIE7pCZElsAF2eiYFCwIQtheFyBbo4SB8TLpPRFeMyFG4AtnSOD8DUo7gAl1ewOR3Gpjg3AgAulDmrbHFBgwAAAABJRU5ErkJggg==",
                "icon48.png": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAABL0lEQVR4nO2Z4RHCIAyFIeckuo/uYOaCHXQfXUV/eef1WiHwAgH7frfJFx4tXOLcrl1V8g6scH68Us/w/QTL61tBaxXje4GjCvG9wWsLIWcIviS+twJe6gZZhc/N69Hw19sx+Uy8PGFOkBtcZHHrSDjIOnyKZ84tFIyt/i+u+RwIRld/i28+B4YuIBjfPmucczkwosgNroP0hZzbZm2MKLitih2QXoW141OLJJpxqWUyjXjUIykyDtX2ZmqLiAXvf3NCfqOlRUSAg7BzQAqD2n6E7FXmQtXA84IPfhKn4NB/L9LoGG9B1sLzCpfaXWgJq3X4keYQ4gONgOcNHnhrUUP8t61F9DyrRJzIn+VAryI4I68YrMU3wYIFE38D2m6wMP5/TimnmRNbmNTvcp31BjrjlovRR/ZjAAAAAElFTkSuQmCC",
                "icon128.png": "iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAADfElEQVR4nO2d7W0UQRBEF8uRQD6QAxsXkwPkg1MB8cPSCSFud766qvu9/6CZqrc9s2frfBwAAAAAAAAAUIUPRwG+ff75q/ffnj8+pc4o3eZGyq4ohf1GdhSeWQjLhSuUnkUGq8UqF+8qgvwinUp3lEF2YRmKdxDh5RAkY/mq+5IyUjGg7NNAYhGVilcTIfwIqFy+wv5fKm9ehcgcQsYPxescCdsnAOVr5bNVAMrXy2mbAJSvmdcWAShfN7flAlC+dn5LBaB8/RyXCUD5HnkuEYDy17Ai1+kCUP5aZuf7eiTl6/eP0//P9uXtyMbUCcDTv4eZOU8TgPL3MivvKQJQfgwzcg//fQCIZVgAnv5YRvNnAhRnSAGefg1GeugWgPK16O2DI6A4XQLw9GvS0wsToDgIUJzbAjD+tbnbDxOgOLcE4On34E5PTIDiIEBxLgvA+Pfial9MgOIgQHEQoDiXBOD89+RKb0yA4iBAcRCgOAhQnKcCcAH05ll/TIDiIEBxEKA4CFAcBCgOAhTnNeM3ebittQV+80j4BMj4tStO+w8XQCGEyvuWEEAljIr7Db8D/CsUp3uBa/FyE0A5pMz7khRANayM+5EVQDm0TPt4Uf+zZsrhOaz/WX/SE0AlxMzrthDAJUzH9Uq9BmZ4TWwmxdtNAIeQm+i6hgWIvgg6hN3E1nO1N8sJoBZ6E1lHD9YCKITfjMtPIUBkCc28/FsCKN4DIsto4uVf7cvqNVDhNbGJF1/yCNhVUktW/m0B1I+BlWU1o/Lv9JRyAswurRmVf5fbAjhNgRnlNbPy7/aTegKMltjMyu+hhAA9ZbYC5f+he5w7f2/A/14Tm3HxPcdzmQlwpeRmXH4v3QK4XQafld3My+/tY2gCZJGgFS2/7BHwSDMvf5RhAdyngDuj+ZefANWZIgBTIIYZuU+bAEiwl1l5Tz0CkGAPM3PmDlCc6QIwBdYyO98lEwAJ1rAi12VHABJ45Ln0DoAE+jkuvwQigXZ+W94CkEA3t22vgUigmdfWzwGQQC+n7R8EIYFWPqE/ynX+vcIsD0boR8FMg/gcwn8WUF2CM3j/UuFXOhJOEfElFlFJhFOkeJkjwCGkzPuSW1DGaXAKFv+O7MLcZTiFS3/EYpFOIpwmxb9jtVhVGU6z0h+xXXikEKdx4X+TZiOrpDgTlQ0AAAAAAADl+Q0q/n7nxz37KwAAAABJRU5ErkJggg=="
            }
            for name, b64_str in icons.items():
                icon_path = os.path.join(ext_dir, name)
                if not os.path.exists(icon_path):
                    with open(icon_path, "wb") as f:
                        f.write(base64.b64decode(b64_str))
        except Exception as e:
            print(f"[Nova] Failed to auto-generate extension files: {e}")

    def open_chrome_extension_dialog(self):
        """Show install instructions and open the extension folder / ZIP."""
        ext_dir = nova_extension_dir()
        self._ensure_extension_files(ext_dir)
        if not os.path.isdir(ext_dir):
            QMessageBox.warning(
                self, "Chrome Extension",
                f"Extension folder not found:\n{ext_dir}",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Nova Chrome Extension")
        dlg.setMinimumWidth(480)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Nova yt-dlp Downloader for Chrome")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        lay.addWidget(title)

        info = QLabel(
            "<b>What it does</b><br>"
            "On any YouTube video in Chrome, open the extension popup, pick "
            "<b>Audio</b> or <b>Video</b>, format, and quality — Nova downloads via yt-dlp.<br><br>"
            "<b>Install (one time)</b><br>"
            "1. Keep NovaX7 running (API on port 8765)<br>"
            "2. Chrome → <code>chrome://extensions</code><br>"
            "3. Enable <b>Developer mode</b><br>"
            "4. Click <b>Load unpacked</b> and select the extension folder below<br><br>"
            f"<small>Folder:<br><code>{ext_dir}</code></small>"
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(info)

        btn_row = QHBoxLayout()
        open_folder = QPushButton("Open extension folder")
        open_folder.setObjectName("toolbar_btn")
        open_folder.clicked.connect(lambda: self._open_path(ext_dir))
        zip_btn = QPushButton("Save as ZIP")
        zip_btn.setObjectName("toolbar_btn")
        zip_btn.clicked.connect(lambda: self._export_extension_zip(ext_dir, dlg))
        chrome_btn = QPushButton("Open chrome://extensions")
        chrome_btn.setObjectName("toolbar_btn")
        chrome_btn.clicked.connect(self._open_chrome_extensions_page)
        btn_row.addWidget(open_folder)
        btn_row.addWidget(zip_btn)
        btn_row.addWidget(chrome_btn)
        lay.addLayout(btn_row)

        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def _open_path(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Open folder", str(e))

    def _export_extension_zip(self, ext_dir, parent):
        default = os.path.join(os.path.expanduser("~"), "Downloads", "NovaYtdlpExtension.zip")
        path, _ = QFileDialog.getSaveFileName(
            parent, "Save Chrome extension ZIP", default, "ZIP archive (*.zip)"
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            base = os.path.splitext(path)[0]
            archive = shutil.make_archive(base, "zip", ext_dir)
            QMessageBox.information(parent, "ZIP created", f"Saved:\n{archive}")
            self._open_path(os.path.dirname(archive))
        except Exception as e:
            QMessageBox.warning(parent, "ZIP failed", str(e))

    def _open_chrome_extensions_page(self):
        exe = None
        if hasattr(self, "yt_browser"):
            exe = self.yt_browser._find_browser_exe()
        url = "chrome://extensions/"
        if exe:
            try:
                subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
        import webbrowser
        webbrowser.open(url)

    # ──────────────────────────── UI INIT ────────────────────────────

    def init_ui(self):
        main = QHBoxLayout()
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # ── SIDEBAR ──
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(256)
        sb_layout = QVBoxLayout()
        sb_layout.setContentsMargins(16, 24, 16, 20)
        sb_layout.setSpacing(2)

        logo_row = QHBoxLayout()
        logo = QLabel("⬡  Nova")
        logo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {self.theme['text']}; letter-spacing: 1px; background: transparent;")
        logo_row.addWidget(logo)
        logo_row.addStretch()
        sb_layout.addLayout(logo_row)
        sb_layout.addSpacing(22)

        lib_section = QLabel("LIBRARY")
        lib_section.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        lib_section.setObjectName("section_label")
        sb_layout.addWidget(lib_section)
        sb_layout.addSpacing(4)

        for label, view, icon in [
            ("All Songs", "library", "♪"),
            ("Videos", "videos", "🎬"),
            ("Media Browser", "ytbrowser", "🌐"),
            ("Favourites", "favourites", "♥"),
            ("Recently Played", "recently", "🕐"),
            ("Most Played", "mostplayed", "🔥"),
            ("Extras", "extras", "⚡"),
        ]:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setFlat(True)
            btn.setProperty("nav", True)
            btn.clicked.connect(lambda _, v=view: self.switch_view(v))
            sb_layout.addWidget(btn)

        sb_layout.addSpacing(20)

        playlists_header = QHBoxLayout()
        pl_label = QLabel("PLAYLISTS")
        pl_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        pl_label.setObjectName("section_label")
        new_pl_btn = QPushButton("+")
        new_pl_btn.setFixedSize(24, 24)
        new_pl_btn.setToolTip("Playlist erstellen / Medien hinzufügen")
        new_pl_btn.setObjectName("icon_btn")
        self._new_pl_menu = QMenu()
        self._new_pl_menu.addAction("♫  Neue leere Playlist",        self.create_playlist)
        self._new_pl_menu.addSeparator()
        self._new_pl_menu.addAction("≡  Aus Mediathek",              self._create_playlist_from_library)
        self._new_pl_menu.addAction("⊞  Lokal importieren",          self._create_playlist_from_local)
        self._new_pl_menu.addAction("⬇  Downloaden & in Playlist",   self._create_playlist_from_download)
        new_pl_btn.clicked.connect(
            lambda: self._new_pl_menu.exec(new_pl_btn.mapToGlobal(new_pl_btn.rect().bottomLeft()))
        )
        redeem_btn = QPushButton("✦")
        redeem_btn.setFixedSize(24, 24)
        redeem_btn.setToolTip("Playlist-Code einlösen")
        redeem_btn.setObjectName("icon_btn")
        redeem_btn.clicked.connect(self._open_redeem_dialog)
        playlists_header.addWidget(pl_label)
        playlists_header.addStretch()
        playlists_header.addWidget(redeem_btn)
        playlists_header.addWidget(new_pl_btn)
        sb_layout.addLayout(playlists_header)
        sb_layout.addSpacing(4)

        self.playlist_list_widget = QListWidget()
        self.playlist_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list_widget.customContextMenuRequested.connect(self.playlist_context_menu)
        self.playlist_list_widget.itemClicked.connect(self.open_playlist)
        self.playlist_list_widget.setMinimumHeight(80)
        self.playlist_list_widget.setMaximumHeight(260)
        self.playlist_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        sb_layout.addWidget(self.playlist_list_widget)

        sb_layout.addStretch()

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setObjectName("settings_btn")
        settings_btn.clicked.connect(self.open_settings)
        sb_layout.addWidget(settings_btn)

        self.sidebar.setLayout(sb_layout)

        # ── CENTER ──
        center = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("top_bar")
        top_bar.setFixedHeight(66)
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(20, 12, 20, 12)
        top.setSpacing(10)

        self.view_title = QLabel("All Songs")
        self.view_title.setFont(QFont("", 15, QFont.Weight.Bold))

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("⌕  Search songs, artists, albums...")
        self.search_box.textChanged.connect(self.on_search)
        self.search_box.setMinimumWidth(120)
        self.search_box.setMaximumWidth(260)
        self.search_box.setFixedHeight(36)

        # ── Import dropdown (local files & folders) ──────────────────────────
        self._import_menu = QMenu()
        self._import_menu.addAction("⊞  Folder",      self.import_music_folder)
        self._import_menu.addAction("♫  Audio & Video Files", self.import_single_files)

        import_file_btn = QPushButton("＋ Import ▾")
        import_file_btn.setObjectName("toolbar_btn")
        import_file_btn.setFixedHeight(36)
        import_file_btn.setToolTip("Import music or video files from your computer")
        import_file_btn.clicked.connect(
            lambda: self._import_menu.exec(import_file_btn.mapToGlobal(
                import_file_btn.rect().bottomLeft()
            ))
        )

        # ── Download dropdown (via URL / yt-dlp) ─────────────────────────────
        self._download_menu = QMenu()
        self._download_menu.addAction("♫   Audio via URL", self.open_ytdlp_importer)
        self._download_menu.addAction("🎬  Video via URL", self.open_video_downloader)
        self._download_menu.addSeparator()
        self._download_menu.addAction("⬡  Chrome Extension…", self.open_chrome_extension_dialog)

        download_btn = QPushButton("⬇ Download ▾")
        download_btn.setObjectName("toolbar_btn")
        download_btn.setFixedHeight(36)
        download_btn.setToolTip("Download audio or video via URL (yt-dlp)")
        download_btn.clicked.connect(
            lambda: self._download_menu.exec(download_btn.mapToGlobal(
                download_btn.rect().bottomLeft()
            ))
        )

        web_btn = QPushButton("🌐 Web")
        web_btn.setObjectName("toolbar_btn")
        web_btn.setFixedHeight(36)
        web_btn.setToolTip("Web Player")
        web_btn.clicked.connect(self.open_web_player)

        convert_btn = QPushButton("🔄 Convert")
        convert_btn.setObjectName("toolbar_btn")
        convert_btn.setFixedHeight(36)
        convert_btn.setToolTip("Convert audio ↔ video using ffmpeg")
        convert_btn.clicked.connect(self.open_converter)

        # ── Sort button with dropdown ─────────────────────────────────────────
        self._sort_order = "az"
        self._sort_btn = QPushButton("↕ A→Z")
        self._sort_btn.setObjectName("toolbar_btn")
        self._sort_btn.setFixedHeight(36)
        self._sort_btn.setToolTip("Sort order")

        def _show_sort_menu():
            menu = QMenu(self._sort_btn)
            for key, label in [
                ("az",     "↑ A → Z"),
                ("za",     "↓ Z → A"),
                ("newest", "🕐 Newest first"),
                ("oldest", "🕐 Oldest first"),
            ]:
                act = QAction(label, menu)
                act.setCheckable(True)
                act.setChecked(self._sort_order == key)
                def _set(checked, k=key): self._apply_sort(k)
                act.triggered.connect(_set)
                menu.addAction(act)
            menu.exec(self._sort_btn.mapToGlobal(
                self._sort_btn.rect().bottomLeft()
            ))

        self._sort_btn.clicked.connect(_show_sort_menu)

        # Store refs for responsive relabelling
        # (button, full_label, short_label, icon_only)
        self._top_bar_btns = [
            (import_file_btn, "＋ Import ▾",   "＋ Import ▾", "＋▾"),
            (download_btn,    "⬇ Download ▾", "⬇▾",          "⬇▾"),
            (self._sort_btn,  "↕ A→Z",         "↕ A→Z",      "↕"),
            (convert_btn,     "🔄 Convert",     "🔄",         "🔄"),
            (web_btn,         "🌐 Web",         "🌐",         "🌐"),
        ]
        self._top_bar_frame = top_bar

        top.addWidget(self.view_title)
        top.addStretch()
        top.addWidget(self.search_box)
        top.addWidget(import_file_btn)
        top.addWidget(download_btn)
        top.addWidget(self._sort_btn)
        top.addWidget(convert_btn)
        top.addWidget(web_btn)

        center_layout.addWidget(top_bar)

        self.col_header = QFrame()
        self.col_header.setObjectName("col_header")
        self.col_header.setFixedHeight(32)
        col_h = QHBoxLayout(self.col_header)
        col_h.setContentsMargins(72, 0, 16, 0)
        col_h.setSpacing(0)
        for txt, stretch in [("#", 0), ("Title / Artist", 1), ("Album", 0), ("Duration", 0), ("Plays", 0)]:
            lbl = QLabel(txt)
            lbl.setObjectName("col_label")
            lbl.setFont(QFont("Arial", 10))
            if stretch:
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            else:
                lbl.setFixedWidth(70 if txt in ("Duration", "Plays") else 24)
            col_h.addWidget(lbl)
        center_layout.addWidget(self.col_header)

        # ── Playlist Header Banner (shown only in playlist view) ──
        self.playlist_banner = QFrame()
        self.playlist_banner.setObjectName("playlist_banner")
        self.playlist_banner.setFixedHeight(120)
        self.playlist_banner.setVisible(False)
        pl_banner_layout = QHBoxLayout(self.playlist_banner)
        pl_banner_layout.setContentsMargins(20, 12, 20, 12)
        pl_banner_layout.setSpacing(18)

        self.pl_banner_cover = QLabel()
        self.pl_banner_cover.setFixedSize(88, 88)
        self.pl_banner_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pl_banner_cover.setObjectName("pl_banner_cover")
        pl_banner_layout.addWidget(self.pl_banner_cover)

        pl_info = QVBoxLayout()
        pl_info.setSpacing(3)
        self.pl_banner_name = QLabel()
        self.pl_banner_name.setFont(QFont("Arial", 17, QFont.Weight.Bold))
        self.pl_banner_name.setObjectName("pl_banner_name")
        self.pl_banner_desc = QLabel()
        self.pl_banner_desc.setObjectName("artist_label")
        self.pl_banner_stats = QLabel()
        self.pl_banner_stats.setObjectName("time_label")
        pl_info.addWidget(self.pl_banner_name)
        pl_info.addWidget(self.pl_banner_desc)
        pl_info.addWidget(self.pl_banner_stats)
        pl_info.addStretch()

        pl_btn_row = QHBoxLayout()
        pl_btn_row.setSpacing(8)
        self.pl_play_all_btn = QPushButton("▶  Play All")
        self.pl_play_all_btn.setObjectName("toolbar_btn")
        self.pl_play_all_btn.setFixedHeight(32)
        self.pl_play_all_btn.clicked.connect(self._playlist_play_all)
        self.pl_shuffle_all_btn = QPushButton("⇀  Shuffle")
        self.pl_shuffle_all_btn.setObjectName("toolbar_btn")
        self.pl_shuffle_all_btn.setFixedHeight(32)
        self.pl_shuffle_all_btn.clicked.connect(self._playlist_shuffle_all)
        self.pl_edit_btn = QPushButton("✏  Edit")
        self.pl_edit_btn.setObjectName("toolbar_btn")
        self.pl_edit_btn.setFixedHeight(32)
        self.pl_edit_btn.clicked.connect(self._playlist_edit_current)

        self.pl_add_btn = QPushButton("＋ Hinzufügen ▾")
        self.pl_add_btn.setObjectName("toolbar_btn")
        self.pl_add_btn.setFixedHeight(32)
        self.pl_add_btn.setToolTip("Songs oder Videos zur Playlist hinzufügen")
        self._pl_add_menu = QMenu()
        self._pl_add_menu.addAction("📚  Aus Mediathek",            self._pl_add_from_library)
        self._pl_add_menu.addAction("📂  Lokal importieren",        self._pl_add_from_local)
        self._pl_add_menu.addAction("⬇  Downloaden & hinzufügen",  self._pl_add_from_download)
        self.pl_add_btn.clicked.connect(
            lambda: self._pl_add_menu.exec(self.pl_add_btn.mapToGlobal(self.pl_add_btn.rect().bottomLeft()))
        )

        pl_btn_row.addWidget(self.pl_play_all_btn)
        pl_btn_row.addWidget(self.pl_shuffle_all_btn)
        pl_btn_row.addWidget(self.pl_edit_btn)
        pl_btn_row.addWidget(self.pl_add_btn)
        pl_btn_row.addStretch()
        pl_info.addLayout(pl_btn_row)

        pl_banner_layout.addLayout(pl_info, 1)
        center_layout.addWidget(self.playlist_banner)

        # ── Stacked: page 0 = song list, page 1 = YouTube browser ──
        self.center_stack = QStackedWidget()

        self.song_list = SmoothListWidget()
        self.song_list.setIconSize(QSize(46, 46))
        self.song_list.setSpacing(2)
        self.song_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.song_list.customContextMenuRequested.connect(self.show_context_menu)
        self.song_list.itemDoubleClicked.connect(self.play_selected_song)
        self.song_list.itemClicked.connect(self.preview_song_info)
        self.center_stack.addWidget(self.song_list)      # index 0

        # Universal Media Browser
        yt_dl_dir = self.db.get_setting("yt_browser_download_dir",
                                        os.path.join(os.path.expanduser("~"), "Downloads"))
        self.yt_browser = YouTubeBrowserPanel(parent=self, db=self.db, download_dir=yt_dl_dir)
        self.center_stack.addWidget(self.yt_browser)     # index 1

        self.extras_panel = ExtrasPanel(self, self.db)
        self.center_stack.addWidget(self.extras_panel)  # index 2
        self.password_manager = self.extras_panel.password_vault_view
        self.center_stack.setCurrentIndex(0)

        center_layout.addWidget(self.center_stack, 1)

        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        status_bar.setFixedHeight(28)
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(16, 0, 16, 0)
        self.status_label = QLabel("Ready")
        sb.addWidget(self.status_label)
        center_layout.addWidget(status_bar)

        center.setLayout(center_layout)

        # ── RIGHT PANEL ──
        right = QFrame()
        right.setObjectName("right_panel")
        right.setMinimumWidth(280)
        right.setMaximumWidth(340)
        right.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(20, 28, 20, 20)
        right_layout.setSpacing(12)

        # ── Cover / Video Stack ──
        self.cover_stack = QStackedWidget()
        self.cover_stack.setFixedSize(248, 248)
        # Prevent the cover from being pushed around when the lyrics panel
        # expands: Fixed policy means Qt will never grow or shrink this widget.
        self.cover_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Page 0: album cover (music mode)
        cover_container = QFrame()
        cover_container.setObjectName("cover_container")
        cover_container.setFixedSize(248, 248)
        cover_inner = QVBoxLayout(cover_container)
        cover_inner.setContentsMargins(4, 4, 4, 4)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(240, 240)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.mouseDoubleClickEvent = lambda e: self._open_cover_fullscreen()
        self.cover_label.setCursor(Qt.CursorShape.PointingHandCursor)
        cover_inner.addWidget(self.cover_label)

        # Page 1: embedded VLC video frame (video mode)
        self.video_frame = QFrame()
        self.video_frame.setObjectName("cover_container")
        self.video_frame.setFixedSize(248, 248)
        self.video_frame.setStyleSheet("background: #000; border-radius: 14px;")
        self.video_frame.mouseDoubleClickEvent = lambda e: self._open_video_fullscreen()

        self.cover_stack.addWidget(cover_container)   # index 0
        self.cover_stack.addWidget(self.video_frame)  # index 1
        self.cover_stack.setCurrentIndex(0)
        right_layout.addWidget(self.cover_stack, alignment=Qt.AlignmentFlag.AlignCenter)

        # Fullscreen button for cover/video
        fs_row = QHBoxLayout()
        fs_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fs_btn = QPushButton("⛶  Vollbild")
        self.fs_btn.setObjectName("toolbar_btn")
        self.fs_btn.setFixedHeight(28)
        self.fs_btn.setToolTip("Vollbild öffnen (oder Doppelklick auf Bild/Video)")
        self.fs_btn.clicked.connect(self._open_fullscreen_current)
        fs_row.addWidget(self.fs_btn)

        # Pop-out button: opens video/browser in a separate, closable window
        # Only shown when a video is active or the browser is open
        self.popout_btn = QPushButton("⧉  Pop-out")
        self.popout_btn.setObjectName("toolbar_btn")
        self.popout_btn.setFixedHeight(28)
        self.popout_btn.setToolTip("In separatem Fenster öffnen (schließbar)")
        self.popout_btn.setVisible(False)   # hidden in audio/idle mode
        self.popout_btn.clicked.connect(self._toggle_popout_window)
        fs_row.addWidget(self.popout_btn)

        right_layout.addLayout(fs_row)

        self.song_title_label = QLabel("No song playing")
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.song_title_label.setWordWrap(True)
        right_layout.addWidget(self.song_title_label)

        self.song_artist_label = QLabel("")
        self.song_artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_artist_label.setObjectName("artist_label")
        right_layout.addWidget(self.song_artist_label)

        fav_row = QHBoxLayout()
        fav_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fav_btn = QPushButton("♡")
        self.fav_btn.setFixedSize(40, 40)
        self.fav_btn.setToolTip("Toggle Favourite")
        self.fav_btn.clicked.connect(self.toggle_favourite_current)
        fav_row.addWidget(self.fav_btn)
        right_layout.addLayout(fav_row)

        rating_row = QHBoxLayout()
        rating_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.star_btns = []
        for i in range(1, 6):
            s = QPushButton("☆")
            s.setFixedSize(28, 28)
            s.setFlat(True)
            s.clicked.connect(lambda _, r=i: self.set_rating(r))
            self.star_btns.append(s)
            rating_row.addWidget(s)
        right_layout.addLayout(rating_row)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.progress_slider.sliderReleased.connect(self.slider_released)
        right_layout.addWidget(self.progress_slider)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setObjectName("time_label")
        right_layout.addWidget(self.time_label)

        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_row.setSpacing(6)
        self.shuffle_btn = QPushButton("⇄")
        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("▶")
        self.pause_btn = QPushButton("⏸")
        self.next_btn = QPushButton("⏭")
        self.loop_btn = QPushButton("↻")

        self.play_btn.setObjectName("play_btn_main")
        self.pause_btn.setObjectName("play_btn_main")

        for b in [self.shuffle_btn, self.prev_btn, self.play_btn, self.pause_btn, self.next_btn, self.loop_btn]:
            b.setFixedSize(38, 38)
            ctrl_row.addWidget(b)

        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.prev_btn.clicked.connect(self.play_previous)
        self.play_btn.clicked.connect(self.resume_song)
        self.pause_btn.clicked.connect(self.pause_song)
        self.next_btn.clicked.connect(self.play_next)
        self.loop_btn.clicked.connect(self.toggle_loop)

        right_layout.addLayout(ctrl_row)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(6)
        vol_icon = QLabel("Vol")
        vol_icon.setObjectName("time_label")
        vol_icon.setFixedWidth(28)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.vol_label = QLabel("80%")
        self.vol_label.setFixedWidth(38)
        self.vol_label.setObjectName("time_label")
        vol_row.addWidget(vol_icon)
        vol_row.addWidget(self.volume_slider)
        vol_row.addWidget(self.vol_label)
        right_layout.addLayout(vol_row)

        self.sleep_label = QLabel("")
        self.sleep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sleep_label.setObjectName("time_label")
        right_layout.addWidget(self.sleep_label)

        # ── Lyrics Panel ──────────────────────────────────────────────────
        lyrics_header = QHBoxLayout()
        lyrics_header.setContentsMargins(0, 4, 0, 0)
        self._lyrics_toggle_btn = QPushButton("♪  Lyrics  ▾")
        self._lyrics_toggle_btn.setObjectName("toolbar_btn")
        self._lyrics_toggle_btn.setFixedHeight(26)
        self._lyrics_toggle_btn.clicked.connect(self._toggle_lyrics_panel)
        lyrics_header.addWidget(self._lyrics_toggle_btn)
        lyrics_header.addStretch()
        self._lyrics_save_btn = QPushButton("↓")
        self._lyrics_save_btn.setObjectName("toolbar_btn")
        self._lyrics_save_btn.setFixedSize(26, 26)
        self._lyrics_save_btn.setToolTip("Save lyrics to library")
        self._lyrics_save_btn.setVisible(False)
        self._lyrics_save_btn.clicked.connect(self._save_lyrics)
        lyrics_header.addWidget(self._lyrics_save_btn)
        self._lyrics_fs_btn = QPushButton("⛶")
        self._lyrics_fs_btn.setObjectName("toolbar_btn")
        self._lyrics_fs_btn.setFixedSize(26, 26)
        self._lyrics_fs_btn.setToolTip("Lyrics fullscreen")
        self._lyrics_fs_btn.setVisible(False)
        self._lyrics_fs_btn.clicked.connect(self._open_lyrics_fullscreen)
        lyrics_header.addWidget(self._lyrics_fs_btn)
        self._lyrics_copy_btn = QPushButton("▤")
        self._lyrics_copy_btn.setObjectName("toolbar_btn")
        self._lyrics_copy_btn.setFixedSize(26, 26)
        self._lyrics_copy_btn.setToolTip("Copy lyrics")
        self._lyrics_copy_btn.setVisible(False)
        self._lyrics_copy_btn.clicked.connect(self._copy_lyrics)
        lyrics_header.addWidget(self._lyrics_copy_btn)
        right_layout.addLayout(lyrics_header)

        # Use a collapsible wrapper so the lyrics box always occupies its slot
        # in the layout — this prevents the cover/video from jumping when lyrics
        # are expanded or collapsed.
        self._lyrics_wrapper = QWidget()
        self._lyrics_wrapper.setMaximumHeight(0)   # collapsed by default
        self._lyrics_wrapper.setMinimumHeight(0)
        self._lyrics_wrapper_layout = QVBoxLayout(self._lyrics_wrapper)
        self._lyrics_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        self._lyrics_wrapper_layout.setSpacing(0)
        self._lyrics_expanded = False

        self._lyrics_box = SmoothScrollArea()
        self._lyrics_box.setWidgetResizable(True)
        self._lyrics_box.setFrameShape(QFrame.Shape.NoFrame)
        self._lyrics_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._lyrics_box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._lyrics_content = QLabel("–")
        self._lyrics_content.setWordWrap(True)
        self._lyrics_content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._lyrics_content.setObjectName("lyrics_label")
        self._lyrics_content.setTextFormat(Qt.TextFormat.PlainText)
        self._lyrics_content.setMargin(6)
        self._lyrics_box.setWidget(self._lyrics_content)
        self._lyrics_wrapper_layout.addWidget(self._lyrics_box)

        # ── FIX: Stretch goes BEFORE the lyrics wrapper so that expanding
        # lyrics only grows downward into the tools row gap, and never
        # pushes the cover/video upward. ──────────────────────────────────
        right_layout.addStretch()
        right_layout.addWidget(self._lyrics_wrapper)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        sleep_btn = QPushButton("☾  Sleep")
        sleep_btn.setObjectName("toolbar_btn")
        sleep_btn.clicked.connect(self.open_sleep_timer)
        queue_btn = QPushButton("☰  Queue")
        queue_btn.setObjectName("toolbar_btn")
        queue_btn.clicked.connect(self.show_queue)
        tools_row.addWidget(sleep_btn)
        tools_row.addWidget(queue_btn)
        right_layout.addLayout(tools_row)

        right.setLayout(right_layout)

        main.addWidget(self.sidebar)
        main.addWidget(center, 1)
        main.addWidget(right)

        # ── BOTTOM PLAYER BAR (Spotify-style) ──
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottom_bar")
        bottom_bar.setFixedHeight(84)
        bb = QHBoxLayout(bottom_bar)
        bb.setContentsMargins(24, 0, 24, 0)
        bb.setSpacing(0)

        # Left: cover + song info
        bb_left = QHBoxLayout()
        bb_left.setSpacing(12)
        self.bb_cover = QLabel()
        self.bb_cover.setFixedSize(52, 52)
        self.bb_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bb_cover.setStyleSheet("border-radius: 6px; background: #1a1a1a;")
        self.bb_cover.mouseDoubleClickEvent = lambda e: self._open_cover_fullscreen()
        self.bb_cover.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bb_song_title = QLabel("No song playing")
        self.bb_song_title.setObjectName("bb_title")
        self.bb_song_artist = QLabel("")
        self.bb_song_artist.setObjectName("bb_artist")
        bb_info = QVBoxLayout()
        bb_info.setSpacing(2)
        bb_info.addWidget(self.bb_song_title)
        bb_info.addWidget(self.bb_song_artist)
        bb_left.addWidget(self.bb_cover)
        bb_left.addLayout(bb_info)
        bb_left.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Center: controls + progress
        bb_center = QVBoxLayout()
        bb_center.setSpacing(4)
        bb_center.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        bb_ctrl = QHBoxLayout()
        bb_ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bb_ctrl.setSpacing(8)

        self.bb_shuffle_btn = QPushButton("⇄")
        self.bb_prev_btn    = QPushButton("⏮")
        self.bb_play_btn    = QPushButton("▶")
        self.bb_next_btn    = QPushButton("⏭")
        self.bb_loop_btn    = QPushButton("↻")

        self.bb_play_btn.setObjectName("bb_play_btn")
        self.bb_shuffle_btn.setObjectName("bb_ctrl_btn")
        self.bb_prev_btn.setObjectName("bb_ctrl_btn")
        self.bb_next_btn.setObjectName("bb_ctrl_btn")
        self.bb_loop_btn.setObjectName("bb_ctrl_btn")
        for b, sz in [(self.bb_shuffle_btn,30),(self.bb_prev_btn,30),(self.bb_play_btn,38),(self.bb_next_btn,30),(self.bb_loop_btn,30)]:
            b.setFixedSize(sz, sz)
            bb_ctrl.addWidget(b)

        self.bb_shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.bb_prev_btn.clicked.connect(self.play_previous)
        self.bb_play_btn.clicked.connect(self.toggle_play_pause)
        self.bb_next_btn.clicked.connect(self.play_next)
        self.bb_loop_btn.clicked.connect(self.toggle_loop)

        bb_prog_row = QHBoxLayout()
        bb_prog_row.setSpacing(8)
        self.bb_time_cur = QLabel("0:00")
        self.bb_time_cur.setObjectName("time_label")
        self.bb_time_cur.setFixedWidth(36)
        self.bb_time_cur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.bb_progress = QSlider(Qt.Orientation.Horizontal)
        self.bb_progress.setFixedWidth(340)
        self.bb_progress.sliderPressed.connect(self.slider_pressed)
        self.bb_progress.sliderReleased.connect(self.slider_released)
        self.bb_time_tot = QLabel("0:00")
        self.bb_time_tot.setObjectName("time_label")
        self.bb_time_tot.setFixedWidth(36)
        self.bb_time_tot.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bb_prog_row.addWidget(self.bb_time_cur)
        bb_prog_row.addWidget(self.bb_progress)
        bb_prog_row.addWidget(self.bb_time_tot)

        bb_center.addLayout(bb_ctrl)
        bb_center.addLayout(bb_prog_row)

        # Right: volume + fav
        bb_right = QHBoxLayout()
        bb_right.setSpacing(10)
        bb_right.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.bb_fav_btn = QPushButton("♡")
        self.bb_fav_btn.setFixedSize(30, 30)
        self.bb_fav_btn.setObjectName("bb_fav")
        self.bb_fav_btn.clicked.connect(self.toggle_favourite_current)
        bb_vol_icon = QLabel("Vol")
        bb_vol_icon.setObjectName("time_label")
        bb_vol_icon.setFixedWidth(28)
        self.bb_volume = QSlider(Qt.Orientation.Horizontal)
        self.bb_volume.setRange(0, 100)
        self.bb_volume.setValue(80)
        self.bb_volume.setFixedWidth(90)
        self.bb_volume.valueChanged.connect(self.change_volume)
        bb_right.addWidget(self.bb_fav_btn)
        bb_right.addWidget(bb_vol_icon)
        bb_right.addWidget(self.bb_volume)

        bb.addLayout(bb_left, 1)
        bb.addLayout(bb_center, 2)
        bb.addLayout(bb_right, 1)

        # Outer vertical wrapper
        outer = QVBoxLayout()
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)
        content_widget = QWidget()
        content_widget.setLayout(main)
        outer.addWidget(content_widget, 1)
        outer.addWidget(bottom_bar)
        self.setLayout(outer)

    def _setup_shortcuts(self):
        # Shortcuts are stored in self._shortcuts so they can be disabled while the
        # browser tab is focused (otherwise key presses meant for online instruments
        # like virtual pianos are intercepted by Qt before reaching the web page).
        self._shortcuts = []
        def _sc(key, slot, context=Qt.ShortcutContext.WindowShortcut):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(context)
            s.activated.connect(slot)
            self._shortcuts.append(s)
            return s

        # Space/Left/Right use WindowShortcut so they fire even when a child
        # widget (fullscreen overlay, video frame, …) has keyboard focus.
        def _space_guard():
            if not self._focused_widget_is_text_input():
                self.toggle_play_pause()
        def _left_guard():
            if not self._focused_widget_is_text_input():
                self._seek_relative(-5000)
        def _right_guard():
            if not self._focused_widget_is_text_input():
                self._seek_relative(5000)

        _sc("Space",      _space_guard)
        _sc("Left",       _left_guard)
        _sc("Right",      _right_guard)
        _sc("Ctrl+Right", self.play_next)
        _sc("Ctrl+Left",  self.play_previous)
        _sc("Ctrl+Up",    lambda: self.volume_slider.setValue(min(100, self.volume_slider.value() + 5)))
        _sc("Ctrl+Down",  lambda: self.volume_slider.setValue(max(0, self.volume_slider.value() - 5)))
        _sc("Ctrl+L",     self.toggle_loop)
        _sc("Ctrl+S",     self.toggle_shuffle)
        _sc("Ctrl+F",     lambda: self.search_box.setFocus())
        _sc("Ctrl+I",     self.import_single_files)
        _sc("F5",         self.load_library)
        _sc("F11",        self._toggle_window_fullscreen)

    def _focused_widget_is_text_input(self):
        """Returns True if a text input widget currently has keyboard focus."""
        fw = QApplication.focusWidget()
        return isinstance(fw, (QLineEdit, QTextEdit))

    def _seek_relative(self, delta_ms: int):
        """Seek forward/backward by delta_ms milliseconds (negative = rewind)."""
        if not self.current_song_path:
            return
        length = self.player.get_length()
        if length <= 0:
            return
        current = self.player.get_time()
        new_time = max(0, min(length, current + delta_ms))
        self.player.set_time(new_time)

    def keyPressEvent(self, event):
        """Handle global key presses for playback control.

        Space/Left/Right are registered as WindowShortcut QShortcuts in
        _setup_shortcuts(), so they fire regardless of which child widget
        has focus. keyPressEvent only consumes them to prevent Qt from
        forwarding them to the last-focused button.
        """
        key = event.key()
        playback_key = key in (Qt.Key.Key_Space, Qt.Key.Key_Left, Qt.Key.Key_Right)

        if self._focused_widget_is_text_input():
            super().keyPressEvent(event)
            return
        if not getattr(self, "_shortcuts_active", True):
            super().keyPressEvent(event)
            return

        if playback_key:
            event.accept()
            return

        super().keyPressEvent(event)

    def set_browser_shortcuts_enabled(self, enabled: bool):
        """Enable or disable all global keyboard shortcuts.
        Called with enabled=False when the embedded browser tab is in focus so that
        key presses (e.g. piano keys A-L) reach the web page instead of being
        consumed by Qt shortcut handlers."""
        self._shortcuts_active = enabled
        for sc in getattr(self, "_shortcuts", []):
            sc.setEnabled(enabled)

    def paintEvent(self, event):
        """Custom background for Liquid Glass — uses theme bg + accent colors for nebula glows."""
        from PyQt6.QtGui import QPainter, QLinearGradient, QRadialGradient, QBrush, QColor
        if not self.theme.get("_liquid_glass", False):
            super().paintEvent(event)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Base background from theme (custom_bg is already merged into self.theme by apply_theme)
        bg = QColor(self.theme.get("bg", "#0c0c10"))
        # Darken slightly for depth
        base_grad = QLinearGradient(0, 0, w, h)
        base_grad.setColorAt(0.0, bg.darker(130))
        base_grad.setColorAt(0.5, bg)
        base_grad.setColorAt(1.0, bg.darker(120))
        p.fillRect(self.rect(), QBrush(base_grad))

        # Nebula glow top-left — accent color
        a1 = QColor(self.theme.get("accent", "#a0c4ff"))
        a1.setAlpha(28)
        r1 = QRadialGradient(int(w * 0.15), int(h * 0.1), int(w * 0.45))
        r1.setColorAt(0.0, a1)
        r1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(r1))

        # Nebula glow bottom-right — accent2 color
        a2 = QColor(self.theme.get("accent2", "#c8b8ff"))
        a2.setAlpha(22)
        r2 = QRadialGradient(int(w * 0.85), int(h * 0.85), int(w * 0.5))
        r2.setColorAt(0.0, a2)
        r2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(r2))

        p.end()

    # ──────────────────────────── THEMING ────────────────────────────

    def apply_theme(self):
        t = dict(self.theme)  # shallow copy so we don't mutate the global

        # ── Apply custom color overrides (set in Settings → Appearance) ──────
        _color_keys = {
            "custom_accent":  "accent",
            "custom_accent2": "accent2",
            "custom_bg":      "bg",
            "custom_sidebar": "sidebar",
            "custom_panel":   "panel",
            "custom_card":    "card",
            "custom_text":    "text",
            "custom_subtext": "subtext",
        }
        for db_key, theme_key in _color_keys.items():
            saved = self.db.get_setting(db_key, "")
            if saved:                          # always apply if the user saved something
                t[theme_key] = saved
        # Always recompute derived values after overrides
        if "panel" not in t:
            t["panel"] = t["bg"]
        t["highlight"] = t["accent"] + "33"
        # border keeps theme value unless explicitly overridden via custom_border (not exposed yet)
        # Keep self.theme in sync so paintEvent and other direct readers see overrides
        self.theme = t

        # ── Lese Font-Einstellungen aus der Datenbank ──
        ui_font      = self.db.get_setting("ui_font",   "Segoe UI")
        ui_font_size = int(self.db.get_setting("font_size", "13"))
        ui_zoom      = int(self.db.get_setting("ui_zoom",  "100"))

        # Zoom skaliert die Basisschrift
        scaled_font_size = max(8, int(ui_font_size * ui_zoom / 100))
        small_font_size  = max(7, scaled_font_size - 3)
        large_font_size  = scaled_font_size + 2

        # QApplication-weites Zoom via setStyleSheet-Schriftgröße
        font_family = f'"{ui_font}", "Segoe UI", Arial, sans-serif'

        self.setStyleSheet(f"""
            /* ── Base ── */
            QWidget {{
                background-color: {t['bg']};
                color: {t['text']};
                font-size: {scaled_font_size}px;
                font-family: {font_family};
            }}
            QFrame {{ background-color: {t['bg']}; border: none; }}

            /* ── Sidebar ── */
            QFrame#sidebar_frame {{
                background-color: {t['sidebar']};
                border-right: 1px solid {t['border']};
            }}
            QLabel#section_label {{
                color: {t['subtext']};
                font-size: {small_font_size}px;
                font-weight: bold;
                letter-spacing: 2px;
                background: transparent;
                padding: 2px 4px;
                text-transform: uppercase;
            }}

            /* ── Nav buttons (sidebar) ── */
            QPushButton[nav=true] {{
                background-color: transparent;
                color: {t['subtext']};
                border: none;
                border-radius: 10px;
                text-align: left;
                padding: 10px 14px;
                font-size: {scaled_font_size}px;
                font-weight: 500;
            }}
            QPushButton[nav=true]:hover {{
                background-color: {t['highlight']};
                color: {t['text']};
            }}
            QPushButton[nav=true]:pressed {{
                background-color: {t['accent']}22;
                color: {t['accent']};
            }}

            /* ── Icon buttons (+ new playlist, gift) ── */
            QPushButton#icon_btn {{
                background-color: transparent;
                color: {t['subtext']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                font-size: {scaled_font_size}px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#icon_btn:hover {{
                background-color: {t['highlight']};
                color: {t['accent']};
                border-color: {t['accent']}66;
            }}

            /* ── Settings button ── */
            QPushButton#settings_btn {{
                background-color: transparent;
                color: {t['subtext']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 10px 16px;
                text-align: left;
                font-size: {scaled_font_size}px;
            }}
            QPushButton#settings_btn:hover {{
                background-color: {t['highlight']};
                color: {t['text']};
                border-color: {t['accent']}55;
            }}

            /* ── Top bar ── */
            QFrame#top_bar {{
                background-color: {t['sidebar']};
                border-bottom: 1px solid {t['border']};
            }}

            /* ── Column header ── */
            QFrame#col_header {{
                background-color: {t['bg']};
                border-bottom: 1px solid {t['border']};
            }}
            QLabel#col_label {{
                color: {t['subtext']};
                font-size: {small_font_size}px;
                font-weight: bold;
                letter-spacing: 1px;
                text-transform: uppercase;
                background: transparent;
            }}

            /* ── Status bar ── */
            QFrame#status_bar {{
                background-color: {t['sidebar']};
                border-top: 1px solid {t['border']};
            }}

            /* ── Toolbar buttons (top bar) ── */
            QPushButton#toolbar_btn {{
                background-color: transparent;
                color: {t['subtext']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 5px 13px;
                font-size: {small_font_size}px;
                font-weight: 500;
            }}
            QPushButton#toolbar_btn:hover {{
                background-color: {t['highlight']};
                border-color: {t['accent']}66;
                color: {t['text']};
            }}
            QPushButton#toolbar_btn:pressed {{
                background-color: {t['accent']}22;
                color: {t['accent']};
            }}

            QPushButton#nav_btn {{
                background-color: transparent;
                color: {t['subtext']};
                border: none;
                border-radius: 8px;
                padding: 0px;
                font-size: {large_font_size}px;
            }}
            QPushButton#nav_btn:hover {{
                background-color: {t['highlight']};
                color: {t['text']};
            }}
            QPushButton#nav_btn:pressed {{
                background-color: {t['accent']}33;
                color: {t['accent']};
            }}

            /* ── Audio download button (red tint) ── */
            QPushButton#yt_btn {{
                background-color: transparent;
                color: #f87171;
                border: 1px solid #f8717144;
                border-radius: 8px;
                padding: 5px 13px;
                font-size: {small_font_size}px;
                font-weight: 600;
            }}
            QPushButton#yt_btn:hover {{
                background-color: #f8717118;
                border-color: #f87171;
            }}
            QPushButton#yt_dl_btn {{
                background-color: transparent;
                color: #f87171;
                border: 1px solid #f8717144;
                border-radius: 8px;
                padding: 4px 13px;
                font-size: {small_font_size}px;
                font-weight: 600;
            }}
            QPushButton#yt_dl_btn:hover {{
                background-color: #f8717118;
                border-color: #f87171;
            }}
            QPushButton#yt_dl_btn:disabled {{
                color: {t['subtext']};
                border-color: {t['border']};
                background-color: transparent;
            }}

            /* ── Video download button (blue tint) ── */
            QPushButton#vid_btn {{
                background-color: transparent;
                color: #60a5fa;
                border: 1px solid #60a5fa44;
                border-radius: 8px;
                padding: 5px 13px;
                font-size: {small_font_size}px;
                font-weight: 600;
            }}
            QPushButton#vid_btn:hover {{
                background-color: #60a5fa18;
                border-color: #60a5fa;
            }}

            /* ── Browser toolbar / status ── */
            QFrame#yt_browser_toolbar {{
                background-color: {t['sidebar']};
                border-bottom: 1px solid {t['border']};
            }}
            QFrame#yt_status_bar {{
                background-color: {t['panel']};
                border-bottom: 1px solid {t['border']};
            }}

            /* ── Song list ── */
            QListWidget {{
                background-color: {t['bg']};
                border: none;
                padding: 6px 6px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 9px 12px;
                margin: 2px 4px;
                border-radius: 10px;
                background-color: transparent;
                border: 1px solid transparent;
            }}
            QListWidget::item:selected {{
                background-color: {t['accent']}1e;
                border: 1px solid {t['accent']}44;
                color: {t['text']};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {t['highlight']};
                border: 1px solid {t['border']};
            }}

            /* ── Right panel (player) ── */
            QFrame#right_panel {{
                background-color: {t['sidebar']};
                border-left: 1px solid {t['border']};
            }}
            QFrame#cover_container {{
                background-color: {t['card']};
                border-radius: 20px;
                border: 1px solid {t['border']};
            }}
            QLabel#artist_label {{
                color: {t['subtext']};
                font-size: {small_font_size}px;
                background: transparent;
            }}
            QLabel#time_label {{
                color: {t['subtext']};
                font-size: {small_font_size}px;
                background: transparent;
            }}
            QLabel#lyrics_label {{
                background: transparent;
                color: {t['text']};
                font-size: 12px;
                padding: 4px;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}

            /* ── Play button (right panel) ── */
            QPushButton#play_btn_main {{
                background-color: {t['accent']};
                color: white;
                border: none;
                border-radius: 19px;
                font-size: {large_font_size}px;
                font-weight: bold;
            }}
            QPushButton#play_btn_main:hover {{
                background-color: {t['accent2']};
            }}
            QPushButton#play_btn_main:pressed {{
                background-color: {t['accent']};
            }}

            /* ── Generic buttons (dialogs etc.) ── */
            QPushButton {{
                background-color: {t['accent']};
                border: none;
                border-radius: 9px;
                padding: 8px 16px;
                color: white;
                font-weight: 600;
                font-size: {scaled_font_size}px;
            }}
            QPushButton:hover {{ background-color: {t['accent2']}; }}
            QPushButton:pressed {{ background-color: {t['accent']}cc; }}

            /* ── Bottom bar play button ── */
            QPushButton#bb_play_btn {{
                background-color: {t['text']};
                color: {t['bg']};
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#bb_play_btn:hover {{
                background-color: white;
                transform: scale(1.05);
            }}

            /* ── Bottom bar control buttons ── */
            QPushButton#bb_ctrl_btn {{
                background: transparent;
                border: none;
                color: {t['subtext']};
                font-size: {large_font_size}px;
                border-radius: 15px;
                padding: 0;
                font-weight: normal;
            }}
            QPushButton#bb_ctrl_btn:hover {{
                background: transparent;
                color: {t['text']};
            }}

            /* ── Favourite button (bottom bar) ── */
            QPushButton#bb_fav {{
                background: transparent;
                border: none;
                color: {t['subtext']};
                font-size: {scaled_font_size}px;
                border-radius: 15px;
                padding: 0;
                font-weight: normal;
            }}
            QPushButton#bb_fav:hover {{ color: {t['red']}; }}

            /* ── Sliders ── */
            QSlider::groove:horizontal {{
                height: 4px;
                background: {t['border']};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {t['text']};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
                border: 2px solid {t['accent']};
            }}
            QSlider::handle:horizontal:hover {{
                background: {t['accent']};
                border-color: {t['accent2']};
            }}
            QSlider::sub-page:horizontal {{
                background: {t['accent']};
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: {t['border']};
                border-radius: 2px;
            }}

            /* ── Inputs ── */
            QLineEdit {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 7px 14px;
                color: {t['text']};
                selection-background-color: {t['accent']}44;
            }}
            QLineEdit:focus {{ border-color: {t['accent']}; }}
            QLineEdit:hover {{ border-color: {t['accent']}66; }}

            QLabel {{ color: {t['text']}; background: transparent; }}

            /* ── Tabs ── */
            QTabWidget::pane {{
                border: 1px solid {t['border']};
                border-radius: 10px;
                background: {t['bg']};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {t['subtext']};
                padding: 8px 20px;
                margin-right: 4px;
                border-radius: 8px;
                font-weight: 500;
                border: none;
            }}
            QTabBar::tab:selected {{
                background: {t['accent']};
                color: white;
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {t['highlight']};
                color: {t['text']};
            }}

            /* ── ComboBox / SpinBox ── */
            QComboBox {{
                background: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 9px;
                padding: 6px 12px;
                color: {t['text']};
                selection-background-color: {t['accent']};
            }}
            QComboBox:hover {{ border-color: {t['accent']}66; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QSpinBox {{
                background: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 9px;
                padding: 5px 10px;
                color: {t['text']};
            }}
            QSpinBox:hover {{ border-color: {t['accent']}66; }}

            QCheckBox {{ color: {t['text']}; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border-radius: 4px;
                border: 1px solid {t['border']};
                background: {t['card']};
            }}
            QCheckBox::indicator:checked {{
                background: {t['accent']};
                border-color: {t['accent']};
            }}

            QTextEdit {{
                background: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                color: {t['text']};
                padding: 4px;
                selection-background-color: {t['accent']}44;
            }}
            QTextEdit:focus {{ border-color: {t['accent']}; }}

            /* ── Context menu ── */
            QMenu {{
                background: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 12px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 9px 22px;
                border-radius: 8px;
                color: {t['text']};
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background: {t['accent']};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {t['border']};
                margin: 5px 10px;
            }}

            /* ── Dialogs & scrollbars ── */
            QDialog {{ background: {t['bg']}; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                border-radius: 2px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 2px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t['subtext']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

            QScrollBar:horizontal {{
                background: transparent;
                height: 5px;
                border-radius: 2px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {t['border']};
                border-radius: 2px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

            /* ── Progress bar ── */
            QProgressBar {{
                background: {t['card']};
                border: none;
                border-radius: 4px;
                text-align: center;
                color: {t['subtext']};
                font-size: {small_font_size}px;
                max-height: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent2']});
                border-radius: 4px;
            }}

            /* ── Bottom player bar ── */
            QFrame#bottom_bar {{
                background-color: {t['panel']};
                border-top: 1px solid {t['border']};
            }}
            QLabel#bb_title {{
                font-size: {scaled_font_size}px;
                font-weight: 600;
                color: {t['text']};
                background: transparent;
            }}
            QLabel#bb_artist {{
                font-size: {small_font_size}px;
                color: {t['subtext']};
                background: transparent;
            }}

            /* ── Group boxes (settings) ── */
            QGroupBox {{
                border: 1px solid {t['border']};
                border-radius: 10px;
                margin-top: 14px;
                padding: 8px;
                font-weight: 600;
                color: {t['subtext']};
                font-size: 11px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {t['subtext']};
            }}
        """)

        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {t['sidebar']};
                border-right: 1px solid {t['border']};
            }}
        """)

        self.cover_label.setStyleSheet(
            f"background-color: {t['card']}; border-radius: 16px;"
        )

        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {t['border']};
                border-radius: 20px;
                font-size: {large_font_size}px;
                color: {t['subtext']};
            }}
            QPushButton:hover {{
                border-color: {t['red']};
                color: {t['red']};
                background: {t['red']}15;
            }}
        """)

        for sb in self.star_btns:
            sb.setStyleSheet(
                f"QPushButton {{ background: transparent; font-size: {scaled_font_size}px; color: {t['subtext']}; border: none; }}"
            )

        self.status_label.setStyleSheet(f"color: {t['subtext']}; font-size: {small_font_size}px; background: transparent;")

        # Bottom bar styling — base styles come from the global stylesheet via objectName.
        # Only the play button needs an explicit override here.
        self.bb_play_btn.setStyleSheet(
            f"QPushButton {{ background: {t['text']}; color: {t['bg']}; border: none; border-radius: 19px; font-size: {large_font_size}px; font-weight: bold; padding: 0; }}"
            f"QPushButton:hover {{ background: white; }}"
        )
        # Reset ctrl buttons to base (toggle_loop/shuffle will re-apply active state)
        for b in [self.bb_shuffle_btn, self.bb_prev_btn, self.bb_next_btn, self.bb_loop_btn]:
            b.setStyleSheet("")
        self.bb_fav_btn.setStyleSheet("")

        # ── Liquid Glass override ─────────────────────────────────────────────
        if t.get("_liquid_glass"):
            # Enable styled background so paintEvent renders our gradient
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            self.update()
            self._apply_liquid_glass_theme(t, scaled_font_size, small_font_size, large_font_size, font_family)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _apply_liquid_glass_theme(self, t, fs, ss, ls, ff):
        """
        Apply the Liquid Glass aesthetic on top of the base stylesheet.

        Technique: Qt QSS cannot do real backdrop-filter blur, but we fake the
        frosted glass look with:
          • semi-transparent backgrounds via rgba()
          • layered border: 1px solid rgba(255,255,255,N) (the 'rim highlight')
          • a subtle inner top-highlight (box-shadow workaround via gradient)
          • smooth radius everywhere
          • a cool cyan/violet accent palette

        Every widget section is re-declared so the override wins specificity.
        """
        # ── Palette — pulled from t so custom color overrides work ──────────
        # t already has all custom_* DB values merged in by apply_theme().
        text_primary = t["text"]
        text_sub     = t["subtext"]
        accent       = t["accent"]
        accent2      = t["accent2"]
        red          = t["red"]
        green        = t["green"]
        accent_solid = accent  # solid accent for opaque fills (play button etc.)

        def _hex_to_rgba(hex_color, alpha):
            h = hex_color.lstrip("#")
            if len(h) == 3:
                h = "".join(c*2 for c in h)
            try:
                r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
            except Exception:
                r, g, b = 160, 196, 255
            return f"rgba({r},{g},{b},{alpha})"

        glass_base   = "rgba(255,255,255,12)"
        glass_mid    = "rgba(255,255,255,18)"
        glass_hover  = "rgba(255,255,255,28)"
        glass_active = _hex_to_rgba(accent, 40)   # accent-tinted, respects user pick
        rim_subtle   = "rgba(255,255,255,30)"
        rim_bright   = "rgba(255,255,255,55)"

        self.setStyleSheet(f"""
            /* ═══════════════════════ LIQUID GLASS BASE ═══════════════════════ */

            QWidget {{
                background-color: transparent;
                color: {text_primary};
                font-size: {fs}px;
                font-family: {ff};
            }}

            /* Root window must have an opaque background */
            QMainWindow, QDialog {{
                background-color: #0c0c10;
            }}

            QFrame {{
                background-color: transparent;
                border: none;
            }}

            /* ── Sidebar ── */
            QFrame#sidebar_frame {{
                background-color: {glass_base};
                border-right: 1px solid {rim_subtle};
            }}

            QLabel#section_label {{
                color: {text_sub};
                font-size: {ss}px;
                font-weight: bold;
                letter-spacing: 2px;
                background: transparent;
                padding: 2px 4px;
            }}

            /* ── Nav buttons ── */
            QPushButton[nav=true] {{
                background-color: transparent;
                color: {text_sub};
                border: none;
                border-radius: 12px;
                text-align: left;
                padding: 10px 14px;
                font-size: {fs}px;
                font-weight: 500;
            }}
            QPushButton[nav=true]:hover {{
                background-color: {glass_hover};
                color: {text_primary};
                border: 1px solid {rim_subtle};
            }}
            QPushButton[nav=true]:pressed {{
                background-color: {glass_active};
                color: {accent};
                border: 1px solid {rim_bright};
            }}

            /* ── Icon buttons ── */
            QPushButton#icon_btn {{
                background-color: {glass_base};
                color: {text_sub};
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                font-size: {fs}px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#icon_btn:hover {{
                background-color: {glass_hover};
                color: {accent};
                border-color: {rim_bright};
            }}

            /* ── Settings button ── */
            QPushButton#settings_btn {{
                background-color: {glass_base};
                color: {text_sub};
                border: 1px solid {rim_subtle};
                border-radius: 12px;
                padding: 10px 16px;
                text-align: left;
                font-size: {fs}px;
            }}
            QPushButton#settings_btn:hover {{
                background-color: {glass_hover};
                color: {text_primary};
                border-color: {rim_bright};
            }}

            /* ── Top bar ── */
            QFrame#top_bar {{
                background-color: {glass_base};
                border-bottom: 1px solid {rim_subtle};
            }}

            /* ── Column header ── */
            QFrame#col_header {{
                background-color: transparent;
                border-bottom: 1px solid {rim_subtle};
            }}
            QLabel#col_label {{
                color: {text_sub};
                font-size: {ss}px;
                font-weight: bold;
                letter-spacing: 1px;
                background: transparent;
            }}

            /* ── Status bar ── */
            QFrame#status_bar {{
                background-color: {glass_base};
                border-top: 1px solid {rim_subtle};
            }}

            /* ── Toolbar buttons ── */
            QPushButton#toolbar_btn {{
                background-color: {glass_base};
                color: {text_sub};
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                padding: 5px 14px;
                font-size: {ss}px;
                font-weight: 500;
            }}
            QPushButton#toolbar_btn:hover {{
                background-color: {glass_hover};
                border-color: {rim_bright};
                color: {text_primary};
            }}
            QPushButton#toolbar_btn:pressed {{
                background-color: {glass_active};
                color: {accent};
                border-color: rgba(160,196,255,120);
            }}

            QPushButton#nav_btn {{
                background-color: transparent;
                color: {text_sub};
                border: none;
                border-radius: 8px;
                padding: 0px;
                font-size: {ls}px;
            }}
            QPushButton#nav_btn:hover {{
                background-color: {glass_hover};
                color: {text_primary};
            }}

            /* ── YT / media buttons ── */
            QPushButton#yt_btn, QPushButton#yt_dl_btn {{
                background-color: rgba(255, 107, 157, 12);
                color: {red};
                border: 1px solid rgba(255,107,157,50);
                border-radius: 10px;
                padding: 5px 14px;
                font-size: {ss}px;
                font-weight: 600;
            }}
            QPushButton#yt_btn:hover, QPushButton#yt_dl_btn:hover {{
                background-color: rgba(255,107,157,22);
                border-color: rgba(255,107,157,120);
            }}
            QPushButton#yt_dl_btn:disabled {{
                color: {text_sub};
                border-color: {rim_subtle};
                background-color: transparent;
            }}
            QPushButton#vid_btn {{
                background-color: rgba(100,175,255,12);
                color: #74c0fc;
                border: 1px solid rgba(100,175,255,50);
                border-radius: 10px;
                padding: 5px 14px;
                font-size: {ss}px;
                font-weight: 600;
            }}
            QPushButton#vid_btn:hover {{
                background-color: rgba(100,175,255,22);
                border-color: rgba(100,175,255,120);
            }}

            /* ── Browser toolbar ── */
            QFrame#yt_browser_toolbar {{
                background-color: {glass_base};
                border-bottom: 1px solid {rim_subtle};
            }}
            QFrame#yt_status_bar {{
                background-color: {glass_base};
                border-bottom: 1px solid {rim_subtle};
            }}

            /* ── Song list ── */
            QListWidget {{
                background-color: transparent;
                border: none;
                padding: 6px 6px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 9px 12px;
                margin: 2px 4px;
                border-radius: 12px;
                background-color: transparent;
                border: 1px solid transparent;
            }}
            QListWidget::item:selected {{
                background-color: {glass_active};
                border: 1px solid rgba(160,196,255,80);
                color: {text_primary};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {glass_hover};
                border: 1px solid {rim_subtle};
            }}

            /* ── Right panel ── */
            QFrame#right_panel {{
                background-color: {glass_base};
                border-left: 1px solid {rim_subtle};
            }}
            QFrame#cover_container {{
                background-color: {glass_mid};
                border-radius: 22px;
                border: 1px solid {rim_subtle};
            }}
            QLabel#artist_label {{
                color: {text_sub};
                font-size: {ss}px;
                background: transparent;
            }}
            QLabel#time_label {{
                color: {text_sub};
                font-size: {ss}px;
                background: transparent;
            }}
            QLabel#lyrics_label {{
                background: transparent;
                color: {text_primary};
                font-size: 12px;
                padding: 4px;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}

            /* ── Main Play button ── */
            QPushButton#play_btn_main {{
                background-color: {accent_solid};
                color: white;
                border: 1px solid {rim_bright};
                border-radius: 19px;
                font-size: {ls}px;
                font-weight: bold;
            }}
            QPushButton#play_btn_main:hover {{
                background-color: rgba(91,141,238,220);
            }}

            /* ── Generic buttons (dialogs) ── */
            QPushButton {{
                background-color: {glass_mid};
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                padding: 8px 16px;
                color: {text_primary};
                font-weight: 600;
                font-size: {fs}px;
            }}
            QPushButton:hover {{
                background-color: {glass_hover};
                border-color: {rim_bright};
            }}
            QPushButton:pressed {{
                background-color: {glass_active};
                color: {accent};
            }}

            /* ── Bottom bar play button ── */
            QPushButton#bb_play_btn {{
                background-color: {accent_solid};
                color: white;
                border: 1px solid {rim_bright};
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#bb_play_btn:hover {{
                background-color: rgba(91,141,238,255);
            }}

            /* ── Bottom bar ctrl buttons ── */
            QPushButton#bb_ctrl_btn {{
                background: transparent;
                border: none;
                color: {text_sub};
                font-size: {ls}px;
                border-radius: 15px;
                padding: 0;
            }}
            QPushButton#bb_ctrl_btn:hover {{
                color: {text_primary};
            }}
            QPushButton#bb_fav {{
                background: transparent;
                border: none;
                color: {text_sub};
                font-size: {fs}px;
                border-radius: 15px;
                padding: 0;
            }}
            QPushButton#bb_fav:hover {{ color: {red}; }}

            /* ── Sliders ── */
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(255,255,255,20);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: white;
                width: 13px;
                height: 13px;
                margin: -5px 0;
                border-radius: 7px;
                border: 2px solid {accent};
            }}
            QSlider::handle:horizontal:hover {{
                background: {accent};
                border-color: {accent2};
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent_solid}, stop:1 {accent2});
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: rgba(255,255,255,15);
                border-radius: 2px;
            }}

            /* ── Inputs ── */
            QLineEdit {{
                background-color: {glass_mid};
                border: 1px solid {rim_subtle};
                border-radius: 12px;
                padding: 7px 14px;
                color: {text_primary};
                selection-background-color: rgba(160,196,255,60);
            }}
            QLineEdit:focus {{ border-color: {rim_bright}; background-color: {glass_hover}; }}
            QLineEdit:hover {{ border-color: {rim_subtle}; }}

            QLabel {{ color: {text_primary}; background: transparent; }}

            /* ── Tabs ── */
            QTabWidget::pane {{
                border: 1px solid {rim_subtle};
                border-radius: 12px;
                background: {glass_base};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {text_sub};
                padding: 8px 20px;
                margin-right: 4px;
                border-radius: 8px;
                font-weight: 500;
                border: none;
            }}
            QTabBar::tab:selected {{
                background: {glass_active};
                color: {accent};
                border: 1px solid rgba(160,196,255,80);
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {glass_hover};
                color: {text_primary};
            }}

            /* ── ComboBox / SpinBox ── */
            QComboBox {{
                background: {glass_mid};
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                padding: 6px 12px;
                color: {text_primary};
            }}
            QComboBox:hover {{ border-color: {rim_bright}; background: {glass_hover}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background: #181828;
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                selection-background-color: {glass_active};
                color: {text_primary};
            }}
            QSpinBox {{
                background: {glass_mid};
                border: 1px solid {rim_subtle};
                border-radius: 10px;
                padding: 5px 10px;
                color: {text_primary};
            }}
            QSpinBox:hover {{ border-color: {rim_bright}; }}

            QCheckBox {{ color: {text_primary}; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border-radius: 5px;
                border: 1px solid {rim_subtle};
                background: {glass_mid};
            }}
            QCheckBox::indicator:checked {{
                background: {accent_solid};
                border-color: {rim_bright};
            }}

            QTextEdit {{
                background: {glass_mid};
                border: 1px solid {rim_subtle};
                border-radius: 12px;
                color: {text_primary};
                padding: 4px;
                selection-background-color: rgba(160,196,255,60);
            }}
            QTextEdit:focus {{ border-color: {rim_bright}; }}

            /* ── Context menu ── */
            QMenu {{
                background: rgba(15, 15, 25, 220);
                border: 1px solid {rim_subtle};
                border-radius: 14px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 9px 22px;
                border-radius: 8px;
                color: {text_primary};
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background: {glass_active};
                color: {accent};
                border: 1px solid rgba(160,196,255,60);
            }}
            QMenu::separator {{
                height: 1px;
                background: {rim_subtle};
                margin: 5px 10px;
            }}

            /* ── Dialogs ── */
            QDialog {{ background: #0c0c10; }}

            /* ── Scrollbars ── */
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                border-radius: 2px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,25);
                border-radius: 2px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,50);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 5px;
                border-radius: 2px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(255,255,255,25);
                border-radius: 2px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

            /* ── Progress bar ── */
            QProgressBar {{
                background: {glass_mid};
                border: none;
                border-radius: 4px;
                text-align: center;
                color: {text_sub};
                font-size: {ss}px;
                max-height: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent_solid}, stop:1 {accent2});
                border-radius: 4px;
            }}

            /* ── Bottom player bar ── */
            QFrame#bottom_bar {{
                background-color: {glass_base};
                border-top: 1px solid {rim_subtle};
            }}
            QLabel#bb_title {{
                font-size: {fs}px;
                font-weight: 600;
                color: {text_primary};
                background: transparent;
            }}
            QLabel#bb_artist {{
                font-size: {ss}px;
                color: {text_sub};
                background: transparent;
            }}

            /* ── Group boxes (settings) ── */
            QGroupBox {{
                border: 1px solid {rim_subtle};
                border-radius: 12px;
                margin-top: 14px;
                padding: 8px;
                font-weight: 600;
                color: {text_sub};
                font-size: 11px;
                background: {glass_base};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {text_sub};
            }}

            /* ── Splitter ── */
            QSplitter::handle {{
                background: {rim_subtle};
            }}
        """)

        # Override individual widget styles for glass consistency
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255,255,255,8);
                border-right: 1px solid rgba(255,255,255,22);
            }}
        """)
        self.cover_label.setStyleSheet(
            "background-color: rgba(255,255,255,10); border-radius: 18px;"
        )
        self.fav_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,10);
                border: 1px solid rgba(255,255,255,25);
                border-radius: 20px;
                font-size: {ls}px;
                color: {text_sub};
            }}
            QPushButton:hover {{
                border-color: rgba(255,107,157,140);
                color: {red};
                background: rgba(255,107,157,18);
            }}
        """)
        for sb in self.star_btns:
            sb.setStyleSheet(
                f"QPushButton {{ background: transparent; font-size: {fs}px; color: {text_sub}; border: none; }}"
            )
        self.status_label.setStyleSheet(
            f"color: {text_sub}; font-size: {ss}px; background: transparent;"
        )
        self.bb_play_btn.setStyleSheet(
            f"QPushButton {{ background: {accent_solid}; color: white; border: 1px solid rgba(255,255,255,50); "
            f"border-radius: 19px; font-size: {ls}px; font-weight: bold; padding: 0; }}"
            f"QPushButton:hover {{ background: rgba(91,141,238,240); }}"
        )
        for b in [self.bb_shuffle_btn, self.bb_prev_btn, self.bb_next_btn, self.bb_loop_btn]:
            b.setStyleSheet("")
        self.bb_fav_btn.setStyleSheet("")

    # ──────────────────────────── VIEWS ────────────────────────────

    def switch_view(self, view):
        if self.current_view == "extras" and view != "extras":
            self.password_manager.lock()

        self.current_view = view
        self.current_playlist_id = None
        self.playlist_banner.setVisible(False)
        titles = {
            "library": "All Songs",
            "videos": "🎬  Videos",
            "ytbrowser": "🌐  Media Browser",
            "favourites": "♥  Favourites",
            "recently": "🕐  Recently Played",
            "mostplayed": "🔥  Most Played",
            "extras": "⚡  Extras",
        }
        self.view_title.setText(titles.get(view, view))

        # Video always plays in the cover area (top-left) regardless of which tab
        # is active — never detach VLC from the video_frame on tab switches.
        if self.is_video_mode:
            if not (hasattr(self, "_fs_win") and self._fs_win):
                self.cover_stack.setCurrentIndex(1)


        # Fullscreen button always enabled
        self.fs_btn.setEnabled(True)
        self.fs_btn.setToolTip("Vollbild öffnen (oder Doppelklick auf Bild/Video)")

        if view == "extras":
            self.center_stack.setCurrentIndex(2)
            self.col_header.setVisible(False)
            self.extras_panel.show_dashboard()
            self.popout_btn.setVisible(False)
        # Show YouTube browser panel or the normal song list
        elif view == "ytbrowser":
            self.center_stack.setCurrentIndex(1)   # YouTube panel
            self.col_header.setVisible(False)
            self.status_label.setText("Media Browser  ·  YouTube, Vimeo, SoundCloud, Twitch, Bandcamp, …")
            self.popout_btn.setVisible(True)   # pop-out available for browser
        else:
            self.center_stack.setCurrentIndex(0)   # Normal library view
            self.col_header.setVisible(True)
            self.load_library()
            if not self.is_video_mode:
                self.popout_btn.setVisible(False)


    def open_playlist(self, item):
        import traceback as _tb
        try:
            if item is None:
                return
            playlist_id = item.data(Qt.ItemDataRole.UserRole)
            if playlist_id is None:
                return
            playlist = self.db.get_playlist(playlist_id)
            if not playlist:
                return
            self.current_view = "playlist"
            self.current_playlist_id = playlist_id
            self.view_title.setText(f"▶  {playlist[1]}")

            pid, name, desc, created, cover = playlist
            self.pl_banner_name.setText(name)
            self.pl_banner_desc.setText(desc or "")
            try:
                song_count = len(self.db.get_playlist_songs(pid))
                video_count = len(self.db.get_playlist_videos(pid))
            except Exception:
                song_count = 0
                video_count = 0
            parts = []
            if song_count:
                parts.append(f"{song_count} Song{'s' if song_count != 1 else ''}")
            if video_count:
                parts.append(f"{video_count} Video{'s' if video_count != 1 else ''}")
            self.pl_banner_stats.setText("  ·  ".join(parts) if parts else "Leer")

            cover_shown = False
            try:
                if cover and os.path.exists(cover):
                    px = QPixmap(cover).scaled(88, 88, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                               Qt.TransformationMode.SmoothTransformation)
                    if not px.isNull():
                        self.pl_banner_cover.setPixmap(px)
                        cover_shown = True
            except Exception:
                pass
            if not cover_shown:
                try:
                    for s in self.db.get_playlist_songs(pid):
                        cp = s[5]
                        if cp and os.path.exists(cp):
                            px = QPixmap(cp).scaled(88, 88, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                    Qt.TransformationMode.SmoothTransformation)
                            if not px.isNull():
                                self.pl_banner_cover.setPixmap(px)
                                cover_shown = True
                                break
                except Exception:
                    pass
            if not cover_shown:
                self.pl_banner_cover.clear()
                self.pl_banner_cover.setText("♪")
                self.pl_banner_cover.setFont(QFont("Arial", 32))
            self.playlist_banner.setVisible(True)
            self.load_library()
        except Exception:
            _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_crash.log")
            try:
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(f"\n--- open_playlist error ---\n{_tb.format_exc()}")
            except Exception:
                pass

    def _pl_add_from_library(self):
        """Medien aus der Bibliothek zur aktuellen Playlist hinzufügen."""
        pid = self.current_playlist_id
        if not pid:
            return
        pl = self.db.get_playlist(pid)
        if not pl:
            return
        dlg = PlaylistContentDialog(self, self.db, pid, pl[1])
        dlg.exec()
        self.refresh_sidebar()
        self.load_library()

    def _pl_add_from_local(self):
        """Lokale Audio- & Videodateien importieren und zur aktuellen Playlist hinzufügen."""
        pid = self.current_playlist_id
        if not pid:
            return
        pl = self.db.get_playlist(pid)
        playlist_name = pl[1] if pl else "Playlist"
        file_dlg = QFileDialog(self, f"Dateien für '{playlist_name}' auswählen")
        file_dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dlg.setNameFilters([
            "Alle Medien (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)",
            "Audio (*.mp3 *.ogg *.wav *.flac *.m4a *.aac)",
            "Video (*.mp4 *.mkv *.avi *.gif *.webm *.mov)",
        ])
        file_dlg.selectNameFilter("Alle Medien (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)")
        if not file_dlg.exec():
            return
        files = file_dlg.selectedFiles()
        audio_files = [f for f in files if any(f.lower().endswith(e) for e in SUPPORTED_FORMATS)]
        video_files = [f for f in files if any(f.lower().endswith(e) for e in SUPPORTED_VIDEO_FORMATS)]
        cover = self.ask_cover_image() if audio_files else None
        added = 0
        for f in audio_files:
            self.process_song_import(f, cover)
            song = self.db.get_song_by_path(f)
            if song:
                self.db.add_song_to_playlist(pid, song[0])
                added += 1
        for f in video_files:
            existing = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (f,)).fetchone()
            if not existing:
                title = Path(os.path.basename(f)).stem
                file_size = os.path.getsize(f) if os.path.exists(f) else 0
                fmt = os.path.splitext(f)[1].lstrip(".")
                self.db.add_video(title, "", f, None, 0, file_size, fmt, "")
            vid = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (f,)).fetchone()
            if vid:
                self.db.add_video_to_playlist(pid, vid[0])
                added += 1
        self.load_library()
        self.refresh_sidebar()
        self.status_label.setText(f"{added} Datei(en) zu '{playlist_name}' hinzugefügt.")

    def _pl_add_from_download(self):
        """Download-Dialog öffnen und Ergebnis zur aktuellen Playlist hinzufügen."""
        pid = self.current_playlist_id
        if not pid:
            return
        pl = self.db.get_playlist(pid)
        playlist_name = pl[1] if pl else "Playlist"
        type_menu = QMenu(self)
        type_menu.addAction("♫  Audio via URL", lambda: self._dl_into_playlist(pid, playlist_name, "audio"))
        type_menu.addAction("🎬  Video via URL", lambda: self._dl_into_playlist(pid, playlist_name, "video"))
        type_menu.exec(self.pl_add_btn.mapToGlobal(self.pl_add_btn.rect().bottomLeft()))

    def _playlist_play_all(self):
        """Play all songs in the current playlist from the beginning."""
        if not self.current_playlist_id:
            return
        if self.song_list.count() == 0:
            return
        self.shuffle_enabled = False
        self.current_index = 0
        item = self.song_list.item(0)
        self.play_selected_song(item)

    def _playlist_shuffle_all(self):
        """Shuffle and play all songs in the current playlist."""
        if not self.current_playlist_id:
            return
        count = self.song_list.count()
        if count == 0:
            return
        self.shuffle_enabled = True
        indices = list(range(count))
        random.shuffle(indices)
        self.shuffle_queue = [
            self.song_list.item(i).data(Qt.ItemDataRole.UserRole + 1)
            for i in indices
        ]
        self.current_index = indices[0]
        item = self.song_list.item(indices[0])
        self.play_selected_song(item)

    def _playlist_edit_current(self):
        """Open the content editor for the current playlist."""
        if not self.current_playlist_id:
            return
        self._edit_playlist_content(self.current_playlist_id)

    def _apply_sort(self, order: str):
        """Set sort order and refresh the library."""
        self._sort_order = order
        labels = {"az": "↑ A→Z", "za": "↓ Z→A", "newest": "🕐 Neu", "oldest": "🕐 Alt"}
        self._sort_btn.setText(labels.get(order, "↕"))
        self.load_library(self.search_box.text())

    def _sort_songs(self, songs: list) -> list:
        """Sort a song list according to self._sort_order."""
        order = getattr(self, "_sort_order", "az")
        if order == "az":
            return sorted(songs, key=lambda s: (s[2].lower(), s[1].lower()))  # artist, title
        elif order == "za":
            return sorted(songs, key=lambda s: (s[2].lower(), s[1].lower()), reverse=True)
        elif order == "newest":
            # song tuple: id,title,artist,album,path,cover_path,duration,fav,rating,plays
            # date_added is not in the tuple — sort by id desc (higher id = newer)
            return sorted(songs, key=lambda s: s[0], reverse=True)
        elif order == "oldest":
            return sorted(songs, key=lambda s: s[0])
        return songs

    def get_current_songs(self, search=""):
        if self.current_view == "library":
            return self._sort_songs(self.db.get_all_songs(search))
        elif self.current_view == "favourites":
            songs = self.db.get_favourites()
            if search:
                s = search.lower()
                songs = [x for x in songs if s in (x[1]+x[2]+x[3]).lower()]
            return self._sort_songs(songs)
        elif self.current_view == "recently":
            return self.db.get_recently_played()   # keep chronological order
        elif self.current_view == "mostplayed":
            return self.db.get_most_played()        # keep play-count order
        elif self.current_view == "playlist" and self.current_playlist_id:
            songs = self.db.get_playlist_songs(self.current_playlist_id)
            if search:
                s = search.lower()
                songs = [x for x in songs if s in (x[1]+x[2]+x[3]).lower()]
            return self._sort_songs(songs)
        return []

    # ──────────────────────────── LIBRARY ────────────────────────────

    def load_library(self, search=""):
        self.song_list.clear()

        if self.current_view == "videos":
            self._load_video_library(search)
            return

        songs = self.get_current_songs(search)
        show_covers = self.db.get_setting("show_covers", "1") == "1"

        for idx, song in enumerate(songs):
            sid, title, artist, album, path, cover_path, duration, fav, rating, plays = song
            fav_icon = "♥ " if fav else ""
            dur_str = format_duration(duration)
            plays_str = f"  ·  {plays}▶" if plays else ""

            line1 = f"{fav_icon}{title}"
            line2 = f"{artist}  ·  {album}{plays_str}"
            if dur_str and dur_str != "0:00":
                line2 += f"  [{dur_str}]"

            display = f"{line1}\n{line2}"

            item = QListWidgetItem(display)

            if show_covers and cover_path and os.path.exists(cover_path):
                px = QPixmap(cover_path).scaled(
                    46, 46,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item.setIcon(QIcon(px))

            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, sid)
            item.setData(Qt.ItemDataRole.UserRole + 2, "song")
            item.setToolTip(f"{title}\n{artist} · {album}\nPlays: {plays}\n{path}")
            self.song_list.addItem(item)

        # In playlist view, also load videos that belong to the playlist
        playlist_videos = []
        if self.current_view == "playlist" and self.current_playlist_id:
            playlist_videos = self.db.get_playlist_videos(self.current_playlist_id)
            if search:
                s = search.lower()
                playlist_videos = [v for v in playlist_videos if s in (v[1] + v[2]).lower()]
            self.song_list.setIconSize(QSize(80, 56))
            for vid in playlist_videos:
                vid_id, title, channel, path, thumb_path, duration, file_size, fmt, resolution = vid
                dur_str = format_duration(duration)
                size_str = f"{file_size // (1024*1024)} MB" if file_size > 0 else ""
                meta_parts = [p for p in [channel, fmt.upper() if fmt else "", resolution, dur_str, size_str] if p]
                line2 = "  ·  ".join(meta_parts)
                display = f"🎬  {title}\n{line2}"
                vitem = QListWidgetItem(display)
                vitem.setData(Qt.ItemDataRole.UserRole, path)
                vitem.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
                vitem.setData(Qt.ItemDataRole.UserRole + 2, "video")
                vitem.setToolTip(f"{title}\n{channel}\n{resolution}  {dur_str}\n{path}")
                if thumb_path and os.path.exists(thumb_path):
                    px = QPixmap(thumb_path).scaled(
                        80, 56,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    vitem.setIcon(QIcon(px))
                self.song_list.addItem(vitem)

        total_count = len(songs) + len(playlist_videos)
        count = len(songs)
        view_labels = {
            "library": "All Songs", "favourites": "Favourites",
            "recently": "Recently Played", "mostplayed": "Most Played",
            "playlist": "Playlist",
        }
        if self.current_view == "playlist" and playlist_videos:
            self.status_label.setText(
                f"{count} song{'s' if count != 1 else ''}  ·  {len(playlist_videos)} video{'s' if len(playlist_videos) != 1 else ''}  ·  Playlist"
            )
        else:
            self.status_label.setText(
                f"{count} song{'s' if count != 1 else ''}  ·  {view_labels.get(self.current_view, '')}"
            )

    def _sort_videos(self, videos: list) -> list:
        """Sort a video list according to self._sort_order."""
        order = getattr(self, "_sort_order", "az")
        if order == "az":
            return sorted(videos, key=lambda v: v[1].lower())   # title
        elif order == "za":
            return sorted(videos, key=lambda v: v[1].lower(), reverse=True)
        elif order == "newest":
            return sorted(videos, key=lambda v: v[0], reverse=True)  # id desc
        elif order == "oldest":
            return sorted(videos, key=lambda v: v[0])
        return videos

    def _load_video_library(self, search=""):
        """Populate the song_list with videos — thumbnails loaded asynchronously."""
        # Stop any running thumbnail worker from a previous load
        if hasattr(self, "_thumb_worker") and self._thumb_worker is not None:
            self._thumb_worker.stop()
            self._thumb_worker.wait()
            self._thumb_worker = None

        videos = self._sort_videos(self.db.get_all_videos(search))
        self.song_list.setIconSize(QSize(80, 56))

        pending_thumbs = []  # (row_index, vid_id, video_path)

        for row, vid in enumerate(videos):
            vid_id, title, channel, path, thumb_path, duration, file_size, fmt, resolution = vid

            dur_str = format_duration(duration)
            size_str = f"{file_size // (1024*1024)} MB" if file_size > 0 else ""
            meta_parts = [p for p in [channel, fmt.upper() if fmt else "", resolution, dur_str, size_str] if p]
            line2 = "  ·  ".join(meta_parts)

            display = f"{title}\n{line2}"
            item = QListWidgetItem(f"🎬  {display}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
            item.setData(Qt.ItemDataRole.UserRole + 2, "video")
            item.setToolTip(f"{title}\n{channel}\n{resolution}  {dur_str}\n{path}")

            # If thumbnail already exists, set it immediately — otherwise queue async generation
            if thumb_path and os.path.exists(thumb_path):
                px = QPixmap(thumb_path).scaled(
                    80, 56,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item.setIcon(QIcon(px))
            elif os.path.exists(path):
                pending_thumbs.append((row, vid_id, path))

            self.song_list.addItem(item)

        count = len(videos)
        self.status_label.setText(f"{count} video{'s' if count != 1 else ''}  ·  Video Library")

        # Kick off background thumbnail generation for videos that don't have one yet
        if pending_thumbs:
            self._thumb_worker = ThumbnailWorker(pending_thumbs)
            self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._thumb_worker.thumbnail_saved.connect(self._on_thumbnail_save_db)
            self._thumb_worker.start()

    def _on_thumbnail_ready(self, row, thumb_path):
        """Called from ThumbnailWorker when a thumbnail image has been generated."""
        item = self.song_list.item(row)
        if not item:
            return
        px = QPixmap(thumb_path).scaled(
            80, 56,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        item.setIcon(QIcon(px))

    def _on_thumbnail_save_db(self, vid_id, thumb_path):
        """Persist the newly generated thumbnail path to the database."""
        try:
            self.db.cursor.execute(
                "UPDATE videos SET thumbnail_path=? WHERE id=?", (thumb_path, vid_id)
            )
            self.db.conn.commit()
        except Exception as e:
            print(f"[Nova] Thumbnail DB update error: {e}")

    def on_search(self, text):
        self.load_library(text)

    # ──────────────────────────── IMPORT ────────────────────────────

    def ask_cover_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, "Cover Image (optional)", "", "Images (*.png *.jpg *.jpeg)")
        return image_path or None

    def process_song_import(self, full_path, batch_cover=None):
        file_name = os.path.basename(full_path)
        title = Path(file_name).stem
        artist = "Unknown Artist"
        album = "Unknown Album"
        duration = 0

        try:
            audio = MutagenFile(full_path, easy=True)
            if audio:
                title = audio.get("title", [title])[0]
                artist = audio.get("artist", [artist])[0]
                album = audio.get("album", [album])[0]
                if hasattr(audio, "info") and hasattr(audio.info, "length"):
                    duration = int(audio.info.length * 1000)
        except Exception as e:
            print(f"Metadata: {e}")

        if self.db.get_song_by_path(full_path):
            return False

        cover_path = None
        if self.db.get_setting("extract_covers", "1") == "1":
            cover_path = extract_cover_from_audio(full_path)
        if not cover_path:
            cover_path = batch_cover

        self.db.add_song(title, artist, album, full_path, cover_path, duration)
        return True

    def import_single_files(self):
        dlg = QFileDialog(self, "Import Audio & Video Files")
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dlg.setNameFilters([
            "All Media (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)",
            "Audio Files (*.mp3 *.ogg *.wav *.flac *.m4a *.aac)",
            "Video Files (*.mp4 *.mkv *.avi *.gif *.webm *.mov)",
        ])
        dlg.selectNameFilter("All Media (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)")
        if not dlg.exec():
            return
        files = dlg.selectedFiles()
        if not files:
            return
        audio_files = [f for f in files if any(f.lower().endswith(ext) for ext in SUPPORTED_FORMATS)]
        video_files = [f for f in files if any(f.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS)]
        cover = self.ask_cover_image() if audio_files else None
        added_audio = sum(1 for f in audio_files if self.process_song_import(f, cover))
        added_video = 0
        for f in video_files:
            title = Path(os.path.basename(f)).stem
            file_size = os.path.getsize(f) if os.path.exists(f) else 0
            fmt = os.path.splitext(f)[1].lstrip(".")
            if not self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (f,)).fetchone():
                self.db.add_video(title, "", f, None, 0, file_size, fmt, "")
                added_video += 1
        self.load_library()
        parts = []
        if added_audio:
            parts.append(f"{added_audio} song(s)")
        if added_video:
            parts.append(f"{added_video} video(s)")
        self.status_label.setText(f"Imported {' and '.join(parts)}." if parts else "No new files imported.")

    def import_music_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return
        count = 0
        for root, dirs, files in os.walk(folder):
            for file in files:
                if any(file.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                    if self.process_song_import(os.path.join(root, file)):
                        count += 1
        QMessageBox.information(self, "Import Complete", f"Imported {count} new song(s)")
        self.load_library()

    def open_ytdlp_importer(self):
        default_dir = self.db.get_setting(
            "ytdlp_dir",
            os.path.join(os.path.expanduser("~"), "Music", "Nova Downloads")
        )
        dlg = YtdlpImportDialog(self, self.db, default_dir)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.set_setting("ytdlp_dir", dlg.download_dir)
            self.load_library()
            self.status_label.setText(
                f"Imported {len(dlg.downloaded_files)} downloaded track(s) into library."
            )

    def open_video_downloader(self):
        default_dir = self.db.get_setting(
            "video_dir",
            os.path.join(os.path.expanduser("~"), "Videos", "Nova Downloads")
        )
        dlg = VideoDownloadDialog(self, self.db, default_dir)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.set_setting("video_dir", dlg.download_dir)
            self.status_label.setText(
                f"Downloaded {len(dlg.downloaded_files)} video(s)."
            )

    def open_converter(self):
        input_path = self.current_song_path if self.current_song_path else None
        dlg = ConvertDialog(self, self.db, input_path)
        dlg.exec()

    # ──────────────────────────── DRAG & DROP ────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        event.acceptProposedAction()
        audio_exts = set(SUPPORTED_FORMATS)
        video_exts = set(SUPPORTED_VIDEO_FORMATS)
        imported_audio = 0
        imported_video = 0
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in audio_exts:
                meta = MutagenFile(path, easy=True)
                title = os.path.splitext(os.path.basename(path))[0]
                artist, album, duration = "", "", 0
                cover_path = None
                if meta:
                    title = (meta.get("title") or [title])[0]
                    artist = (meta.get("artist") or [""])[0]
                    album = (meta.get("album") or [""])[0]
                    duration = int(meta.info.length) if hasattr(meta, "info") else 0
                self.db.add_song(title, artist, album, path, cover_path, duration)
                imported_audio += 1
            elif ext in video_exts:
                title = os.path.splitext(os.path.basename(path))[0]
                self.db.add_video(title, "", path, duration=0)
                imported_video += 1
        if imported_audio or imported_video:
            self.load_library(self.search_box.text())
            self.refresh_sidebar()
            parts = []
            if imported_audio:
                parts.append(f"{imported_audio} song(s)")
            if imported_video:
                parts.append(f"{imported_video} video(s)")
            self.status_label.setText(f"Imported {' and '.join(parts)} via drag & drop.")

    # ──────────────────────────── PLAYBACK ────────────────────────────

    def _get_crossfade_ms(self):
        try:
            return max(0, int(self.db.get_setting("crossfade", "0"))) * 1000
        except (TypeError, ValueError):
            return 0

    def _peek_next_item(self):
        if self.song_list.count() == 0:
            return None
        if self.shuffle_enabled:
            idx = random.randint(0, self.song_list.count() - 1)
        else:
            idx = (self.current_index + 1) % self.song_list.count()
        return self.song_list.item(idx)

    def _cancel_crossfade(self):
        if self._crossfade_timer.isActive():
            self._crossfade_timer.stop()
        was_active = self._crossfade_active
        self._crossfade_active = False
        self._crossfade_phase = None
        self._crossfade_triggered = False
        self._crossfade_pending_item = None
        self._crossfade_elapsed = 0
        self._crossfade_out_ms = 0
        self._crossfade_in_ms = 0
        self._crossfade_last_vol = -1
        if was_active and self.player.get_state() in (
            vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering,
        ):
            self.player.audio_set_volume(self.volume_slider.value())

    def _set_crossfade_volume(self, vol):
        vol = max(0, min(100, int(vol)))
        if vol != self._crossfade_last_vol:
            self.player.audio_set_volume(vol)
            self._crossfade_last_vol = vol

    def _tick_crossfade(self):
        if not self._crossfade_active or not self._crossfade_phase:
            return
        self._crossfade_elapsed = self._crossfade_clock.elapsed()
        target = self._crossfade_target_vol

        if self._crossfade_phase == "out":
            duration = self._crossfade_out_ms
            if duration <= 0:
                self._crossfade_switch_track()
                return
            progress = min(1.0, self._crossfade_elapsed / duration)
            fade = math.cos(progress * math.pi / 2)
            self._set_crossfade_volume(round(target * fade))
            if progress >= 1.0:
                self._crossfade_switch_track()
        elif self._crossfade_phase == "in":
            duration = self._crossfade_in_ms
            if duration <= 0:
                self._finish_crossfade()
                return
            progress = min(1.0, self._crossfade_elapsed / duration)
            fade = math.sin(progress * math.pi / 2)
            self._set_crossfade_volume(round(target * fade))
            if progress >= 1.0:
                self._finish_crossfade()

    def _crossfade_switch_track(self):
        item = self._crossfade_pending_item
        if item is None:
            self._cancel_crossfade()
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            self._cancel_crossfade()
            self.play_selected_song(item)
            return

        self._crossfade_phase = "in"
        self._crossfade_elapsed = 0
        self._crossfade_last_vol = -1
        self._crossfade_clock.restart()

        media = self.instance.media_new(path)
        self.player.set_media(media)
        self.player.audio_set_volume(0)
        self.player.play()

        for i in range(self.song_list.count()):
            if self.song_list.item(i) == item:
                self.current_index = i
                break

    def _finish_crossfade(self):
        self._crossfade_timer.stop()
        self._crossfade_active = False
        self._crossfade_phase = None
        self._crossfade_triggered = False
        item = self._crossfade_pending_item
        self._crossfade_pending_item = None
        self._crossfade_elapsed = 0
        self._crossfade_out_ms = 0
        self._crossfade_in_ms = 0
        self._crossfade_last_vol = -1
        vol = self.volume_slider.value()
        self.player.audio_set_volume(vol)
        self._end_handled = True
        if item is not None:
            QTimer.singleShot(0, lambda it=item: self._update_audio_now_playing(it))

    def _update_crossfade_labels(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        song = self.db.get_song_by_path(path)
        if not song:
            return
        _, title, artist, album, *_ = song
        label = f"{artist}  ·  {album}" if album else artist
        self.song_title_label.setText(title)
        self.song_artist_label.setText(label)
        self.bb_song_title.setText(title)
        self.bb_song_artist.setText(label)

    def _start_crossfade_to_item(self, item, duration_ms=None):
        path = item.data(Qt.ItemDataRole.UserRole)
        item_type = item.data(Qt.ItemDataRole.UserRole + 2)
        if not path or not os.path.exists(path) or item_type == "video":
            self.play_selected_song(item)
            return

        crossfade_ms = self._get_crossfade_ms()
        if crossfade_ms <= 0 or self.is_video_mode:
            self.play_selected_song(item)
            return

        self._cancel_crossfade()
        self._crossfade_pending_item = item
        total_ms = duration_ms if duration_ms is not None else crossfade_ms
        if total_ms <= 0:
            self.play_selected_song(item)
            return
        self._crossfade_out_ms = max(300, total_ms // 2)
        self._crossfade_in_ms = max(300, total_ms - self._crossfade_out_ms)
        self._crossfade_elapsed = 0
        self._crossfade_target_vol = self.volume_slider.value()
        self._crossfade_active = True
        self._crossfade_phase = "out"
        self._crossfade_triggered = True
        self._end_handled = True
        self._crossfade_last_vol = -1
        self._crossfade_clock.start()
        self._update_crossfade_labels(item)
        self._crossfade_timer.start(50)

    def _update_audio_now_playing(self, item, *, increment_plays=True):
        path = item.data(Qt.ItemDataRole.UserRole)
        item_id = item.data(Qt.ItemDataRole.UserRole + 1)

        self.is_video_mode = False
        self.cover_stack.setCurrentIndex(0)
        self.popout_btn.setVisible(False)
        self.current_song_path = path
        self.current_song_id = item_id

        song = self.db.get_song_by_path(path)
        if song:
            _, title, artist, album, _, cover_path, duration, fav, rating, plays = song
            self.song_title_label.setText(title)
            self.song_artist_label.setText(f"{artist}  ·  {album}")
            self._update_fav_btn(bool(fav))
            self._update_stars(rating)

            if cover_path and os.path.exists(cover_path):
                self.current_cover_path = cover_path
                px = QPixmap(cover_path).scaled(
                    240, 240,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cover_label.setPixmap(px)
                px_small = QPixmap(cover_path).scaled(
                    52, 52,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.bb_cover.setPixmap(px_small)
            else:
                self.current_cover_path = None
                self.cover_label.clear()
                self.cover_label.setText("♫")
                self.cover_label.setFont(QFont("Arial", 48))
                self.bb_cover.clear()
                self.bb_cover.setText("♫")
                self.bb_cover.setFont(QFont("Arial", 20))

            self.bb_song_title.setText(title)
            self.bb_song_artist.setText(f"{artist}  ·  {album}")
            self._update_bb_fav(bool(fav))
            if increment_plays:
                self.db.increment_play_count(item_id)
            self._load_lyrics(artist, title, song_id=item_id)
            self._discord.set_playing(
                title=title,
                artist=artist,
                album=album,
                duration_ms=int(duration) if duration else 0,
                elapsed_ms=0,
                is_video=False,
            )

        for i in range(self.song_list.count()):
            if self.song_list.item(i) == item:
                self.current_index = i
                break

    def play_song(self, path, song_id):
        """Play a song directly by file path and database ID.
        Builds a temporary QListWidgetItem so play_selected_song can be reused."""
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole + 1, song_id)
        item.setData(Qt.ItemDataRole.UserRole + 2, None)  # audio, not video
        self.play_selected_song(item)

    def play_selected_song(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        item_id = item.data(Qt.ItemDataRole.UserRole + 1)
        item_type = item.data(Qt.ItemDataRole.UserRole + 2)  # "video" or None

        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Missing File", f"File not found:\n{path}")
            return

        # ── VIDEO ──
        if item_type == "video":
            self._cancel_crossfade()
            self.is_video_mode = True
            # Only switch cover_stack when NOT in fullscreen (video_frame may be reparented)
            if not (hasattr(self, "_fs_win") and self._fs_win):
                self.cover_stack.setCurrentIndex(1)

            self.player.stop()
            media = self.instance.media_new(path)
            self.player.set_media(media)

            # Attach VLC output to our embedded frame (works for both normal & fullscreen)
            wid = int(self.video_frame.winId())
            if sys.platform == "win32":
                self.player.set_hwnd(wid)
            elif sys.platform == "darwin":
                self.player.set_nsobject(wid)
            else:
                self.player.set_xwindow(wid)

            self.player.play()

            # Show meta in right panel
            vid = self.db.get_video_by_path(path)
            title = vid[1] if vid else Path(path).stem
            channel = vid[2] if vid else ""
            self.song_title_label.setText(title)
            self.song_artist_label.setText(channel)
            self.bb_song_title.setText(title)
            self.bb_song_artist.setText(channel)
            self.bb_cover.clear()
            self.bb_cover.setText("🎬")
            self.bb_cover.setFont(QFont("Arial", 20))

            # ── Discord Rich Presence ────────────────────────────────────
            self._discord.set_playing(
                title=title,
                artist=channel,
                album="",
                duration_ms=0,
                elapsed_ms=0,
                is_video=True,
            )

            # Show pop-out button for videos
            self.popout_btn.setVisible(False)

            # ── Lyrics for video ─────────────────────────────────────────
            self._load_lyrics(channel, title, video_id=item_id)

            for i in range(self.song_list.count()):
                if self.song_list.item(i) == item:
                    self.current_index = i
                    break
            self.current_song_path = path
            self.current_song_id = item_id
            return

        # ── AUDIO ──
        self._cancel_crossfade()
        self._crossfade_triggered = False
        self.player.stop()
        media = self.instance.media_new(path)
        self.player.set_media(media)
        self.player.play()
        self._update_audio_now_playing(item)

    def preview_song_info(self, item):
        pass

    def toggle_play_pause(self):
        state = self.player.get_state()
        if state in (vlc.State.Playing,):
            self.pause_song()
            # ── Discord: Pause-Status setzen ──
            title = self.song_title_label.text()
            artist = self.song_artist_label.text().split("  ·  ")[0]
            self._discord.set_paused(title, artist)
        else:
            self.resume_song()
            # ── Discord: Wiedergabe-Status wiederherstellen ──
            if self.current_song_path:
                song = self.db.get_song_by_path(self.current_song_path)
                if song and not self.is_video_mode:
                    _, title, artist, album, _, _, duration, *_ = song
                    elapsed = self.player.get_time()
                    self._discord.set_playing(
                        title=title, artist=artist, album=album,
                        duration_ms=int(duration) if duration else 0,
                        elapsed_ms=elapsed,
                        is_video=False,
                    )
                elif self.is_video_mode:
                    vid = self.db.get_video_by_path(self.current_song_path)
                    title = vid[1] if vid else Path(self.current_song_path).stem
                    channel = vid[2] if vid else ""
                    self._discord.set_playing(
                        title=title, artist=channel, album="",
                        duration_ms=0, elapsed_ms=0, is_video=True,
                    )

    def resume_song(self):
        self.player.play()

    def pause_song(self):
        self.player.pause()

    def stop_song(self):
        self._cancel_crossfade()
        self.player.stop()
        self.progress_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        self._discord.clear()

    def change_volume(self, value):
        if self._crossfade_active:
            self._crossfade_target_vol = value
            if self._crossfade_phase == "out":
                duration = self._crossfade_out_ms
                progress = min(1.0, self._crossfade_elapsed / duration) if duration > 0 else 1.0
                fade = math.cos(progress * math.pi / 2)
                self._set_crossfade_volume(round(value * fade))
            elif self._crossfade_phase == "in":
                duration = self._crossfade_in_ms
                progress = min(1.0, self._crossfade_elapsed / duration) if duration > 0 else 1.0
                fade = math.sin(progress * math.pi / 2)
                self._set_crossfade_volume(round(value * fade))
        else:
            self.player.audio_set_volume(value)
        self.vol_label.setText(f"{value}%")
        # Keep both sliders in sync without causing infinite recursion
        if self.sender() is self.volume_slider and self.bb_volume.value() != value:
            self.bb_volume.blockSignals(True)
            self.bb_volume.setValue(value)
            self.bb_volume.blockSignals(False)
        elif self.sender() is self.bb_volume and self.volume_slider.value() != value:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(value)
            self.volume_slider.blockSignals(False)
        # Sync video overlay volume slider
        if self._vid_controls is not None and self._vid_controls.vol_slider is not self.sender():
            self._vid_controls.sync_volume(value)

    def slider_pressed(self):
        self.is_slider_pressed = True
        self._slider_source = self.sender()

    def slider_released(self):
        self.is_slider_pressed = False
        # Use whichever slider triggered the release
        src = getattr(self, "_slider_source", None)
        if src == self.bb_progress:
            self.player.set_time(self.bb_progress.value())
            self.progress_slider.setValue(self.bb_progress.value())
        else:
            self.player.set_time(self.progress_slider.value())
            self.bb_progress.setValue(self.progress_slider.value())

    def play_next(self):
        if self.song_list.count() == 0:
            return
        if self.shuffle_enabled:
            self.current_index = random.randint(0, self.song_list.count() - 1)
        else:
            self.current_index = (self.current_index + 1) % self.song_list.count()
        item = self.song_list.item(self.current_index)
        if self._get_crossfade_ms() > 0 and not self.is_video_mode:
            self._start_crossfade_to_item(item)
        else:
            self.play_selected_song(item)

    def play_previous(self):
        if self.song_list.count() == 0:
            return
        if self.player.get_time() > 3000:
            self.player.set_time(0)
            return
        self.current_index = (self.current_index - 1 + self.song_list.count()) % self.song_list.count()
        item = self.song_list.item(self.current_index)
        self.play_selected_song(item)

    def toggle_loop(self):
        self.loop_enabled = not self.loop_enabled
        t = self.theme
        if self.loop_enabled:
            style_on = (
                f"QPushButton {{ background-color: {t['green']}; border-radius: 19px; color: white; border: none; }}"
            )
            self.loop_btn.setStyleSheet(style_on)
            self.bb_loop_btn.setStyleSheet(
                f"QPushButton {{ background: {t['green']}22; border: 1px solid {t['green']}88; "
                f"color: {t['green']}; border-radius: 15px; font-size: 13px; }}"
            )
        else:
            self.loop_btn.setStyleSheet("")
            self.bb_loop_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {t['subtext']}; "
                f"font-size: 13px; border-radius: 15px; }}"
                f"QPushButton:hover {{ background: {t['highlight']}; color: {t['text']}; }}"
            )
        if self._vid_controls is not None:
            self._vid_controls.sync_loop(self.loop_enabled, t["accent"], t["subtext"], t["highlight"])

    def toggle_shuffle(self):
        self.shuffle_enabled = not self.shuffle_enabled
        t = self.theme
        if self.shuffle_enabled:
            style_on = (
                f"QPushButton {{ background-color: {t['green']}; border-radius: 19px; color: white; border: none; }}"
            )
            self.shuffle_btn.setStyleSheet(style_on)
            self.bb_shuffle_btn.setStyleSheet(
                f"QPushButton {{ background: {t['green']}22; border: 1px solid {t['green']}88; "
                f"color: {t['green']}; border-radius: 15px; font-size: 13px; }}"
            )
        else:
            self.shuffle_btn.setStyleSheet("")
            self.bb_shuffle_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {t['subtext']}; "
                f"font-size: 13px; border-radius: 15px; }}"
                f"QPushButton:hover {{ background: {t['highlight']}; color: {t['text']}; }}"
            )
        if self._vid_controls is not None:
            self._vid_controls.sync_shuffle(self.shuffle_enabled, t["accent"], t["subtext"], t["highlight"])

    def update_progress(self):
        try:
            if self._crossfade_active:
                state = self.player.get_state()
                if self._vid_controls is not None:
                    self._vid_controls.sync_play_state(state == vlc.State.Playing)
                if self._crossfade_phase == "out" and state == vlc.State.Ended:
                    self._crossfade_switch_track()
                if self.sleep_timer:
                    if self.player.is_playing():
                        self.sleep_elapsed += 0.4
                    remaining = self.sleep_minutes * 60 - self.sleep_elapsed
                    if remaining <= 0:
                        self._cancel_crossfade()
                        self.player.stop()
                        self.sleep_timer = None
                        self.sleep_label.setText("")
                        QMessageBox.information(self, "Sleep Timer", "Sleep timer elapsed. Playback stopped.")
                    else:
                        mins = int(remaining // 60)
                        secs = int(remaining % 60)
                        self.sleep_label.setText(f"☾ {mins}:{secs:02d}")
                return

            length = self.player.get_length()
            current = self.player.get_time()
            if length > 0 and not self.is_slider_pressed:
                self.progress_slider.setMaximum(length)
                self.progress_slider.setValue(current)
                self.time_label.setText(f"{format_duration(current)} / {format_duration(length)}")
                # Sync bottom bar
                self.bb_progress.setMaximum(length)
                self.bb_progress.setValue(current)
                self.bb_time_cur.setText(format_duration(current))
                self.bb_time_tot.setText(format_duration(length))
                # Sync video overlay
                if self._vid_controls is not None:
                    self._vid_controls.sync_progress(current, length)

                # ── Lyrics sync ─────────────────────────────────────────
                if (self._lyrics_lines
                        and self._lyrics_timestamps
                        and not self.is_video_mode
                        and not self._crossfade_active
                        and self._lyrics_box.isVisible()):
                    # Find the last line whose timestamp <= current position
                    new_line = -1
                    for idx, ts in enumerate(self._lyrics_timestamps):
                        if current >= ts:
                            new_line = idx
                        else:
                            break
                    if new_line != self._lyrics_current_line:
                        self._lyrics_current_line = new_line
                        self._render_lyrics(new_line)

                if (not self._crossfade_active
                        and not self._crossfade_triggered
                        and not self.is_video_mode
                        and not self.loop_enabled
                        and self.db.get_setting("auto_next", "1") == "1"):
                    crossfade_ms = self._get_crossfade_ms()
                    out_length = self.player.get_length()
                    out_current = self.player.get_time()
                    if crossfade_ms > 0 and out_length > 0:
                        effective_ms = min(crossfade_ms, max(500, out_length // 2))
                        remaining = out_length - out_current
                        if 0 < remaining <= effective_ms:
                            next_item = self._peek_next_item()
                            if (next_item
                                    and next_item.data(Qt.ItemDataRole.UserRole + 2) != "video"):
                                self._start_crossfade_to_item(next_item, duration_ms=effective_ms)

            state = self.player.get_state()
            # Sync play-button icon in overlay
            if self._vid_controls is not None:
                self._vid_controls.sync_play_state(state == vlc.State.Playing)
            if state == vlc.State.Ended:
                if not self._end_handled and not self._crossfade_active and not self._crossfade_triggered:
                    self._end_handled = True
                    # If the video was playing inside a pop-out window, close it
                    # first so VLC's handle is released before we reload media.
                    # Skipping this step causes a crash because VLC tries to
                    # render into the (already-destroyed) pop-out frame.
                    if (getattr(self, "_popout_win", None) is not None
                            and not (hasattr(self, "yt_browser")
                                     and self.yt_browser.parent() == self._popout_win)):
                        self._close_popout_window()
                    if self.loop_enabled:
                        media = self.instance.media_new(self.current_song_path)
                        self.player.set_media(media)
                        self.player.play()
                    else:
                        if self.db.get_setting("auto_next", "1") == "1":
                            self.play_next()
            elif state in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering):
                self._end_handled = False

            if self.sleep_timer:
                if self.player.is_playing():
                    self.sleep_elapsed += 0.4
                remaining = self.sleep_minutes * 60 - self.sleep_elapsed
                if remaining <= 0:
                    self.player.stop()
                    self.sleep_timer = None
                    self.sleep_label.setText("")
                    QMessageBox.information(self, "Sleep Timer", "Sleep timer elapsed. Playback stopped.")
                else:
                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    self.sleep_label.setText(f"☾ {mins}:{secs:02d}")

        except Exception as e:
            print(f"Progress error: {e}")

    def _update_discord_progress(self):
        """Aktualisiert Discord Rich Presence jede Sekunde mit aktueller Position."""
        if not self._discord._enabled or not self.current_song_path:
            return
        state = self.player.get_state()
        # Nicht updaten wenn der Player nicht wirklich läuft
        if state not in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering):
            return
        if not self.player.is_playing():
            return

        current_ms = self.player.get_time()
        length_ms = self.player.get_length()

        if self.is_video_mode:
            vid = self.db.get_video_by_path(self.current_song_path)
            title = vid[1] if vid else Path(self.current_song_path).stem
            channel = vid[2] if vid else ""
            pos_str = format_duration(current_ms) if current_ms >= 0 else "0:00"
            dur_str = format_duration(length_ms) if length_ms > 0 else "?"
            self._discord.set_playing(
                title=title,
                artist=channel,
                album=f"{pos_str} / {dur_str}",
                duration_ms=0,
                elapsed_ms=current_ms if current_ms >= 0 else 0,
                is_video=True,
            )
        else:
            song = self.db.get_song_by_path(self.current_song_path)
            if not song:
                return
            _, title, artist, album, _, _, duration, *_ = song
            pos_str = format_duration(current_ms) if current_ms >= 0 else "0:00"
            dur_str = format_duration(length_ms) if length_ms > 0 else format_duration(int(duration)) if duration else "?"
            self._discord.set_playing(
                title=title,
                artist=f"{artist}  ·  {album}" if album else artist,
                album=f"{pos_str} / {dur_str}",
                duration_ms=0,
                elapsed_ms=current_ms if current_ms >= 0 else 0,
                is_video=False,
            )

    # ──────────────────────────── FAVOURITES ────────────────────────────

    def toggle_favourite_current(self):
        if not self.current_song_id:
            return
        new_fav = self.db.toggle_favourite(self.current_song_id)
        self._update_fav_btn(bool(new_fav))
        self.load_library(self.search_box.text())

    def _update_fav_btn(self, is_fav):
        t = self.theme
        if is_fav:
            self.fav_btn.setText("♥")
            self.fav_btn.setStyleSheet(
                f"QPushButton {{ background: {t['red']}22; border: 1px solid {t['red']}88; "
                f"border-radius: 20px; font-size: 17px; color: {t['red']}; }}"
            )
        else:
            self.fav_btn.setText("♡")
            self.fav_btn.setStyleSheet(
                f"QPushButton {{ background: {t['card']}; border: 1px solid {t['border']}; "
                f"border-radius: 20px; font-size: 17px; color: {t['subtext']}; }}"
            )

    def set_rating(self, rating):
        if not self.current_song_id:
            return
        self.db.set_rating(self.current_song_id, rating)
        self._update_stars(rating)

    def _update_stars(self, rating):
        t = self.theme
        for i, btn in enumerate(self.star_btns):
            if i < rating:
                btn.setText("★")
                btn.setStyleSheet(
                    "QPushButton { background: transparent; font-size: 15px; color: #f0b429; border: none; }"
                )
            else:
                btn.setText("☆")
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; font-size: 15px; color: {t['subtext']}; border: none; }}"
                )

    def _update_bb_fav(self, is_fav):
        t = self.theme
        if is_fav:
            self.bb_fav_btn.setText("♥")
            self.bb_fav_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {t['red']}; font-size: 15px; border-radius: 15px; }}"
            )
        else:
            self.bb_fav_btn.setText("♡")
            self.bb_fav_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {t['subtext']}; font-size: 15px; border-radius: 15px; }}"
                f"QPushButton:hover {{ color: {t['red']}; }}"
            )

    def _toggle_window_fullscreen(self):
        """F11: Hauptfenster in Vollbild umschalten und zurück."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _open_cover_fullscreen(self):
        """Show cover art fullscreen inside the main window as an overlay — full resolution."""
        if not self.current_cover_path or not os.path.exists(self.current_cover_path):
            # fallback: use whatever is in the label
            if not self.cover_label.pixmap() or self.cover_label.pixmap().isNull():
                return
        if hasattr(self, "_fs_overlay") and self._fs_overlay is not None:
            return

        overlay = QFrame(self)
        overlay.setStyleSheet("background: #000000;")
        overlay.setGeometry(self.rect())
        overlay.raise_()

        ol_layout = QVBoxLayout(overlay)
        ol_layout.setContentsMargins(0, 0, 0, 0)
        ol_layout.setSpacing(0)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("background: #000000;")

        # Load at full resolution from file, then scale to overlay size
        if self.current_cover_path and os.path.exists(self.current_cover_path):
            src_px = QPixmap(self.current_cover_path)
        else:
            src_px = self.cover_label.pixmap()

        hint = QLabel("ESC oder Doppelklick zum Schließen")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 11px; background: transparent; padding: 6px;")
        ol_layout.addWidget(img_lbl, 1)
        ol_layout.addWidget(hint)
        overlay.show()
        self._fs_overlay = overlay

        # Fix: Pixmap erst nach dem ersten Layout-Pass skalieren (overlay.width/height
        # sind direkt nach show() noch 0 wenn das Widget gerade erstellt wurde)
        def _scale_cover():
            w, h = overlay.width(), overlay.height() - 28
            if w > 0 and h > 0:
                img_lbl.setPixmap(src_px.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                QTimer.singleShot(50, _scale_cover)
        QTimer.singleShot(0, _scale_cover)

        def close_overlay(e=None):
            overlay.hide()
            overlay.deleteLater()
            self._fs_overlay = None

        overlay.mouseDoubleClickEvent = lambda e: close_overlay()
        overlay.keyPressEvent = lambda e: close_overlay() if e.key() == Qt.Key.Key_Escape else None
        overlay.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        overlay.setFocus()

    # ──────────────────────── VIDEO CONTROLS OVERLAY ────────────────────────

    def _attach_video_controls(self, frame: QFrame):
        """
        VideoControlsOverlay auf frame erzeugen.

        Auf Windows mit QT_OPENGL=software übernimmt VLC den nativen HWND
        von frame vollständig — Children werden nicht compositet und bleiben
        unsichtbar, ein überlappender Sibling-Widget macht das Video schwarz.

        Lösung: Das Overlay ist ein rahmenloses Tool-Fenster (Top-Level),
        das sich über frame legt und mit dem Parent-Fenster mitbewegt.
        """
        frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)

        # Doppelklick-Handler merken
        frame._dbl_click_handler = getattr(frame, "mouseDoubleClickEvent", None)

        # Overlay als rahmenloses Top-Level-Tool-Fenster
        vc = VideoControlsOverlay(None, self)
        vc.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        vc.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._vid_controls = vc
        self._vid_controls_frame = frame

        vc.sync_volume(self.volume_slider.value())
        vc.sync_play_state(self.player.is_playing())
        t = self.theme
        vc.sync_loop(self.loop_enabled, t["accent"], t["subtext"], t["highlight"])
        vc.sync_shuffle(self.shuffle_enabled, t["accent"], t["subtext"], t["highlight"])

        def _do_position_and_show():
            if self._vid_controls is None:
                return
            w = frame.width()
            h = frame.height()
            if w > 0 and h > 0:
                # Globale Bildschirmposition von frame ermitteln
                gp = frame.mapToGlobal(QPoint(0, 0))
                vc.setGeometry(gp.x(), gp.y(), w, h)
                vc._bar.setGeometry(
                    0, h - VideoControlsOverlay.CONTROLS_H,
                    w, VideoControlsOverlay.CONTROLS_H
                )
                vc.show()
                vc.raise_()
                vc.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                vc.setFocus()
                vc.show_and_reset(first_time=True)
            else:
                QTimer.singleShot(100, _do_position_and_show)

        _do_position_and_show()

    def _detach_video_controls(self):
        """Overlay entfernen."""
        if self._vid_controls is not None:
            self._vid_controls._poll_timer.stop()
            self._vid_controls.hide()
            self._vid_controls.setParent(None)
            self._vid_controls.deleteLater()
            self._vid_controls = None
        self._vid_controls_frame = None

    def eventFilter(self, obj, event):
        """Fallback: MouseMove/Press vom VLC-Frame ans Overlay weiterleiten."""
        from PyQt6.QtCore import QEvent
        if self._vid_controls is not None and obj is self._vid_controls.parent():
            if event.type() == QEvent.Type.MouseMove:
                self._vid_controls.show_and_reset()
            elif event.type() == QEvent.Type.MouseButtonPress:
                self._vid_controls.toggle()
        return super().eventFilter(obj, event)

    def _open_video_fullscreen(self):
        """
        Video-Vollbild: video_frame aus dem cover_stack nehmen,
        als direktes Child von self reparenten, und auf volle
        Fenstergröße setzen. VLC rendert weiter — kein neuer HWND.
        """
        if not self.current_song_path or not self.is_video_mode:
            return
        if hasattr(self, "_fs_win") and self._fs_win is not None:
            return

        # Größe des gesamten Fensterinhalts (ohne Titelleiste)
        w, h = self.width(), self.height()

        # Aus dem QStackedWidget herausnehmen und direkt ins Hauptfenster
        self.video_frame.setParent(self)
        # Fixed-Size entfernen damit setGeometry uneingeschränkt wirkt
        self.video_frame.setMinimumSize(0, 0)
        self.video_frame.setMaximumSize(16777215, 16777215)
        self.video_frame.setGeometry(0, 0, w, h)
        self.video_frame.raise_()
        self.video_frame.show()
        self._fs_win = True

        # Hint-Label
        if not hasattr(self, "_fs_hint") or self._fs_hint is None:
            self._fs_hint = QLabel("ESC oder Doppelklick zum Schließen", self.video_frame)
            self._fs_hint.setStyleSheet(
                "color: rgba(255,255,255,0.45); font-size: 11px;"
                " background: transparent; padding: 6px;"
            )
        self._fs_hint.adjustSize()
        self._fs_hint.move(
            (w - self._fs_hint.width()) // 2,
            h - self._fs_hint.height() - 10
        )
        self._fs_hint.show()
        self._fs_hint.raise_()

        self.video_frame.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video_frame.setFocus()

        def _vf_key(e):
            k = e.key()
            if k == Qt.Key.Key_Escape:
                self._close_video_fullscreen()
            elif k == Qt.Key.Key_Space:
                if not self._focused_widget_is_text_input():
                    self.toggle_play_pause()
            elif k == Qt.Key.Key_Left:
                self._seek_relative(-5000)
            elif k == Qt.Key.Key_Right:
                self._seek_relative(5000)

        self.video_frame.keyPressEvent = _vf_key
        self.video_frame.mouseDoubleClickEvent = lambda e: self._close_video_fullscreen()

        # ── Video-Controls-Overlay einblenden ─────────────────────────────
        # Fix: Retry-Loop statt einmaligem processEvents — video_frame hat erst
        # nach dem ersten Render-Pass eine echte width/height > 0.
        def _attach_fs_controls():
            if not hasattr(self, "_fs_win") or self._fs_win is None:
                return
            QApplication.processEvents()
            w = self.video_frame.width()
            h = self.video_frame.height()
            if w > 0 and h > 0:
                self._attach_video_controls(self.video_frame)
            else:
                QTimer.singleShot(100, _attach_fs_controls)
        QTimer.singleShot(0, _attach_fs_controls)

    def _close_video_fullscreen(self):
        """video_frame zurück in den cover_stack einsetzen."""
        if not hasattr(self, "_fs_win") or self._fs_win is None:
            return
        self._fs_win = None
        if hasattr(self, "_fs_hint") and self._fs_hint:
            self._fs_hint.hide()

        # ── Overlay entfernen ─────────────────────────────────────────────
        self._detach_video_controls()

        # Zurück in den cover_stack (Index 1)
        self.video_frame.setParent(self.cover_stack)
        # Fix: Widget sauber entfernen falls es schon im Stack ist, dann neu einsetzen
        idx = self.cover_stack.indexOf(self.video_frame)
        if idx != -1:
            self.cover_stack.removeWidget(self.video_frame)
        self.cover_stack.insertWidget(1, self.video_frame)
        self.cover_stack.setCurrentIndex(1)
        # Fix: Kein hardcodiertes setFixedSize(248,248) — stattdessen flexible
        # Size-Policy damit das Frame den Stack korrekt ausfüllt
        self.video_frame.setMinimumSize(0, 0)
        self.video_frame.setMaximumSize(16777215, 16777215)
        self.video_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.video_frame.show()
        self.video_frame.mouseDoubleClickEvent = lambda e: self._open_video_fullscreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_fs_overlay") and self._fs_overlay is not None:
            self._fs_overlay.setGeometry(self.rect())
        if hasattr(self, "_fs_win") and self._fs_win is not None:
            w, h = self.width(), self.height()
            self.video_frame.setGeometry(0, 0, w, h)
            if hasattr(self, "_fs_hint") and self._fs_hint:
                self._fs_hint.move(
                    (w - self._fs_hint.width()) // 2,
                    h - self._fs_hint.height() - 10
                )
            if self._vid_controls is not None:
                self._vid_controls.reposition(w, h)
        # ── Responsive top bar ───────────────────────────────────────────────
        if hasattr(self, "_top_bar_btns"):
            w = self.width()
            # Thresholds (window width):
            #   > 1100 px  → full labels
            #   > 860 px   → short labels
            #   ≤ 860 px   → icon only
            if w > 1100:
                mode = "full"
            elif w > 860:
                mode = "short"
            else:
                mode = "icon"
            label_idx = {"full": 1, "short": 2, "icon": 3}[mode]
            for btn, full, short, icon in self._top_bar_btns:
                btn.setText([full, full, short, icon][label_idx])
            # Shrink search box on very narrow windows
            if w <= 860:
                self.search_box.setMaximumWidth(140)
            elif w <= 1100:
                self.search_box.setMaximumWidth(200)
            else:
                self.search_box.setMaximumWidth(260)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._vid_controls is not None and self._vid_controls_frame is not None:
            gp = self._vid_controls_frame.mapToGlobal(QPoint(0, 0))
            self._vid_controls.move(gp)

    def changeEvent(self, event):
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent
        if event.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            # Tool-Window gehört zu Nova — wenn es Fokus hat, gilt das als aktiv
            vc = self._vid_controls
            if vc is not None:
                tool_has_focus = vc.isActiveWindow()
                if (not self.isActiveWindow() and not tool_has_focus) or self.isMinimized():
                    vc.hide()
                    vc._hide_bar()

    def _open_fullscreen_current(self):
        """Toggle fullscreen: video if in video mode, cover otherwise."""
        if self.is_video_mode:
            if self._fs_win is None:
                self._open_video_fullscreen()
            else:
                self._close_video_fullscreen()
        else:
            if self._fs_overlay is None:
                self._open_cover_fullscreen()

    # ──────────────────────────── POP-OUT WINDOW ────────────────────────────

    def _toggle_popout_window(self):
        """Open video/browser in a separate, resizable, closable pop-out window."""
        if hasattr(self, "_popout_win") and self._popout_win is not None:
            self._close_popout_window()
            return

        is_browser = (self.current_view == "ytbrowser")
        if not is_browser and (not self.current_song_path or not self.is_video_mode):
            return

        self._popout_win = QWidget(None, Qt.WindowType.Window)
        self._popout_win.setWindowTitle("Nova – Pop-out")
        self._popout_win.resize(900, 560)
        self._popout_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._popout_win.setStyleSheet("background: #000;")

        lay = QVBoxLayout(self._popout_win)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header bar with close button
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet("background: #181818; border-bottom: 1px solid #333;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(12, 0, 12, 0)
        hdr_lay.setSpacing(8)
        icon = "🌐" if is_browser else "🎬"
        title_lbl = QLabel(f"{icon}  Pop-out")
        title_lbl.setStyleSheet("color: #aaa; font-size: 12px; background: transparent;")
        close_btn = QPushButton("✕  Schließen")
        close_btn.setFixedHeight(26)
        close_btn.setFixedWidth(110)
        close_btn.setStyleSheet(
            "QPushButton { background: #333; color: #ccc; border: none;"
            " border-radius: 5px; padding: 0 12px; font-size: 12px; }"
            "QPushButton:hover { background: #f85149; color: #fff; }"
        )
        close_btn.clicked.connect(self._close_popout_window)
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        hdr_lay.addWidget(close_btn)
        lay.addWidget(hdr)

        if is_browser:
            # Reparent the browser widget into the pop-out window
            self.yt_browser.setParent(self._popout_win)
            lay.addWidget(self.yt_browser, 1)
            self._popout_win.show()
            self.yt_browser.show()
        else:
            # VLC fix: stop → set new handle → reload media → play
            # Trying to redirect the handle while VLC is playing always gives black screen.
            self._popout_saved_time = self.player.get_time()   # remember position
            self._popout_saved_path = self.current_song_path

            self._popout_video_frame = QFrame()
            self._popout_video_frame.setStyleSheet("background: #000;")
            # Fix: WA_NativeWindow setzen damit winId() sofort einen echten HWND
            # liefert und reposition() eine gültige Größe bekommt
            self._popout_video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            lay.addWidget(self._popout_video_frame, 1)

            # Show window FIRST so the OS assigns a real native handle
            self._popout_win.show()
            self._popout_win.raise_()
            QApplication.processEvents()

            def _start_in_popout():
                if self._popout_video_frame is None or self._popout_win is None:
                    return
                # Stop current playback completely
                self.player.stop()
                # Point VLC at the new frame
                wid = int(self._popout_video_frame.winId())
                if sys.platform == "win32":
                    self.player.set_hwnd(wid)
                elif sys.platform == "darwin":
                    self.player.set_nsobject(wid)
                else:
                    self.player.set_xwindow(wid)
                # Reload media and seek to saved position
                media = self.instance.media_new(self._popout_saved_path)
                self.player.set_media(media)
                self.player.play()
                if self._popout_saved_time and self._popout_saved_time > 0:
                    # Seek after a brief delay — VLC needs to buffer first
                    QTimer.singleShot(400, lambda: self.player.set_time(self._popout_saved_time))
                # ── Overlay nach dem VLC-Start attachieren ─────────────────────
                # Retry-Loop: erst wenn Frame wirklich eine Größe hat (VLC muss
                # seinen HWND erst schreiben, Layout-Pass muss durch sein).
                def _attach_later():
                    if self._popout_video_frame is None or self._popout_win is None:
                        return
                    QApplication.processEvents()
                    w = self._popout_video_frame.width()
                    h = self._popout_video_frame.height()
                    if w > 0 and h > 0:
                        self._attach_video_controls(self._popout_video_frame)
                    else:
                        QTimer.singleShot(100, _attach_later)
                QTimer.singleShot(600, _attach_later)
                # Pop-out ResizeEvent weiterleiten → Overlay + Catcher repositionieren
                def _popout_resize(e):
                    if self._vid_controls and self._popout_video_frame:
                        self._vid_controls.reposition(
                            self._popout_video_frame.width(),
                            self._popout_video_frame.height(),
                        )
                self._popout_video_frame.resizeEvent = _popout_resize

            QTimer.singleShot(80, _start_in_popout)

        self.popout_btn.setText("✕  Pop-out schließen")
        self._popout_win.closeEvent = lambda e: self._close_popout_window() or e.accept()

    def _close_popout_window(self):
        """Close the pop-out window and restore VLC to the embedded frame."""
        if not hasattr(self, "_popout_win") or self._popout_win is None:
            return

        # If browser was reparented into pop-out, move it back
        if hasattr(self, "yt_browser") and self.yt_browser.parent() == self._popout_win:
            self.center_stack.insertWidget(1, self.yt_browser)
            if self.current_view == "ytbrowser":
                self.center_stack.setCurrentIndex(1)
            self.yt_browser.show()
            win = self._popout_win
            self._popout_win = None          # null first, then destroy
            win.hide()
            win.deleteLater()
            self.popout_btn.setText("⧉  Pop-out")
            return

        # Video mode: stop → move handle back → reload → play
        # Fix: saved_time VOR stop() holen — danach gibt VLC -1 zurück
        saved_time = self.player.get_time()
        saved_path = getattr(self, "_popout_saved_path", self.current_song_path)

        # ── Overlay sauber entfernen bevor der Frame zerstört wird ────────
        self._detach_video_controls()

        self.player.stop()
        self._popout_video_frame = None
        win = self._popout_win
        self._popout_win = None              # null first, then destroy
        win.hide()
        win.deleteLater()

        def _reattach():
            if not self.is_video_mode or not saved_path:
                return
            wid = int(self.video_frame.winId())
            if sys.platform == "win32":
                self.player.set_hwnd(wid)
            elif sys.platform == "darwin":
                self.player.set_nsobject(wid)
            else:
                self.player.set_xwindow(wid)
            media = self.instance.media_new(saved_path)
            self.player.set_media(media)
            self.player.play()
            if saved_time and saved_time > 0:
                QTimer.singleShot(400, lambda: self.player.set_time(saved_time))

        QTimer.singleShot(80, _reattach)
        self.popout_btn.setText("⧉  Pop-out")



    def refresh_sidebar(self):
        import traceback as _tb
        try:
            self.playlist_list_widget.clear()
            self.playlist_list_widget.setIconSize(QSize(32, 32))
            for pl in self.db.get_all_playlists():
                pid, name, desc, created, cover = pl
                try:
                    song_count = len(self.db.get_playlist_songs(pid))
                    video_count = len(self.db.get_playlist_videos(pid))
                except Exception:
                    song_count = 0
                    video_count = 0
                total_count = song_count + video_count
                item = QListWidgetItem(f"♪  {name}  ({total_count})")
                item.setData(Qt.ItemDataRole.UserRole, pid)
                item.setToolTip(desc or f"{total_count} item{'s' if total_count != 1 else ''}")

                # Show playlist cover; fall back to first song cover
                cover_shown = False
                try:
                    if cover and os.path.exists(cover):
                        px = QPixmap(cover).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                   Qt.TransformationMode.SmoothTransformation)
                        if not px.isNull():
                            item.setIcon(QIcon(px))
                            cover_shown = True
                except Exception:
                    pass

                if not cover_shown:
                    try:
                        songs = self.db.get_playlist_songs(pid)
                        for s in songs:
                            cp = s[5]
                            if cp and os.path.exists(cp):
                                px = QPixmap(cp).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                        Qt.TransformationMode.SmoothTransformation)
                                if not px.isNull():
                                    item.setIcon(QIcon(px))
                                    cover_shown = True
                                    break
                    except Exception:
                        pass

                self.playlist_list_widget.addItem(item)
        except Exception:
            _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_crash.log")
            try:
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(f"\n--- refresh_sidebar error ---\n{_tb.format_exc()}")
            except Exception:
                pass

    # ──────────────────────── PLAYLIST FROM DROPDOWN ────────────────────────

    def _create_playlist_from_library(self):
        """Playlist erstellen und direkt Medien aus der Bibliothek wählen."""
        import traceback as _tb
        try:
            dlg = PlaylistDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            name = dlg.name_edit.text().strip()
            if not name:
                return
            pid = self.db.create_playlist(name, dlg.desc_edit.text().strip())
            if not pid:
                QMessageBox.warning(self, "Error", "Eine Playlist mit diesem Namen existiert bereits.")
                return
            if dlg.new_cover_path:
                self.db.update_playlist(pid, name, dlg.desc_edit.text().strip(), dlg.new_cover_path)
            self.refresh_sidebar()
            # Direkt den Inhalt-Dialog öffnen (Mediathek-Auswahl)
            content_dlg = PlaylistContentDialog(self, self.db, pid, name)
            content_dlg.exec()
            self.refresh_sidebar()
        except Exception:
            QMessageBox.critical(self, "Error", _tb.format_exc()[-400:])

    def _create_playlist_from_local(self):
        """Playlist erstellen und direkt lokale Audio- & Videodateien importieren."""
        import traceback as _tb
        try:
            dlg = PlaylistDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            name = dlg.name_edit.text().strip()
            if not name:
                return
            pid = self.db.create_playlist(name, dlg.desc_edit.text().strip())
            if not pid:
                QMessageBox.warning(self, "Error", "Eine Playlist mit diesem Namen existiert bereits.")
                return
            if dlg.new_cover_path:
                self.db.update_playlist(pid, name, dlg.desc_edit.text().strip(), dlg.new_cover_path)
            self.refresh_sidebar()
            # Datei-Dialog für Audio & Video
            file_dlg = QFileDialog(self, f"Dateien für '{name}' auswählen")
            file_dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
            file_dlg.setNameFilters([
                "Alle Medien (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)",
                "Audio (*.mp3 *.ogg *.wav *.flac *.m4a *.aac)",
                "Video (*.mp4 *.mkv *.avi *.gif *.webm *.mov)",
            ])
            file_dlg.selectNameFilter("Alle Medien (*.mp3 *.ogg *.wav *.flac *.m4a *.aac *.mp4 *.mkv *.avi *.gif *.webm *.mov)")
            if not file_dlg.exec():
                return
            files = file_dlg.selectedFiles()
            audio_files = [f for f in files if any(f.lower().endswith(e) for e in SUPPORTED_FORMATS)]
            video_files = [f for f in files if any(f.lower().endswith(e) for e in SUPPORTED_VIDEO_FORMATS)]
            cover = self.ask_cover_image() if audio_files else None
            added = 0
            for f in audio_files:
                self.process_song_import(f, cover)
                song = self.db.get_song_by_path(f)
                if song:
                    self.db.add_song_to_playlist(pid, song[0])
                    added += 1
            for f in video_files:
                existing = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (f,)).fetchone()
                if not existing:
                    title = Path(os.path.basename(f)).stem
                    file_size = os.path.getsize(f) if os.path.exists(f) else 0
                    fmt = os.path.splitext(f)[1].lstrip(".")
                    self.db.add_video(title, "", f, None, 0, file_size, fmt, "")
                vid = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (f,)).fetchone()
                if vid:
                    self.db.add_video_to_playlist(pid, vid[0])
                    added += 1
            self.load_library()
            self.refresh_sidebar()
            self.status_label.setText(f"Playlist '{name}' erstellt mit {added} Datei(en).")
        except Exception:
            QMessageBox.critical(self, "Error", _tb.format_exc()[-400:])

    def _create_playlist_from_download(self):
        """Playlist erstellen und dann den Download-Dialog öffnen (Audio & Video)."""
        import traceback as _tb
        try:
            dlg = PlaylistDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            name = dlg.name_edit.text().strip()
            if not name:
                return
            pid = self.db.create_playlist(name, dlg.desc_edit.text().strip())
            if not pid:
                QMessageBox.warning(self, "Error", "Eine Playlist mit diesem Namen existiert bereits.")
                return
            if dlg.new_cover_path:
                self.db.update_playlist(pid, name, dlg.desc_edit.text().strip(), dlg.new_cover_path)
            self.refresh_sidebar()
            # Download-Typ wählen
            type_menu = QMenu(self)
            type_menu.addAction("♫  Audio via URL", lambda: self._dl_into_playlist(pid, name, "audio"))
            type_menu.addAction("🎬  Video via URL", lambda: self._dl_into_playlist(pid, name, "video"))
            type_menu.exec(self.cursor() and self.mapToGlobal(self.rect().center()) or self.rect().center())
        except Exception:
            QMessageBox.critical(self, "Error", _tb.format_exc()[-400:])

    def _dl_into_playlist(self, pid, playlist_name, media_type):
        """Öffnet den passenden Download-Dialog und fügt Ergebnisse der Playlist hinzu."""
        if media_type == "audio":
            default_dir = self.db.get_setting(
                "ytdlp_dir",
                os.path.join(os.path.expanduser("~"), "Music", "Nova Downloads")
            )
            dlg = YtdlpImportDialog(self, self.db, default_dir)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.db.set_setting("ytdlp_dir", dlg.download_dir)
                added = 0
                for fp in dlg.downloaded_files:
                    song = self.db.get_song_by_path(fp)
                    if song:
                        self.db.add_song_to_playlist(pid, song[0])
                        added += 1
                self.load_library()
                self.refresh_sidebar()
                self.status_label.setText(f"{added} Track(s) heruntergeladen und zu '{playlist_name}' hinzugefügt.")
        else:
            default_dir = self.db.get_setting(
                "video_dir",
                os.path.join(os.path.expanduser("~"), "Videos", "Nova Downloads")
            )
            dlg = VideoDownloadDialog(self, self.db, default_dir)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.db.set_setting("video_dir", dlg.download_dir)
                added = 0
                for fp in dlg.downloaded_files:
                    vid = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (fp,)).fetchone()
                    if vid:
                        self.db.add_video_to_playlist(pid, vid[0])
                        added += 1
                self.refresh_sidebar()
                self.status_label.setText(f"{added} Video(s) heruntergeladen und zu '{playlist_name}' hinzugefügt.")

    def create_playlist(self):
        import traceback as _tb
        try:
            dlg = PlaylistDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                name = dlg.name_edit.text().strip()
                if name:
                    pid = self.db.create_playlist(name, dlg.desc_edit.text().strip())
                    if pid:
                        if dlg.new_cover_path:
                            self.db.update_playlist(pid, name, dlg.desc_edit.text().strip(), dlg.new_cover_path)
                        self.refresh_sidebar()
                    else:
                        QMessageBox.warning(self, "Error", "A playlist with that name already exists.")
        except Exception:
            _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_crash.log")
            try:
                with open(_log, "a", encoding="utf-8") as _f:
                    _f.write(f"\n--- create_playlist error ---\n{_tb.format_exc()}")
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to create playlist:\n{_tb.format_exc()[-300:]}")

    def playlist_context_menu(self, pos):
        item = self.playlist_list_widget.itemAt(pos)
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid is None:
            return
        # Capture pid as a local int so the lambdas don't hold a reference to
        # the QListWidgetItem, which may be deleted if refresh_sidebar() is called
        # while the menu is still open (causes a use-after-free crash on Windows).
        _pid = int(pid)
        _item_ref = item  # keep a Python ref so Qt doesn't GC it under the menu
        menu = QMenu(self)
        open_a = QAction("▶  Öffnen", self)
        edit_a = QAction("✏  Name & Cover bearbeiten", self)
        content_a = QAction("🎵  Inhalt bearbeiten", self)
        share_a = QAction("🔗  Teilen (Code generieren)", self)
        delete_a = QAction("🗑  Löschen", self)
        open_a.triggered.connect(lambda: self.open_playlist(_item_ref))
        edit_a.triggered.connect(lambda: self.rename_playlist(_pid, _item_ref))
        content_a.triggered.connect(lambda: self._edit_playlist_content(_pid))
        share_a.triggered.connect(lambda: self._share_playlist(_pid))
        delete_a.triggered.connect(lambda: self.delete_playlist(_pid))
        menu.addAction(open_a)
        menu.addSeparator()
        menu.addAction(edit_a)
        menu.addAction(content_a)
        menu.addAction(share_a)
        menu.addSeparator()
        menu.addAction(delete_a)
        menu.exec(self.playlist_list_widget.mapToGlobal(pos))

    def rename_playlist(self, pid, item=None):
        pl = self.db.get_playlist(pid)
        if not pl:
            return
        dlg = PlaylistDialog(self, pl[1], pl[2] or "", pl[4])
        dlg.setWindowTitle("Playlist bearbeiten")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name = dlg.name_edit.text().strip()
            if new_name:
                self.db.update_playlist(pid, new_name, dlg.desc_edit.text().strip(), dlg.new_cover_path)
                # refresh_sidebar clears the list — don't touch `item` after this point
                self.refresh_sidebar()
                if self.current_view == "playlist" and self.current_playlist_id == pid:
                    self.view_title.setText(f"▶  {new_name}")

    def delete_playlist(self, pid):
        pl = self.db.get_playlist(pid)
        if QMessageBox.question(
            self, "Delete Playlist", f"Delete playlist '{pl[1]}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.db.delete_playlist(pid)
            self.refresh_sidebar()
            if self.current_view == "playlist" and self.current_playlist_id == pid:
                self.switch_view("library")

    def _edit_playlist_content(self, playlist_id):
        """Open a dialog to add/remove/reorder songs and videos in a playlist."""
        pl = self.db.get_playlist(playlist_id)
        if not pl:
            return
        dlg = PlaylistContentDialog(self, self.db, playlist_id, pl[1])
        dlg.exec()
        self.refresh_sidebar()
        if self.current_view == "playlist" and self.current_playlist_id == playlist_id:
            self.load_library()

    def _share_playlist(self, playlist_id):
        """Open the share dialog for a playlist."""
        dlg = SharePlaylistDialog(self, self.db, playlist_id)
        dlg.exec()

    def _open_redeem_dialog(self):
        """Open the redeem-code dialog."""
        dl_dir = self.db.get_setting("download_dir", str(Path.home() / "Music"))
        dlg = RedeemCodeDialog(self, self.db, dl_dir)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_sidebar()
            self.load_library()

    def _add_to_playlist(self, playlist_id, song_id):
        self.db.add_song_to_playlist(playlist_id, song_id)
        pl = self.db.get_playlist(playlist_id)
        self.status_label.setText(f"Added to '{pl[1]}'")
        self.refresh_sidebar()

    def _remove_from_playlist(self, playlist_id, song_id):
        self.db.remove_song_from_playlist(playlist_id, song_id)
        self.refresh_sidebar()
        if self.current_view == "playlist" and self.current_playlist_id == playlist_id:
            self.load_library()

    # ──────────────────────────── CONTEXT MENU ────────────────────────────

    def show_context_menu(self, pos):
        item = self.song_list.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        item_id = item.data(Qt.ItemDataRole.UserRole + 1)
        item_type = item.data(Qt.ItemDataRole.UserRole + 2)  # "video" or "song"
        global_pos = self.song_list.mapToGlobal(pos)

        menu = QMenu(self)

        play_a = QAction("▶  Play Now", self)
        play_a.triggered.connect(lambda: self.play_selected_song(item))

        open_folder_a = QAction("📁  Open Folder", self)
        open_folder_a.triggered.connect(lambda: self.open_song_folder(path))

        menu.addAction(play_a)

        if item_type != "video":
            fav_a = QAction("♥  Toggle Favourite", self)
            fav_a.triggered.connect(lambda: self._toggle_fav_by_id(item_id))
            menu.addAction(fav_a)

        # ── Add to Playlist (songs AND videos) ──
        playlist_menu = QMenu("➕  Add to Playlist", self)
        all_playlists = self.db.get_all_playlists()
        if all_playlists:
            for pl in all_playlists:
                pid, name = pl[0], pl[1]
                if item_type == "video":
                    in_pl = self.db.video_in_playlist(pid, item_id)
                    icon = "✓  " if in_pl else "     "
                    a = QAction(f"{icon}{name}", self)
                    if in_pl:
                        a.triggered.connect(lambda _, p=pid, v=item_id: self.db.remove_video_from_playlist(p, v) or self.refresh_sidebar())
                    else:
                        a.triggered.connect(lambda _, p=pid, v=item_id: self.db.add_video_to_playlist(p, v) or self.refresh_sidebar())
                else:
                    in_pl = self.db.song_in_playlist(pid, item_id)
                    icon = "✓  " if in_pl else "     "
                    a = QAction(f"{icon}{name}", self)
                    if in_pl:
                        a.triggered.connect(lambda _, p=pid, s=item_id: self._remove_from_playlist(p, s))
                    else:
                        a.triggered.connect(lambda _, p=pid, s=item_id: self._add_to_playlist(p, s))
                playlist_menu.addAction(a)
        else:
            na = QAction("No playlists — click + to create one", self)
            na.setEnabled(False)
            playlist_menu.addAction(na)

        menu.addMenu(playlist_menu)
        menu.addSeparator()

        # Edit: audio tracks and videos
        if item_type != "video":
            edit_menu = menu.addMenu("✏  Bearbeiten")
            edit_a = QAction("🖼  Bild & Name bearbeiten", self)
            edit_a.triggered.connect(lambda: self._edit_song(item_id, path))
            edit_menu.addAction(edit_a)
            menu.addSeparator()
        else:
            edit_a = QAction("✏  Titel & Kanal bearbeiten", self)
            edit_a.triggered.connect(lambda: self._edit_video(item_id))
            menu.addAction(edit_a)
            menu.addSeparator()

        menu.addAction(open_folder_a)

        if self.current_view == "playlist" and self.current_playlist_id:
            rm_pl_a = QAction("✂  Remove from This Playlist", self)
            if item_type == "video":
                rm_pl_a.triggered.connect(lambda: self.db.remove_video_from_playlist(self.current_playlist_id, item_id) or self.load_library())
            else:
                rm_pl_a.triggered.connect(lambda: self._remove_from_playlist(self.current_playlist_id, item_id))
            menu.addAction(rm_pl_a)

        menu.addSeparator()

        # Remove from Library
        if item_type == "video":
            remove_a = QAction("🗑  Remove from Library", self)
            remove_a.triggered.connect(lambda: self._remove_video_from_library_confirmed(item_id))
        else:
            remove_a = QAction("🗑  Remove from Library", self)
            remove_a.triggered.connect(lambda: self._remove_from_library(item_id))
        menu.addAction(remove_a)
        menu.exec(global_pos)

    def _edit_song(self, song_id, path):
        song = self.db.get_song_by_path(path)
        if not song:
            return
        _, title, artist, _, _, cover_path, _, fav, rating, _ = song
        dlg = EditSongDialog(self, self.db, song_id, title, artist, cover_path)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_library(self.search_box.text())
            if song_id == self.current_song_id:
                updated = self.db.get_song_by_path(path)
                if updated:
                    self.song_title_label.setText(updated[1])
                    self.song_artist_label.setText(f"{updated[2]}  ·  {updated[3]}")
                    self.bb_song_title.setText(updated[1])
                    self.bb_song_artist.setText(f"{updated[2]}  ·  {updated[3]}")
                    if updated[5] and os.path.exists(updated[5]):
                        px = QPixmap(updated[5]).scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.cover_label.setPixmap(px)
                        px_s = QPixmap(updated[5]).scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        self.bb_cover.setPixmap(px_s)
                    # Reload lyrics panel with new data
                    self._load_lyrics(updated[2], updated[1], song_id=song_id)

    def _edit_video(self, video_id):
        """Inline-Editor für Titel, Kanal, YouTube-URL und Lyrics eines Videos."""
        vid = self.db.cursor.execute(
            "SELECT title, channel FROM videos WHERE id=?", (video_id,)
        ).fetchone()
        if not vid:
            return
        old_title, old_channel = vid
        old_yt_url = self.db.get_video_yt_url(video_id) or ""
        old_lyrics_row = self.db.cursor.execute(
            "SELECT lyrics FROM videos WHERE id=?", (video_id,)
        ).fetchone()
        old_lyrics = (old_lyrics_row[0] or "") if old_lyrics_row else ""

        dlg = QDialog(self)
        dlg.setWindowTitle("✏  Video bearbeiten")
        dlg.setFixedWidth(480)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        title_edit = QLineEdit(old_title)
        channel_edit = QLineEdit(old_channel)
        url_edit = QLineEdit(old_yt_url)
        url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…")
        form.addRow("Titel:", title_edit)
        form.addRow("Kanal:", channel_edit)
        form.addRow("YouTube-URL:", url_edit)
        layout.addLayout(form)

        # ── Lyrics field ──────────────────────────────────────────────────
        layout.addWidget(QLabel("Lyrics:"))

        lsearch_row = QHBoxLayout()
        lyrics_search = QLineEdit()
        lyrics_search.setPlaceholderText(f"{old_channel or 'Artist'} - {old_title or 'Title'}")
        lyrics_search.setText(f"{old_channel} - {old_title}" if old_channel and old_title else "")
        lyrics_search.setToolTip("Format: Artist - Title  (e.g.  Eminem - Slim Shady)")
        lyrics_fetch_btn = QPushButton("🔍 Fetch")
        lyrics_fetch_btn.setFixedWidth(70)
        lsearch_row.addWidget(lyrics_search)
        lsearch_row.addWidget(lyrics_fetch_btn)
        layout.addLayout(lsearch_row)

        lyrics_status = QLabel("Format: Artist - Title")
        lyrics_status.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(lyrics_status)

        lyrics_edit = QTextEdit()
        lyrics_edit.setPlainText(old_lyrics)
        lyrics_edit.setPlaceholderText("Lyrics appear here after fetching, or paste manually…")
        lyrics_edit.setFixedHeight(130)
        layout.addWidget(lyrics_edit)

        # wire fetch button
        _fetcher_holder = [None]
        def _do_fetch():
            query = lyrics_search.text().strip()
            if not query:
                lyrics_status.setText("⚠  Enter  Artist - Title  first.")
                return
            if " - " in query:
                a, _, t = query.partition(" - ")
            else:
                a, t = "", query
            lyrics_fetch_btn.setEnabled(False)
            lyrics_status.setText("Searching…")
            lyrics_status.setStyleSheet("color: #666; font-size: 11px;")
            f = LyricsFetcher(a.strip(), t.strip())
            _fetcher_holder[0] = f
            def _ok(raw, _lines):
                lyrics_edit.setPlainText(raw)
                lyrics_status.setText("✓ Lyrics loaded — save to keep them.")
                lyrics_status.setStyleSheet("color: #4caf50; font-size: 11px;")
                lyrics_fetch_btn.setEnabled(True)
            def _fail(msg):
                lyrics_status.setText(f"✗ {msg}")
                lyrics_status.setStyleSheet("color: #e57373; font-size: 11px;")
                lyrics_fetch_btn.setEnabled(True)
            f.lyrics_ready.connect(_ok)
            f.lyrics_failed.connect(_fail)
            f.start()
        lyrics_fetch_btn.clicked.connect(_do_fetch)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_title = title_edit.text().strip() or old_title
            new_channel = channel_edit.text().strip()
            new_url = url_edit.text().strip() or None
            new_lyrics = lyrics_edit.toPlainText().strip() or None
            self.db.update_video(video_id, new_title, new_channel, yt_url=new_url)
            self.db.cursor.execute(
                "UPDATE videos SET lyrics=? WHERE id=?", (new_lyrics, video_id)
            )
            self.db.conn.commit()
            self.load_library(self.search_box.text())
            # Update now-playing labels if this is the active video
            if self.is_video_mode:
                vrow = self.db.cursor.execute(
                    "SELECT path FROM videos WHERE id=?", (video_id,)
                ).fetchone()
                if vrow and vrow[0] == self.current_song_path:
                    self.song_title_label.setText(new_title)
                    self.song_artist_label.setText(new_channel)
                    # Reload lyrics immediately if panel is open
                    if new_lyrics:
                        lines = new_lyrics.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                        self._on_lyrics_ready(new_lyrics, lines)
                    else:
                        self._lyrics_content.setText("No lyrics saved.")

    def _toggle_fav_by_id(self, song_id):
        self.db.toggle_favourite(song_id)
        if song_id == self.current_song_id:
            song = self.db.get_song_by_path(self.current_song_path)
            if song:
                self._update_fav_btn(bool(song[7]))
        self.load_library(self.search_box.text())

    def _remove_from_library(self, song_id):
        if QMessageBox.question(
            self, "Remove Song", "Remove this song from the library?\n(The file is not deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.db.delete_song(song_id)
            self.load_library(self.search_box.text())

    def _remove_video_from_library_confirmed(self, video_id):
        if QMessageBox.question(
            self, "Remove Video", "Remove this video from the library?\n(The file is not deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.db.delete_video(video_id)
            self.load_library(self.search_box.text())

    def open_song_folder(self, path):
        if os.path.exists(path):
            folder = os.path.dirname(path)
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    # ──────────────────────────── LYRICS ────────────────────────────

    def _toggle_lyrics_panel(self):
        """Collapse/expand the lyrics panel without shifting the cover/video above it."""
        self._lyrics_expanded = not self._lyrics_expanded
        if self._lyrics_expanded:
            self._lyrics_wrapper.setMinimumHeight(120)
            self._lyrics_wrapper.setMaximumHeight(280)
            self._lyrics_toggle_btn.setText("♪  Lyrics  ▴")
        else:
            self._lyrics_wrapper.setMinimumHeight(0)
            self._lyrics_wrapper.setMaximumHeight(0)
            self._lyrics_toggle_btn.setText("♪  Lyrics  ▾")
        # Trigger a layout pass only on the wrapper, not the whole right column,
        # so the cover_stack above is not repositioned.
        self._lyrics_wrapper.updateGeometry()

    def _load_lyrics(self, artist: str, title: str, song_id=None, video_id=None):
        """Load lyrics: memory cache first, then DB, then API fallback."""
        # Cancel any in-flight fetch
        if self._lyrics_fetcher and self._lyrics_fetcher.isRunning():
            self._lyrics_fetcher.terminate()
            self._lyrics_fetcher.wait()

        self._lyrics_lines        = []
        self._lyrics_timestamps   = []
        self._lyrics_current_line = -1

        # Remember the DB context so _on_lyrics_ready can auto-save API results
        self._lyrics_song_id  = song_id
        self._lyrics_video_id = video_id

        # ── 0. Check in-memory cache ─────────────────────────────────────────
        cache_key = (artist.lower().strip(), title.lower().strip())
        self._lyrics_current_key = cache_key
        if cache_key in self._lyrics_cache:
            cached = self._lyrics_cache[cache_key]
            self._on_lyrics_ready("\n".join(cached), cached)
            return

        # ── 1. Check DB for manually saved lyrics ────────────────────────
        db_lyrics = None
        if song_id:
            row = self.db.cursor.execute("SELECT lyrics FROM songs WHERE id=?", (song_id,)).fetchone()
            db_lyrics = (row[0] or "").strip() if row else ""
        elif video_id:
            row = self.db.cursor.execute("SELECT lyrics FROM videos WHERE id=?", (video_id,)).fetchone()
            db_lyrics = (row[0] or "").strip() if row else ""

        if db_lyrics:
            lines = db_lyrics.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            # Also populate in-memory cache so subsequent switches don't re-query the DB
            self._lyrics_cache[cache_key] = list(lines)
            self._on_lyrics_ready(db_lyrics, lines)
            return

        # ── 2. API fallback ───────────────────────────────────────────────
        artist = (artist or "").strip()
        title  = (title  or "").strip()

        import re as _re
        # Don't send placeholder values to the API
        if _re.match(r'(?i)^(unknown(\s+artist)?|youtube|converted)$', artist):
            artist = ""
        title = _re.sub(r'\s*[\(\[][^\)\]]{0,40}[\)\]]', '', title).strip()

        if not title:
            self._lyrics_content.setText("No title info — can't fetch lyrics.")
            return

        display = f"{artist} — {title}" if artist else title
        self._lyrics_content.setText(f"Searching: {display}…")

        fetcher = LyricsFetcher(artist, title, self)
        fetcher.lyrics_ready.connect(self._on_lyrics_ready)
        fetcher.lyrics_failed.connect(self._on_lyrics_failed)
        self._lyrics_fetcher = fetcher
        fetcher.start()

    def _on_lyrics_ready(self, _raw: str, lines: list):
        """Store lines, populate cache, auto-save to DB, and build timestamp estimates."""
        self._lyrics_lines        = lines
        self._lyrics_current_line = -1
        has_lines = bool(lines)
        self._lyrics_copy_btn.setVisible(has_lines)
        self._lyrics_save_btn.setVisible(has_lines)
        self._lyrics_fs_btn.setVisible(has_lines)

        # Populate in-memory cache so switching back to this song is instant
        if has_lines and self._lyrics_current_key:
            self._lyrics_cache[self._lyrics_current_key] = list(lines)

        # ── Auto-save freshly fetched lyrics to DB so they survive restarts ──
        # Only write when the lyrics came from the API (not from DB itself),
        # i.e. when the DB entry was still empty. We detect this by checking
        # whether _lyrics_song_id / _lyrics_video_id is set.
        if has_lines:
            raw = "\n".join(lines)
            try:
                if self._lyrics_song_id:
                    # Only write if the DB row is still empty (don't overwrite manual edits)
                    existing = self.db.cursor.execute(
                        "SELECT lyrics FROM songs WHERE id=?", (self._lyrics_song_id,)
                    ).fetchone()
                    if existing and not (existing[0] or "").strip():
                        self.db.cursor.execute(
                            "UPDATE songs SET lyrics=? WHERE id=?", (raw, self._lyrics_song_id)
                        )
                        self.db.conn.commit()
                elif self._lyrics_video_id:
                    existing = self.db.cursor.execute(
                        "SELECT lyrics FROM videos WHERE id=?", (self._lyrics_video_id,)
                    ).fetchone()
                    if existing and not (existing[0] or "").strip():
                        self.db.cursor.execute(
                            "UPDATE videos SET lyrics=? WHERE id=?", (raw, self._lyrics_video_id)
                        )
                        self.db.conn.commit()
            except Exception:
                pass  # DB write failure is non-critical

        # We don't have real word-level timestamps, so distribute lines
        # evenly over the song duration. Once we know the length we update.
        length_ms = self.player.get_length()
        if length_ms <= 0:
            length_ms = 240_000   # fallback 4 min
        n = len(lines)
        # Leave a short silence at start (~2 s) and don't go to the very end
        start = 2_000
        end   = max(length_ms - 4_000, start + 1_000)
        if n > 0:
            step = (end - start) / n
            self._lyrics_timestamps = [start + i * step for i in range(n)]
        else:
            self._lyrics_timestamps = []

        self._render_lyrics(-1)

    def _on_lyrics_failed(self, msg: str):
        self._lyrics_lines        = []
        self._lyrics_timestamps   = []
        self._lyrics_current_line = -1
        self._lyrics_copy_btn.setVisible(False)
        self._lyrics_save_btn.setVisible(False)
        self._lyrics_fs_btn.setVisible(False)
        # Show what was searched so user can see if artist/title are wrong
        searched = self._lyrics_content.text()   # still shows "Searching: X — Y…"
        self._lyrics_content.setText(
            f"{msg}\n{searched.replace('Searching: ', 'Searched: ').replace('…', '')}"
        )

    def _copy_lyrics(self):
        """Copy all lyrics lines to the clipboard."""
        if not self._lyrics_lines:
            return
        text = "\n".join(self._lyrics_lines)
        QApplication.clipboard().setText(text)
        self._lyrics_copy_btn.setText("✓")
        QTimer.singleShot(1500, lambda: self._lyrics_copy_btn.setText("▤"))

    def _save_lyrics(self):
        """Save currently displayed lyrics to the DB for the active song/video."""
        if not self._lyrics_lines:
            return
        raw = "\n".join(self._lyrics_lines)
        if self.current_song_id and not self.is_video_mode:
            self.db.cursor.execute("UPDATE songs SET lyrics=? WHERE id=?", (raw, self.current_song_id))
            self.db.conn.commit()
            self._lyrics_save_btn.setText("✓")
            QTimer.singleShot(1500, lambda: self._lyrics_save_btn.setText("↓"))
        elif self.is_video_mode and self.current_song_path:
            row = self.db.cursor.execute("SELECT id FROM videos WHERE path=?", (self.current_song_path,)).fetchone()
            if row:
                self.db.cursor.execute("UPDATE videos SET lyrics=? WHERE id=?", (raw, row[0]))
                self.db.conn.commit()
                self._lyrics_save_btn.setText("✓")
                QTimer.singleShot(1500, lambda: self._lyrics_save_btn.setText("↓"))

    def _open_lyrics_fullscreen(self):
        """Show lyrics in a full-window overlay (press Esc to close)."""
        if not self._lyrics_lines:
            return
        LyricsFullscreenOverlay(
            self, self.theme, self.song_title_label.text(), self._lyrics_lines
        ).show()

    def _render_lyrics(self, active_idx: int):
        """Render lyrics as plain text, no highlighting."""
        if not self._lyrics_lines:
            return
        self._lyrics_content.setText("\n".join(self._lyrics_lines))

    # ──────────────────────────── QUEUE ────────────────────────────

    def show_queue(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Up Next")
        dlg.setFixedSize(420, 520)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Up Next")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        lw = QListWidget()
        start = max(0, self.current_index)
        count = self.song_list.count()
        for i in range(count):
            idx = (start + i) % count
            it = self.song_list.item(idx)
            q_item = QListWidgetItem(it.text())
            if i == 0:
                q_item.setForeground(QColor(self.theme["accent"]))
            lw.addItem(q_item)
        layout.addWidget(lw)

        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.setLayout(layout)
        dlg.exec()

    # ──────────────────────────── SLEEP TIMER ────────────────────────────

    def open_sleep_timer(self):
        if self.sleep_timer:
            if QMessageBox.question(
                self, "Sleep Timer", "Cancel existing sleep timer?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                self.sleep_timer = None
                self.sleep_elapsed = 0
                self.sleep_label.setText("")
            return
        dlg = SleepTimerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.sleep_minutes = dlg.minutes_spin.value()
            self.sleep_elapsed = 0
            self.sleep_timer = True
            self.status_label.setText(f"Sleep timer set for {self.sleep_minutes} minutes.")

    # ──────────────────────────── SETTINGS ────────────────────────────

    def open_settings(self):
        dlg = SettingsDialog(self, self.db, self.current_theme_name)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.current_theme_name = self.db.get_setting("theme", "Midnight")
            self.theme = THEMES.get(self.current_theme_name, THEMES["Midnight"])
            self.apply_theme()
            self.load_library(self.search_box.text())
            # Update the browser panel's home URL if it exists
            if hasattr(self, "yt_browser") and self.yt_browser is not None:
                new_url = self.db.get_setting("browser_home_url", "https://www.google.com")
                self.yt_browser.HOME_URL = new_url or "https://www.google.com"
            # ── Discord RPC: Ein/Aus je nach Einstellung ──────────────────
            if self.db.get_setting("discord_rpc", "0") == "1" and _PYPRESENCE_AVAILABLE:
                self._discord.enable()
                # Sofort aktualisieren falls gerade etwas läuft
                if self.current_song_path and self.player.is_playing():
                    song = self.db.get_song_by_path(self.current_song_path)
                    if song and not self.is_video_mode:
                        _, title, artist, album, _, _, duration, *_ = song
                        self._discord.set_playing(
                            title=title, artist=artist, album=album,
                            duration_ms=int(duration) if duration else 0,
                            elapsed_ms=self.player.get_time(),
                            is_video=False,
                        )
            else:
                self._discord.disable()

    def closeEvent(self, event):
        """Trennt Discord RPC sauber beim Beenden der App."""
        if getattr(self, "_ext_server", None):
            self._ext_server.stop()
        self._discord.disconnect()
        super().closeEvent(event)

    # ──────────────────────────── WEB PLAYER ────────────────────────────

    def open_web_player(self):
        search = self.search_box.text()
        songs = self.get_current_songs(search)
        if not songs:
            QMessageBox.information(self, "Web Player", "No songs to export.")
            return
        dlg = WebPlayerDialog(self, songs, self.current_song_path, self.theme)
        dlg.exec()


if __name__ == "__main__":
    import traceback

    # Write all unhandled exceptions to a log file next to the script
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_crash.log")

    def _excepthook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(f"\n{'='*60}\n{__import__('datetime').datetime.now()}\n{msg}")
        except Exception:
            pass
        # Also print so a console user sees it
        print(msg, file=sys.__stderr__)

    sys.excepthook = _excepthook

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass

    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = NovaPlayer()
        window.show()
        sys.exit(app.exec())
    except Exception:
        _excepthook(*sys.exc_info())
        sys.exit(1)