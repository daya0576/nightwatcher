import base64
from functools import partial

from nicegui import ui

from nightwatcher import utils
from nightwatcher.pipeline import Pipeline, Request, Response
from nightwatcher.streams import CameraGroup, RTSPCameraStream


def update_image(camera: RTSPCameraStream, video_image: ui.interactive_image):
    request, response = Request(camera), Response()
    Pipeline("camera").invoke(request, response)

    image = response.snapshot_annotated
    assert image is not None, "Failed to fetch any snapshot from stream"

    image_bytes = utils.convert(image)

    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    video_image.set_source(f"data:image/png;base64,{base64_str}")


@ui.refreshable
def create_camera_grid(cameras: CameraGroup):
    with ui.column().classes("max-w-6xl mx-auto"):
        ui.label("Night Watcher").classes("test-xl")
        with ui.column().classes("grid grid-cols-1 lg:grid-cols-2 gap-4"):
            for camera in cameras:
                video_image = ui.interactive_image().classes("w-full h-full")

                # Load images immediately when page load.
                update_image(camera, video_image)

                # A timer constantly updates the source of the image.
                # Because data from same paths is cached by the browser,
                # we must force an update by adding the current timestamp to the source.
                timer = ui.timer(
                    interval=1,
                    callback=partial(update_image, camera, video_image),
                    immediate=False,
                )
                ui.context.client.on_disconnect(timer.deactivate)
