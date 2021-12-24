from pykeigan import usbcontroller
import time

# デバイスネームをお持ちのものに置き換えて下さい
dev1=usbcontroller.USBController('/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KHJE-if00-port0')
dev2=usbcontroller.USBController('/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DM00KHN4-if00-port0')

# KeiganMotor バージョンは、2.73B 以降をお使い下さい
dev1.enable_check_sum(True)
dev2.enable_check_sum(True)
time.sleep(1.0)
dev1.enable_action()
dev2.enable_action()
dev1.set_speed(1.0)
dev2.set_speed(1.0)

dev1.run_forward()
dev2.run_forward()

time.sleep(3)

dev1.disable_action()
dev2.disable_action()

