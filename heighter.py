import math
import time
import serial
from datetime import datetime
from copy import deepcopy
from common import fn, data_parse
import common.data_parse
from common import sys_data
from models import pipeline_record_model


class HeightLightCurtain:
    def __init__(self):
        self.weight_obj = None
        self.data = []  # [lowest point, highest point, blocked point, timestamp]
        self.h_serial = None
        self._initialize_serial()
        self.last_blocked_points = 0
        self.faze_count = 0
        self.t_motor = sys_data.thread_motor
        self.h_data = []  # [blocked point, blocked point, blocked point]
        self.low_data = []  # [lowest point, lowest point, lowest point]
        self.recode = False
        if sys_data.web_api.config["simulation"] == 2:
            self.d_value_time = time.time() - float(sys_data.simulation["height"][0][1])

    def _initialize_serial(self):
        if sys_data.web_api.config["simulation"] != 2:
            self.h_serial = serial.Serial(
                sys_data.serial_dict["height_serial"]["serial_port"], 115200,
                timeout=sys_data.web_api.config.get("relay_serial_timeout", 0.03)
            )

    def run(self):
        if sys_data.web_api.config["simulation"] != 2:
            msg = self._get_serial_msg()
        last_count_time = 0
        serial_read_speed_interval = 5
        serial_read_speed_count = 0

        while True:
            if sys_data.web_api.config.get("simulation") not in [0, 1, 2]:
                fn.logger("config 配置缺少simulation配置", level="error")

            response_str = self._get_response_str(msg)

            data_array = response_str.split(" ")
            if sys_data.web_api.config.get("h_curtain_debug", False):
                fn.logger(f"{response_str}", level='info', r_path=r"D:\nextsls\h_curtain_log.txt", print_to_c=False)

            data_count = int(data_array[2], 16) / 3
            if len(data_array) == data_count * 3 + 5:
                self._process_data(data_array, data_count)

            if sys_data.debug and len(fn.debug_levels) > 0:
                serial_read_speed_count += 1
                int_time = int(time.time())
                if int_time != last_count_time and int_time % serial_read_speed_interval == 0:
                    last_count_time = int_time
                    fn.dp('height serial read speed count', serial_read_speed_count, level='height_serial_speed')
                    serial_read_speed_count = 0
            time.sleep(0.01)

    def _get_serial_msg(self):
        msg = "03030000000F042C"
        prefix = sys_data.serial_dict['lightCurtainHeightPrefix']
        if prefix == "01":
            msg = '01030000000F05CE'
        elif prefix == '02':
            msg = '02030000000F05FD'
        elif prefix == '03':
            msg = '03030000000F042C'
        return msg

    def _get_response_str(self, msg):
        if sys_data.web_api.config["simulation"] == 0:
            return self._read_serial(msg)
        elif sys_data.web_api.config["simulation"] == 1:
            response_str = self._read_serial(msg)
            if sys_data.simulation_temp:
                sys_data.simulation["height"].append([response_str, str(time.time())])
            else:
                sys_data.simulation_temp_data["height"].append([response_str, str(time.time())])
            return response_str
        elif sys_data.web_api.config["simulation"] == 2:
            if sys_data.simulation["height"]:
                if time.time() - float(sys_data.simulation["height"][0][1]) - self.d_value_time >= 0:
                    response_str = sys_data.simulation["height"][0][0]
                    sys_data.simulation["height"].pop(0)
                else:
                    time.sleep(0.001)
                    return ""
            else:
                fn.logger(f"高仿真结束", level='info', r_path=sys_data.r_path)
                time.sleep(5000)
                return ""
        return ""

    def _read_serial(self, msg):
        self.h_serial.write(bytes.fromhex(msg))
        response = self.h_serial.readall()
        return ' '.join(map(lambda x: '%02x' % x, response))

    def _process_data(self, data_array, data_count):
        data_list = []
        for data_n in range(int(data_count)):
            data_list.append([int(data_array[data_n * 3 + 3], 16), int(data_array[data_n * 3 + 4], 16), int(data_array[data_n * 3 + 5], 16)])

        for v in data_list:
            if v[2] > 0:
                self.faze_count += 50
                height = round(v[2] / 2.0, 1)
                self.h_data.append(height)
            current_result = [v[1], v[0], v[2], self.faze_count]
            sys_data.debug_data["height"] = [v[1], v[0], v[2]]

            if self.last_blocked_points == 0 and v[2] > 0:
                self.t_motor.create_thread(func=self.event_in)
                self.recode = True

            if self.last_blocked_points > 0 and v[2] == 0:
                self.t_motor.create_thread(func=self.event_out)
                self.recode = False

            self.last_blocked_points = v[2]

            if self.recode:
                self.low_data.append(int(v[1]))
                self.data.append(current_result)

    def event_in(self):
        fn.logger(f"高光幕-进入", event='height_in')
        if sys_data.web_api.config.get("h_curtain_debug", False):
            fn.logger(f"\n\n\n\n高光幕-进入\n", level='info', r_path=r"D:\nextsls\h_curtain_log.txt", print_to_c=False)

        sys_data.data_dict["height_hide"] = True
        wait_time = time.time()

        while time.time() - wait_time < 0.5:
            time.sleep(0.1)
            if len(self.low_data) > sys_data.web_api.config["low_count_judgment"] and self.low_data[-1] <= sys_data.web_api.config["lowest_judgment"]:
                break

        if len(self.low_data) < sys_data.web_api.config["low_count_judgment"]:
            if sys_data.web_api.config.get("not_parcel_obj_show", False):
                sys_data.thread_motor.create_thread(func=sys_data.web_api.show_info, info="高数据量异常")
            fn.logger(f"高数据{self.low_data} 量：{len(self.low_data)} 太少 {sys_data.web_api.config['low_count_judgment']} 判断不是货物", event='height')
            sys_data.web_api.play_sound("not_parcel_obj")
            return None

        low_list = sorted(deepcopy(self.low_data))
        fn.logger(f'low_list[0] > {sys_data.web_api.config["lowest_judgment"]},{low_list[0], low_list[0] > sys_data.web_api.config["lowest_judgment"]}', level='info', r_path=sys_data.r_path)

        if low_list[0] > sys_data.web_api.config["lowest_judgment"]:
            if sys_data.web_api.config.get("not_parcel_obj_show", False):
                sys_data.thread_motor.create_thread(func=sys_data.web_api.show_info, info="最低点异常判断为干扰")
            fn.logger(f"高最低点源数据{low_list} {low_list[0]}高数据达不到最低点{sys_data.web_api.config['lowest_judgment']} 判断不是货物", event='height')
            sys_data.web_api.play_sound("not_parcel_obj")
            return None

        if not self._should_create():
            fn.logger(f"高光幕-离开 判断为干扰", event='height_in')
            sys_data.web_api.play_sound("not_parcel_obj")
            return None

        self._create_parcel_object()

    def _should_create(self):
        do_create = False
        out_start = time.time()

        if not sys_data.web_api.config.get("first_hide_judgment_ban", 1):
            for laser1_recode in sys_data.laser1_recode_list:
                if out_start - laser1_recode["time"] < 3 and laser1_recode["hide"]:
                    do_create = True
                    break
        else:
            do_create = True

        return do_create

    def _create_parcel_object(self):
        sys_data.data_dict["measuring"] = True
        sys_data.debug_data["measuring"] = "测量中"
        create_id = str(fn.get_mongoid())
        sys_data.data_dict["current_id"] = create_id
        sys_data.data_dict

["lowest_point"] = min(self.low_data)
        self.weight_obj = pipeline_record_model.PipelineRecord(_id=create_id)
        self.weight_obj.direction = 0
        self.weight_obj.height = self.data
        self.weight_obj.save_db()
        if sys_data.web_api.config.get("height_data_show", False):
            sys_data.thread_motor.create_thread(func=sys_data.web_api.show_info, info=f"低点{sys_data.data_dict['lowest_point']} 开始ID{create_id}", type="height")

    def event_out(self):
        fn.logger(f"高光幕-离开", event='height_out')

        if sys_data.web_api.config.get("h_curtain_debug", False):
            fn.logger(f"\n\n\n\n高光幕-离开\n", level='info', r_path=r"D:\nextsls\h_curtain_log.txt", print_to_c=False)

        sys_data.data_dict["height_hide"] = False
        sys_data.data_dict["measuring"] = False
        sys_data.debug_data["measuring"] = "无"
        if self.weight_obj:
            self.weight_obj.direction = 1
            self.weight_obj.save_db()
        if sys_data.web_api.config.get("height_data_show", False):
            sys_data.thread_motor.create_thread(func=sys_data.web_api.show_info, info=f"完成ID{self.weight_obj._id}", type="height")

        self.reset_data()

    def reset_data(self):
        self.weight_obj = None
        self.data = []
        self.h_data = []
        self.low_data = []
        self.recode = False
        
        
if __name__ == "main":

heighter = HeightLightCurtain()
heighter.run()