from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.Qt import QMutex

import time
import traceback
import sys
from sys import platform
from enum import Enum

from usb import UsbConnection

qt_creator_file = "mainwindow_bat_gps.ui"
Ui_MainWindow, QtBaseClass = uic.loadUiType(qt_creator_file)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # print("Worker created")

        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.is_done = False

    def __del__(self):
        return

    @pyqtSlot()
    def run(self):
        self.fn(*self.args, **self.kwargs)

    def done(self):
        return self.is_done


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        # connection - USB
        self.usb_com = UsbConnection()
        self.device_connected = False

        # thread pool
        self.thread_pool = QThreadPool()
        # self.live_data_worker = Worker(self.read_live_data)
        # self.live_data_worker.setAutoDelete(False)

        # mutex
        self.mutex = QMutex()

        # icons
        self.pixmapBad = QPixmap('icons/cross.png')
        self.pixmapGood = QPixmap('icons/tick.png')
        self.pixmapUnknown = QPixmap('icons/question.png')
        self.pixmapUpdate = QPixmap('icons/arrow-circle.png')
        self.pixmapFileBrowse = QPixmap('icons/folder-horizontal-open.png')

        self.updateStatePushButton.setIcon(QtGui.QIcon(self.pixmapUpdate))
        self.fileBrowserPushButton.setIcon(QtGui.QIcon(self.pixmapFileBrowse))
        self.setWindowIcon(QtGui.QIcon('icons/bat2.png'))

        # dialog
        self.msg_box = QMessageBox()

        # Connect callback functions to buttons
        self.connectButton.pressed.connect(self.serial_connect)
        self.disconnectButton.pressed.connect(self.serial_disconnect)
        self.fileBrowserPushButton.pressed.connect(self.browse_files)
        self.saveDataPushButton.pressed.connect(self.save_logged_data)
        self.erasePushButton.pressed.connect(self.erase_data)
        self.setTimePushButton.pressed.connect(self.set_time)
        self.setClockPushButton.pressed.connect(self.set_clock)
        self.setAltPushButton.pressed.connect(self.set_altitude)
        self.updateStatePushButton.pressed.connect(self.update_state_info)

        # Set combo box items
        self.comPortComboBox.addItem("9600")
        self.comPortComboBox.addItem("14400")
        self.comPortComboBox.addItem("19200")
        self.comPortComboBox.addItem("38400")
        self.comPortComboBox.addItem("57600")
        self.comPortComboBox.addItem("115200")
        self.comPortComboBox.setCurrentIndex(5)

    def __del__(self):
        return

    def closeEvent(self, event):
        if self.device_connected:
            self.serial_disconnect()

    def browse_files(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "QFileDialog.getOpenFileName()",
                                                  "", "All Files (*);;Python Files (*.py)", options=options)
        if fileName:
            self.fileBrowserLineEdit.setText(fileName)

    def serial_connect(self):
        if platform == "linux":
            port = "/dev/ttyUSB" + self.comPortLineEdit.text()
            self.usb_com.set_port(port)
        elif platform == "win32":
            port = "COM" + self.comPortLineEdit.text()
            self.usb_com.set_port(port)
        else:
            self.stateLineEdit.setText("Unsupported OS platform ...")

        baud = int(self.comPortComboBox.currentText())
        self.usb_com.set_baud_rate(baud)

        # Try to connect in new thread
        self.stateLineEdit.setText("Connecting ...")
        worker = Worker(self.connect_device)
        worker.setAutoDelete(True)
        self.thread_pool.start(worker)

    def serial_disconnect(self):
        if self.device_connected:
            try:
                self.mutex.lock()
                self.usb_com.disconnect()
                # self.mutex.unlock()
            except Exception as e:
                self.mutex.unlock()
                self.stateLineEdit.setText(str(e))
            else:
                self.mutex.unlock()
                self.stateLineEdit.setText("Disconnected")

            self.device_connected = False
            self.connectButton.setEnabled(True)
            self.comPortLineEdit.setEnabled(True)
            self.comPortComboBox.setEnabled(True)
            self.stateLineEdit.setEnabled(True)
            # Disable device setup, status, data
            self.dataGroupBox.setEnabled(False)
            self.deviceStateGroupBox.setEnabled(False)
            self.deviceSetUpGroupBox.setEnabled(False)
            self.liveDataGroupBox.setEnabled(False)

    def connect_device(self):
        try:
            self.mutex.lock()
            self.usb_com.connect()
            self.mutex.unlock()

            # print("Connected")
            self.get_memory_state()
            # print("Got mem state")
            self.get_device_state()
            # print("Got dev state")

        except Exception as e:
            self.mutex.unlock()
            print(e.__cause__)
            self.stateLineEdit.setText(str(e))
        else:
            # print("Success")
            self.mutex.unlock()
            # Set connection status
            self.device_connected = True
            self.stateLineEdit.setText("Connected")
            # Disable connection window
            self.connectButton.setEnabled(False)
            self.comPortLineEdit.setEnabled(False)
            self.comPortComboBox.setEnabled(False)
            self.stateLineEdit.setEnabled(False)
            # Enable device setup, status, data
            self.dataGroupBox.setEnabled(True)
            self.deviceStateGroupBox.setEnabled(True)
            self.deviceSetUpGroupBox.setEnabled(True)
            self.liveDataGroupBox.setEnabled(True)
            # Start live data thread
            # self.thread_pool.tryStart(self.live_data_worker)

    def save_logged_data(self):
        try:
            self.mutex.lock()
            self.usb_com.log_data(self.fileBrowserLineEdit.text())
        except Exception as e:
            print(e)
            self.mutex.unlock()
            self.show_dialog()
        else:
            self.mutex.unlock()

    def erase_data(self):
        if self.confirm_action_dialog():
            try:
                self.mutex.lock()
                self.usb_com.erase_flash_memory()
                self.mutex.unlock()
                self.get_memory_state()
            except Exception as e:
                self.mutex.unlock()
                print(e)
            else:
                self.mutex.unlock()

    def set_time(self):
        hour = self.setHourSpinBox.value()
        minute = self.setMinuteSpinBox.value()
        self.mutex.lock()
        self.usb_com.set_time(hour, minute)
        self.mutex.unlock()

    def set_clock(self):
        hour = self.setClockHourSpinBox.value()
        minute = self.setClockMinuteSpinBox.value()
        self.mutex.lock()
        self.usb_com.set_clock(hour, minute)
        self.mutex.unlock()

    def set_altitude(self):
        alt = self.setAltSpinBox.value()
        self.mutex.lock()
        self.usb_com.set_altitude(alt)
        self.mutex.unlock()

    def get_memory_state(self):
        self.mutex.lock()
        used_mem, state_mem = self.usb_com.get_memory_state()
        self.mutex.unlock()

        self.memoryProgressBar.setValue(used_mem/100)
        self.memoryProgressBar.setFormat("%.02f %%" % (used_mem/100))

        if state_mem == 1:
            self.memoryStateLabel.setPixmap(self.pixmapGood)
        elif state_mem == 2:
            self.memoryStateLabel.setPixmap(self.pixmapUnknown)
        else:
            self.memoryStateLabel.setPixmap(self.pixmapBad)

    def get_device_state(self):
        self.mutex.lock()
        gps, baro, state, gps_fix = self.usb_com.get_device_state()
        self.mutex.unlock()

        state_str = str(state)

        if gps == 2:
            self.gpsStateLabel.setPixmap(self.pixmapUnknown)
        elif gps == 1:
            self.gpsStateLabel.setPixmap(self.pixmapGood)
        else:
            self.gpsStateLabel.setPixmap(self.pixmapBad)

        if baro == 2:
            self.baroStateLabel.setPixmap(self.pixmapUnknown)
        elif baro == 1:
            self.baroStateLabel.setPixmap(self.pixmapGood)
        else:
            self.baroStateLabel.setPixmap(self.pixmapBad)

        if gps_fix == ord('3'):
            self.gpsFixStateLabel.setPixmap(self.pixmapGood)
        else:
            self.gpsFixStateLabel.setPixmap(self.pixmapBad)

        if state_str[0] == "0":
            self.labelDeviceState.setText('WAIT_FIRST_FIX')
        elif state_str[0] == "1":
            self.labelDeviceState.setText('WAIT_TIME_SETUP')
        elif state_str[0] == "2":
            self.labelDeviceState.setText('WAIT_ALT_SETUP')
        elif state_str[0] == "3":
            self.labelDeviceState.setText('SET_SLEEP_MODE')
        elif state_str[0] == "4":
            if state_str[1] == "0":
                self.labelDeviceState.setText('WAIT_ALT_TRIGGER')
            elif state_str[1] == "1":
                self.labelDeviceState.setText('WAKE_UP_GPS')
            elif state_str[1] == "2":
                self.labelDeviceState.setText('WAIT_FOR_GPS_FIX')
            elif state_str[1] == "3":
                self.labelDeviceState.setText('LOG_MEAS_DATA')

    def update_state_info(self):
        self.get_memory_state()
        self.get_device_state()
        self.read_live_data()

    def show_dialog(self):
        self.msg_box.setIcon(QMessageBox.Warning)
        self.msg_box.setWindowTitle("Log file browser")
        self.msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        self.msg_box.setText("Please select valid address for log file ...")

        self.msg_box.exec()

    def confirm_action_dialog(self):
        self.msg_box.setIcon(QMessageBox.Information)
        self.msg_box.setWindowTitle("Confirmation")
        self.msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        self.msg_box.setText("Please confirm action ...")

        return_value = self.msg_box.exec()

        if return_value == QMessageBox.Ok:
            return True
        else:
            return False

    def read_live_data(self):
        try:
            self.mutex.lock()
            baro_alt, gps_long, gps_lat, gps_alt, gps_time, gps_fix_time, gps_time_time = self.usb_com.get_sensor_data()
            baro_alt_float = float(int(baro_alt)/100.0)

            self.baroAltValue.setText(str(baro_alt_float))
            self.gpsLatValue.setText(gps_lat)
            self.gpsLongValue.setText(gps_long)
            self.gpsAltValue.setText(gps_alt)
            self.gpsTimeValue.setText(gps_time)
            self.gpsFixTime.setText(gps_fix_time)

        except Exception as e:
            self.mutex.unlock()
            print(e.__str__())
        else:
            self.mutex.unlock()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(143, 143, 143))
    palette.setColor(QPalette.WindowText, Qt.white)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    app.exec_()

