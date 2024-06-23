import math
import serial
import time
from common import sys_data, data_parse, fn
from copy import deepcopy
from models import pipeline_record_model

class Weigh:
    def __init__(self):
        self.current_id = None
        self.min_weight = sys_data.web_api.config.get("min_weight", 0)
        self.weight_serial = None

        if sys_data.web_api.config["simulation"] != 2:
            self.weight_serial = serial.Serial(
                sys_data.serial_dict["weight_serial"]["serial_port"],
                sys_data.serial_dict["weight_serial"]["baud_rate"],
                timeout=sys_data.web_api.config.get("weight_serial_timeout", 0.015)
            )

        self.weight_data = []
        self.weight_serial_first = []
        self.t_motor = sys_data.thread_motor
        self.last_weight = 0
        self.send_time = time.time()
        self.recode = False
        self.effective_values = []
        self.current_weight = False

        module_config = sys_data.web_api.config["weight_module"]
        self.weight_module = module_config
        self.msg = {
            'xy': "010300000002c40b",
            't90': "010300000001840a",
            'kpr': "010300500002c41a"
        }.get(module_config, "010300500002c41a")

        if sys_data.web_api.config["simulation"] == 2:
            self.d_value_time = time.time() - float(sys_data.simulation["weight"][0][1])

    def run(self):
        last_count_time = 0
        serial_read_speed_interval = 5
        serial_read_speed_count = 0
        while True:
            try:
                response_str = ""
                if self.weight_serial_first:
                    msg_data = self.weight_serial_first.pop(0)
                    self.weight_write(msg_data)
                    fn.logger(f"去皮操作", level='info', r_path=sys_data.r_path)
                    time.sleep(0.1)
                    continue

                if sys_data.web_api.config["simulation"] != 2:
                    self.weight_write(self.msg)
                    response = self.weight_serial.readall()
                    response_str = response.hex()
                else:
                    # Simulation mode processing
                    pass

                if response_str:
                    weight = self.parse_weight(response_str)
                    if weight is not None:
                        self.process_weight(weight)

                self.adjust_serial_read_speed(serial_read_speed_interval, serial_read_speed_count)
                time.sleep(0.05)

            except Exception as e:
                self.handle_exception(e)

    def weight_write(self, msg_data):
        if self.weight_serial:
            self.weight_serial.write(bytes.fromhex(msg_data))

    def parse_weight(self, response_str):
        # Your logic to parse weight from response_str
        pass

    def process_weight(self, weight):
        # Your logic to process weight
        pass

    def adjust_serial_read_speed(self, interval, count):
        count += 1
        if count >= interval:
            count = 0
            # Adjust serial read speed logic
        return count

    def handle_exception(self, e):
        if sys_data.web_api.config["fail_stop"]:
            sys_data.web_api.stop("重量测量失败_stop")
        data_parse.update_status_info(self.current_id, status=0, info=f"重量测量失败:{e}")
        fn.logger(f"重量测量失败:{repr(e)}", level='error', r_path=sys_data.r_path)
        sys_data.web_api.parcel_update_data(self.current_id)

    @staticmethod
    def adjust_values(weight):
        weight += sys_data.web_api.config['weight_adjust_value']
        weight = data_parse.adapt_value('weight', weight)
        return weight


if __name__ == "__main__":
    weighting = Weigh()
    weighting.run()
    time.sleep(10000)
