根据文档的说明，这里提供了优化和修改后的设备状态监听类。这个类会实时读取 DI1 和 DI2 的状态，并将状态值保存到一个唯一数组中。

[+]需要调用称重测量类，以确定是否在称重测量中。
```python
import serial
import struct
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DeviceStatusMonitor:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.di1_status = 0
        self.di2_status = 0
        self.weighing_status = 0
        self.states = set()
        self.open_serial()

    def open_serial(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            logging.info(f'Serial port {self.port} opened successfully.')
        except Exception as e:
            logging.error(f'Error opening serial port: {e}')

    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logging.info(f'Serial port {self.port} closed.')

    def calculate_crc(self, data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return struct.pack('<H', crc)

    def send_command(self, command):
        crc = self.calculate_crc(command)
        full_command = command + crc
        self.ser.write(full_command)
        logging.info(f'Sent command: {full_command.hex()}')
        return self.ser.read(7)

    def parse_response(self, response):
        if len(response) != 7:
            logging.error(f'Invalid response length: {len(response)}')
            return None
        addr, func, byte_count, status, crc1, crc2 = struct.unpack('>BBBHB', response[:6])
        if self.calculate_crc(response[:5]) != response[5:7]:
            logging.error('CRC check failed')
            return None
        return status

    def update_status(self):
        command = b'\xFE\x02\x00\x00\x00\x04'
        response = self.send_command(command)
        status = self.parse_response(response)
        if status is not None:
            self.di1_status = status & 0b0001
            self.di2_status = (status & 0b0010) >> 1
            self.states.add((self.di1_status, self.di2_status, self.weighing_status))
            logging.info(f'DI1: {self.di1_status}, DI2: {self.di2_status}, Weighing: {self.weighing_status}')
            self.control_logic()

    def control_logic(self):
        if self.di1_status == 1 and self.di2_status == 0:
            self.weighing_status = 1
        elif self.di1_status == 0 and self.weighing_status == 1:
            self.di2_status = 1
        if self.di2_status == 1:
            if self.di1_status == 1:
                logging.info('Stopping motor')
                # Add motor control code here

    def run(self):
        try:
            while True:
                self.update_status()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.close_serial()

if __name__ == '__main__':
    monitor = DeviceStatusMonitor('COM3')  # Replace 'COM3' with your serial port
    monitor.run()
```

在这个类中：
- `DeviceStatusMonitor` 初始化并打开串口通信。
- `calculate_crc` 方法计算命令的 CRC 校验码。
- `send_command` 方法发送命令并读取响应。
- `parse_response` 方法解析响应并进行 CRC 校验。
- `update_status` 方法更新 DI1 和 DI2 的状态，并将状态保存到 `states` 集合中，确保值唯一。
- `control_logic` 方法根据状态执行控制逻辑。
- `run` 方法循环调用 `update_status` 更新状态。

这样，设备状态监听类就可以实时读取 DI1 和 DI2 的状态，并确保状态值唯一，同时根据状态执行相应的控制逻辑。