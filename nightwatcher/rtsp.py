import logging
import threading
import time

import cv2


class RTSPCameraStream:
    """
    A class to handle RTSP camera streaming using OpenCV and threading.

    References:
    - http://github.com/god233012yamil/How-to-Stream-a-Camera-Using-OpenCV-and-Threads
    """

    def __init__(self, url: str):
        self.url = url
        self.cap = None
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        self.frame: tuple[bool, cv2.typing.MatLike] | None = None

        self.logger = logging.getLogger(self.__class__.__name__)

    def _connect(self) -> bool:
        try:
            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(self.url)
            if not self.cap.isOpened():
                self.logger.error("Failed to open RTSP stream")
                return False

            self.logger.info("Successfully connected to RTSP stream")
            return True

        except Exception as e:
            self.logger.error(f"Error connecting to RTSP stream: {e}")
            return False

    def start(self) -> None:
        self.logger.info(f"Start rtsp streaming service: {self.url}")

        if self.is_running:
            self.logger.warning("Stream is already running")
            return

        if not self._connect():
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._update_frame, args=(), daemon=True)
        self.thread.start()

        self.logger.info("Stream service started.")

    def stop(self) -> None:
        self.is_running = False

        if self.thread is not None:
            self.thread.join()

        if self.cap and self.cap.isOpened():
            self.cap.release()

    def restart(self) -> None:
        self.logger.info("[Producer]Restarting stream...")
        self.stop()
        self.start()
        self.logger.info("[Producer]Restarting stream done")

    def _update_frame(self) -> None:
        while self.is_running:
            if self.cap is None or not self.cap.isOpened():
                self.logger.info("Attemp to reconnect...")
                if not self._connect():
                    time.sleep(1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                # Retry interval and max times
                self.logger.warning("Failed to read frame, reconnect...")
                self._connect()
                continue

            with self.lock:
                self.frame = (ret, frame)
                self.logger.debug(f"Update frame: {ret}")

    def read(self) -> tuple[bool, cv2.typing.MatLike | None]:
        with self.lock:
            if self.frame is not None:
                return self.frame
            return False, None
