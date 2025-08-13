import logging

import supervision as sv

from nightwatcher import models
from nightwatcher.pipeline import Request, Response, task


@task("after_start")
def read_frame(request: Request, response: Response):
    ret, frame = request.stream.read()
    logging.debug(f"[Consumer]Read latest frame: {ret},{str(frame)[:10]}")

    assert ret is True
    assert frame is not None

    # image_bytes = convert(frame)
    # logging.debug(f"[Consumer]Convert frame to byte: {len(image_bytes)}")

    response.snapshot = frame


@task("before_stop")
def detection(_: Request, response: Response):
    image = response.snapshot
    assert image is not None

    # Run Detection
    # https://docs.ultralytics.com/tasks/detect/
    model = models.yolo
    results = model(image, classes=[0])[0]

    # Load Predictions into Supervision
    detections = sv.Detections.from_ultralytics(results)
    if not detections:
        return

    # Annotate Image with Detections
    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()

    annotated_image = box_annotator.annotate(scene=image, detections=detections)
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections
    )

    response.snapshot_annotated = annotated_image


@task("after_stop")
def validate(_: Request, response: Response):
    assert response.snapshot is not None
