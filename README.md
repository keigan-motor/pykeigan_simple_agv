Simple line tracer AGV framework using KeiganMotor
==============================================

## はじめに
KeiganMotor，Raspberry Pi, カメラ, を使用して、USBモバイルバッテリーで動作するライントレーサーAGVを作ることができます。

デフォルト状態では、青色のテープをトレースし、赤色のテープを検知すると停止します。

## KeiganAGV Kit
本AGVシステムを製作するために必要なパーツをキット化したものです。
動作に必要なソフトウェアはセットアップされています。

- 製品ページ: 作成中

（参考）
- 製品サイト: https://keigan-motor.com
- ドキュメント: https://docs.keigan-motor.com

## 必要条件
### ハードウェア
- Raspberry Pi 3B+ または 3A+
- Pi Camera https://picamera.readthedocs.io/
- KeiganMotor KM-1S-M6829
- KeiganMotor KM-1S-M6829 搬送ローラー

### ソフトウェア
- Linux 系 OS
- Python >= 3.5 (recommended) or 2.7
- pyserial >= 3.4
- opencv-contrib-python 4.3

## OpenCV のインストール
```
pip3 install opencv-contrib-python
```
上記だけで動作しない場合、以下を全てインストールします。
***必ず 1個ずつ行うこと。一気にコピペしてやると[Y]入力のところで失敗します。***

```
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
## Picamera の準備
Raspberry Pi デスクトップ画面のメニューボタンから「設定」＞「Raspberry Piの設定」を選択します。

「インターフェイス」タブから、「カメラ」が「有効」になっていることを確認します。


## ダウンロードと実行
本リポジトリのzipファイルをダウンロードし、解凍します。以下を実行します。
```
python3 picam_line_tracer_hsv.py
```

## ライントレースの原理
OpenCVを使ってHSV画像→指定領域を抽出し、最大重心の面積を求めています。
- HSV化 (RGB -> HSV画像)
- 赤停止マーカーを区別するため、指定のHSV領域を分離し、最大面積の重心を取る get_blue_moment() 関数参照
- 青ラインを区別するため、指定のHSV領域を分離し、最大面積の重心を取る get_blue_moment() 関数参照
- 青ラインの重心座標から、センターからのズレ量を算出し、 pid_controller() 関数でモーターに与える速度を決定する

### ライン検知の設定変更
場合によっては以下の定義を変更します。
```
LINE_AREA_THRESHOLD = 7000 # ライン検知用の面積の閾値
LINE_CROSS_PASS_AREA_THRESHOLD = 30000 # ラインを横切った場合に前回のライン位置を採用するための面積の閾値
STOP_MARKER_AREA_THRESHOLD = 40000 # 停止テープマーカーを検知するための面積の閾値（※テープ, arucoマーカーではない）
```

## HSV画像抽出、PIDパラメタの調整

picam_line_tracer_hsv.py を実行すると、各ウインドウの下に、スライダー＝トラックバーが生成されます。
スライダーを動かすことにより、値を調整します。（値は整数値 0-255 しか設定できません。）

### HSV画像抽出
HSVによるラインの色抽出は、H: 色相, S:彩度, V:明度 により行います。
以下リンク参照。
- https://algorithm.joho.info/programming/python/opencv-color-detection/
- https://www.peko-step.com/html/hsv.html

※ OpenCVでの H は、0-179 しか受け付けないので、Hは 0-360° 表記の半分にする必要があります。

### PIDゲイン調整
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
steer_p = 0.05 # 比例
steer_i = 0.0025 # 積分
steer_d = 0 # 微分
# PIDコントローラのゲイン値：負荷あり
steer_load_p = 0.75 # 比例
steer_load_i = 0.5 # 積分
steer_load_d = 0 # 微分
```


***
## 2輪AGV用の KeiganMotorライブラリ twd.py
KeiganMotor での AGV開発を簡単にするためのライブラリです。
メインファイルと同じフォルダに、twd.py を置いて下さい。

### インポート
```python
from twd import TWD
```

### 初期化
port_left, port_right は、従来の KeiganMotor デバイスアドレス。
```python
port_left='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KG0L-if00-port0'
port_right='/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KWNH-if00-port0'

twd = TWD(port_left, port_right) # KeiganMotor の2輪台車
```

オプションで、以下のプロパティを指定できる
- safe_time: 安全装置。この値以上超えて次の動作命令を受信できないと、自動的にKeiganMotorが停止する
- safe_option: 安全オプション。安全装置で作動する停止アクション。(0:free,1:disable,2:stop, 3:position固定)
- wheel_d: ホイールタイヤの直径（最外径）[mm]
- tread: トレッド幅。左右の車輪間の距離 [mm]

```python
twd = TWD(self, port_left, port_right, safe_time = 1, safe_option = 1, wheel_d = 100, tread = 400)
```

#### KeiganMotor デバイスアドレスの見つけ方
従来と同じで、デバイスアドレス（ポート）は固有IDで指定する
"/dev/ttyUSB0"で表示されるデバイス名での接続は、複数のモーターを接続した場合に変わる可能性がある。
複数のモーターがある場合で、モーターを特定して接続する場合は "$ls /dev/serial/by-id/" で表示されるデバイスを使用する。
```
/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00LSSA-if00-port0
```

### 動作許可
```python
twd.enable()
```

### 動作不許可（トルクゼロ）
```python
twd.disable()
```

### 速度制御
左右の rpm を引数とする。速度差をつけることにより旋回が可能。
```python
twd.run(10, 10) # 左 10[rpm], 右 10[rpm]
```

### 直進（位置制御）
まっすぐ進む。左右共通の rpm, 回転角度[deg], タイムアウト[s]を指定する
負の回転角度で後退となる 
```python
twd.move_straight(10, 360, 5) # 10rpm, 360[deg], 5[s]
```

### その場で旋回（位置制御）
回転軸を変えずにその場で旋回する。左右共通の rpm, 真上から見た車体旋回角度[deg], タイムアウト[s]を指定する
正の旋回角度で ccw 反時計回り、負の旋回角度で cw 時計回りとなる 
***本コマンドを使用するためには、初期化時に、wheel_d（車輪径）及び tread （トレッド幅）が設定されていなければならない。***
```python
twd.pivot_turn(10, 90, 5) # 10rpm, 90[deg], 5[s]
```

### 停止
指定秒数停止する（トルクあり）
```python
twd.stop(10) # 10秒後に安全装置復活
```

### フリー
指定秒数フリー状態とする（粘性トルクあり）
```python
twd.free(10) # 10秒後に安全装置復活
```

### LED
KeiganMotor 搭載フルカラーLED
```python
twd.led(1, 355, 0, 0) # 1:点灯, red, green, blue:0-255
```

***
## ラインテープの貼り方
ライントレース用のラインは、50mm幅の、青ラインテープを使う。

停止用の赤テープも含めて、monotaro等で購入可能
https://www.monotaro.com/g/01259483/

***停止用の赤テープも同様であるが、青ラインに対して垂直に、400mm 以上の長さを貼ること。***
***