from functools import partial

from nicegui import app, ui

from nightwatcher.pipeline import Pipeline, Request, Response
from nightwatcher.streams import CameraGroup, RTSPCameraStream

DETECTION_KEY = "enable_detection"


def update_image(camera: RTSPCameraStream, video_image: ui.interactive_image):
    enable_detection = app.storage.client.get(DETECTION_KEY) is True
    request, response = Request(camera, enable_detection), Response()
    Pipeline("camera").invoke(request, response)
    video_image.set_source(response.image_base64)


def camera_image(camera: RTSPCameraStream):
    interactive_image = ui.interactive_image().classes("w-full h-full")

    # Load images immediately when page load.
    update_image(camera, interactive_image)

    # A timer constantly updates the source of the image.
    timer = ui.timer(
        interval=0.5,
        callback=partial(update_image, camera, interactive_image),
        immediate=False,
    )
    ui.context.client.on_disconnect(timer.deactivate)

    # Options
    with ui.dialog() as dialog, ui.card():
        ui.label("Options")
        with ui.column().classes("gap-1"):
            ui.checkbox("Enable Detection").bind_value(
                app.storage.client, DETECTION_KEY
            )
    interactive_image.on("click", dialog.open)


@ui.refreshable
def create_camera_grid(cameras: CameraGroup):
    with ui.column().classes("max-w-6xl mx-auto"):
        ui.label("Night Watcher")
        with ui.column().classes("grid grid-cols-1 lg:grid-cols-2 gap-4"):
            for camera in cameras:
                camera_image(camera)
