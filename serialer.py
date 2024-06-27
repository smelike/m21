# 为了提高代码的效率和可读性，可以使用面向对象编程（OOP）将功能封装在类中。以下是重新设计的代码，使用类、面向对象编程、日志方法、以及封装的串口操作函数：

# ```python
import copy
import json
import os
import time
from pathlib import Path

import serial
import serial.tools.list_ports
# from common import fn, data_parse, sys_data
# from device import crc_16

class SerialManager:
    def __init__(self):
        self.comconf_log_path = fn.format_path(sys_data.base_path + "/log/comconf.json")
        self.serials_dict = {
            "lightCurtainHeightPrefix": "", "height_serial": dict(), 
            "length_width_serial": dict(), "weight_serial": dict(), 
            "relay_serial": dict(), "motor_serial": dict()
        }
        self.bin_serials_dict = dict()
        self.exclusive_coms = list()
        self.log_path = fn.format_path(sys_data.base_path + "/log/serials_log.txt")
        self.serials_motor = fn.thread_motor()

    def log_message(self, message, level="debug"):
        fn.logger(message, level=level, r_path=sys_data.r_path)

    def load_serial(self):
        sys_data.serials_detect_status = True
        self.exclusive_coms = list()
        task_list = list()
        self.bin_serials_dict = {10: {}}
        port_len = int(sys_data.web_api.config.get("bin_len", 7) - 1 / 2)
        for i in range(port_len):
            self.bin_serials_dict[i + 11] = dict()

        port_list = list(serial.tools.list_ports.comports())
        for port in port_list:
            rcode_port = port.device
            if rcode_port not in self.exclusive_coms:
                task_list.append(self.serials_motor.create_thread(func=self.do_serials_detecter, rcode_port=rcode_port))

        self.wait_for_tasks(task_list)

        self.assign_predefined_serials()
        self.clean_up_empty_bin_serials()

        self.log_message(f"DWS检测结果:{self.serials_dict}")
        self.log_message(f"实物分拣检测结果:{self.bin_serials_dict}")

        self.write_serial_log()
        self.update_pipelinebin_config()

        return self.serials_dict

    def wait_for_tasks(self, task_list):
        start_time = int(time.time())
        while True:
            if int(time.time()) - start_time > 10 or all(not task.is_alive() for task in task_list):
                break
            time.sleep(0.1)

    def assign_predefined_serials(self):
        if sys_data.web_api.config.get("given_weight_serial", ""):
            self.serials_dict['weight_serial'] = {
                "serial_port": sys_data.web_api.config["given_weight_serial"],
                "baud_rate": sys_data.web_api.config.get("given_weight_baud_rate", 19200)
            }
        if sys_data.web_api.config.get("given_height_serial", ""):
            self.serials_dict["height_serial"]["serial_port"] = sys_data.web_api.config["given_height_serial"]

    def clean_up_empty_bin_serials(self):
        self.bin_serials_dict = {k: v for k, v in self.bin_serials_dict.items() if v}

    def write_serial_log(self):
        serial_str = "重量:" + json.dumps(self.serials_dict['weight_serial'])
        serial_str += "\n长宽:" + json.dumps(self.serials_dict['length_width_serial'])
        serial_str += "\n高度:" + json.dumps(self.serials_dict['height_serial'])
        serial_str += "\n继电器:" + json.dumps(self.serials_dict['relay_serial'])
        if self.serials_dict.get("motor_serial", None):
            serial_str += "\n电机:" + json.dumps(self.serials_dict['motor_serial'])
            if not sys_data.web_api.config["motor_cfg"]:
                sys_data.web_api.config["motor_cfg"] = {
                    "mod3": {
                        "corotation": True,
                        "addr": "2",
                        "com": self.serials_dict['motor_serial']['serial_port']
                    },
                    "mod2": {
                        "corotation": True,
                        "addr": "1",
                        "com": self.serials_dict['motor_serial']['serial_port']
                    }
                }
        self.log_message(f"DWS检测结果:{serial_str}")
        self.log_message(f"实物分拣检测结果:{self.bin_serials_dict}")
        Path(fn.format_path(sys_data.base_path + "/log/")).mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w+", encoding='utf-8') as f:
            f.write(serial_str)

    def update_pipelinebin_config(self):
        config_path = fn.format_path(r"C:\nextsls\pipelinebin\conf\config.json")
        if os.path.exists(config_path) and self.bin_serials_dict:
            try:
                with open(config_path, "r", encoding='utf-8') as f:
                    bin_config = json.load(f)
                if bin_config["motor_cfg"]:
                    self.log_message(f"bin配置不为空,pipelinbin不能配置")
                else:
                    self.log_message(f"更改一次pipelinbin配置")
                    bin_serails_list = sorted(self.bin_serials_dict.keys(), key=int)
                    for i, addr in enumerate(bin_serails_list):
                        bin_config["motor_cfg"][str(i)] = {
                            "corotation": True,
                            "speed": 2500,
                            "addr": addr,
                            "turn_type": "sniki",
                            "com": self.bin_serials_dict[addr]["serial_port"],
                            "baudate": self.bin_serials_dict[addr]["baud_rate"]
                        }
                    bin_config["motor_cfg"]["0"]["turn_type"] = None
                    with open(config_path, "w", encoding='utf-8') as f:
                        json.dump(bin_config, f, indent=1, ensure_ascii=False)
            except Exception as e:
                self.log_message(f"pipelinebin json解析出现错误:{str(e)}")

    def do_serials_detecter(self, rcode_port):
        try:
            self.detect_length_width(rcode_port)
            self.detect_relay(rcode_port)
            self.detect_motor(rcode_port)
            self.detect_weight(rcode_port)
            self.detect_height(rcode_port)
            self.detect_bin_serial(rcode_port)
            sys_data.serials_detect_status = False
        except Exception as e:
            self.log_message(f"do_serials_detecter 串口{rcode_port}发生错误： 错误原因：{str(e)}")

    def detect_length_width(self, rcode_port):
        if not self.serials_dict['length_width_serial']:
            result = self.read_serial(rcode_port, 115200, 0.05)
            if len(result) > 100:
                self.serials_dict['length_width_serial'] = {"serial_port": rcode_port, "baud_rate": 115200, "cmd": None, "timeout": 0.05}

    def detect_relay(self, rcode_port):
        if not self.serials_dict['relay_serial']:
            result = self.write_and_read_serial(rcode_port, 9600, 'FE0100000002A9C4', 0.05)
            if len(result) == 18:
                self.serials_dict['relay_serial'] = {"serial_port": rcode_port, "baud_rate": 9600, "cmd": 'FE0100000002A9C4', "timeout": 0.05}

    def detect_motor(self, rcode_port):
        if not self.serials_dict['motor_serial']:
            result = self.write_and_read_serial(rcode_port, 19200, '0106200000054209', 0.05)
            if result.replace(" ", "") == '0106200000054209':
                self.serials_dict['motor_serial'] = {"serial_port": rcode_port, "baud_rate": 19200, "cmd": '0106200000054209', "timeout": 0.05}

    def detect_weight(self, rcode_port):
        if not self.serials_dict['weight_serial']:
            result = self.write_and_read_serial(rcode_port, 19200, '010300500002c41a', 0.1, retries=5)
            if len(result) > 0:
                self.serials_dict['weight_serial'] = {"serial_port": rcode_port, "baud_rate": 19200, "cmd": '010300500002c41a', "timeout": 0.1}
            result = self.write_and_read_serial(rcode_port, 57600, '0106200000054209', 0.1)
            if result.replace(" ", "") == '0106200000054209':
                self.serials_dict['weight_serial'] = {"serial_port": rcode_port, "baud_rate": 57600, "cmd": '0106200000054209', "timeout": 0.1}
            result = self.write_and_read_serial(rcode_port, 9600, '010300500002c41a', 0.1, retries=5)
            if len(result) >= 14:
                self.serials_dict['weight_serial'] = {"serial_port": rcode_port, "baud_rate": 9600, "cmd": '010300500002c41a', "timeout": 0.1}

    def detect_height(self, rcode_port):
        if not self.serials_dict['height_serial']:
            result = self.read_serial(rcode_port, 115

200, 0.2, 5)
            if result and result[0:1] == b'a' and len(result) > 2:
                self.serials_dict['height_serial'] = {"serial_port": rcode_port, "baud_rate": 115200, "cmd": None, "timeout": 0.2}

    def detect_bin_serial(self, rcode_port):
        result = self.write_and_read_serial(rcode_port, 115200, '0A0312000000', 0.2)
        if len(result) > 0 and result[1] == 3 and result[2] == 2:
            addr = result[0]
            self.bin_serials_dict[addr] = {"serial_port": rcode_port, "baud_rate": 115200}

    def read_serial(self, rcode_port, baud_rate, timeout, retries=1):
        result = b''
        for _ in range(retries):
            with serial.Serial(rcode_port, baud_rate, timeout=timeout) as ser:
                result = ser.read(150)
            if result:
                break
        return result

    def write_and_read_serial(self, rcode_port, baud_rate, cmd, timeout, retries=1):
        result = b''
        for _ in range(retries):
            with serial.Serial(rcode_port, baud_rate, timeout=timeout) as ser:
                ser.write(bytes.fromhex(cmd))
                result = ser.read(150)
            if result:
                break
        return result

    def bin_speed(self, motor_address, rpm=2500):
        speed_hex = f"{rpm:04x}"
        cmd = f"{motor_address:02x}062000{speed_hex}"
        return cmd + crc_16.get_crc16_modbus(cmd)


if __name__ == '__main__':
    serial_manager = SerialManager()
    start_time = time.time()
    serials = serial_manager.load_serial()
    print(f"Serial detection and configuration took {time.time() - start_time} seconds")
```

### 代码解释

1. **SerialManager 类**:
   - **__init__**: 初始化类，定义全局变量。
   - **log_message**: 日志记录方法。
   - **load_serial**: 主函数，检测并配置串口设备。
   - **wait_for_tasks**: 等待所有检测任务完成。
   - **assign_predefined_serials**: 分配预定义的串口。
   - **clean_up_empty_bin_serials**: 清理空的 bin 串口。
   - **write_serial_log**: 写入串口检测结果日志。
   - **update_pipelinebin_config**: 更新 pipelinebin 配置文件。
   - **do_serials_detecter**: 检测单个串口，识别设备。
   - **detect_length_width**: 检测长宽设备。
   - **detect_relay**: 检测继电器设备。
   - **detect_motor**: 检测电机设备。
   - **detect_weight**: 检测称重设备。
   - **detect_height**: 检测高度设备。
   - **detect_bin_serial**: 检测 bin 串口设备。
   - **read_serial**: 读取串口数据。
   - **write_and_read_serial**: 写入并读取串口数据。
   - **bin_speed**: 生成设置电机速度的命令。

通过这种方式，将代码组织得更加模块化和可维护，每个功能都清晰地封装在相应的方法中，日志记录也在每个方法执行后自动调用。