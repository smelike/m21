import serial
import time
import struct
import numpy as np

class WeightSensor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=19200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.is_measuring = False
        self.weight_readings = []

    def open_serial(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Opened serial port {self.port} successfully.")
            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port {self.port}: {e}")
            return False

    def close_serial(self):
        if self.ser and self.ser.isOpen():
            self.ser.close()
            print(f"Closed serial port {self.port}.")

    def start_measurement(self):
        if not self.ser or not self.ser.isOpen():
            print("Serial port is not open. Cannot start measurement.")
            return False
        
        # Send read command
        # command = bytearray.fromhex('010300500002c41a')  # Read command: 010300500002
        command = bytes.fromhex('010300500002c41a')
        self.ser.write(command)
        
        self.is_measuring = True
        print("Measurement started.")
        return True

    def stop_measurement(self):
        if self.is_measuring:
            self.is_measuring = False
            print("Measurement stopped.")

    def is_measuring_now(self):
        return self.is_measuring

    def read_weight_data(self):
        if not self.ser or not self.ser.isOpen():
            print("Serial port is not open. Cannot read weight data.")
            return None

        # Read response
        response = self.ser.read(9)  # Read 9 bytes (fixed response length)
        
        if len(response) < 9:
            print(f"Error: Incomplete response. Expected 9 bytes, received {len(response)} bytes.")
            return None

        # Parse response
        try:
            # Extract weight bytes (4th to 7th byte)
            weight_bytes = response[3:7]
            # Convert bytes to float
            weight_value = struct.unpack('>f', weight_bytes)[0]
            # Append to readings
            self.weight_readings.append(weight_value)
            return weight_value
        except Exception as e:
            print(f"Error parsing weight data: {e}")
            return None

    def log_weight_readings(self):
        print("Logging weight readings:")
        for idx, reading in enumerate(self.weight_readings):
            print(f"{idx + 1}: {reading:.2f} kg")
        print("End of weight readings logging.")

    def get_stable_weight(self, resolution=0.01, interval=0.03):
        if not self.weight_readings or not self.is_measuring:
            print("No weight readings available or measurement not started.")
            return None

        sorted_readings = sorted(self.weight_readings, reverse=True)

        stable_weight = None
        for reading in sorted_readings:
            if reading % resolution == 0 or abs(reading - stable_weight) < interval:
                stable_weight = reading
                break

        return stable_weight

    def detect_item_entry(self):
        # Simulate detection of item entering the platform (Di1 changes from 1 to 0)
        # Replace with actual hardware detection or trigger mechanism
        if not self.is_measuring:
            self.start_measurement()

    def __del__(self):
        self.close_serial()

# Example usage:
if __name__ == "__main__":
    sensor = WeightSensor(port='COM6')

    # Open serial port
    sensor.open_serial()

    # Simulate item entering the platform to start measurement
    sensor.detect_item_entry()

    # Simulate reading weight data
    for _ in range(1000):
        weight = sensor.read_weight_data()
        if weight is not None:
            print(f"Current weight: {weight:.2f} kg")
        time.sleep(1)  # Simulate time delay between readings

    # Simulate stopping measurement
    sensor.stop_measurement()

    # Check if currently measuring
    print("Is measuring now:", sensor.is_measuring_now())

    # Log all weight readings
    sensor.log_weight_readings()

    # Get the most stable weight reading
    stable_weight = sensor.get_stable_weight()
    if stable_weight is not None:
        print(f"Most stable weight: {stable_weight:.2f} kg")
    else:
        print("No stable weight within specified criteria.")

    # Close serial port
    del sensor  # Automatically closes serial port in destructor
