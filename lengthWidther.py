import math
import serial
import time
import cv2
import numpy as np
from copy import deepcopy
from common import sys_data, data_parse, fn
from models import pipeline_record_model

class LengthWidthLightCurtain:
    def __init__(self):
        self.data = []  # [最低点，最高点，挡光点，速度编码器]
        self.last_data = [0, 0, 0, 0]
        self.t_motor = sys_data.thread_motor
        self.send_time = int(time.time())
        self.d_value_time = 0
        
        # Simulation settings
        simulation_mode = sys_data.web_api.config["simulation"]
        if simulation_mode != 2:
            self.lw_serial = serial.Serial(sys_data.serial_dict["length_width_serial"]["serial_port"], 115200, timeout=sys_data.web_api.config.get("length_width_serial_timeout", 0.01))
        elif simulation_mode == 2:
            self.d_value_time = time.time() - float(sys_data.simulation["lw"][0][1])

    def run(self):
        recode = False
        last_count_time = 0
        serial_read_speed_interval = 5
        serial_read_speed_count = 0

        while True:
            response_str = self.read_serial_data()

            if sys_data.web_api.config.get("lw_curtain_debug", False):
                fn.logger(f"{response_str}", level='info', r_path=r"D:\nextsls\lw_curtain_log.txt", print_to_c=False)
            
            response_array = response_str.split("01 03 08")
            for v in response_array:
                if len(v) != 31:
                    continue
                result_str = "01 03 08" + v
                current_result = self.parse_response(result_str)
                
                if int(time.time()) - self.send_time > 0.1:
                    self.send_time = int(time.time())
                    sys_data.debug_data["lw"] = current_result
                
                if sum(self.last_data) == 0 and sum(current_result) != 0:
                    self.data = []
                    self.t_motor.create_thread(func=self.event_in)
                    recode = True
                if sum(self.last_data) != 0 and sum(current_result) == 0:
                    self.t_motor.create_thread(func=self.event_out)
                    recode = False
                
                self.last_data = current_result
                
                if recode:
                    self.data.append(current_result)
            
            if sys_data.debug and len(fn.debug_levels) > 0:
                serial_read_speed_count += 1
                int_time = int(time.time())
                if int_time != last_count_time and int_time % serial_read_speed_interval == 0:
                    last_count_time = int_time
                    fn.dp('length width serial read speed count', serial_read_speed_count, level='lw_serial_speed')
                    serial_read_speed_count = 0
            
            time.sleep(0.01)

    def read_serial_data(self):
        simulation_mode = sys_data.web_api.config["simulation"]
        if simulation_mode == 0 or simulation_mode == 1:
            response = self.lw_serial.read(1000)
            response_str = " ".join(map(lambda x: "%02x" % x, response))
            if simulation_mode == 1:
                if sys_data.simulation_temp:
                    sys_data.simulation["lw"].append([response_str, str(time.time())])
                else:
                    sys_data.simulation_temp_data["lw"].append([response_str, str(time.time())])
        elif simulation_mode == 2:
            if sys_data.simulation["lw"]:
                if time.time() - float(sys_data.simulation["lw"][0][1]) - self.d_value_time >= 0:
                    response_str = sys_data.simulation["lw"][0][0]
                    sys_data.simulation["lw"].pop(0)
                else:
                    time.sleep(0.001)
                    return ""
            else:
                fn.logger(f"长宽仿真结束", level='info', r_path=sys_data.r_path)
                time.sleep(5000)
                return ""
        else:
            return ""
        return response_str

    def parse_response(self, result_str):
        data_array = result_str.split(" ")
        low_spots = int(data_array[4], 16) + int(data_array[5], 16)
        height_spots = int(data_array[6], 16) + int(data_array[7], 16)
        spots_count = int(data_array[8], 16) + int(data_array[9], 16)
        encoders_count = int(data_array[9] + data_array[10], 16)
        return [low_spots, height_spots, spots_count, encoders_count]

    def event_in(self):
        if sys_data.web_api.config.get("lw_curtain_debug", False):
            fn.logger(f"\n\n\n\n长宽光幕-进入\n", level='info', r_path=r"D:\nextsls\lw_curtain_log.txt", print_to_c=False)
        fn.logger(f"进入长宽光幕", event='length_width_in')

    def event_out(self):
        fn.logger(f"离开长宽光幕", event='length_width_out')
        if sys_data.web_api.config.get("lw_curtain_debug", False):
            fn.logger(f"\n\n\n\n长宽光幕-离开\n", level='info', r_path=r"D:\nextsls\lw_curtain_log.txt", print_to_c=False)
        
        current_id = sys_data.data_dict.get('current_id', None)
        if current_id is not None:
            try:
                source = deepcopy(self.data)
                self.data = []
                if len(source) >= 15:
                    if sys_data.web_api.config["simulation"] in [0, 1]:
                        fn.logger(f"发送结束扫码指令", event='length_width_out')
                        sys_data.pipeline_motor.barcode_scan_end()
                    if sys_data.web_api.config.get("bin_yolo", False):
                        box_encoder_len = source[-1][-1]
                        pulse_length = self.get_length_of_each_pulse()
                        turn_time = pulse_length * box_encoder_len * sys_data.web_api.config['bin_pre_cm_turn_time']
                        sys_data.data_dict["parcel_object_dict"][current_id]["bin_turning_time"] = turn_time
                    fn.logger(f"开始计算长宽-源数据：{source}", event='length_width_out')
                    self.lw_calculate(source, current_id)
                else:
                    sys_data.data_dict["parcel_object_dict"][current_id]["ext_flag"]["lw_insufficient"] = True
                    fn.logger(f"长宽数据不足不做长宽计算-源数据：{source},长度为{len(source)}", event='length_width_out')
            except Exception as e:
                self.data = []
                fn.logger(f"离开长宽光幕处理失败:{e}", level='error', event='length_width_out')
                data_parse.update_status_info(current_id, status=0, info="长处理失败")

    @staticmethod
    def adjust_values(lw_res):
        reverse = False
        if lw_res[0] > lw_res[1]:
            length = lw_res[0]
            width = lw_res[1]
        else:
            length = lw_res[1]
            width = lw_res[0]
            reverse = True
        
        length += sys_data.web_api.config['length_adjust_value']
        width += sys_data.web_api.config['width_adjust_value']
        
        if sys_data.web_api.config['length_width_adjust_value']:
            length = length * sys_data.web_api.config['length_width_adjust_value']
            width = width * sys_data.web_api.config['length_width_adjust_value']
        
        length = data_parse.adapt_value('length', length)
        width = data_parse.adapt_value('width', width)
        
        return [width, length] if reverse else [length, width]

    @staticmethod
    def get_length_of_each_pulse():
        p_r = sys_data.web_api.config["encoder_rotate_speed"]
        s_round = sys_data.web_api.config["encoder_perimeter"]
        return s_round * 0.1 / p_r

    @staticmethod
    def check_contour_useful(img_w, img_h, w, h, min_w):
        zero_contour_pix = 5
        if w <= min_w or h <= min_w:
            return False
        if w == 0 or h == 0:
            return False
        if w > img_w - zero_contour_pix or h > img_h - zero_contour_pix:
            return False
        return True

    def lw_calculate(self, source_arr, current_id):
        try:
            max_len = sys_data.web_api.config["max_len"]
            cm_cv_pix = sys_data.web_api.config["cm_cv_pix"]
            min_size = sys_data.web_api.config.get("min_sizes", [10, 10, 5])
            canvas_size = sys_data.web_api.config["lw_canvas_size"]
            min_size_list = [min_size[0] * cm_cv_pix, min_size[1] * cm_cv_pix]
            pulse_length = self.get_length_of_each_pulse()
            width = int(110 * cm_cv_pix * canvas_size)
            height = int(165 * cm_cv_pix * canvas_size)
            img = np.zeros((width, height), np.uint8)
            
            lw_res = [0, 0]
            min_w = int(5 * cm_cv_pix)
            data_slice = max(5, int(max_len / pulse_length))
            all_heights = []
            
            for data_index, data_arr in enumerate(source_arr):
                if data_index % data_slice == 0:
                    all_heights.append(int(data_arr[1] * cm_cv_pix))
            
            max_height = max(all_heights) + 10 * cm_cv_pix
            img[:, :max_height] = 255
            
            for data_index, data_arr in enumerate(source_arr):
                for encoder_index in range(int(data_arr[2])):
                    cv2.circle(img, (int(data_arr[1] * cm_cv_pix), int(encoder_index * pulse_length * cm_cv_pix)), 2, (0, 0, 0), 1)
            
            contours, _ = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                rect = cv2.minAreaRect(c)
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                w = int(rect[1][0])
                h = int(rect[1][1])
                
                if self.check_contour_useful(width, height, w, h, min_w):
                    lw_res = [w, h]
                    break
            
            lw_res = list(map(lambda x: x / cm_cv_pix, lw_res))
            lw_res = self.adjust_values(lw_res)
            
            sys_data.data_dict["parcel_object_dict"][current_id].update({"length": lw_res[0], "width": lw_res[1]})
            fn.logger(f"长宽计算结果：{lw_res}", event='length_width_calculate')
        except Exception as e:
            fn.logger(f"长宽计算失败: {e}", level='error', event='length_width_calculate')
            sys_data.data_dict["parcel_object_dict"][current_id]["ext_flag"]["lw_calculate_failed"] = True


if __name__ == "main":

lw_curtain = LengthWidthLightCurtain()
lw_curtain.run()
