import time
import cv2

CAM_U1_DEVICE_ID = 0 #USBcam1 /dev/video0
CAM_U_WIDTH = 640
CAM_U_HEIGHT = 480
CAM_U_FPS = 30

camera = cv2.VideoCapture(CAM_U1_DEVICE_ID)
camera.set(cv2.CAP_PROP_FRAME_WIDTH,CAM_U_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT,CAM_U_HEIGHT)
camera.set(cv2.CAP_PROP_FPS,CAM_U_FPS)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
camera.set(cv2.CAP_PROP_BUFFERSIZE,1)

# allow the camera to warmup
time.sleep(0.1)

# カメラからフレームをキャプチャする
while(True):
    # grab the raw NumPy array representing the image, then initialize the timestamp
    # and occupied/unoccupied text
    # ret,frame = capture.read()
    ret,frame = camera.read()
    image = frame.copy()
    cv2.imshow("Frame", image)
    key = cv2.waitKey(1) & 0xFF

    # if the `q` key was pressed, break from the loop
    if key == ord("s"):
        print("s")


    # clear the stream in preparation for the next frame
    # rawCapture.truncate(0)
