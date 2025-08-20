import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable

import numpy as np

from nightwatcher.streams import RTSPCameraStream

TASKS: dict[str, list[Callable]] = defaultdict(list)


def task(stage: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # register the callback function
        TASKS[stage].append(func)

        return wrapper

    return decorator


@dataclass
class Request:
    stream: RTSPCameraStream
    enable_detection: bool = True


@dataclass
class Response:
    # camera frames
    frame: np.ndarray | None = None

    # detections (custom scripts)
    annotation: np.ndarray | None = None
    color: str | None = None

    # output
    image_bytes: bytes = b""
    image_base64: str = ""


class LifeCycle(Enum):
    BEFORE_START = "before_start"
    AFTER_START = "after_start"

    BEFORE_STOP = "before_stop"
    AFTER_STOP = "after_stop"


class Pipeline:
    def __init__(self, name) -> None:
        self.name = name
        self.tasks = TASKS.copy()

    def invoke(self, request: Request, response: Response) -> bool:
        logging.debug("[Pipeline]Starting...")
        try:
            for lifecycle in LifeCycle:
                for task in self.tasks[lifecycle.value]:
                    task_start = time.time()
                    task(request, response)
                    task_duration = (time.time() - task_start) * 1000
                    logging.debug(
                        f"[Pipeline][{lifecycle.value}]Task {task.__name__} "
                        f"completed in {task_duration:.0f}ms"
                    )
        except Exception:
            logging.exception("Pipeline failed")
            return False

        return True
