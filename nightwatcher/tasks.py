import logging

import numpy as np
import supervision as sv

from nightwatcher import models
from nightwatcher.pipeline import Request, Response, task


@task("after_start")
def read_frame(request: Request, response: Response):
    ret, frame = request.stream.read()
    logging.debug(f"[Consumer]Read latest frame: {ret},{str(frame)[:10]}")

    response.snapshot = frame


@task("before_stop")
def detection(_: Request, response: Response):
    image = response.snapshot
    if image is None:
        return

    # Run Detection
    # https://docs.ultralytics.com/tasks/detect/
    model = models.yolo
    results = model(image, conf=0.15, classes=[0], verbose=False)[0]

    # Load Predictions into Supervision
    # https://supervision.roboflow.com/latest/how_to/detect_and_annotate/
    detections = sv.Detections.from_ultralytics(results)

    # Annotate Image with Detections
    box_annotator = sv.BoxAnnotator()
    annotated_image = box_annotator.annotate(scene=image, detections=detections)

    # Custom labels
    label_annotator = sv.LabelAnnotator(
        text_scale=1.5,
        text_thickness=3,
        text_padding=10,
        smart_position=True,
    )
    labels = [
        f"{class_name} {confidence:.2f}"
        for class_name, confidence in zip(
            detections["class_name"], detections.confidence
        )
    ]
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections, labels=labels
    )

    response.snapshot_annotated = annotated_image


@task("after_stop")
def validate(_: Request, response: Response):
    if response.snapshot is None:
        response.snapshot = np.zeros((480, 640, 3), dtype=np.uint8)

    if response.snapshot_annotated is None:
        response.snapshot_annotated = response.snapshot
