import datetime
import sys
import time
import os
import pathlib
import json
import threading
from win32 import win32gui, win32console, win32con

python_version = "m20-240531"

def hide_console():
    """Hide the console window."""
    window = win32console.GetConsoleWindow()
    win32gui.ShowWindow(window, win32con.SW_HIDE)

# Project path setup
base_path = pathlib.Path(__file__).resolve().parents[1]
log_path = base_path / 'log' / 'console' / datetime.datetime.now().strftime('%Y/%m/%d')
log_path.mkdir(parents=True, exist_ok=True)

# Console visibility setup
console = True
config_path = base_path / 'conf' / 'config.json'
try:
    with config_path.open('r', encoding='utf-8') as f:
        console = json.load(f).get("console", True)
except Exception:
    pass

if not console:
    hide_console()
    timestamp = datetime.datetime.now().strftime('%Y/%m/%d/tool_%H-%M-%S')
    sys.stdout = open(log_path / f'{timestamp}.txt', 'w', encoding='utf-8')
    sys.stderr = open(log_path / f'{timestamp}_error.txt', 'w', encoding='utf-8')

# Log and data structures
log_dict = {}

data_dict = {
    "current_id": None,
    "is_cover": False,
    "height_hide": False,
    "order_recode": 0,
    "last_mongoid": None,
    "current_weight": 0,
    "shipment_number": "",
    "measuring": False,
    "parcel_object_dict": {
        "mogo_object_id": {
            "length": None,
            "width": None,
            "height": None,
            "weight": None,
            "barcode": None,
            "time": None,
            "pic": {
                "path": None,
                "yolo_save_path": None,
                "lw_h_path": None,
                "scan_path": None,
            }
        }
    }
}

weight_recode_list = []  # len3 间隔1s
laser1_recode_list = []  # 4 0.5s

# Motor status
current_time = int(time.time())
black_motor = {"status": False, "time": current_time}
white_motor = {"status": False, "time": current_time}

# Debug and simulation settings
debug = False
barcode_scan_status = {"top": 0, "bottom": 0, "left": 0, "right": 0, "front": 0, "back": 0}
debug_data = {"height": [], "weight": "0", "lw": [], "laser1": 0, "laser2": 0, "measuring": "未测量", "black_motor": "启动", "white_motor": "启动"}
simulation = {"height": [], "weight": [], "lw": [], "motor": [], "barcode": []}
simulation_temp = True
simulation_temp_data = {"height": [], "weight": [], "lw": [], "motor": [], "barcode": []}
parcel_time_out_recode = current_time

# Event serial numbers
event_serial_number = {
    "di1_in": 1,
    "di1_out": 2,
    "height_in": 3,
    "height_out": 4,
    "barcode_scan_start": 5,
    "length_width_in": 6,
    "length_width_out": 7,
    "barcode_scan_end": 8,
    "di2_in": 9,
    "di2_out": 10,
    "js_enter_barcode": 11,
    "js_do_check_barcode_exist": 12,
    "js_do_pickup": 13
}

# Mode configurations
lw_mode = {
    "lw_050_160": {"spacing": 0.5, "max_len": 160},
    "lw_025_320": {"spacing": 0.25, "max_len": 320}
}

h_mode = {
    "h1_050_160": {"spacing": 0.5, "max_len": 160},
    "h2_050_160": {"spacing": 0.5, "max_len": 160},
    "h2_025_320": {"spacing": 0.25, "max_len": 320}
}

# Audio settings
sounds_list = []
voice_text_list = []

# Bin management
bins_locks = False
bins_list = []
bins_count = []
bins_check = False

# Mutex lock for integrity check
complete_lock = threading.Lock()

# Sorting status
serials_detect_status = False
bin_stop = False

def event_serial_number_show(event):
    return f"{event_serial_number.get(event, 'none')}--"
