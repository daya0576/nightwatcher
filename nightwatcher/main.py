import logging
import os
import signal

from dotenv import load_dotenv
from nicegui import Client, app, core, ui

from nightwatcher import views
from nightwatcher.streams import CameraGroup, RTSPCameraStream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(),
    ],
)


load_dotenv()


def setup() -> None:
    rtsp_urls = os.getenv("RTSP_URLS", "")
    assert rtsp_urls, f"Invalid rtsp urls: {rtsp_urls}"

    cameras = tuple(RTSPCameraStream(url) for url in rtsp_urls.split(","))
    camera_group = CameraGroup(cameras).start()

    @ui.page("/")
    async def index():
        # common headers
        ui.add_head_html(
            """
            <link rel="manifest" href="/statics/pwa/manifest.json">
            <link rel="apple-touch-icon" href="/statics/images/bat_300x300.png">
            <meta name="theme-color" content="#F9F9F9" media="(prefers-color-scheme: light)" />
            <meta name="theme-color" content="#121212" media="(prefers-color-scheme: dark)" />
            """
        )

        views.create_camera_grid(camera_group)

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
oneyear = 365 * 24 * 60 * 60
app.add_static_files("/statics", "statics", max_cache_age=oneyear)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Night Watcher",
        favicon="🦇",
        dark=True,
        port=12505,
    )
