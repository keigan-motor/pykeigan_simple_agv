#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on June 1 2020
@author: Takashi Tokuda
"""

# import the necessary packages
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import threading # タイマー用 SignalライブラリがOpenCVと一緒に使えないため

import cv2 # OpenCV
import numpy as np # numpy 計算が得意
from enum import Enum # 列挙子
import RPi.GPIO as GPIO  # GPIOにアクセスするライブラリ
import csv # CSVファイルを取り扱う（読み書き）ライン検知のキャリブレーションデータを作製

from twd import TWD # KeiganMotor での AGV開発を簡単にするためのライブラリ。メインファイルと同じフォルダに、twd.py を置いて下さい。
from pykeigan import utils

#config
import configparser
import os
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'config_test.ini'), encoding='utf-8')

command_list={}
for i in config["aruco_id_command"]:
    command_list[i]=config["aruco_id_command"][i]

#1D detect
isMovingForward=True
#revertF=-1


# ボタン（赤黄緑）
BUTTON_RED_PIN = 13
BUTTON_RED_PIN_2 = 6 # ２つ目の赤ボタンを追加
BUTTON_YELLOW_PIN = 19
BUTTON_GREEN_PIN = 26

# カメライメージサイズ
IMAGE_WIDTH_PIXEL = 320
IMAGE_HEIGHT_PIXEL = 240

# カメラを初期化し、生画像への参照を取得する
camera = PiCamera()
camera.resolution = (IMAGE_WIDTH_PIXEL, IMAGE_HEIGHT_PIXEL)
camera.framerate = 32 #32
rawCapture = PiRGBArray(camera, size=(IMAGE_WIDTH_PIXEL, IMAGE_HEIGHT_PIXEL))
time.sleep(0.1) # カメラのウォームアップ時間

# ライントレーサー
"""
トラックバー（Mainウインドウ下のスライダー）により決定される、
HSV値の範囲の色をラインとして認識する
"""
# 領域分離を行った後、この面積を超えた領域のみ処理を行う
LINE_AREA_THRESHOLD = 7000/4 # ライン検知用の面積の閾値
LINE_CROSS_PASS_AREA_THRESHOLD = 20000/4 # ラインを横切った場合に前回のライン位置を採用するための面積の閾値
LINE_UPPER_AREA_THRESHOLD = 5500/4
STOP_MARKER_AREA_THRESHOLD = 30000/4 # 停止テープマーカーを検知するための面積の閾値（※テープ, arucoマーカーではない）

RUN_CMD_INTERVAL = 0.05 # 0.1秒ごとに処理を行う
#RUN_BASE_RPM = 50
RUN_BASE_RPM=int(config['rpm']['base'])
#RUN_LOWER_RPM = 15
RUN_LOWER_RPM=int(config['rpm']['lower'])
STOP_AFTER_RPM = 10

# 負荷有無で PIDコントローラゲインを変更するため（デフォルトは未使用）
hasPayload = False # 負荷あり: True, 負荷なし: False

# マーカーなどで停止する場合に関する変数
isPausingLinetrace = False # マーカー発見等で停止すべき場合 True
isResuming = False # 停止→ライントレース動作再開までの判定状態
RESUME_THRESHOLD = 10 # resumeCounter がこの回数以上の場合、動作再開する（動作しても良い）
resumeCounter = 0 # 動作再開用のカウンタ 
# ドッキング中であることを示す 
isDocking = False # ドッキング中なら True
dockingCounter = 0 # ドッキング中ロストカウンタ
DOCKING_THRESHOLD = 5 # dockingCounter がこの回数以上の場合、moveStraight でC箱を実際につかみにいく

# ラインロスト（OFFにしている）
is_lost = False # Trueならば、ラインがロストしている
lost_count = 0 # ラインをロストしたカウント
LOST_THRESHOLD = 7 # ラインをロストしたとみなす判定の閾値
lost_total_count = 0 # ラインをロストした回数の合計
LOST_TOTAL_THRESHOLD = 5 # ラインをロストした回数の合計がこの値以上になると、AGVはアイドル状態に戻る

# PID limit
DELTA_MAX = 25
# PIDコントローラのゲイン値：負荷なし
steer_p = 0.05 # 比例
steer_i = 0.0025 # 積分
steer_d = 0 # 微分
# PIDコントローラのゲイン値：負荷あり
steer_load_p = 0.75 # 比例
steer_load_i = 0.5 # 積分
steer_load_d = 0 # 微分
eI = 0 # 前回の偏差の積分値を保存しておく
x = 0 # ライン位置
x_old = 0 # ラインの前回の位置を保存しておく
CHARGING_TIME_SEC = 10 # 充電ステーションでの待機時間

#run rpm variable
run_rpm = RUN_BASE_RPM

# システムの状態を表す列挙子クラス
class State(Enum):
    """システムのステート（状態）を表す列挙子

     状態遷移を管理するため

    Attributes:
        State (Enum): システムのステート（状態）

    """
    STATE_IDLE = 0 # 待機状態
    STATE_LINE_TRACE = 1 # ライントレーサー
    STATE_DEBUG = 10 # デバッグ用


# KeiganMotor 本体のボタンから、システムのステートをセットする
def set_state_by_button(event):
    # ■ 停止ボタンでアイドル状態へ（停止）
    # ▶ 再生ボタンでライントレース開始
    if event['event_type'] == 'button':
        if event['number'] == 2:
            set_state(State.STATE_IDLE)
        elif event['number'] == 3:
            set_state(State.STATE_LINE_TRACE)     

# KeiganMotor 本体のボタンが押されたときのコールバック
def motor_event_cb(event):
    #print("event")
    set_state_by_button(event)


# KeiganMotor デバイスアドレス定義
"""
以下の２通りの方法がある
（１）特定のUSBポート番号を、特定のデバイスアドレスで固定する
（２）KeiganMotor固有のデバイスアドレスを使用する
    ターミナルで
        $ls /dev/serial/by-id/
    で表示されるデバイスアドレス（デバイスファイル）を記録する
    usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0

（２）KeiganMotor固有のデバイスアドレスを使用する場合

デバイスアドレス（ポート）は固有IDで指定する
----------------------
モーターへの接続
----------------------
    モーターのデバイスファイル指定について
        "/dev/ttyUSB0"で表示されるデバイス名での接続は、複数のモーターを接続した場合に変わる可能性がある。
        複数のモーターがある場合で、モーターを特定して接続する場合は "$ls /dev/serial/by-id/" で表示されるデバイスを使用する。
            ex)/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0
"""

from pykeigan import usbcontroller
#config
port_left=config['port']['port_L']
port_right=config['port']['port_R']
wheel_d_c = float(config['parameter']['wheel_d'])
tread_c = float(config['parameter']['tread'])

d_marker = float(config['parameter']['d_marker'])
d_corner = float(config['parameter']['d_corner'])

#other parameter
d_deg = float(config['parameter_other']['d_deg'])
pause_t = float(config['parameter_other']['pause_t'])

# sensor pin list 
sensorList = [config['sensor']['pin_0'], config['sensor']['pin_1'], config['sensor']['pin_2'], config['sensor']['pin_3'], config['sensor']['pin_4']]


# 2輪台車 wheel_d: 車輪直径[mm], tread: トレッド幅 = 車輪センター間の距離[mm]
# 特に トレッド幅については、実際と合致していない場合、その場旋回で角度のズレが生じる
#twd = TWD(port_left, port_right, wheel_d, tread, button_event_cb = motor_event_cb)
twd = TWD(port_left, port_right, wheel_d = wheel_d_c, tread = tread_c, button_event_cb = motor_event_cb) 

cur_state = State.STATE_IDLE # システムの現在の状態



def set_state(state: State):
    """システムのステートをセットする

    同時に、モーターのLEDをステートに応じて色変更する

    Args:
        state (State): ステート（状態）
    """       
    global cur_state , eI # グローバル変数: これがないと参照不可能
    #print("in set_state old:", str(cur_state), "new:", str(state))
    cur_state = state
    eI = 0

    if state == State.STATE_IDLE: # 赤
        print("-> State.STATE_IDLE")
        twd.disable()
        twd.led(2, 255, 0, 0)
    elif state == State.STATE_LINE_TRACE: # 緑
        print("-> State.STATE_LINE_TRACE")    
        t = threading.Thread(target = scheduler)
        t.start()
        twd.enable()
        #twd.run(10, 10)
        twd.led(2, 0, 255, 0)
    elif state == State.STATE_DEBUG: # ログだけ流れる。台車は動かない。水色
        print("-> State.STATE_DEBUG")
        t = threading.Thread(target = scheduler)
        t.start()
        twd.disable()
        twd.led(2, 0, 255, 255)



# ラインの位置から左右のモーターに与える回転速度rpmを計算する
def pid_controller():

    global steer_p, steer_i, steer_d
    global steer_load_p, steer_load_i, steer_load_d
    global eI, x, x_old 

    # トラックバーの値を取る
    steer_p = cv2.getTrackbarPos("Gain_P", "Main") / 100
    steer_i = cv2.getTrackbarPos("Gain_I", "Main") / 100
    steer_load_p = cv2.getTrackbarPos("Gain_Load_P", "Main") / 100
    steer_load_i = cv2.getTrackbarPos("Gain_Load_I", "Main") / 100

    # 負荷有無によりPIDゲインを変更する
    if hasPayload:
        gain_p = steer_load_p
        gain_i = steer_load_i
        gain_d = steer_load_d
    else:
        gain_p = steer_p
        gain_i = steer_i
        gain_d = steer_d        

    eI = eI + RUN_CMD_INTERVAL * x # 偏差 積分
    eD = (x - x_old) / RUN_CMD_INTERVAL # 偏差 微分
    delta_v = gain_p * x + gain_i * eI + gain_d * eD

    # アンチワインドアップ
    if delta_v > DELTA_MAX:
        eI -= (delta_v - DELTA_MAX) / gain_i
        if eI < 0: eI = 0
        delta_v = DELTA_MAX
    elif delta_v < - DELTA_MAX:
        eI -= (delta_v + DELTA_MAX) / gain_i
        if eI > 0:
            eI = 0
        delta_v = - DELTA_MAX

    x_old = x
    rpm = (run_rpm + delta_v, run_rpm - delta_v)
    #print("x =", x, ", rpm =", rpm)
    return rpm
        
    
# 赤黄緑ボタンを押したときのコールバック関数
def red_callback(gpio_pin):
    time.sleep(0.05)
    if GPIO.input(gpio_pin) == GPIO.LOW:
        set_state(State.STATE_IDLE)
        print("red pushed")

def yellow_callback(gpio_pin):
    time.sleep(0.05)
    print("yellow pushed: nothing")

def green_callback(gpio_pin):
    time.sleep(0.05)
    if GPIO.input(gpio_pin) == GPIO.LOW:
        set_state(State.STATE_LINE_TRACE)
        print("green pushed")


# 重心の検出
def get_moment(mask, threshold):
    # 面積・重心計算付きのラベリング処理を行う
    num_labels, label_image, stats, center = cv2.connectedComponentsWithStats(mask)
    # 最大のラベルは画面全体を覆う黒なので不要．データを削除
    num_labels = num_labels - 1
    stats = np.delete(stats, 0, 0)
    center = np.delete(center, 0, 0)

    isExist = False
    x1, y1 = 0, 0
    area = 0

    if num_labels > 0:
        # 面積最大のラベル
        max_label = np.argmax(stats[:,4])
        area = stats[max_label][4]
        if area > threshold:
            #print("area: ", area)
            x1, y1 = int(center[max_label][0]), int(center[max_label][1])
            cv2.circle(mask, (x1, y1), 4, 100, 2, 4)
            isExist = True    
            
    return isExist, (x1, y1), area


# 赤色の重心の検出
# 存在する場合 true と、重心座標と、面積を返す
def get_red_moment(hsv):
    # 赤色のHSVの値域1
    h_max_low = cv2.getTrackbarPos("(Red)_H_max_low", "Red")
    s_min = cv2.getTrackbarPos("(Red)_S_min", "Red")
    v_min = cv2.getTrackbarPos("(Red)_V_min", "Red")
    hsv_min = np.array([0,s_min,v_min])
    hsv_max = np.array([h_max_low,255,255])
    mask1 = cv2.inRange(hsv, hsv_min, hsv_max)

    # 赤色のHSVの値域2
    h_min_high = cv2.getTrackbarPos("(Red)_H_min_high", "Red")
    hsv_min = np.array([h_min_high,s_min,v_min])
    hsv_max = np.array([179,255,255])
    mask2 = cv2.inRange(hsv, hsv_min, hsv_max)

    # 赤色領域のマスク
    mask = mask1+mask2

    cv2.imshow("Red", mask)
            
    return get_moment(mask, STOP_MARKER_AREA_THRESHOLD) 



# 青色の重心の検出
# 存在する場合 true と、重心座標と、面積を返す
def get_blue_moment(hsv):
    # 青色のHSVの値域1
    h_min = cv2.getTrackbarPos("(Trace)_H_min", "Trace")
    h_max = cv2.getTrackbarPos("(Trace)_H_max", "Trace")
    s_min = cv2.getTrackbarPos("(Trace)_S_min", "Trace")
    v_min = cv2.getTrackbarPos("(Trace)_V_min", "Trace")
    hsv_min = np.array([h_min, s_min, v_min])
    hsv_max = np.array([h_max,255,255])

    # 青色領域のマスク
    mask = cv2.inRange(hsv, hsv_min, hsv_max)

    cv2.imshow("Trace", mask)

    return get_moment(mask, LINE_AREA_THRESHOLD) 

def reset_pid_params():
    eI = 0
    x = 0
    x_old = 0 

def scheduler():
    global cur_state, isPausingLinetrace, isDocking
    if cur_state == State.STATE_IDLE:
        return
    # タイマーの再生成
    t = threading.Timer(RUN_CMD_INTERVAL, scheduler)
    t.start()
    if isPausingLinetrace: # マーカー検知時など停止するべき場合
        reset_pid_params()
        return
    #print(time.time())
    rpm = pid_controller() # PIDコントローラに突っ込む
    if isDocking:
        rpm = (rpm[0] * 0.5, rpm[1] * 0.5) # ドッキング時は半分の速度にする
    
    if cur_state == State.STATE_LINE_TRACE:
        twd.run(rpm[0], rpm[1]) # 速度指令



# トラックバーのコールバック関数は何もしない空の関数
def nothing(x):
    pass

# aruco マーカー
# aruco マーカーの辞書定義
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# arucoマーカーを検知する
def aruco_reader(roi_ar):
    corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(roi_ar, dictionary)
    cv2.aruco.drawDetectedMarkers(roi_ar, corners, ids, (0,255,0)) 
    cv2.imshow('detectedMakers',roi_ar)
    return corners,ids

#adjust
def moveToMarker():
    twd.move_straight(RUN_LOWER_RPM, d_marker, 4.5) # 直進。マーカー位置によって調整すること。
def moveToCorner():
    twd.move_straight(RUN_LOWER_RPM, d_corner, 4.5) # 直進。マーカー位置によって調整すること。    
def passMarker():
    twd.move_straight(RUN_BASE_RPM, d_marker, 4.5) # 直進。マーカー位置によって調整すること。


if __name__ == '__main__':

    print("Keigan Line Tracer Start !")

    # GPIOをBCM番号で呼ぶことを宣言
    GPIO.setmode(GPIO.BCM) 

    # ボタン入力の設定
    GPIO.setup(BUTTON_RED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_RED_PIN_2, GPIO.IN, pull_up_down=GPIO.PUD_UP) 
    GPIO.setup(BUTTON_YELLOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) 
    GPIO.setup(BUTTON_GREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) 

    # センサー入力の設定
    for i in range(len(sensorList)):
        print(sensorList[i])
        GPIO.setup(sensorList[i], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # ボタンを押したときのコールバックを登録
    GPIO.add_event_detect(BUTTON_RED_PIN, GPIO.FALLING, callback=red_callback, bouncetime=50)
    GPIO.add_event_detect(BUTTON_RED_PIN_2, GPIO.FALLING, callback=red_callback, bouncetime=50)
    GPIO.add_event_detect(BUTTON_YELLOW_PIN, GPIO.FALLING, callback=yellow_callback, bouncetime=50)
    GPIO.add_event_detect(BUTTON_GREEN_PIN, GPIO.FALLING, callback=green_callback, bouncetime=50)

    set_state(State.STATE_IDLE) # アイドル状態でスタート

    print("キーボードの [s] + Enter または 赤ボタン: ストップ STATE_IDLE")
    print("キーボードの [t] + Enter または 緑ボタン: ライントレーサー STATE_LINE_TRACE")
    print("キーボードの [d] + Enter :デバッグ用 STATE_DEBUG")

    # 画像表示用ウィンドウの生成 なくても動くが、ウィンドウにフォーカスさせてキー入力を受け付けるため必要
    cv2.namedWindow("Main") 
    cv2.namedWindow("Trace")
    cv2.namedWindow("Red") 

    # 各ウインドウの下に、スライダー＝トラックバーが生成される
    # 値は整数値 0-255 しか設定できない
    # スライダーを動かすことにより、値を調整する

    # HSVによるラインの色抽出の調整
    # H: 色相, S:彩度, V:明度
    # 以下リンクを見ること
    # https://algorithm.joho.info/programming/python/opencv-color-detection/
    # https://www.peko-step.com/html/hsv.html
    # ※ OpenCVでの H は、0-179 しか受け付けないので、Hは 0-360° 表記の半分にしなければならない

    # PIDコントローラのゲイン調整
    cv2.createTrackbar("Gain_P", "Main", 10, 100, nothing)
    cv2.createTrackbar("Gain_I", "Main", 5, 100, nothing)
    cv2.createTrackbar("Gain_Load_P", "Main", 15, 100, nothing)
    cv2.createTrackbar("Gain_Load_I", "Main", 7, 100, nothing)

    # 青ラインのHSV抽出領域設定
    #cv2.createTrackbar("(Trace)_H_min", "Blue", 15, 179, nothing)
    #cv2.createTrackbar("(Trace)_H_max", "Blue", 40, 179, nothing)

    # 黄ライントレース設定
    # cv2.createTrackbar("(Trace)_H_min", "Trace", 10, 179, nothing)
    # cv2.createTrackbar("(Trace)_H_max", "Trace", 40, 179, nothing)
    # cv2.createTrackbar("(Trace)_S_min", "Trace", 0, 255, nothing) # 64
    # cv2.createTrackbar("(Trace)_V_min", "Trace", 145, 255, nothing) # 0

    # 青ライントレース設定
    cv2.createTrackbar("(Trace)_H_min", "Trace", 90, 179, nothing)
    cv2.createTrackbar("(Trace)_H_max", "Trace", 130, 179, nothing)
    cv2.createTrackbar("(Trace)_S_min", "Trace", 64, 255, nothing)
    cv2.createTrackbar("(Trace)_V_min", "Trace", 20, 255, nothing)   

    # 赤マーカーのHSV抽出領域設定
    cv2.createTrackbar("(Red)_H_min_high", "Red", 150, 179, nothing)
    cv2.createTrackbar("(Red)_H_max_low", "Red", 20, 179, nothing)
    cv2.createTrackbar("(Red)_S_min", "Red", 64, 255, nothing)
    cv2.createTrackbar("(Red)_V_min", "Red", 20, 255, nothing)

    # 停止マーカーを検知したカウント数（正常であれば周回数になる）
    stop_marker_count = 0

    try:
        # カメラからフレームをキャプチャする
        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            # grab the raw NumPy array representing the image, then initialize the timestamp
            # and occupied/unoccupied text
            image = frame.array
            # show the frame
            roi = image[IMAGE_HEIGHT_PIXEL - 50:IMAGE_HEIGHT_PIXEL, 0:IMAGE_WIDTH_PIXEL]
            roi_u = image[45:95, 0:IMAGE_WIDTH_PIXEL]
            hsvImg = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) # HSV画像
            hsvImg_u = cv2.cvtColor(roi_u, cv2.COLOR_BGR2HSV)
            img = cv2.medianBlur(hsvImg,5)
            img_u = cv2.medianBlur(hsvImg_u,5)

            # ライントレース中の動作フラグ
            cmdFlag=False
            stopFlag = False # 停止

            # (a) Arucoマーカー検知で停止を行う場合
            roi_ar = image[80:240, 0:320] # [80:240, 0:320]
            corners,ids = aruco_reader(roi_ar) #ArUcoマーカー検知

            if ids is not None:
                #marker_mean_y = corners[0][0][1][1]+corners[0][0][1][1]+corners[0][0][1][1]+corners[0][0][1][1]
                #print(corners[0][0][1][1])
                cmdFlag=True
                cmd=-1
                # 発見した aruco id が、command_list 内のコマンドid とマッチしている場合 cmd = id とする
                for i in range (len(command_list)): 
                    if i == ids[0,0]:
                        #cmdFlag=True
                        cmd=i
                        break

            # (b) 赤ラインマーカーで停止を行う場合
            #red = get_red_moment(img)
            #stopFlag = red[0] # 赤マーカーが存在する場合、True

            if cur_state == State.STATE_LINE_TRACE or cur_state == State.STATE_DEBUG:
                if stopFlag:
                    stop_marker_count += 1
                    print("Detected Stop Marker:", stop_marker_count)
                    reset_pid_params()
                    isPausingLinetrace = True # ライントレース一時停止
                    twd.enable() # ラインロストで disable 状態になっている場合がある
                    twd.free(0.5) # 停止、タイムアウト0.5秒 その場で 180°旋回する
                    twd.pivot_turn(20, 180, 10) # TWD初期化時、tread を正確に設定していない場合、ズレる
                elif cmdFlag:
                    cmd_str = command_list.get(str(cmd))
                    print(cmd_str)
                    if cmd_str == 'stop':
                        stop_marker_count += 1
                        print("Detected Stop Marker:", stop_marker_count)
                        reset_pid_params()
                        isPausingLinetrace = True # ライントレース一時停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒 その場で 180°旋回する
                        twd.pivot_turn(20, 180, 10) # TWD初期化時、tread を正確に設定していない場合、ズレる

                           # (ア) 搬送ローラーで荷物の搬送を行う場合
                                #    twd.move_straight(15, 390, 7)
                                #    do_taskset()
                                #    twd.stop(10)
                                    
                                #    run_rpm = RUN_BASE_RPM # 速度を元に戻す

                                    # 以下を有効にすると、緑（白）ボタンを押すまで動作再開しない
                                    # set_state(State.STATE_IDLE)
                    elif cmd_str == 'pause':
                        print("Detected Pause Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        # moveToMarker()
                        twd.stop(pause_t)
                    elif cmd_str == 'idle':
                        print("Detected idle Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        moveToMarker()
                        set_state(State.STATE_IDLE) # IDLE 状態にする（Bluetoothからの再開処理待ち）                    
                    elif cmd_str == 'placing_task':
                        print("Detected Placing Task Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        moveToMarker()
                        ## ============ Add Task Command Code Here ============ ##
                        for i in range (len(sensorList)):
                            print("...placing task ("+str(i+1)+")...")
                            while(True):
                                #wait
                                time.sleep(0.1)
                                if GPIO.input(sensorList[i]) == GPIO.HIGH:
                                    time.sleep(0.05)
                                    if GPIO.input(sensorList[i]) == GPIO.HIGH:
                                        print(str(sensorList[i]) + "pin is HIGH")
                                        twd.enable()
                                        twd.move_straight(RUN_LOWER_RPM, d_deg, 4.5)
                                        break
                            
                            twd.stop(0.5)
                        print("...Task done")
                        
                        ## ==================================================== ##
                    elif cmd_str == 'picking_task':
                        print("Detected Picking Task Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        moveToMarker()
                        ## ============ Add Task Command Code Here ============ ##
                        for i in range (len(sensorList)):
                            print("...picking task ("+str(i+1)+")...")
                            while(True):
                                #wait
                                time.sleep(0.1)
                                if GPIO.input(sensorList[i]) == GPIO.LOW:
                                    time.sleep(0.05)
                                    if GPIO.input(sensorList[i]) == GPIO.LOW:
                                        print(str(sensorList[i]) + "pin is LOW")
                                        twd.enable()
                                        twd.move_straight(RUN_LOWER_RPM, d_deg, 4.5)
                                        break
                            
                            twd.stop(0.5)
                        print("...Task done")
                        
                        ## ==================================================== ##
                    
                    elif cmd_str == 'turnR':
                        print("Detected Right Turn Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        moveToCorner()
                        twd.pivot_turn(RUN_LOWER_RPM, -90, 3) # 90°回転。TWD初期化時、tread を正確に設定していない場合、ズレる。
                        twd.stop(0.1)
                    
                    elif cmd_str == 'turnL':
                        print("Detected Left Turn Marker")
                        x = 0
                        eI = 0
                        #if not isMovingForward:
                        print("turning left...")
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.5) # 停止、タイムアウト0.5秒
                        moveToCorner()
                        twd.pivot_turn(RUN_LOWER_RPM, 90, 3) 
                        twd.stop(0.1)
                                    
                    elif cmd_str== 'uturn':
                        print("Detected U-Turn Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.1) # 停止、タイムアウト0.5秒
                        twd.pivot_turn(RUN_LOWER_RPM, -180, 5.5) 
                        twd.stop(0.1)
                        #isMovingForward = not isMovingForward
                        #print("Moving Forward?", isMovingForward)
                                           
                    elif cmd_str=='low_speed':
                        print("Detected Low Speed Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        run_rpm = RUN_LOWER_RPM # 低速モードとする
                    
                    elif cmd_str=='pass':
                        print("Detected Pass Marker")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.1) # 停止、タイムアウト0.5秒
                        passMarker()
                    
                    else:
                        print("Detected Unknown Marker - Pass")
                        x = 0
                        eI = 0
                        isPausingLinetrace = True # ライントレース停止
                        twd.enable() # ラインロストで disable 状態になっている場合がある
                        twd.free(0.1) # 停止、タイムアウト0.5秒
                        passMarker()
                        
                        
                        

                else: # ライントレース処理
                    blue = get_blue_moment(img)
                    blue_u = get_blue_moment(img_u)
                    isLineExist = False # ラインが存在する場合、True
                    isLineExist = blue[0]
                    lineArea = blue[2]
                    lineArea_u = blue_u[2]
                    if isLineExist:
                        lost_count = 0 # ラインロストのカウントをリセット
                        lost_total_count = 0 # ライントータルロストのカウントをリセット
                        # print(lineArea_u)
                        if lineArea > LINE_CROSS_PASS_AREA_THRESHOLD:
                            pass
                        else:
                            if lineArea_u < LINE_UPPER_AREA_THRESHOLD:
                                run_rpm = RUN_LOWER_RPM*(0.7+lineArea_u/LINE_UPPER_AREA_THRESHOLD)
                            else:
                                run_rpm = RUN_BASE_RPM
                            isPausingLinetrace = False
                            x = blue[1][0] - 160 # ラインのx位置を更新
                            twd.enable()
                    else:
                        lost_count += 1 # ロストしたカウントアップ
                        if lost_count >= LOST_THRESHOLD:
                            # 一定回数以上、ラインロスト判定になると、AGVはアイドル状態に戻る
                            if lost_total_count >= LOST_TOTAL_THRESHOLD:
                                if cur_state == State.STATE_LINE_TRACE:
                                    set_state(State.STATE_IDLE)
                                lost_total_count = 0
                            else:
                                # ラインロスト処理
                                lost_total_count += 1
                                print("Line not Exist")
                                cv2.imwrite("img_linelost.jpg",roi)
                                isPausingLinetrace = True # ライントレース停止
                                twd.free()
                                print("Back")
                                # 後退してラインを再発見する。車輪径に応じて調整必要
                                if cur_state == State.STATE_LINE_TRACE:
                                    twd.move_straight(STOP_AFTER_RPM, -180, 5) # 車輪半回転 180°後退、15秒タイムアウトで前進 hsv3:440->510
                                print("Resume Line Trace")
                                reset_pid_params()
                                isPausingLinetrace = False # ライントレース再開
                    # print("x, eI:", x, eI)



            cv2.imshow("Main", hsvImg)
            #cv2.imshow("Raw", image)
            key = cv2.waitKey(1) & 0xFF

            # if the `q` key was pressed, break from the loop
            if key == ord("s"):
                set_state(State.STATE_IDLE)
            elif key == ord("t"):
                set_state(State.STATE_LINE_TRACE)
            elif key == ord("d"):
                set_state(State.STATE_DEBUG)


            # clear the stream in preparation for the next frame
            rawCapture.truncate(0)


    except KeyboardInterrupt:
        twd.disable()




           


