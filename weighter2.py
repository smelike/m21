# ```
# 称重类：读取稳定的重量值


# 波特率 19200

# 默认通讯格式：19200,n,8,1


# 指令格式：模块地址+功能代码+数据+CRC16校验


# 读取指令：010300500002c41a

# 串口响应返回，有正数和负数的表示形式。

# 如1：01 03 04 FF FF FF FF FB A7，转换结果是 -0.01kg.

# 如2：01 03 04 00 00 00 C6 7A 61，00 00 00 C6 转换结果是 1.98kg.
# 如3：01 03 04 00 00 00 C5 3A 60，00 00 00 C5 转换结果是 1.97kg



# 动态过程：皮带转动的线速度是一定的，受限于 辊筒的直径大小、电机的主动轮直径、皮带传动的从动轮直径，主动轮的转速又取决于电机的rpm转速设置。



# 1/打开串口，发送读取指令，等待响应返回;

# 2/ 记录指定发出时间，和指令返回时间;

# 3/ 返回响应字节的 3~7 字节，是重量数据，需转换为以 kg 为单位的十进制浮点数;

# 4/ 以[重量值,...]格式记录日志;


# 5/ 获取稳定的重量值，要先获知从货物进入称台，货物在线速度 60m/min的皮带上经过，称台的长度是 1180mm;

# (一件货物在 60m/min 转动的皮带上流动经过，皮带总长度为 1180mm，通过算法计算获取到合适稳定的重量变化值。) 
# # + 添加一个公共方法，返回状态：是否在测量中；

# # + 测量中状态的定义——读取到的重量数据是在做陡峭的上升变化；

# # + 需要将所有解释出来的重量值，按照先后顺序保存到数组，并进行递减的排序保存到新的数组中，获取最稳定变化的数据，即数据是在仪器的分度值(0.01)之内 ，或者配置中指定的数值间隔的分度(0.03)

# 在货物的中心进入称台中间时，获得的数据肯定就是稳定值，所以应该计算获取在称台中间位置所停留的时间点 t/m，进行 t/m +/- x时间的范围取值；


# 计算货物的重心位置：假设货物的长度是 x，称台的长度是 s, x <= s，以固定的运行速度流动通过称台；


# 如何保证是在货物进入称台后，才开始读取数据呢？在 Di1 由 1 变为 0 时？
# ```

import serial
import time
import json
from pathlib import Path
import struct

class WeightSensor:
    def __init__(self, config_path):
        self.config_path = config_path
        self.serial_port = None
        self.baud_rate = 19200
        self.timeout = 0.1
        self.cmd = "010300500002c41a"
        self.load_config()
        self.logger("WeightSensor initialized.")

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.serial_port = config.get("serial_port")
                self.baud_rate = config.get("baud_rate", self.baud_rate)
                self.timeout = config.get("timeout", self.timeout)
                self.cmd = config.get("cmd", self.cmd)
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
            start_time = time.time()
            self.serial.write(bytes.fromhex(self.cmd))
            response = self.serial.read(9)  # Read expected 9 bytes response
            end_time = time.time()
            self.logger(f"Command sent at {start_time}, response received at {end_time}")
            weight = self.parse_weight(response)
            self.logger(f"Weight read: {weight}")
            return weight
        except Exception as e:
            self.logger(f"Error reading weight: {e}")
            return None

    def parse_weight(self, response):
        if len(response) != 9:
            self.logger(f"Unexpected response length: {len(response)}")
            return None
        try:
            # Extract the 3rd to 7th bytes and convert to a float representing kg
            weight_bytes = response[3:7]
            weight_int = struct.unpack('>f', weight_bytes)[0]
            weight_kg = weight_int / 100.0  # Convert to kg
            return weight_kg
        except Exception as e:
            self.logger(f"Error parsing weight: {e}")
            return None

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger("Serial port closed.")

    def __del__(self):
        self.close()
        self.logger("WeightSensor object deleted.")

# Usage example:
config_path = "./config.json"
weight_sensor = WeightSensor(config_path)
if weight_sensor.connect():
    weight = weight_sensor.read_weight()
    print(f"Measured weight: {weight}")
else:
    print("Failed to connect to the weight sensor.")
