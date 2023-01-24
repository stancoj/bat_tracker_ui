import time
import serial
import os
from contextlib import contextmanager
import enum


class UsbConnection:
    def __init__(self, port="", baud_rate=0):
        self.ser = serial.Serial()
        self.port = port
        self.baud_rate = baud_rate
        self.rx_data = bytearray()
        self.termination_char = '#'
        self.starting_char = '$'
        self.command = {
            "CONNECTION_RESPONSE": '01',
            "ERASE_MEMORY": '02',
            "READ_MEMORY": '03',
            "STATE_MEMORY": '04',
            "SET_TIME": '05',
            "SET_ALTITUDE": '06',
            "STATE_DEVICE": '07',
            "DISCONNECT": '08',
            "SET_CLOCK": '09',
            "READ_SENSOR_DATA": '10',
        }

    def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=2
            )
        except serial.SerialException as e:
            print(e)
            raise Exception("Bad port!")

        try:
            self.ser.write(bytes('$01#', 'utf-8'))
            self.rx_data = self.ser.read_until(expected=bytes('$BAT_GPS#', 'utf-8'))

            if '$BAT_GPS#' not in self.rx_data.decode('utf-8'):
                raise Exception("Device is not responding!")

        except Exception as e:
            self.ser.close()
            raise e

    def log_data(self, file_name):
        if self.ser.isOpen():
            try:
                with open(file_name, 'w') as f:
                    cmd = self.starting_char + self.command["READ_MEMORY"] + self.termination_char
                    self.send_cmd(cmd)
                    self.ser.timeout = 500
                    preprocessed_data = self.receive_data('$EOF_LOG#')
                    preprocessed_data = preprocessed_data[1:-10]
                    f.write(preprocessed_data)
            except Exception as e:
                raise e

    def send_cmd(self, cmd):
        if self.ser.isOpen():
            try:
                self.ser.write(bytes(cmd, 'utf-8'))
            except Exception as e:
                print(e)
                self.ser.reset_output_buffer()
                return False
            else:
                self.ser.reset_output_buffer()
                return True

    def receive_data(self, termination):
        if self.ser.isOpen():
            try:
                self.rx_data = self.ser.read_until(expected=bytes(termination, 'utf-8'))
                if termination not in self.rx_data.decode('utf-8'):
                    raise Exception("Device is not responding!")
            except Exception as e:
                self.ser.reset_input_buffer()
                raise e
            else:
                if self.check_received_str(self.rx_data.decode('utf-8')):
                    self.ser.reset_input_buffer()
                    return self.rx_data.decode('utf-8')
                else:
                    self.ser.reset_input_buffer()
                    raise Exception("Invalid string received!")

    def get_memory_state(self):
        cmd = self.starting_char + self.command["STATE_MEMORY"] + self.termination_char

        if self.send_cmd(cmd) is True:
            preprocessed_data = self.receive_data(self.termination_char)
            preprocessed_data = preprocessed_data[1:-1]
            used_mem, state = preprocessed_data.split(',')
            used_mem = int(used_mem)
            state = int(state)
            return used_mem, state
        else:
            return [0, 0]

    def get_device_state(self):
        cmd = self.starting_char + self.command["STATE_DEVICE"] + self.termination_char

        if self.send_cmd(cmd) is True:
            preprocessed_data = self.receive_data(self.termination_char)
            preprocessed_data = preprocessed_data[1:-1]
            baro, gps, state, gps_fix = preprocessed_data.split(',')
            return int(gps), int(baro), int(state), int(gps_fix)
        else:
            return [0, 0, 0, 0]

    def get_sensor_data(self):
        cmd = self.starting_char + self.command["READ_SENSOR_DATA"] + self.termination_char

        if self.send_cmd(cmd) is True:
            try:
                preprocessed_data = self.receive_data(self.termination_char)
                preprocessed_data = preprocessed_data[1:-1]
                print(preprocessed_data)
                baro_alt, gps_long, gps_lat, gps_alt, gps_time, gps_fix_time, gps_time_time = preprocessed_data.split(',')
            except Exception:
                raise Exception
            else:
                return baro_alt, gps_long, gps_lat, gps_alt, gps_time, gps_fix_time, gps_time_time
        else:
            return []

    def set_altitude(self, alt):
        alt = int(alt)

        if alt < 10:
            cmd = self.starting_char + self.command["SET_ALTITUDE"] + '000' + str(alt) + self.termination_char
        elif alt < 100:
            cmd = self.starting_char + self.command["SET_ALTITUDE"] + '00' + str(alt) + self.termination_char
        elif alt < 1000:
            cmd = self.starting_char + self.command["SET_ALTITUDE"] + '0' + str(alt) + self.termination_char
        else:
            cmd = self.starting_char + self.command["SET_ALTITUDE"] + '0' + str(alt) + self.termination_char

        return self.send_cmd(cmd)

    def set_time(self, hh, mm):
        if hh < 10:
            hour = '0' + str(hh)
        else:
            hour = str(hh)

        if mm < 10:
            minute = '0' + str(mm)
        else:
            minute = str(mm)

        cmd = self.starting_char + self.command["SET_TIME"] + hour + minute + self.termination_char
        self.send_cmd(cmd)

    def set_clock(self, hh, mm):
        if hh < 10:
            hour = '0' + str(hh)
        else:
            hour = str(hh)

        if mm < 10:
            minute = '0' + str(mm)
        else:
            minute = str(mm)

        cmd = self.starting_char + self.command["SET_CLOCK"] + hour + minute + self.termination_char
        self.send_cmd(cmd)

    def erase_flash_memory(self):
        try:
            cmd = self.starting_char + self.command["ERASE_MEMORY"] + self.termination_char
            self.send_cmd(cmd)
            # increase timeout, flash arase takes some time
            self.ser.timeout = 60
            preprocessed_data = self.receive_data(self.termination_char)
            # set timeout back to its previous value
            self.ser.timeout = 2
            preprocessed_data = preprocessed_data[1:-1]
            if preprocessed_data != 'OK':
                raise Exception("Unsuccessful memory erase!")
        except Exception as e:
            raise e

    def disconnect(self):
        if self.ser.isOpen():
            try:
                cmd = self.starting_char + self.command["DISCONNECT"] + self.termination_char
                self.send_cmd(cmd)
                preprocessed_data = self.receive_data(self.termination_char)
                preprocessed_data = preprocessed_data[1:-1]
                if preprocessed_data != 'OK':
                    raise Exception("Device disconnection failed! :(")
            except Exception as e:
                self.ser.close()
                raise e
            else:
                self.ser.close()

    def set_port(self, port):
        self.port = port

    def get_port(self):
        return self.port

    def set_baud_rate(self, baud):
        self.baud_rate = baud

    def get_baud_rate(self):
        return self.baud_rate

    ''' Checks if received string has proper starting and termination  '''
    def check_received_str(self, string):
        if string[0] != self.starting_char and string[-1] != self.termination_char:
            return False
        else:
            return True

