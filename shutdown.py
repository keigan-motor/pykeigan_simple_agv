#!/usr/bin/python 
# coding:utf-8 
import time
import RPi.GPIO as GPIO
import os
 
SHUTDOWN_PIN = 13
REBOOT_PIN = 19
SHUTDOWN_SEC = 3
REBOOT_SEC = SHUTDOWN_SEC

def shutdown_callback(gpio_pin):
    #time.sleep(SHUTDOWN_SEC)
    sw_counter = 0 
    while True:
        sw_status = GPIO.input(SHUTDOWN_PIN)
        if sw_status == 0:
            sw_counter += 1
            if sw_counter >= SHUTDOWN_SEC * 100:
                print("Detect Long Press for shutdown")
                os.system("sudo shutdown -h now")
                break
        else:
            print("Ignore Short Press for shutdown")
            break
        time.sleep(0.01)

def reboot_callback(gpio_pin):
    #time.sleep(REBOOT_SEC)
    sw_counter = 0 
    while True:
        sw_status = GPIO.input(REBOOT_PIN)
        if sw_status == 0:
            sw_counter += 1
            if sw_counter >= REBOOT_SEC * 100:
                print("Detect Long Press for reboot")
                os.system("sudo reboot now")
                break
        else:
            print("Ignore Short Press for reboot")
            break
        time.sleep(0.01)


GPIO.setmode(GPIO.BCM)
 
GPIO.setup(SHUTDOWN_PIN,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(REBOOT_PIN,GPIO.IN,pull_up_down=GPIO.PUD_UP)

GPIO.add_event_detect(SHUTDOWN_PIN, GPIO.FALLING, callback=shutdown_callback, bouncetime=50)
GPIO.add_event_detect(REBOOT_PIN, GPIO.FALLING, callback=reboot_callback, bouncetime=50)

while True:
    # do nothing
    continue