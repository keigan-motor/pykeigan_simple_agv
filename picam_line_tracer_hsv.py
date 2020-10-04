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

# ボタン（赤黄緑）
BUTTON_RED_PIN = 13
BUTTON_RED_PIN_2 = 6 # ２つ目の赤ボタンを追加
BUTTON_YELLOW_PIN = 19
BUTTON_GREEN_PIN = 26

# カメラを初期化し、生画像への参照を取得する
camera = PiCamera()
camera.resolution = (640, 480)
camera.framerate = 32 #32
rawCapture = PiRGBArray(camera, size=(640, 480))
time.sleep(0.1) # カメラのウォームアップ時間

# ライントレーサー
"""
トラックバー（Mainウインドウ下のスライダー）により決定される、
HSV値の範囲の色をラインとして認識する
"""
# 領域分離を行った後、この面積を超えた領域のみ処理を行う
LINE_AREA_THRESHOLD = 7000 # ライン検知用の面積の閾値
LINE_CROSS_PASS_AREA_THRESHOLD = 20000 # ラインを横切った場合に前回のライン位置を採用するための面積の閾値
STOP_MARKER_AREA_THRESHOLD = 40000 # 停止テープマーカーを検知するための面積の閾値（※テープ, arucoマーカーではない）

RUN_CMD_INTERVAL = 0.05 # 0.1秒ごとに処理を行う
RUN_BASE_RPM = 50
STOP_AFTER_RPM = 10
STOP_AFTER_RPM1 = 5

# 負荷有無で PIDコントローラゲインを変更するため（デフォルトは未使用）
hasPayload = False # 負荷あり: True, 負荷なし: False

# マーカーなどで停止する場合に関する変数
shouldStop = False # マーカー発見等で停止すべき場合 True
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

# PIDコントローラのゲイン値：負荷なし
steer_p = 0.05 # 比例
steer_i = 0.0025 # 積分
steer_d = 0 # 微分
# PIDコントローラのゲイン値：負荷あり
steer_load_p = 0.75 # 比例
steer_load_i = 0.5 # 積分
steer_load_d = 0 # 微分

CHARGING_TIME_SEC = 10 # 充電ステーションでの待機時間

old_moment = (320, 50)


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

# KeiganMotor デバイスアドレス（上記参照）
port_left='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KGOA-if00-port0'
port_right='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KVJM-if00-port0'

twd = TWD(port_left, port_right, wheel_d = 101.6, tread = 375, button_event_cb = motor_event_cb) # KeiganMotor の2輪台車 TODO

cur_state = State.STATE_IDLE # システムの現在の状態

eI = 0 # 前回の偏差の積分値を保存しておく
x = 0 # ライン位置
x_old = 0 # ラインの前回の位置を保存しておく


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
    x_old = x
    rpm = (RUN_BASE_RPM + delta_v, RUN_BASE_RPM - delta_v)
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



def scheduler():
    global cur_state, shouldStop, isDocking
    if cur_state == State.STATE_IDLE:
        return
    # タイマーの再生成
    t = threading.Timer(RUN_CMD_INTERVAL, scheduler)
    t.start()
    if shouldStop: # マーカー検知時など停止するべき場合
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


if __name__ == '__main__':

    print("Keigan Line Tracer Start !")

    # GPIOをBCM番号で呼ぶことを宣言
    GPIO.setmode(GPIO.BCM) 

    # ボタン入力の設定
    GPIO.setup(BUTTON_RED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_RED_PIN_2, GPIO.IN, pull_up_down=GPIO.PUD_UP) 
    GPIO.setup(BUTTON_YELLOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) 
    GPIO.setup(BUTTON_GREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) 

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
            roi = image[380:480, 0:640]
            hsvImg = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) # HSV画像
            img = cv2.medianBlur(hsvImg,5)

            # 赤重心の検出
            red = get_red_moment(img)
                        
            isRedMarker = red[0] # 赤マーカーが存在する場合、True
            isLineExist = False # ラインが存在する場合、True

            if cur_state == State.STATE_LINE_TRACE or cur_state == State.STATE_DEBUG:

                if isRedMarker: # 赤マーカーを検知したら、停止して処理（TODO、未使用？）
                    stop_marker_count += 1
                    print("Detected Stop Marker:", stop_marker_count)
                    x = 0
                    eI = 0
                    shouldStop = True # ライントレース停止
                    twd.enable() # ラインロストで disable 状態になっている場合がある
                    twd.free(5) # 停止、タイムアウト5秒
                    #twd.move_straight(10, 360, 5)
                    twd.pivot_turn(10, 180, 10) # TWD初期化時、tread を正確に設定していない場合、ズレる
                    
                    # 以下を有効にすると、緑（白）ボタンを押すまで動作再開しない
                    # set_state(State.STATE_IDLE) 
                    # shouldStop = False # ライントレース再開


                else: 
                    blue = get_blue_moment(img)
                    isLineExist = blue[0]
                    lineArea = blue[2]
                    if isLineExist:
                        lost_count = 0 # ラインロストのカウントをリセット
                        lost_total_count = 0 # ライントータルロストのカウントをリセット
                        if lineArea > LINE_CROSS_PASS_AREA_THRESHOLD:
                            pass
                        else:
                            shouldStop = False
                            x = blue[1][0] - 320 # ラインのx位置を更新
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
                                x = 0
                                eI = 0
                                shouldStop = True # ライントレース停止
                                print("Back")
                                # 半回転戻る TODO
                                if cur_state == State.STATE_LINE_TRACE:
                                    twd.move_straight(STOP_AFTER_RPM, -180, 5) # 1回転=360°、15秒タイムアウトで前進 hsv3:440->510
                                print("Resume Line Trace")
                                #shouldStop = False # ライントレース再開
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




           


