import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Iterator, Self

import cv2


class RTSPCameraStream:
    """
    A class to handle RTSP camera streaming using OpenCV and threading.

    References:
    - http://github.com/god233012yamil/How-to-Stream-a-Camera-Using-OpenCV-and-Threads
    """

    # Number of consecutive read failures before triggering a reconnect.
    MAX_READ_FAILURES = 5
    # Short pause between retries (seconds) to avoid busy-looping.
    RETRY_INTERVAL = 0.3

    def __init__(self, url: str):
        self.url = url
        self.cap = None
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        self.frame: tuple[bool, cv2.typing.MatLike] | None = None
        self._consecutive_failures = 0

        self.logger = logging.getLogger(self.__class__.__name__)

    def _connect(self) -> bool:
        try:
            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5_000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5_000,
                ],
            )

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
                self.logger.info("Attempt to reconnect...")
                if not self._connect():
                    time.sleep(1)
                    continue
                continue

            ret, frame = self.cap.read()
            if not ret:
                self._consecutive_failures += 1
                self.logger.warning(
                    "Failed to read frame (%d/%d)",
                    self._consecutive_failures,
                    self.MAX_READ_FAILURES,
                )
                if self._consecutive_failures < self.MAX_READ_FAILURES:
                    time.sleep(self.RETRY_INTERVAL)
                    continue
                # Exceeded threshold — reconnect
                self.logger.warning("Too many consecutive failures, reconnecting...")
                self._consecutive_failures = 0
                if not self._connect():
                    time.sleep(2)
                else:
                    time.sleep(0.5)
                continue

            self._consecutive_failures = 0
            with self.lock:
                self.frame = (ret, frame)
                self.logger.debug(f"Update frame: {ret}")

    def read(self) -> tuple[bool, cv2.typing.MatLike | None]:
        with self.lock:
            if self.frame is not None:
                return self.frame
            return False, None


class CameraGroup:
    def __init__(self, cameras: tuple[RTSPCameraStream, ...]):
        self.cameras = cameras
        self.stop_event = Event()
        self._executor = ThreadPoolExecutor(max_workers=len(self.cameras))
        self._current = 0

    def start(self) -> Self:
        for camera in self.cameras:
            self._executor.submit(camera.start)

        return self

    def stop(self):
        self.stop_event.set()
        for camera in self.cameras:
            camera.stop()
        self._executor.shutdown(wait=True)

    def __iter__(self) -> Iterator[RTSPCameraStream]:
        return self

    def __next__(self) -> RTSPCameraStream:
        if self._current >= len(self.cameras):
            self._current = 0
            raise StopIteration
        camera = self.cameras[self._current]
        self._current += 1
        return camera
