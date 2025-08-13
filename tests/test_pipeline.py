import logging
import os
import unittest
from pathlib import Path

import cv2
import numpy as np

from nightwatcher.pipeline import Pipeline, Request, Response, task
from nightwatcher.rtsp import RTSPCameraStream


class MockRTSPCameraStream(RTSPCameraStream):
    def __init__(self, image_path: str):
        self.image = cv2.imread(image_path)

    def read(self) -> tuple[bool, np.ndarray]:
        if self.image is None:
            raise ValueError(f"Failed to load image")
        return True, self.image.copy()

    def release(self):
        pass


@task("after_stop")
def show_image(_: Request, response: Response):
    assert response.snapshot_annotated is not None

    cv2.imshow("Annotated Image", response.snapshot_annotated)
    cv2.waitKey(0)  # 等待按键
    cv2.destroyAllWindows()


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.test_images_dir = Path(__file__).parent / "test_images"
        self.pipeline = Pipeline("test_pipeline")

    def test_pipeline_with_images(self):
        logging.info(f"Running {self._testMethodName}")
        self.assertTrue(
            self.test_images_dir.exists(), "Test images directory not found"
        )

        for image_path in self.test_images_dir.glob("*"):
            with self.subTest(image=image_path.name):
                request = Request()
                request.stream = MockRTSPCameraStream(str(image_path))
                response = Response()

                result = self.pipeline.invoke(request, response)
                self.assertTrue(result)
