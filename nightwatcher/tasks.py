import base64
import logging

import numpy as np
import supervision as sv

from nightwatcher import models, utils
from nightwatcher.pipeline import Request, Response, task


@task("before_start")
def read_frame(request: Request, response: Response):
    ret, frame = request.stream.read()
    logging.debug(f"[Consumer]Read latest frame: {ret},{str(frame)[:10]}")

    response.frame = frame


@task("after_start")
def detection(req: Request, response: Response):
    frame = response.frame
    if frame is None or not req.enable_detection:
        return

    # Run Detection
    # https://docs.ultralytics.com/tasks/detect/
    model = models.yolo
    results = model(frame, conf=0.15, classes=[0], verbose=False)[0]

    # Load Predictions into Supervision
    # https://supervision.roboflow.com/latest/how_to/detect_and_annotate/
    detections = sv.Detections.from_ultralytics(results)

    # Annotate Image with Detections
    box_annotator = sv.BoxAnnotator()
    annotated_image = box_annotator.annotate(scene=frame, detections=detections)

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

    response.annotation = annotated_image


@task("before_stop")
def validate(_: Request, response: Response):
    if response.annotation is None:
        response.annotation = response.frame


@task("after_stop")
def convert(_: Request, response: Response):
    if response.annotation is None:
        response.annotation = np.zeros((1440, 2560, 1), dtype=np.uint8)

    response.image_bytes = utils.convert(response.annotation)

    base64_str = base64.b64encode(response.image_bytes).decode("utf-8")
    response.image_base64 = f"data:image/png;base64,{base64_str}"
