import serial
import time
import struct
import sys

class DigitalCalibration:
    def __init__(self, port, baudrate=19200):
        self.port = port
        self.baudrate = baudrate
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.log = []

    def log_message(self, message):
        self.log.append(message)
        print(message)

    def send_command(self, command):
        self.ser.write(command)
        self.log_message(f"Sent: {command.hex()}")
        response = self.ser.read(8)  # Assuming response length is 8 bytes
        self.log_message(f"Received: {response.hex()}")
        return response

    def calculate_sensitivity(self, single_sensor_capacity, num_sensors, sensor_sensitivity, max_capacity):
        sensitivity = sensor_sensitivity / (single_sensor_capacity * num_sensors)
        total_sensitivity = sensitivity * max_capacity
        return int(total_sensitivity * 1000)

    def calculate_hex_value(self, value):
        return struct.pack('>H', value).hex()

    def sensitivity_command(self, sensitivity):
        sensitivity_hex = self.calculate_hex_value(sensitivity)
        command = bytes.fromhex(f"01 10 00 2E 00 02 04 00 00 {sensitivity_hex} F3 66")
        return command

    def capacity_command(self, capacity):
        capacity_hex = self.calculate_hex_value(capacity)
        command = bytes.fromhex(f"01 10 00 30 00 02 04 00 00 {capacity_hex} EA 87")
        return command

    def max_capacity_command(self, max_capacity):
        max_capacity_hex = self.calculate_hex_value(max_capacity)
        command = bytes.fromhex(f"01 10 00 56 00 02 04 00 00 {max_capacity_hex} 6C 85")
        return command

    def start_calibration(self, single_sensor_capacity, num_sensors, sensor_sensitivity, max_capacity):
        sensitivity = self.calculate_sensitivity(single_sensor_capacity, num_sensors, sensor_sensitivity, max_capacity)
        self.log_message(f"Calculated Sensitivity: {sensitivity}")
        
        sensitivity_cmd = self.sensitivity_command(sensitivity)
        self.send_command(sensitivity_cmd)

        capacity = max_capacity * 1000  # Convert to appropriate unit
        self.log_message(f"Capacity (in g): {capacity}")

        capacity_cmd = self.capacity_command(capacity)
        self.send_command(capacity_cmd)

        max_capacity_cmd = self.max_capacity_command(capacity)
        self.send_command(max_capacity_cmd)

        self.log_message("Calibration completed.")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python calibration.py <single_sensor_capacity> <num_sensors> <sensor_sensitivity> <max_capacity>")
        sys.exit(1)

    single_sensor_capacity = float(sys.argv[1])
    num_sensors = int(sys.argv[2])
    sensor_sensitivity = float(sys.argv[3])
    max_capacity = float(sys.argv[4])

    calibration = DigitalCalibration(port='/dev/ttyS1')  # Replace with the appropriate port
    calibration.start_calibration(single_sensor_capacity, num_sensors, sensor_sensitivity, max_capacity)
