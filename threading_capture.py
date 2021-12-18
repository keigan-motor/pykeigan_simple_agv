import threading


class threading_capture:
    def __init__(self, cap, max_queue_size=1):
        self.video = cap
        self.stopped = False
        self.frame = None

    def start(self):
        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()
        return self

    def update(self):
        while True:

            if self.stopped:
                return

            ok, frame = self.video.read()
            self.frame = frame

            if not ok:
                self.stop()
                return

    def read(self):
        if self.frame is None:
            return False, None
        else:
            return True, self.frame

    def stop(self):
        self.stopped = True

    def release(self):
        self.stopped = True
        self.video.release()

    def isOpened(self):
        return self.video.isOpened()

    def get(self, i):
        return self.video.get(i)