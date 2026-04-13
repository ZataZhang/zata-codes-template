"""DrissionPage integration helpers for slider captcha recognition."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Tuple

import cv2
import numpy as np

from .slider import Slider


@dataclass(frozen=True)
class SliderGapResult:
    """Result of a slider gap identification."""

    box: Tuple[float, float, float, float]
    confidence: float

    @property
    def offset_x(self) -> float:
        """Return the left X coordinate of the detected gap box."""
        return self.box[0]


@dataclass(frozen=True)
class SliderSolveResult:
    """Summary of a slider captcha solve attempt."""

    success: bool
    distance: float
    confidence: float
    attempts: int


def _rect_to_box(rect: Any) -> Optional[Tuple[int, int, int, int]]:
    """Convert a DrissionPage rect into a box tuple."""
    if rect is None:
        return None
    if hasattr(rect, "location") and hasattr(rect, "size"):
        x, y = rect.location
        width, height = rect.size
    elif hasattr(rect, "x"):
        x = rect.x
        y = rect.y
        width = rect.width
        height = rect.height
    else:
        x = rect.get("x")
        y = rect.get("y")
        width = rect.get("width")
        height = rect.get("height")
    if x is None or y is None or width is None or height is None:
        return None
    return int(x), int(y), int(width), int(height)


def _get_element(page: Any, selector: str, timeout: float) -> Any:
    """Locate an element using DrissionPage selector syntax."""
    return page.ele(selector, timeout=timeout)


def capture_element_image(
    page: Any, selector: str, timeout: float = 8.0
) -> Optional[np.ndarray]:
    """Capture an element screenshot as a numpy array.

    Args:
        page: DrissionPage page instance.
        selector: Selector for the element to capture.
        timeout: Timeout in seconds to wait for the element.

    Returns:
        A numpy array (BGR) for the element image, or None if capture failed.
    """
    element = _get_element(page, selector, timeout)
    if not element:
        return None
    rect = _rect_to_box(element.rect)
    if rect is None:
        return None

    screenshot = page.get_screenshot(as_bytes=True)
    nparr = np.frombuffer(screenshot, np.uint8)
    full_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if full_img is None:
        return None

    x, y, width, height = rect
    return full_img[y : y + height, x : x + width]


def identify_slider_gap(
    image: np.ndarray, model: Optional[Slider] = None
) -> Optional[SliderGapResult]:
    """Identify slider gap location from a background image.

    Args:
        image: Captcha background image as a numpy array.
        model: Optional Slider model instance to reuse.

    Returns:
        SliderGapResult if a gap is found, otherwise None.
    """
    model = model or Slider()
    box, confidence = model.identify(source=image, show=False)
    if not box or len(box) < 4:
        return None
    return SliderGapResult(
        box=tuple(float(x) for x in box[:4]), confidence=float(confidence)
    )


def _build_track(distance: float, rng: random.Random) -> Tuple[float, ...]:
    """Build a human-like movement track."""
    track = []
    current = 0.0
    mid = distance * rng.uniform(0.55, 0.7)
    velocity = 0.0

    while current < distance:
        t = rng.uniform(0.015, 0.03)
        accel = rng.uniform(2.0, 3.5) if current < mid else rng.uniform(-3.8, -2.0)
        v0 = velocity
        velocity = max(0.0, v0 + accel * t)
        move = v0 * t + 0.5 * accel * t * t
        move = max(0.6, move)
        current += move
        track.append(move)

    overshoot = rng.uniform(1.0, 3.0)
    track.append(overshoot)
    track.append(-overshoot * rng.uniform(0.6, 1.0))
    return tuple(track)


class DrissionPageSliderSolver:
    """Solve slider captchas with DrissionPage and captcha-recognizer."""

    def __init__(
        self,
        model: Optional[Slider] = None,
        calibration: float = 0.0,
        jitter: float = 2.0,
        distance_sweep: Optional[Sequence[float]] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        """Initialize the solver.

        Args:
            model: Optional Slider model instance to reuse.
            calibration: Base calibration offset applied to drag distance.
            jitter: Random jitter applied to drag distance.
            distance_sweep: Optional list of extra offsets to try.
            rng: Optional random generator for deterministic tests.
        """
        self._model = model or Slider()
        self._calibration = calibration
        self._jitter = jitter
        self._distance_sweep = (
            tuple(distance_sweep) if distance_sweep is not None else (0.0,)
        )
        self._rng = rng or random.Random()

    def compute_distance(
        self,
        page: Any,
        background_selector: str,
        slider_selector: str,
        timeout: float = 8.0,
    ) -> Optional[Tuple[float, float]]:
        """Compute the slider drag distance.

        Args:
            page: DrissionPage page instance.
            background_selector: Selector for the captcha background image.
            slider_selector: Selector for the draggable slider element.
            timeout: Timeout in seconds to wait for elements.

        Returns:
            A tuple of (distance, confidence) or None if computation fails.
        """
        bg_image = capture_element_image(page, background_selector, timeout=timeout)
        if bg_image is None or bg_image.shape[1] == 0:
            return None

        gap = identify_slider_gap(bg_image, model=self._model)
        if gap is None:
            return None

        bg_element = _get_element(page, background_selector, timeout)
        slider_element = _get_element(page, slider_selector, timeout)
        bg_box = _rect_to_box(bg_element.rect) if bg_element else None
        slider_box = _rect_to_box(slider_element.rect) if slider_element else None
        if bg_box is None or slider_box is None:
            return None

        bg_x, _, bg_w, _ = bg_box
        slider_x, _, slider_w, _ = slider_box
        scale = bg_w / float(bg_image.shape[1])
        target_x = bg_x + gap.offset_x * scale
        slider_center_x = slider_x + slider_w / 2.0
        distance = target_x - slider_center_x
        distance += self._calibration + self._rng.uniform(-self._jitter, self._jitter)
        return distance, gap.confidence

    def drag_slider(
        self,
        page: Any,
        slider_selector: str,
        distance: float,
        timeout: float = 8.0,
    ) -> bool:
        """Drag the slider using a human-like path.

        Args:
            page: DrissionPage page instance.
            slider_selector: Selector for the draggable slider element.
            distance: Drag distance in pixels.
            timeout: Timeout in seconds to wait for the element.

        Returns:
            True if a drag was attempted, otherwise False.
        """
        slider = _get_element(page, slider_selector, timeout)
        if not slider:
            return False
        rect = _rect_to_box(slider.rect)
        if rect is None:
            return False

        x, y, width, height = rect
        start_x = x + width / 2.0
        start_y = y + height / 2.0

        page.actions.move_to((start_x, start_y), duration=0.1)
        time.sleep(0.1)
        page.actions.hold()

        track = _build_track(distance, self._rng)
        for move in track:
            jitter_y = self._rng.uniform(-1.0, 1.0)
            page.actions.move(move, jitter_y, duration=self._rng.uniform(0.01, 0.03))
            time.sleep(self._rng.uniform(0.01, 0.03))

        time.sleep(self._rng.uniform(0.08, 0.15))
        page.actions.release()
        return True

    def solve(
        self,
        page: Any,
        background_selector: str,
        slider_selector: str,
        timeout: float = 8.0,
        success_check: Optional[Callable[[Any], bool]] = None,
    ) -> SliderSolveResult:
        """Solve a slider captcha.

        Args:
            page: DrissionPage page instance.
            background_selector: Selector for the captcha background image.
            slider_selector: Selector for the draggable slider element.
            timeout: Timeout in seconds to wait for elements.
            success_check: Optional callback that returns True if captcha is solved.

        Returns:
            SliderSolveResult describing the attempt.
        """
        computed = self.compute_distance(
            page, background_selector, slider_selector, timeout=timeout
        )
        if computed is None:
            return SliderSolveResult(False, 0.0, 0.0, 0)

        base_distance, confidence = computed
        attempts = 0
        for offset in self._distance_sweep:
            attempts += 1
            distance = base_distance + offset
            if distance <= 0:
                continue
            dragged = self.drag_slider(page, slider_selector, distance, timeout=timeout)
            if not dragged:
                return SliderSolveResult(False, distance, confidence, attempts)
            if success_check is None:
                return SliderSolveResult(True, distance, confidence, attempts)
            if success_check(page):
                return SliderSolveResult(True, distance, confidence, attempts)

        return SliderSolveResult(False, base_distance, confidence, attempts)
