#!/usr/bin/python 
# coding:utf-8 
import asyncio
import RPi.GPIO as GPIO
import os
import time
 
SHUTDOWN_PIN = 13
REBOOT_PIN = 19
SHUTDOWN_SEC = 3
REBOOT_SEC = 2

def shutdown_callback(gpio_pin):
    sw_counter = 0
    while True:
        sw_status = GPIO.input(SHUTDOWN_PIN)
        if sw_status == 0:
            sw_counter += 1
            if sw_counter >= SHUTDOWN_SEC:
                print("Detect Long Press for shutdown")
                os.system("sudo shutdown -h now")
        time.sleep(1)
  
       

def reboot_callback(gpio_pin):
    sw_counter = 0
    while True:
        sw_status = GPIO.input(REBOOT_PIN)
        if sw_status == 0:
            sw_counter += 1
            if sw_counter >= REBOOT_SEC:
                print("Detect Long Press for reboot")
                os.system("sudo reboot now")
        time.sleep(1)


GPIO.setmode(GPIO.BCM)
 
GPIO.setup(SHUTDOWN_PIN,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(REBOOT_PIN,GPIO.IN,pull_up_down=GPIO.PUD_UP)

GPIO.add_event_detect(SHUTDOWN_PIN, GPIO.FALLING, callback=shutdown_callback, bouncetime=200)
GPIO.add_event_detect(REBOOT_PIN, GPIO.FALLING, callback=reboot_callback, bouncetime=200)

async def main():
    print("shutdown main()")
    while True:
        # print("ho")
        await asyncio.sleep(10)
    
if __name__ == "__main__":
    asyncio.run(main())


