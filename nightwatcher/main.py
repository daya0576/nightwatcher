import base64
import logging
import os
import signal
from functools import partial

from dotenv import load_dotenv
from nicegui import Client, app, core, ui
from rtsp import RTSPCameraStream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(),
    ],
)


load_dotenv()


def convert(frame: np.ndarray) -> bytes:
    """Converts a frame from OpenCV to a JPEG image.

    This is a free function (not in a class or inner-function),
    to allow run.cpu_bound to pickle it and send it to a separate process.
    """
    _, imencode_image = cv2.imencode(".jpg", frame)
    return imencode_image.tobytes()


def update_image(camera: RTSPCameraStream, video_image: ui.interactive_image):
    ret, frame = camera.read()
    logging.debug(f"[Consumer]Read latest frame: {ret},{str(frame)[:10]}")
    if not ret:
        return

    image_bytes = convert(frame)
    logging.debug(f"[Consumer]Convert frame to byte: {len(image_bytes)}")

    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    video_image.set_source(f"data:image/png;base64,{base64_str}")


def setup() -> None:
    rtsp_urls = os.getenv("RTSP_URLS", "")
    assert rtsp_urls, f"Invalid rtsp urls: {rtsp_urls}"

    cameras = tuple(RTSPCameraStream(url) for url in rtsp_urls.split(","))
    for camera in cameras:
        camera.start()

    @ui.page("/")
    async def index():
        with ui.column().classes("max-w-6xl mx-auto"):
            ui.label("Night Watcher")
            with ui.column().classes("grid grid-cols-1 lg:grid-cols-2 gap-4"):
                images = {
                    camera: ui.interactive_image().classes("w-full h-full")
                    for camera in cameras
                }
                for camera, video_image in images.items():
                    update_image(camera, video_image)

                    # A timer constantly updates the source of the image.
                    # Because data from same paths is cached by the browser,
                    # we must force an update by adding the current timestamp to the source.
                    ui.timer(
                        interval=1,
                        callback=partial(update_image, camera, video_image),
                        immediate=False,
                    )

    async def disconnect() -> None:
        """Disconnect all clients from current running server."""
        for client_id in Client.instances:
            logging.info(f"Disconnect client {client_id}")
            await core.sio.disconnect(client_id)

    async def cleanup() -> None:
        # This prevents ugly stack traces when auto-reloading on code change,
        # because otherwise disconnected clients try to reconnect to the newly started server.
        await disconnect()
        # Release the webcam hardware so it can be used by other applications again.
        for camera in cameras:
            camera.stop()

    app.on_shutdown(cleanup)

    def handle_sigint(signum, frame) -> None:
        # `disconnect` is async, so it must be called from the event loop; we use `ui.timer` to do so.
        ui.timer(0.1, disconnect, once=True)
        # Delay the default handler to allow the disconnect to complete.
        ui.timer(1, lambda: signal.default_int_handler(signum, frame), once=True)

    # We also need to disconnect clients when the app is stopped with Ctrl+C,
    # because otherwise they will keep requesting images which lead to unfinished subprocesses blocking the shutdown.
    signal.signal(signal.SIGINT, handle_sigint)


# All the setup is only done when the server starts. This avoids the webcam being accessed
# by the auto-reload main process (see https://github.com/zauberzeug/nicegui/discussions/2321).
app.on_startup(setup)

ui.run(
    title="Night Watcher",
    favicon="🦇",
)
