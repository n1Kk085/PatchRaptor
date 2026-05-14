import sys
import os

GUI_COLORS = {
    'PRIMARY': '#5B83C9',
    'DARK_BG': '#222222',
    'SUCCESS': '#44ff44',
    'DANGER': '#ff4444'
}

GUI_FONTS = {
    'MAIN': 'Consolas',
    'SIZE': 14
}

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)
