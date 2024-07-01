import time
import logging
import json
import serial

class DeviceStatusMonitor:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()
        self.serial = None
        self.setup_logger()
        
    def setup_logger(self):
        logging.basicConfig(filename=self.log_file, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s: %(message)s')
        self.logger = logging.getLogger()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            print(config)
        self.port = config.get('port')
        self.baudrate = config.get('baudrate', 9600)
        self.timeout = config.get('timeout', 0.1)
        self.log_file = config.get('log_file', 'device_status.log')

    def connect(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.logger.info(f"Connected to serial port {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to serial port {self.port}: {e}")
            return False

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger.info("Serial port closed")

    def send_command(self, command):
        if self.serial and self.serial.is_open:
            self.serial.write(command)
            self.logger.info(f"Sent command: {command}")
            return self.serial.readall()
        else:
            self.logger.error("Serial port is not open")
            return None

    def read_device_status(self):
        # FE 02 00 00 00 04 6D C6
        command = b'\xFE\x02\x00\x00\x00\x04\x6D\xC6'  # Example command to read device status
        response = self.send_command(command)
        if response:
            status = self.parse_status_response(response)
            self.logger.info(f"Device status: {status}")
            return status
        else:
            self.logger.error("Failed to read device status")
            return None

    def parse_status_response(self, response):
        # Parse the response from the device
        if len(response) < 6:
            self.logger.error(f"Invalid response length: {len(response)}")
            return None
        
        address = response[0]
        function_code = response[1]
        data_length = response[2]
        data = response[3:3 + data_length]
        crc = response[-2:]
        
        # Assuming status is in the data part of the response
        status = data.hex()
        self.logger.debug(f"Parsed status: {status}")
        return status

    def monitor_status(self, interval=0.05):
        status_set = set()
        while True:
            status = self.read_device_status()
            status_set.add(status)
            # 00-01-02 属于正常的过货发生的状态
            # 00-02 或 00-02-01 代表光电被遮挡了
            # 02 - 遮挡
            if status:
                print(f"Current device status: {status}")
                print(status_set)
                if len(status_set) == 3:
                    self.logger.debug(f"Parsed status: {status_set}")
                    print(status_set)
                    if not(status in ['01', '02']): status_set.clear()
            # 在何时清空 set
            time.sleep(interval)

    def __del__(self):
        self.disconnect()
        self.logger.info("DeviceStatusMonitor object deleted")

if __name__ == "main":
    # Usage example:
    config_path = "./device_config.json"
    device_monitor = DeviceStatusMonitor(config_path)
    if device_monitor.connect():
        device_monitor.monitor_status(interval=0.03)
    else:
        print("Failed to connect to the device.")
