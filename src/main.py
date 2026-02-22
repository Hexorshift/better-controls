import os
import sys
import gc
import pyautogui
import vgamepad as vg
from pynput import mouse, keyboard
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QIcon
import ctypes


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ==============================
# Screen
# ==============================
SCREEN_W, SCREEN_H = pyautogui.size()

# ==============================
# State
# ==============================
controller_enabled = False
invert_elevator = False
rudder_pressed = False
gamepad = None
last_yoke_pos = (0.0, 0.0)
left_mouse_pressed = False

# ==============================
# Windows API for active window
# ==============================
user32 = ctypes.windll.user32


def is_msfs_active():
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buffer = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buffer, length)
    return "Microsoft Flight Simulator" in buffer.value

# ==============================
# Controller lifecycle
# ==============================


def connect_gamepad():
    global gamepad
    if gamepad is None:
        gamepad = vg.VX360Gamepad()
        print("[MSFS Add-on] Controller connected")


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
        print("[MSFS Add-on] Controller disconnected")

# ==============================
# Mouse callbacks
# ==============================


def on_move(x, y):
    global last_yoke_pos
    if not controller_enabled or gamepad is None:
        return

    rel_x = (x / SCREEN_W) * 2 - 1
    rel_y = -((y / SCREEN_H) * 2 - 1)
    if invert_elevator:
        rel_y *= -1

    rel_x = max(-1.0, min(1.0, rel_x))
    rel_y = max(-1.0, min(1.0, rel_y))

    if not rudder_pressed:
        gamepad.left_joystick_float(rel_x, rel_y)
        last_yoke_pos = (rel_x, rel_y)
    else:
        gamepad.left_joystick_float(*last_yoke_pos)

    if rudder_pressed:
        left_trigger = max(0.0, -rel_x)
        right_trigger = max(0.0, rel_x)
        gamepad.left_trigger_float(left_trigger)
        gamepad.right_trigger_float(right_trigger)
    else:
        gamepad.left_trigger_float(0.0)
        gamepad.right_trigger_float(0.0)

    gamepad.update()


def on_click(x, y, button, pressed):
    global rudder_pressed, left_mouse_pressed
    if button == mouse.Button.left:
        left_mouse_pressed = pressed
        rudder_pressed = pressed
        hud.update()


# ==============================
# Keyboard hotkeys (Ctrl + F1/F2/F3)
# ==============================
current_keys = set()


def on_press(key):
    global controller_enabled, invert_elevator
    try:
        current_keys.add(key)
        if keyboard.Key.ctrl_l in current_keys or keyboard.Key.ctrl_r in current_keys:
            if key == keyboard.Key.f1:  # Ctrl+F1
                controller_enabled = not controller_enabled
                if controller_enabled:
                    connect_gamepad()
                else:
                    disconnect_gamepad()
                hud.update()
            elif key == keyboard.Key.f2:  # Ctrl+F2
                invert_elevator = not invert_elevator
                hud.update()
            elif key == keyboard.Key.f3:  # Ctrl+F3
                pyautogui.moveTo(SCREEN_W//2, SCREEN_H//2)
    except AttributeError:
        pass


def on_release(key):
    if key in current_keys:
        current_keys.remove(key)


keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
keyboard_listener.start()

# ==============================
# HUD Overlay
# ==============================


class HUDOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint |
                            Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(50, 50, 180, 60)  # compact HUD
        self.show()

        # Click-through
        hwnd = self.winId().__int__()
        WS_EX_LAYERED = 0x80000
        GWL_EXSTYLE = -20
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)

        # Refresh every 50ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_hud)
        self.timer.start()

    def update_hud(self):
        if controller_enabled and is_msfs_active():
            self.show()
        else:
            self.hide()
        self.update()

    def paintEvent(self, event):
        if not controller_enabled or not is_msfs_active():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(30, 30, 30, 180))
        painter.setPen(QColor(0, 120, 215))
        painter.drawRoundedRect(0, 0, self.width()-1, self.height()-1, 10, 10)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            10, 18, f"Controller: {'ON' if controller_enabled else 'OFF'}")
        painter.drawText(
            10, 34, f"Invert Elevator: {'ON' if invert_elevator else 'OFF'}")
        painter.drawText(
            10, 50, f"Rudder Active: {'YES' if rudder_pressed else 'NO'}")

# ==============================
# Main Settings Window (Instructions Only)
# ==============================


class MouseYokeGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("src/icon_256x256.ico")))
        self.setWindowTitle("Better Controls")
        self.setFixedWidth(250)

        layout = QVBoxLayout()
        instructions = [
            "Ctrl + F1: Toggle Controller",
            "Ctrl + F2: Invert Elevator",
            "Ctrl + F3: Center Mouse"
        ]
        for instr in instructions:
            label = QLabel(instr)
            label.setFont(QFont("Segoe UI", 10))
            layout.addWidget(label)

        self.setLayout(layout)


# ==============================
# Startup
# ==============================
mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
mouse_listener.start()

app = QApplication(sys.argv)
hud = HUDOverlay()
window = MouseYokeGUI()
window.show()
sys.exit(app.exec())
