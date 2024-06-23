import serial
import time
from common import sys_data, fn

class PipelineMotor:
    def __init__(self):
        self.relay_first_list = []
        self.send_time = time.time()
        self.last_di1 = 0
        self.last_di2 = 0
        self.di1 = 0
        self.di2 = 0
        self.t_motor = sys_data.thread_motor

        self.setup_serial()

    def setup_serial(self):
        if sys_data.web_api.config["simulation"] != 2:
            self.motor_serial = serial.Serial(
                sys_data.serial_dict["motor_serial"]["serial_port"],
                sys_data.serial_dict["motor_serial"]["baud_rate"],
                timeout=sys_data.web_api.config.get("motor_serial_timeout", 0.015)
            )
        else:
            self.motor_serial = None

    def run(self):
        while True:
            try:
                response_str = self.read_serial()
                if response_str:
                    self.process_response(response_str)
                time.sleep(0.05)
            except Exception as e:
                self.handle_exception(e)

    def read_serial(self):
        response_str = ""
        if self.relay_first_list:
            cmd = self.relay_first_list.pop(0)
            self.send_serial_command(cmd)
            fn.logger("去皮操作", level='info', r_path=sys_data.r_path)
            time.sleep(0.1)
        elif self.motor_serial:
            response = self.motor_serial.readall()
            response_str = response.hex()
        return response_str

    def send_serial_command(self, cmd):
        if self.motor_serial:
            self.motor_serial.write(bytes.fromhex(cmd))

    def process_response(self, response_str):
        response_array = response_str.split(" ")
        if len(response_array) == 6:
            status_str = bin(int(response_array[-3], 16))[2:].zfill(4)
            current_di1, current_di2 = map(int, status_str[::-1][:2])

            if sys_data.web_api.config.get("relay_debug", False):
                fn.logger(f"current_di1:{current_di1}, current_di2:{current_di2}, response_array:{response_array}", level='info', r_path="D:\\nextsls\\motor_log.txt", print_to_c=False)

            self.update_status(current_di1, current_di2)
            self.check_events(current_di1, current_di2)

    def update_status(self, current_di1, current_di2):
        if time.time() - self.send_time > 0.2:
            self.send_time = time.time()
            sys_data.debug_data["laser1"] = current_di1
            sys_data.debug_data["laser2"] = current_di2

        self.di1 = current_di1
        self.di2 = current_di2

    def check_events(self, current_di1, current_di2):
        if self.last_di1 == 0 and current_di1 == 1:
            self.t_motor.create_thread(func=self.event_di1_in)
        elif self.last_di1 == 1 and current_di1 == 0:
            self.t_motor.create_thread(func=self.event_di1_out)

        if self.last_di2 == 0 and current_di2 == 1:
            self.t_motor.create_thread(func=self.event_di2_in)
        elif self.last_di2 == 1 and current_di2 == 0:
            self.t_motor.create_thread(func=self.event_di2_out)

        self.last_di1 = current_di1
        self.last_di2 = current_di2

    def handle_exception(self, e):
        if sys_data.web_api.config["fail_stop"]:
            sys_data.web_api.stop("电机运行失败_stop")
        fn.logger(f"电机运行失败:{repr(e)}", level='error', r_path=sys_data.r_path)

    def event_di1_in(self):
        fn.logger("DI1进入事件", level='info', r_path=sys_data.r_path)
        # Handle DI1 in event

    def event_di1_out(self):
        fn.logger("DI1离开事件", level='info', r_path=sys_data.r_path)
        # Handle DI1 out event

    def event_di2_in(self):
        fn.logger("DI2进入事件", level='info', r_path=sys_data.r_path)
        # Handle DI2 in event

    def event_di2_out(self):
        fn.logger("DI2离开事件", level='info', r_path=sys_data.r_path)
        # Handle DI2 out event

    def motor_turn_off(self):
        corotation_cmd = 'FE05000200007805'
        self.send_serial_command(corotation_cmd)
        result = self.read_serial()  # Assuming read_serial() will capture the command result
        if "success" in result.lower():
            fn.logger(f"黑皮带电机关闭 成功", level='info', r_path=sys_data.r_path)
        else:
            fn.logger(f"黑皮带电机关闭 失败 命令{corotation_cmd} 结果{result}", level='error', r_path=sys_data.r_path)
        sys_data.black_motor = {"status": False, "time": int(time.time())}
        sys_data.debug_data["black_motor"] = "关闭"

    def take_photo(self):
        fn.logger("执行拍照---", level='info', r_path=sys_data.r_path)
        fn.logger("触发扫码", level='info', r_path=sys_data.r_path)
        self.relay_first_list.extend(['FE05000200007805', 'FE050002FF0039F5'])
        fn.logger("触发扫码完成", level='info', r_path=sys_data.r_path)

    def barcode_scan_start(self):
        sys_data.barcode_scan_status['top'] = time.time()
        self.relay_first_list.append('FE050002FF0039F5')
        fn.logger("扫码进行中", event='barcode_scan_start')

    def barcode_scan_end(self):
        sys_data.barcode_scan_status['top'] = 0
        self.relay_first_list.append('FE05000200007805')
        barcode_scan_delay_second = sys_data.web_api.config.get("barcode_scan_delay_second", 0)
        if barcode_scan_delay_second > 0:
            time.sleep(barcode_scan_delay_second)
        fn.logger("扫码已结束", event='barcode_scan_end')

    def barcode_light_turn_on(self):
        fn.logger("条形码灯开---", level='info', r_path=sys_data.r_path)
        if sys_data.web_api.config["simulation"] != 2:
            self.relay_first_list.append('FE050003FF006835')

    def barcode_light_turn_off(self):
        fn.logger("条形码灯关---", level='info', r_path=sys_data.r_path)
        if sys_data.web_api.config["simulation"] != 2:
            self.relay_first_list.append('FE050003000029C5')


if __name__ == '__main__':
    motor = PipelineMotor()
    motor.run()
    time.sleep(10000)
