import os
import sys
import gc
import pyautogui
import vgamepad as vg
from pynput import mouse, keyboard
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QIcon, QPen, QPixmap, QPainterPath
import ctypes

# ==============================
# Constants
# ==============================
SCREEN_W, SCREEN_H = pyautogui.size()
PADDING = 14
ROW_H = 36
TITLE_H = 36
HUD_ROW_H = 24
HUD_HEADER_H = 28
DOT_R = 5
RADIUS = 8
VERSION = "1.0.1"

user32 = ctypes.windll.user32


def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base, relative_path)


def is_msfs_active():
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return "Microsoft Flight Simulator" in buf.value


# ==============================
# Shared logo pixmaps (loaded once)
# ==============================
_LOGO_20 = None
_LOGO_16 = None


def get_logo(size):
    global _LOGO_20, _LOGO_16
    if size == 20:
        if _LOGO_20 is None:
            _LOGO_20 = QPixmap(resource_path("src/icon_256x256.ico")).scaled(
                20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return _LOGO_20
    if size == 16:
        if _LOGO_16 is None:
            _LOGO_16 = QPixmap(resource_path("src/icon_256x256.ico")).scaled(
                16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return _LOGO_16


# ==============================
# State
# ==============================
state = {
    "controller": False,
    "invert": False,
    "rudder": False,
    "hud_visible": True,
}
gamepad = None
last_yoke_pos = (0.0, 0.0)
current_keys = set()


# ==============================
# Gamepad
# ==============================
def connect_gamepad():
    global gamepad
    if gamepad is None:
        gamepad = vg.VX360Gamepad()
        print("[Better Controls] Controller connected")


def disconnect_gamepad():
    global gamepad
    if gamepad:
        gamepad.left_joystick_float(0.0, 0.0)
        gamepad.left_trigger_float(0.0)
        gamepad.right_trigger_float(0.0)
        gamepad.update()
        del gamepad
        gamepad = None
        gc.collect()
        print("[Better Controls] Controller disconnected")


# ==============================
# Mouse
# ==============================
def on_move(x, y):
    global last_yoke_pos
    if not state["controller"] or gamepad is None:
        return

    rx = max(-1.0, min(1.0, (x / SCREEN_W) * 2 - 1))
    ry = max(-1.0, min(1.0, -((y / SCREEN_H) * 2 - 1)))
    if state["invert"]:
        ry *= -1

    if not state["rudder"]:
        gamepad.left_joystick_float(rx, ry)
        last_yoke_pos = (rx, ry)
        gamepad.left_trigger_float(0.0)
        gamepad.right_trigger_float(0.0)
    else:
        gamepad.left_joystick_float(*last_yoke_pos)
        gamepad.left_trigger_float(max(0.0, -rx))
        gamepad.right_trigger_float(max(0.0, rx))

    gamepad.update()


def on_click(x, y, button, pressed):
    if button == mouse.Button.left:
        state["rudder"] = pressed
        hud.update()


# ==============================
# Keyboard
# ==============================
def on_press(key):
    try:
        current_keys.add(key)
        ctrl = keyboard.Key.ctrl_l in current_keys or keyboard.Key.ctrl_r in current_keys
        if not ctrl:
            return
        if key == keyboard.Key.f1:
            state["controller"] = not state["controller"]
            connect_gamepad() if state["controller"] else disconnect_gamepad()
            hud.update()
        elif key == keyboard.Key.f2:
            state["invert"] = not state["invert"]
            hud.update()
        elif key == keyboard.Key.f3:
            pyautogui.moveTo(SCREEN_W // 2, SCREEN_H // 2)
            state["rudder"] = False
            state["invert"] = False
            if gamepad:
                gamepad.left_joystick_float(0.0, 0.0)
                gamepad.left_trigger_float(0.0)
                gamepad.right_trigger_float(0.0)
                gamepad.update()
            hud.update()
    except AttributeError:
        pass


def on_release(key):
    current_keys.discard(key)


keyboard.Listener(on_press=on_press, on_release=on_release).start()
mouse.Listener(on_move=on_move, on_click=on_click).start()


# ==============================
# Shared drawing helpers
# ==============================
def draw_dot(painter, x, y, active):
    color = QColor(100, 220, 120) if active else QColor(180, 60, 60)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(x - DOT_R, y - DOT_R, DOT_R * 2, DOT_R * 2)
    glow = QColor(color)
    glow.setAlpha(60)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(glow, 2))
    painter.drawEllipse(x - DOT_R - 2, y - DOT_R - 2,
                        DOT_R * 2 + 4, DOT_R * 2 + 4)


def draw_pill(painter, x, y, w, h, active):
    painter.setBrush(QColor(21, 101, 192) if active else QColor(80, 80, 80))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(x, y, w, h, h // 2, h // 2)
    knob = h - 4
    kx = (x + w - knob - 2) if active else (x + 2)
    painter.setBrush(QColor(255, 255, 255))
    painter.drawEllipse(kx, y + 2, knob, knob)


def rounded_top_path(x, y, w, h, r):
    path = QPainterPath()
    path.moveTo(x + r, y)
    path.lineTo(x + w - r, y)
    path.quadTo(x + w, y, x + w, y + r)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.lineTo(x, y + r)
    path.quadTo(x, y, x + r, y)
    path.closeSubpath()
    return path


def rounded_bottom_path(x, y, w, h, r):
    path = QPainterPath()
    path.moveTo(x, y)
    path.lineTo(x + w, y)
    path.lineTo(x + w, y + h - r)
    path.quadTo(x + w, y + h, x + w - r, y + h)
    path.lineTo(x + r, y + h)
    path.quadTo(x, y + h, x, y + h - r)
    path.lineTo(x, y)
    path.closeSubpath()
    return path


# ==============================
# HUD Overlay
# ==============================
class HUDOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint |
                            Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(50, 50, 210, HUD_HEADER_H + HUD_ROW_H * 3)
        self.show()

        hwnd = self.winId().__int__()
        ex = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, ex | 0x80000)

        QTimer(self, timeout=self.update_hud, interval=50).start()

    def update_hud(self):
        show = state["controller"] and is_msfs_active(
        ) and state["hud_visible"]
        self.show() if show else self.hide()
        self.update()

    def paintEvent(self, event):
        if not state["controller"] or not is_msfs_active() or not state["hud_visible"]:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, W, H, RADIUS, RADIUS)
        p.setClipPath(clip)

        p.setBrush(QColor(45, 45, 45, 230))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, W, H, RADIUS, RADIUS)

        p.setBrush(QColor(21, 101, 192))
        p.drawPath(rounded_top_path(0, 0, W, HUD_HEADER_H, RADIUS))

        logo = get_logo(16)
        p.drawPixmap(PADDING, (HUD_HEADER_H - 16) // 2, logo)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRect(PADDING + 20, 0, W, HUD_HEADER_H),
                   Qt.AlignVCenter, "Better Controls")

        rows = [
            ("Controller",      state["controller"]),
            ("Invert Elevator", state["invert"]),
            ("Rudder",          state["rudder"]),
        ]
        p.setFont(QFont("Segoe UI", 9))

        for i, (label, val) in enumerate(rows):
            y = HUD_HEADER_H + i * HUD_ROW_H
            is_last = i == len(rows) - 1
            p.setBrush(QColor(50, 50, 50, 200) if i %
                       2 == 0 else QColor(42, 42, 42, 200))
            p.setPen(Qt.NoPen)
            if is_last:
                p.drawPath(rounded_bottom_path(0, y, W, HUD_ROW_H, RADIUS))
            else:
                p.drawRect(0, y, W, HUD_ROW_H)
            if not is_last:
                p.setPen(QColor(65, 65, 65))
                p.drawLine(0, y + HUD_ROW_H - 1, W, y + HUD_ROW_H - 1)
            p.setPen(QColor(210, 210, 210))
            p.drawText(QRect(PADDING, y, W - 30, HUD_ROW_H),
                       Qt.AlignVCenter, label)
            draw_dot(p, W - 16, y + HUD_ROW_H // 2, val)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(80, 80, 80), 1))
        p.drawRoundedRect(0, 0, W - 1, H - 1, RADIUS, RADIUS)


# ==============================
# Toggle Row
# ==============================
class MSFSToggleRow(QWidget):
    def __init__(self, text, on_toggle):
        super().__init__()
        self._checked = False
        self._text = text
        self._on_toggle = on_toggle
        self.setFixedHeight(ROW_H)
        self.setCursor(Qt.PointingHandCursor)

    def setChecked(self, val):
        self._checked = val
        self.update()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self._on_toggle(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(42, 42, 42))
        p.setPen(QColor(210, 210, 210))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(PADDING, 0, W - 60, H), Qt.AlignVCenter, self._text)
        draw_pill(p, W - 48, (H - 16) // 2, 36, 16, self._checked)


# ==============================
# Title Bar Button
# ==============================
class TitleBarButton(QWidget):
    def __init__(self, symbol, hover_color, on_click):
        super().__init__()
        self.symbol = symbol
        self.hover_color = QColor(hover_color)
        self._hovered = False
        self._on_click = on_click
        self.setFixedSize(TITLE_H, TITLE_H)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e): self._hovered = True;  self.update()
    def leaveEvent(self, e): self._hovered = False; self.update()
    def mousePressEvent(self, e): self._on_click()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hovered:
            p.fillRect(self.rect(), self.hover_color)
        p.setPen(QColor(220, 220, 220))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(self.rect(), Qt.AlignCenter, self.symbol)


# ==============================
# Main Window
# ==============================
class MouseYokeGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("src/icon_256x256.ico")))
        self.setWindowTitle(f"Better Controls {VERSION}")
        self.setFixedWidth(340)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = QWidget(objectName="container")
        container.setStyleSheet("""
            QWidget#container {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        container.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(TITLE_H)
        title_bar.setStyleSheet("""
            background-color: #1565C0;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            border: none;
        """)
        title_bar.setAttribute(Qt.WA_StyledBackground, True)
        title_bar.mousePressEvent = self._drag_start
        title_bar.mouseMoveEvent = self._drag_move
        title_bar.mouseReleaseEvent = self._drag_end

        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(PADDING, 0, 0, 0)
        tl.setSpacing(8)

        logo_lbl = QLabel()
        logo_lbl.setPixmap(get_logo(20))
        logo_lbl.setStyleSheet("background: transparent;")
        tl.addWidget(logo_lbl)
        tl.addWidget(self._lbl("Better Controls", 10, bold=True))
        tl.addStretch()
        tl.addWidget(TitleBarButton("─", "#1976D2", self.showMinimized))
        tl.addWidget(TitleBarButton("✕", "#C62828", self.close))
        layout.addWidget(title_bar)

        # Shortcut rows — no layout margin, padding on label only
        for i, text in enumerate([
            "Ctrl + F1 — Toggle Controller",
            "Ctrl + F2 — Invert Elevator",
            "Ctrl + F3 — Center Mouse",
        ]):
            bg = "#323232" if i % 2 == 0 else "#2a2a2a"
            row = QWidget()
            row.setStyleSheet(f"background-color: {bg}; border: none;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(0)
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(
                f"color: #d2d2d2; padding: 8px 0px 8px {PADDING}px; background: {bg};")
            rl.addWidget(lbl)
            rl.addWidget(self._divider())
            layout.addWidget(row)

        # HUD toggle
        self.hud_toggle = MSFSToggleRow(
            "Show HUD When Active", self._on_hud_toggle)
        self.hud_toggle.setChecked(True)
        layout.addWidget(self.hud_toggle)
        layout.addWidget(self._divider())

        # Version footer
        version_lbl = QLabel(f"v{VERSION}")
        version_lbl.setFont(QFont("Segoe UI", 8))
        version_lbl.setStyleSheet("""
            color: #666666;
            background-color: #252525;
            padding: 4px 0px;
            border: none;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        """)
        version_lbl.setAttribute(Qt.WA_StyledBackground, True)
        version_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_lbl)

    def _lbl(self, text, size, bold=False):
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", size, QFont.Bold if bold else QFont.Normal))
        l.setStyleSheet("color: white; background: transparent;")
        return l

    def _divider(self):
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(
            "background-color: #414141; max-height: 1px; border: none;")
        return d

    def _drag_start(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def _drag_end(self, e):
        self._drag_pos = None

    def _on_hud_toggle(self, checked):
        state["hud_visible"] = checked
        hud.update_hud()


# ==============================
# Startup
# ==============================
app = QApplication(sys.argv)
hud = HUDOverlay()
window = MouseYokeGUI()
window.show()
sys.exit(app.exec())
