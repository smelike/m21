import serial
import time
import json
from pathlib import Path

class WeightSensor:
    def __init__(self, config_path):
        self.config_path = config_path
        self.serial_port = None
        self.baud_rate = 9600  # Default baud rate
        self.timeout = 0.1
        self.cmd = "010300500002c41a"  # Default command to read weight
        self.load_config()
        self.logger("WeightSensor initialized.")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.baud_rate = config.get("baud_rate", self.baud_rate)
                self.timeout = config.get("timeout", self.timeout)
                self.cmd = config.get("cmd", self.cmd)
                self.serial_port = config.get("serial_port")
        except FileNotFoundError:
            self.logger(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError:
            self.logger(f"Error decoding config file: {self.config_path}")

    def logger(self, message):
        log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}"
        print(log_message)
        # Append to log file
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

    def read_weight(self):
        if not self.serial.is_open:
            self.logger("Serial port not open.")
            return None
        try:
            self.serial.write(bytes.fromhex(self.cmd))
            response = self.serial.readall()
            weight = self.parse_weight(response)
            self.logger(f"Weight read: {weight}")
            return weight
        except Exception as e:
            self.logger(f"Error reading weight: {e}")
            return None

    def parse_weight(self, response):
        # Implement your weight parsing logic here
        # This is just a placeholder example
        weight_hex = response.hex()
        weight = int(weight_hex, 16) / 100.0  # Convert to appropriate units
        return weight

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger("Serial port closed.")

    def __del__(self):
        self.close()
        self.logger("WeightSensor object deleted.")

if __name__ == "main":

    # Usage example:
    config_path = "./config.json"
    weight_sensor = WeightSensor(config_path)
    if weight_sensor.connect():
        weight = weight_sensor.read_weight()
        print(f"Measured weight: {weight}")
    else:
        print("Failed to connect to the weight sensor.")
