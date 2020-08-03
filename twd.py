
from pykeigan import usbcontroller
from pykeigan import utils
import time
import math

# KeiganMotor デバイスアドレス定義
"""
デバイスアドレス（ポート）は固有IDで指定する
----------------------
モーターへの接続
----------------------
    モーターのデバイスファイル指定について
        "/dev/ttyUSB0"で表示されるデバイス名での接続は、複数のモーターを接続した場合に変わる可能性がある。
        複数のモーターがある場合で、モーターを特定して接続する場合は "$ls /dev/serial/by-id/" で表示されるデバイスを使用する。
            ex)/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0
"""

# 2輪駆動車のクラス Two Wheel Drive Car
class TWD():
    # port_left, port_right はそれぞれ KeiganMotor のデバイスファイルを指定する
    def __init__(self, port_left, port_right, safe_time = 1, safe_option = 1, wheel_d = 100, tread = 400, button_event_cb = None):
        self.left = usbcontroller.USBController(port_left,False)
        self.right = usbcontroller.USBController(port_right,False)
        self.safe_time = safe_time
        self.safe_option = safe_option
        self.curve(0)
        self.safe_setting(True)
        self.round_num = tread / wheel_d # 360度回転するのに必要な回転数
        self.button_setting(button_event_cb)

    def enable(self): # モーター動作の許可
        self.safe_setting(True) # 安全装置開始
        self.left.enable_action()
        self.right.enable_action()

    def disable(self): # モーターの動作不許可
        self.left.disable_action()
        self.right.disable_action()

    def button_setting(self, button_event_cb): # KeiganMotor のボタンを有効化する
        self.left.set_button_setting(30)
        self.right.set_button_setting(30)
        # KeiganMotor 本体ボタンが押されたときに呼ばれるコールバック関数を登録する
        self.left.on_motor_event_cb = button_event_cb
        self.right.on_motor_event_cb = button_event_cb

    def led(self, state, r, g, b): # LEDの色変更 state = 1 が点灯, 0 は消灯, 2 は点滅
        self.left.set_led(state, r, g, b)
        self.right.set_led(state, r, g, b)

    def run(self, left_rpm, right_rpm): # 左右のモーターを指定の速度rpmで動作させる
        self.left.run_at_velocity(utils.rpm2rad_per_sec(left_rpm))
        self.right.run_at_velocity(utils.rpm2rad_per_sec(-right_rpm))
    
    def move_straight(self, rpm, degree, timeout = 0): # 左右のモーターを前進するように、degree 角度分だけ回転させる。timeout[s]を超えると安全装置再開
        self.safe_setting(False) # 安全装置解除
        self.left.set_speed(utils.rpm2rad_per_sec(rpm))
        self.right.set_speed(utils.rpm2rad_per_sec(rpm))        
        self.left.move_by_dist(utils.deg2rad(degree))
        self.right.move_by_dist(utils.deg2rad(-degree))
        # timeout == 0 の場合、安全装置は解除されたまま、動作完了まで続ける
        if timeout > 0:
            time.sleep(timeout)
            self.safe_setting(True) # 安全装置再開

    def pivot_turn(self, rpm, degree, timeout = 0):
        self.safe_setting(False) # 安全装置解除
        self.left.set_speed(utils.rpm2rad_per_sec(rpm))
        self.right.set_speed(utils.rpm2rad_per_sec(rpm))
        dist =  2 * math.pi * (self.round_num * degree / 360) # 2π * (真上から見て一回転する距離 * 角度/360)         
        self.left.move_by_dist(-dist)
        self.right.move_by_dist(-dist)
        # timeout == 0 の場合、安全装置は解除されたまま、動作完了まで続ける
        if timeout > 0:
            time.sleep(timeout)
            self.safe_setting(True) # 安全装置再開    
        

    def stop(self, timeout = 0): # timeout[s] だけその場で停止する（トルクあり）
        self.safe_setting(False) # 安全装置解除
        self.left.stop_motor()
        self.right.stop_motor()
        # timeout == 0 の場合、安全装置は解除されたまま、stop（rpm = 0 速度制御）を続ける
        if timeout > 0:
            time.sleep(timeout)    
            self.safe_setting(True)

    def free(self, timeout = 0): # # timeout[s] だけモーターフリー状態（粘性トルクあり）
        self.safe_setting(False) # 安全装置解除
        self.left.free_motor()
        self.right.free_motor()    
        # timeout == 0 の場合、安全装置は解除されたまま、free を続ける   
        if timeout > 0: 
            time.sleep(timeout)    
            self.safe_setting(True) # 安全装置再開

    def curve(self, type): # type 0: 台形制御 OFF, 1:  台形制御 ON
        # ※ 100ms間隔など、連続で命令を送る場合には、curve(0) とするべき
        self.left.set_curve_type(type)
        self.right.set_curve_type(type)

    def safe_setting(self, isEnabled): # モーションントロールの台形速度カーブを使わない(0)
        if isEnabled:
            # 第1引数が True safe_time[s]以内に次の動作命令が来ないと、停止する 0:free,1:disable,2:stop, 3:position固定
            self.left.set_safe_run_settings(True, self.safe_time * 1000, self.safe_option) 
            self.right.set_safe_run_settings(True, self.safe_time * 1000, self.safe_option) 
        else:
            self.left.set_safe_run_settings(False, self.safe_time * 1000, self.safe_option)
            self.right.set_safe_run_settings(False, self.safe_time * 1000, self.safe_option)