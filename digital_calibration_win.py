import serial
import struct
import time
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DigitalCalibration:
    def __init__(self, port, baudrate=19200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.open_serial()

    def open_serial(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            logging.info(f'Serial port {self.port} opened successfully.')
        except Exception as e:
            logging.error(f'Error opening serial port: {e}')
            sys.exit(1)

    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logging.info(f'Serial port {self.port} closed.')

    def calculate_sensitivity(self, sensor_capacity, sensor_count, max_load):
        sensitivity = 2.0 / (sensor_capacity * sensor_count)  # mv/V
        sensitivity_value = sensitivity * max_load  # mv/V for the given max load
        sensitivity_value *= 1000  # scale by 1000
        sensitivity_hex = struct.pack('>H', int(sensitivity_value))
        logging.info(f'Sensitivity (mv/V): {sensitivity_value} - Hex: {sensitivity_hex.hex()}')
        return sensitivity_hex

    def calculate_load_capacity(self, max_load):
        max_load_value = int(max_load * 1000)  # scale by 1000 to get in g
        max_load_hex = struct.pack('>H', max_load_value)
        logging.info(f'Max Load (g): {max_load_value} - Hex: {max_load_hex.hex()}')
        return max_load_hex

    def calculate_crc(self, data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return struct.pack('<H', crc)

    def send_command(self, command):
        crc = self.calculate_crc(command)
        full_command = command + crc
        logging.info(f'Sending command: {full_command.hex()}')
        self.ser.write(full_command)
        response = self.ser.read(8)
        logging.info(f'Response: {response.hex()}')
        return response

    def calibrate(self, sensor_capacity, sensor_count, sensitivity, max_load):
        sensitivity_hex = self.calculate_sensitivity(sensor_capacity, sensor_count, sensitivity)
        load_hex = self.calculate_load_capacity(max_load)

        # Command for sensitivity
        sensitivity_command = b'\x01\x10\x00\x2E\x00\x02\x04' + sensitivity_hex
        self.send_command(sensitivity_command)

        # Command for load capacity
        load_command = b'\x01\x10\x00\x30\x00\x02\x04' + load_hex
        self.send_command(load_command)

        # Set max weighing capacity
        max_weighing_command = b'\x01\x10\x00\x56\x00\x02\x04' + load_hex
        self.send_command(max_weighing_command)

        # Set scale division
        division_command = b'\x01\x10\x00\x58\x00\x01\x02\x00\x06'  # Assuming 0.01
        self.send_command(division_command)

        # Manual zeroing
        zeroing_command = b'\x01\x10\x00\x5E\x00\x01\x02\x00\x01'
        self.send_command(zeroing_command)

    def listen_and_calibrate(self):
        if len(sys.argv) != 5:
            logging.error('Invalid number of arguments. Expected: sensor_capacity, sensor_count, sensitivity, max_load')
            sys.exit(1)

        sensor_capacity = float(sys.argv[1])
        sensor_count = int(sys.argv[2])
        sensitivity = float(sys.argv[3])
        max_load = float(sys.argv[4])

        self.calibrate(sensor_capacity, sensor_count, sensitivity, max_load)

if __name__ == '__main__':
    calibration = DigitalCalibration(port='COM3')
    calibration.listen_and_calibrate()
    calibration.close_serial()

# 使用说明
# 将此代码保存为 digital_calibration.py。
# 打开命令行终端并导航到保存该文件的目录。
# 运行命令，例如：python digital_calibration.py 100 4 2.0 40，其中参数依次为传感器量程、传感器数量、传感器灵敏度和最大量程。