import serial
import time
import json
from pathlib import Path
import statistics
import DeviceStatusMonitor


class WeightSensor:
    # 分度值
    DIVISION_MAP = {
        0x00: 0.0001, 0x01: 0.0002, 0x02: 0.0005,
        0x03: 0.001,  0x04: 0.002,  0x05: 0.005,
        0x06: 0.01,   0x07: 0.02,   0x08: 0.05,
        0x09: 0.1,    0x0A: 0.2,    0x0B: 0.5,
        0x0C: 1,      0x0D: 2,      0x0E: 5,
        0x0F: 10,     0x10: 20,     0x11: 50
    }
    # 重量单位
    UNIT_MAP = {
        0: 'none', 1: 'g', 2: 'kg', 3: 't', 4: 'N'
    }

    def __init__(self, config_path):
        self.config_path = config_path
        self.serial_port = None
        self.baud_rate = 19200
        self.timeout = 0.1
        self.read_weight_cmd = "010300500002c41a"
        self.read_division_cmd = "01030058000105D9"
        self.read_unit_cmd = "01030068000105D6"
        self.set_unit_cmd_template = "0110006800010200016F78"  # Template for setting unit
        self.division_value = 1.0  # Default division value
        self.unit = 'kg'  # Default unit
        self.load_config()
        self.logger("WeightSensor initialized.")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.serial_port = config.get("serial_port")
                self.baud_rate = config.get("baud_rate", self.baud_rate)
                self.timeout = config.get("timeout", self.timeout)
                self.read_weight_cmd = config.get("read_weight_cmd", self.read_weight_cmd)
                self.read_division_cmd = config.get("read_division_cmd", self.read_division_cmd)
                self.read_unit_cmd = config.get("read_unit_cmd", self.read_unit_cmd)
                self.set_unit_cmd_template = config.get("set_unit_cmd_template", self.set_unit_cmd_template)
        except FileNotFoundError:
            self.logger(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError:
            self.logger(f"Error decoding config file: {self.config_path}")

    def logger(self, message):
        log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
        print(log_message)
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "weight_sensor.log", "a", encoding='utf-8') as log_file:
            log_file.write(log_message + "\n")

    def connect(self):
        if not self.serial_port:
            self.logger("No serial port specified.")
            return False
        try:
            self.serial = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=self.timeout
            )
            self.logger(f"Connected to {self.serial_port} at {self.baud_rate} baud.")
            return True
        except serial.SerialException as e:
            self.logger(f"Failed to connect to {self.serial_port}: {e}")
            return False

    def read_division_value(self):
        if not self.serial.is_open:
            self.logger("Serial port not open.")
            return False
        try:
            self.serial.write(bytes.fromhex(self.read_division_cmd))
            response = self.serial.read(7)  # Read expected 7 bytes response
            if len(response) == 7 and response[0:2] == bytes.fromhex("0103"):
                division_hex = response[4]
                self.division_value = self.DIVISION_MAP.get(division_hex, 1.0)
                self.logger(f"Division value read: {self.division_value}")
                return True
            else:
                self.logger("Failed to read division value.")
                return False
        except Exception as e:
            self.logger(f"Error reading division value: {e}")
            return False

    def read_weight_unit(self):
        if not self.serial.is_open:
            self.logger("Serial port not open.")
            return False
        try:
            self.serial.write(bytes.fromhex(self.read_unit_cmd))
            response = self.serial.read(7)  # Read expected 7 bytes response
            if len(response) == 7 and response[0:2] == bytes.fromhex("0103"):
                unit_hex = response[3]
                self.unit = self.UNIT_MAP.get(unit_hex, 'kg')  # Default to kg if unknown unit
                self.logger(f"Weight unit read: {self.unit}")
                return True
            else:
                self.logger("Failed to read weight unit.")
                return False
        except Exception as e:
            self.logger(f"Error reading weight unit: {e}")
            return False

    def set_weight_unit(self, unit):
        if not self.serial.is_open:
            self.logger("Serial port not open.")
            return False
        unit_code = next((k for k, v in self.UNIT_MAP.items() if v == unit), None)
        if unit_code is None:
            self.logger(f"Invalid unit: {unit}")
            return False
        set_unit_cmd = self.set_unit_cmd_template[:14] + f"{unit_code:02X}" + self.set_unit_cmd_template[16:]
        try:
            self.serial.write(bytes.fromhex(set_unit_cmd))
            response = self.serial.read(8)  # Read expected 8 bytes response
            if len(response) == 8 and response[0:2] == bytes.fromhex("0110"):
                self.unit = unit
                self.logger(f"Weight unit set to: {self.unit}")
                return True
            else:
                self.logger("Failed to set weight unit.")
                return False
        except Exception as e:
            self.logger(f"Error setting weight unit: {e}")
            return False

    def read_weight(self):
        if not self.serial.is_open:
            self.logger("Serial port not open.")
            return None
        try:
            start_time = time.time()
            self.serial.write(bytes.fromhex(self.read_weight_cmd))
            response = self.serial.read(9)  # Read expected 9 bytes response
            end_time = time.time()
            self.logger(f"Command sent at {start_time}, response received at {end_time}")
            weight = self.parse_weight(response)
            self.logger(f"Weight read: {weight} {self.unit}")
            return weight
        except Exception as e:
            self.logger(f"Error reading weight: {e}")
            return None

    def parse_weight(self, response):
        if len(response) != 9:
            self.logger(f"Unexpected response length: {len(response)}")
            return None
        try:
            # Extract the 3rd to 6th bytes and convert to integer
            weight_bytes = response[3:7]
            weight_int = int.from_bytes(weight_bytes, byteorder='big', signed=False)

            # Check if the number is negative (two's complement)
            if weight_int & 0x80000000:
                weight_int = -((~weight_int & 0xFFFFFFFF) + 1)

            weight_kg = weight_int * self.division_value  # Convert using the division value
            return weight_kg
        except Exception as e:
            self.logger(f"Error parsing weight: {e}")
            return None

    def sample_weight(self, duration):
        weights = []
        start_time = time.time()
        end_time = start_time + duration
        while time.time() < end_time:
            weight = self.read_weight()
            if weight is not None:
                weights.append(weight)
            time.sleep(0.05)  # Adjust sleep time as needed for your sampling rate
        print("sample_weight:", weights, len(weights))
        return weights

    def get_stable_weight(self, weights):
        if not weights:
            self.logger("No weights sampled.")
            return None
        stable_weight = statistics.median(weights)  # You can also use other methods like mean
        self.logger(f"Stable weight determined: {stable_weight}")
        return stable_weight

    def measure_weight(self, belt_speed_m_per_min, belt_length_mm):
        duration = belt_length_mm / (belt_speed_m_per_min * 1000 / 60)  # Calculate duration in seconds
        self.logger(f"Sampling for {duration} seconds.")
        if self.read_division_value() and self.read_weight_unit():
            weights = self.sample_weight(duration)
            stable_weight = self.get_stable_weight(weights)
            return stable_weight
        else:
            self.logger("Failed to read division value or weight unit.")
            return None

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger("Serial port closed.")

    def __del__(self):
        self.close()
        self.logger("WeightSensor object deleted.")


config_path = "./device_config.json"
device_monitor = DeviceStatusMonitor(config_path)

# Usage example:
config_path = "./config.json"
weight_sensor = WeightSensor(config_path)

if device_monitor.connect():
    # device_monitor.monitor_status(interval=0.03)
    status = device_monitor.read_device_status()
    print(status)
    weight_sensor.sample_weight(3000)
else:
    print("Failed to connect to the device.")

exit(909090)
if device_monitor.read_device_status() == '01':
    weight_sensor.sample_weight(3)

if weight_sensor.connect():
    # weight_sensor.set_weight_unit('kg')
    stable_weight = weight_sensor.measure_weight(60, 2660)
    print(f"Measured stable weight: {stable_weight} {weight_sensor.unit}")
else:
    print("Failed to connect to the weight sensor.")
