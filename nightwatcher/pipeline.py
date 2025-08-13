import logging
import time
from collections import defaultdict
from enum import Enum
from functools import wraps
from typing import Callable

import numpy as np

from nightwatcher.rtsp import RTSPCameraStream

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


class Request:
    stream: RTSPCameraStream


class Response:
    # detection stats
    color: str | None = None

    # screen shots
    snapshot: np.ndarray | None = None
    snapshot_annotated: np.ndarray | None = None


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
        logging.info(f"[Pipeline] Start {self.name}...")
        for lifecycle in LifeCycle:
            for task in self.tasks[lifecycle.value]:
                task_start = time.time()
                task(request, response)
                task_duration = time.time() - task_start
                logging.info(
                    f"[Pipeline][{lifecycle.value}] Task {task.__name__} "
                    f"completed in {task_duration:.0f}ms"
                )

        return True
