Simple line tracer AGV by KeiganMotor
==============================================

# はじめに
KeiganMotor，Raspberry Pi, USBカメラ または PiCamera, を使用して、USBモバイルバッテリーで動作するライントレーサーAGVを作ることができます。

青色のテープをライントレースします。

arucoマーカーや赤色のテープを検知し、停止などを実行することができます。

KeiganMotor を追加することにより、搬送物の積み下ろしなどの応用が可能です。

![AGV上部連携](/img/AGVLoader.gif) 

青色または青色に近い床の場合は、動作しない場合があります。

その場合、黄色のラインテープで動作する場合があります。（HSV値の調整が必要です）

# KeiganAGV Kit
本AGVシステムを製作するために必要なパーツをキット化したものです。
動作に必要なソフトウェアはセットアップされています。

![KeiganAGV10LU](/img/AGVKit_1.jpg) 

- 製品ページ: https://keigan-motor.com/agvtolu/
- 製品サイト: https://keigan-motor.com
- ドキュメント: https://docs.keigan-motor.com


# 必要条件
## ハードウェア
- Raspberry Pi 3B+, 3A+ または 4B（4Bの場合はUSBハブ必須）
- PiCamera または USBカメラ
    - https://picamera.readthedocs.io/
- KeiganMotor 駆動輪 2個分
- AGVフレーム、キャスターなど（5kg 未満推奨）

### USBカメラ
以下の機種を推奨します。
- Buffalo BSW500MBK（広角120°モデル）

#### カメラの設置例
例えば、AGV前方に、カメラレンズ 床面からの高さ 125mm 斜め45°下を投射する形で設置します。

カメラの画角により異なりますので、調整して下さい。

### KeiganMotor 
以下を使用します。
- KeiganMotor KM-1S-M6829TS ホイールキット
    - https://keigan-motor.com/km-1s/

- ファームウェア を ver 2.73B 以降にアップデートして下さい。
    - https://docs.keigan-motor.com/firmware/download
    
- KeiganMotor が走行中に再起動し、停止する問題が生じる場合
    - ver 2.39 ファームウェアを使用することで、安定する場合があります。


## ソフトウェア要件
- Raspberry Pi OS
- Python >= 3.5 (recommended) or 2.7
- pykeigan_motor >= 2.3.1
    - https://github.com/keigan-motor/pykeigan_motor
- OpenCV 
    - opencv-contrib-python 4.3


### Raspberry Pi OS 
バージョンは以下を対象とします。
- Distributor ID: Raspbian
- Description:    Raspbian GNU/Linux 10 (buster)
- Release:        10
- Codename:       buster

# バージョン履歴
- 2021/12/23 ver. 1.1.1 Latest
    - systemd による自動起動の方法を変更（シェル→python）
    - USBカメラ使用時の動作、検知性能の改善
- 2021/12/18 ver. 1.1.0
    - USBカメラ を追加

# 準備
## 画像認識のためのマーカー
### 1. ラインテープ
#### ラインテープの貼り方
ライントレース用のラインは、50mm幅の、青ラインテープを使います。
停止用の赤テープも含めて、monotaro等で購入可能です。
- グローブ社 ラインテープ 50mm×33m
    - https://www.monotaro.com/g/01259483/

引っ張りながら貼ることにより、曲線も綺麗に貼ることができます。
曲線の場合は、500mm 以上の半径 R を取ってください。


***停止用のテープは、青ラインに対して垂直に、400mm 以上の長さを貼ること。***

### 2. aruco マーカー
オープンソースの2次元マーカーです。
OpenCV の contrib パッケージに含まれます。
以下のサイトから印刷することが可能です。
- https://chev.me/arucogen/


![stop to see aruco marker](/img/aruco.jpg) 

aruco マーカーの ID によって、動作を変更するサンプルは、以下を参照下さい。
https://github.com/keigan-motor/pykeigan_simple_agv/tree/cd_dev_0725_picam
config_test.ini に定義されたアクションを実行します。

#### config_test.ini アクションの例
[aruco_id_command]
0 = idle: アイドル状態にする
1 = placing_task: ラズパイのGPIOを用いる特定のタスク
2 = turnL: 左に90度旋回
3 = pass
4 = pass
5 = turnL: 左に90度旋回
6 = picking_task: ラズパイのGPIOを用いる特定のタスク
7 = pass
8 = pass
9 = idle: アイドル状態にする
10 = pause: 一時停止

#### 注意点
- 床面に貼る場合、上から透明の保護テープを貼ることを推奨します。
- 60mm～100mm 角のサイズを推奨しますが、検知失敗する場合はサイズ調整やカメラの高さ変更を実施して下さい。

## PC 側の準備
### VNC Viewer のダウンロード
お使いのPCに、VNC Viewer をダウンロードします。

## Raspberry Pi 側の準備
KeiganAGV Kit では、本「準備」に含まれるソフトウェアはSDカードに全てセットアップ済みです。

Wi-Fi の設定は必要となります。

### インターフェイス機器の接続
Raspberry Pi に HDMIディスプレイ、マウス・キーボード を接続します。
VNC　Viewer でリモート接続後は、不要です。

### PiCamera と VNC Viewer の有効化
Raspberry Pi デスクトップ画面のメニューボタンから「設定」＞「Raspberry Piの設定」を選択します。

「インターフェイス」タブから、以下の「有効」を選択し、[OK] をクリックします。

- カメラ（PiCameraの場合のみ）
- VNC


### Wi-Fi の設定
お使いのPCと同じ Wi-Fi アクセスポイント に Raspberry Pi の接続設定を行って下さい。

右下のタスクトレイから、VNC Viewerのアイコンをクリックし、IPアドレスをメモします。

再起動後、PiCamera と VNC でのリモート接続が有効になります。
以後は、ご使用のPCからリモート開発が可能です。

### OpenCV のインストール
バージョンは 4.1.0.25 を指定して下さい。

Raspberry Pi OS のバージョンは上記参照下さい。

```
pip3 install opencv-contrib-python==4.1.0.25
```
上記だけで cv2（OpenCV）が動作しない場合、以下を全てインストールします。

***必ず 1個ずつ行うこと。一気にコピペしてやると[Y]入力のところで失敗します。***

```
sudo apt install libhdf5-103
sudo apt install libcblas
sudo apt install libatlas-base-dev
sudo apt install libhdf5-100
sudo apt install libharfbuzz0b
sudo apt install libwebp6
sudo apt install libjasper1
sudo apt install libilmbase12
sudo apt install libopenexr22
sudo apt install libgstreamer1.0-0
sudo apt install libavcodec-extra57
sudo apt install libavformat57
sudo apt install libswscale4
sudo apt install libgtk-3
sudo apt install libgtk-3-0
sudo apt install libqtgui4
sudo apt install libqt4-test
```
[Y/n] か聞かれたら、Y+Enter を押す。ImportError が出る場合、
該当するライブラリをコピペしてもう一度インストールする。

（オプション）OpenCVのhighguiモジュールに必要なライブラリであるGTKをインストールする方法。
```
sudo apt-get install libgtk2.0-dev
```

### KeiganMotor Python ライブラリのインストール
pykeigan_motor 2.3.1 以降をご使用下さい。
- https://github.com/keigan-motor/pykeigan_motor

```
pip3 install pykeigan_motor
```

### プログラムのダウンロード
本リポジトリのzipファイルをダウンロードし、解凍します。KeiganAGVKitでは、デスクトップに予め設置しています。

## デバイスの準備

### カメラのフォーカス合わせ
予め PiCamera または USBカメラ のフォーカスを合わせて下さい。
- AGVKit 付属の USBカメラは調整できません。

レンズ鏡筒部を手で回すことにより調整できる場合があります。

フォーカスが合っていない場合、脱線の原因となります。

カメラ単体の確認は、device_test フォルダ内の、usbcamera_test.py または picamera_test.py を実行します。
```
python3 usbcamera_test.py
```
または
```
python3 picamera_test.py
```

実際にラインを撮影し、動画が鮮明になるように調整して下さい。

### KeiganMotor の接続とデバイスアドレス
Python から KeiganMotor を USB経由でコントロールするためには、デバイスアドレス（デバイスファイル名）の指定が必要です。

KeiganMotor を USBポートのどこにつないでも動作するため、通常は以下の手順 A を推奨します。

#### A. KeiganMotor固有のデバイスアドレスを使用する (推奨)
USBポートのどこにつないでも固有のデバイスアドレスを指定する方法です。

KeiganMotorによらず、任意のUSBデバイスに対して固有のデバイスアドレスでアクセスできます。

任意のUSBポートに KeiganMotor を 1つずつ接続し、以下のコマンドにより、表示されるデバイスアドレス（デバイスファイル）を記録します。
```
ls /dev/serial/by-id/
```
KeiganMotor デバイスアドレスの例
```
usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0
```
この場合、Python ファイルで のデバイスアドレス指定は、フルパスとして以下の様に行います。
```
port_left = "/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0"
```

デバイスアドレスを更新した場合、ファイルpicam_line_tracer_hsv.py または usbcam_line_tracer_hsv.py における、port_left, port_right をそれぞれ書き換えて下さい。


#### B. 特定のUSBポート番号に対し、デバイスアドレスを固定する
USBポートの特定の位置に KeiganMotor を接続し、区別する方法です。（非推奨）

KeiganMotor を固定で接続したいUSBポートに接続し、以下で PATH を調べます。
```
sudo udevadm info -q all -n /dev/ttyUSB0
```
出力の中で、DEVPATH が
```
E: DEVPATH=/devices/platform/soc/3f980000.usb/usb1/1-1/1-1.4/1-1.4:1.0/ttyUSB0/tty/ttyUSB0
```
である場合、
```
/usb1/1-1/1-1.4/1-1.4:1.0/
```
の部分を抽出します。

以下で、固定のUSBポートに対して、デバイスアドレスを固定するためのルールファイルを作成します。
```
sudo nano /etc/udev/rules.d/90-usb.rules
```
以下のように書き込んで、ESC キー + :wq により、保存します。
SUBSYSTEM=="tty", DEVPATH=="*/usb1/1-1/1-1.3/1-1.3:1.0/*", SYMLINK+="ttyUSB_RightMotor"

再起動します。
```
sudo reboot now
```
以下で、正常にデバイスアドレスの置き換えができているか確認します。
```
ls -l /dev/ttyUSB*
```
正常であれば、以下のように出力されます。
```
crw-rw---- 1 root dialout 188, 0  7月 22 19:41 /dev/ttyUSB0
lrwxrwxrwx 1 root root         7  7月 22 19:36 /dev/ttyUSB_RightMotor -> ttyUSB0
```
本手順を、KeiganMotor すべてに対して行います。


### モーターのチェック
KeiganMotor の動作チェックを行います。

device_test フォルダ内の、motor_test.py を実行します。


# ライントレースプログラムの実行

***KeiganAGVKit では、本プログラムは起動時に自動実行するように設定しています（後述）。***


VNC Viewer で Raspberry Pi にリモート接続します。

以下をターミナル または Thonny で実行します。

ターミナルの方が実行速度が早くなります。
```
cd /home/pi/Desktop/pykeigan_simple_agv
```

### PiCamera の場合
```
python3 picam_line_tracer_hsv.py
```

### USBカメラ の場合
```
python3 usbcam_line_tracer_hsv.py
```


プログラムが正常に実行されれば、以下のようなログが出力されます。
```
Keigan Line Tracer Start !
-> State.STATE_IDLE
キーボードの [s] + Enter または 赤ボタン: ストップ STATE_IDLE
キーボードの [t] + Enter または 緑ボタン: ライントレーサー STATE_LINE_TRACE
キーボードの [d] + Enter :デバッグ用 STATE_DEBUG
```

## ライントレーサーの開始と停止
以下の3通りの方法で、ライントレースの開始と停止をコントロールできます。
- OpenCV で出力される ウィンドウのいずれかを選択した状態で、上記のキーボード操作
    - ライントレース停止（STATE_IDLE）: キーボードの[s] + Enter
    - ライントレース開始（STATE_LINE_TRACE）: キーボードの[t] + Enter
    - デバッグ用:ログを出力して画像のみ確認（STATE_DEBUG）: キーボードの[d] + Enter 
- 物理ボタンを押す
    - ライントレース停止（STATE_IDLE）: 赤ボタン
    - ライントレース開始（STATE_LINE_TRACE）: 白または緑ボタン
- KeiganMotor コントローラ本体のボタンを押す（いずれのKeiganMotorでも可）
    - ライントレース停止（STATE_IDLE）: 停止（■）ボタン
    - ライントレース開始（STATE_LINE_TRACE）: 再生（▶）ボタン

## 検知率を向上させたい場合
- 共通
    - カメラの位置・角度を調整する
- ライントレースカーブ時のロスト
    - 曲線の半径 R を大きくとる
- Arucoマーカー
    - マーカーのサイズを変更する 
    - 反射の小さいマットな印刷にする


## プログラムの終了
### ターミナルから起動した場合 
[Ctrl] + [C] キーで Python プログラムを終了

### ターミナルから名前を指定して強制終了する
名前を指定してプロセスを強制終了する

pkill -f _line_tracer

# プログラムの自動実行
以下の手順により Pythonプログラムを OS起動直後に自動実行できます。
AGVKit では、本自動起動は設定済みです。

## 自動実行の仕組み systemd
KeiganAGVでは、systemd の仕組みを用いて自動実行を実現しています。

- システム起動
- /etc/systemd/system/km.service を実行
- /home/pi/Desktop/pykeigan_simple_agv/start.py を実行

## 自動起動サービス有効化の手順
root権限で以下の場所に km.service ファイルを作成します
```
sudo nano /etc/systemd/system/km.service
```
#### km.service ファイルの編集
中身を以下とします。start.py を自動起動設定します。

```
[Unit]
Description=Keigan Line Tracer

[Service]
Type=idle
ExecStart=/usr/bin/python3  /home/pi/Desktop/pykeigan_simple_agv/start.py
User=pi
Restart=always
RestartSec=10
Environment=DISPLAY=:0.0
StandardOutput=syslog+console

[Install]
WantedBy=multi-user.target
```

### 注意点
ver 1.1.1 以降、本リポジトリのデフォルトはUSBカメラ用 usbcam_line_tracer_hsv.py の起動設定になっています。

PiCamera を使用する場合は、start.py を編集し、usbcam_line_tracer_hsv.py から picam_line_tracer_hsv.py に変更して下さい。

### start.py で起動されるプログラム
- *_line_tracer_hsv.py # ライントレーサーのメインプログラム
- shutdown.py # 赤ボタン長押しでラズパイを安全にシャットダウンする


### 自動起動有効化と再起動
以下で有効化し、再起動します。問題がなければ自動起動します。
```
sudo systemctl enable km.service
sudo reboot
```

## 自動起動の無効化
サービスの終了（startの反対）
```
sudo systemctl disable km.service
```

### 起動中サービスの確認 
```
systemctl list-units --type=service
```
※ すでにstart済みのサービスを重複して起動はできません

### km.service を変更した場合
サービスの再読み込みに、以下が必要な場合があります。
```
sudo systemctl reload-daemon
```

### 起動しない場合のエラーログ確認。
Pythonプログラムが自動起動しない場合は、以下でログを確認できます。
```
journalctl -e
```

# ライントレースの原理
OpenCVを使ってHSV画像→指定領域を抽出し、最大重心の面積を求めています。
- HSV化 (RGB -> HSV画像)
- 赤停止マーカーを区別するため、指定のHSV領域を分離し、最大面積の重心を取る get_blue_moment() 関数参照
- 青ラインを区別するため、指定のHSV領域を分離し、最大面積の重心を取る get_blue_moment() 関数参照
- 青ラインの重心座標から、センターからのズレ量を算出し、 pid_controller() 関数でモーターに与える速度を決定する

## ライン検知の設定変更
場合によっては以下の定義を変更します。
```
LINE_AREA_THRESHOLD = 7000 # ライン検知用の面積の閾値
LINE_CROSS_PASS_AREA_THRESHOLD = 30000 # ラインを横切った場合に前回のライン位置を採用するための面積の閾値
STOP_MARKER_AREA_THRESHOLD = 40000 # 停止テープマーカーを検知するための面積の閾値（※テープ, arucoマーカーではない）
```

## HSV画像抽出、PIDパラメタの調整
picam_line_tracer_hsv.py を実行すると、各ウインドウの下に、スライダー＝トラックバーが生成されます。
スライダーを動かすことにより、値を調整します。（値は整数値 0-255 しか設定できません。）

## HSV画像抽出
HSVによるラインの色抽出は、H: 色相, S:彩度, V:明度 により行います。
以下リンク参照。
- https://algorithm.joho.info/programming/python/opencv-color-detection/
- https://www.peko-step.com/html/hsv.html

※ OpenCVでの H は、0-179 しか受け付けないので、Hは 0-360° 表記の半分にする必要があります。

## PIDゲイン調整
同フォルダ内 OpenCV_UI_説明.pdf 参照
Main ウインドウ下のスライダー＝トラックバーを操作することにより調整できる
以下のように、負荷あり、負荷なしでゲイン変数を分けているが、
今回は負荷ありのパラメタは使っていない。
必要であれば、
```python
hasPayload = True
```
とすることにより、負荷ありのゲインが採用される
```python
# PIDコントローラのゲイン値：負荷なし
steer_p = 0.075 # 比例
steer_i = 0.0025 # 積分
steer_d = 0 # 微分
# PIDコントローラのゲイン値：負荷あり
steer_load_p = 0.75 # 比例
steer_load_i = 0.5 # 積分
steer_load_d = 0 # 微分
```


***
# 2輪AGV用の KeiganMotorライブラリ twd.py
KeiganMotor での AGV開発を簡単にするためのライブラリです。
メインファイルと同じフォルダに、twd.py を置いて下さい。

## インポート
```python
from twd import TWD
```

## 初期化
port_left, port_right は、従来の KeiganMotor デバイスアドレスとなる。
デバイスアドレスの指定方法は、上記「KeiganMotor の接続とデバイスアドレス」を参照下さい。
```python
port_left='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KG0L-if00-port0'
port_right='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KWNH-if00-port0'
twd = TWD(port_left, port_right) # KeiganMotor の2輪台車
```

オプションで、以下のプロパティを指定できます
- safe_time: 安全装置。この値[msec]以上超えて次の動作命令を受信できないと、自動的にKeiganMotorが停止する
- safe_option: 安全オプション。安全装置で作動する停止アクション。(0:free,1:disable,2:stop, 3:position固定)
- wheel_d: ホイールタイヤの直径（最外径）[mm]
- tread: トレッド幅。左右の車輪間の距離 [mm]

```python
twd = TWD(self, port_left, port_right, safe_time = 1, safe_option = 1, wheel_d = 100, tread = 400)
```


## 動作許可
本コマンドを入れないと、AGVの動作コマンド（run等）は無効となります。
```python
twd.enable()
```

## 動作不許可（トルクゼロ）
```python
twd.disable()
```

## 速度制御
左右の rpm を引数とします。※ 前進したい場合、正の数を引数に取ります。
速度差をつけることにより旋回が可能です。
```python
twd.run(10, 10) # 左 10[rpm], 右 10[rpm] で直進
```

## 直進（位置制御）
まっすぐ進みます。左右共通の rpm, 回転角度[deg], タイムアウト[s]を指定します。
負の回転角度で後退となります。
```python
twd.move_straight(10, 360, 5) # 10rpm, 360[deg], 5[s]
```

## その場で旋回（位置制御）
回転軸を変えずにその場で旋回します。
左右共通の rpm, 真上から見た車体旋回角度[deg], タイムアウト[s]を指定します。

正の旋回角度で ccw 反時計回り、負の旋回角度で cw 時計回りとなります。

***本コマンドを使用するためには、初期化時に、wheel_d（車輪径）及び tread （トレッド幅）が設定されていなければならない。***
```python
twd.pivot_turn(10, 90, 5) # 10rpm, 90[deg], 5[s]
```

## 停止
指定秒数停止します。（トルクあり）
引数なしまたはゼロで、状態を継続します。
```python
twd.stop(10) # 10秒後に安全装置復活
```

## フリー
指定秒数フリー状態とする（粘性トルクあり）
引数なしまたはゼロで、状態を継続します。
```python
twd.free(10) # 10秒後に安全装置復活
```

## LED
KeiganMotor 搭載フルカラーLEDの制御を行います。
```python
twd.led(1, 355, 0, 0) # 1:点灯, red, green, blue:0-255
```

