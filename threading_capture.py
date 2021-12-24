import threading
import time


class threading_capture:
    def __init__(self, cap, max_queue_size=1):
        self.video = cap
        self.stopped = False
        self.frame = None

    def start(self):
        #process = multiprocessing.Process(target=self.update, args=(queue_from_cam, ), daemon=True)
        thread=threading.Thread(target=self.update, daemon=True)
        #process.start()
        thread.start()
        return self

    def update(self): #, queue_from_cam):
        while True:
            try:
                if self.stopped:
                    return
                
                ok, frame = self.video.read()
                self.frame=frame
                #queue_from_cam.put(frame)

                if not ok:
                    self.stop()
                    return
            except cv2.error:
                print("cv2.error")
                
            except KeyboardInterrupt:
                break
            
        self.video.release()

    def read(self):
        #from_queue = queue_from_cam.get()
        if self.frame is None:
        #if from_queue is None:
            return False, None
        else:
            return True, self.frame #from_queue

    def stop(self):
        self.stopped = True

    def release(self):
        self.stopped = True
        self.video.release()

    def isOpened(self):
        return self.video.isOpened()

    def get(self, i):
        return self.video.get(i)