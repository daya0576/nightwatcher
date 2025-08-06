import base64
import logging
import os
import signal
import threading
import time

import cv2
import numpy as np
from dotenv import load_dotenv
from nicegui import Client, app, core, ui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(),
    ],
)


load_dotenv()


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


def convert(frame: np.ndarray) -> bytes:
    """Converts a frame from OpenCV to a JPEG image.

    This is a free function (not in a class or inner-function),
    to allow run.cpu_bound to pickle it and send it to a separate process.
    """
    _, imencode_image = cv2.imencode(".jpg", frame)
    return imencode_image.tobytes()


def create_camera_view(camera: RTSPCameraStream):
    def update_image(camera):
        ret, frame = camera.read()
        logging.debug(f"[Consumer]Read latest frame: {ret},{str(frame)[:10]}")
        if not ret:
            return

        image_bytes = convert(frame)
        logging.debug(f"[Consumer]Convert frame to byte: {len(image_bytes)}")

        base64_str = base64.b64encode(image_bytes).decode("utf-8")
        video_image.set_source(f"data:image/png;base64,{base64_str}")

    video_image = ui.interactive_image().classes("w-full h-full")

    # A timer constantly updates the source of the image.
    # Because data from same paths is cached by the browser,
    # we must force an update by adding the current timestamp to the source.
    ui.timer(interval=0.1, callback=lambda: update_image(camera))


def setup() -> None:
    rtsp_urls = os.getenv("RTSP_URLS", "")
    assert rtsp_urls, f"Invalid rtsp urls: {rtsp_urls}"

    cameras = tuple(RTSPCameraStream(url) for url in rtsp_urls.split(","))
    for camera in cameras:
        camera.start()

    @ui.page("/")
    async def index():
        ui.label("Nightwatchers!!")
        for camera in cameras:
            create_camera_view(camera)

    async def disconnect() -> None:
        """Disconnect all clients from current running server."""
        for client_id in Client.instances:
            await core.sio.disconnect(client_id)

    def handle_sigint(signum, frame) -> None:
        # `disconnect` is async, so it must be called from the event loop; we use `ui.timer` to do so.
        ui.timer(0.1, disconnect, once=True)
        # Delay the default handler to allow the disconnect to complete.
        ui.timer(1, lambda: signal.default_int_handler(signum, frame), once=True)

    async def cleanup() -> None:
        # This prevents ugly stack traces when auto-reloading on code change,
        # because otherwise disconnected clients try to reconnect to the newly started server.
        await disconnect()
        # Release the webcam hardware so it can be used by other applications again.
        for camera in cameras:
            camera.stop()

    app.on_shutdown(cleanup)
    # We also need to disconnect clients when the app is stopped with Ctrl+C,
    # because otherwise they will keep requesting images which lead to unfinished subprocesses blocking the shutdown.
    signal.signal(signal.SIGINT, handle_sigint)


# All the setup is only done when the server starts. This avoids the webcam being accessed
# by the auto-reload main process (see https://github.com/zauberzeug/nicegui/discussions/2321).
app.on_startup(setup)


ui.run()
