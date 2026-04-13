"""Utility helpers for DrissionPage element operations and captcha status checks."""

import time
from time import sleep
from typing import Any, Optional, Tuple

import cv2
import numpy as np
from DrissionPage.errors import NoRectError


def log(message: str) -> None:
    """Log a message to stdout with flushing."""
    print(message, flush=True)


def get_canvas_element_with_rect(page: Any, selector: str, timeout: float = 5.0) -> Any:
    """Wait for a canvas element to have a usable rect.

    Args:
        page (Any): DrissionPage page instance used to locate the element.
        selector (str): Selector used to locate the target element.
        timeout (float): Timeout in seconds for element lookup.

    Returns:
        Any: DrissionPage element with a usable rect.

    Raises:
        ValueError: When the element or its rect is unavailable within timeout.
    """
    deadline = time.monotonic() + timeout
    last_error: Optional[str] = None
    while time.monotonic() < deadline:
        element = page.ele(selector, timeout=0.5)
        if not element:
            last_error = f"Canvas element not found: {selector}"
            sleep(0.2)
            continue
        try:
            rect = element.rect
        except Exception as exc:
            last_error = f"Canvas rect unavailable for {selector}: {exc}"
            sleep(0.3)
            continue
        if rect:
            return element
        last_error = f"Canvas rect empty for {selector}"
        sleep(0.2)
    raise ValueError(last_error or f"Canvas element not found: {selector}")


def is_likely_blank_image(image: np.ndarray) -> bool:
    """Determine whether a captured image is likely blank.

    Args:
        image (np.ndarray): Captured image in BGR or grayscale format.

    Returns:
        bool: True when the image appears blank or invalid.
    """
    if image is None or not isinstance(image, np.ndarray):
        return True
    if image.size == 0:
        return True
    if image.ndim < 2:
        return True
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    except Exception:
        return True
    mean = float(np.mean(gray))
    stddev = float(np.std(gray))
    if stddev < 5.0 and (mean < 5.0 or mean > 250.0):
        return True
    flat = gray.reshape(-1)
    close_to_mean = np.mean(np.abs(flat - mean) < 6.0)
    return close_to_mean > 0.98


def capture_element_image(
    page: Any,
    selector: str,
    timeout: float = 8,
    wait_for_rect: bool = True,
    check_blank: bool = False,
    retry_interval: float = 0.3,
) -> np.ndarray:
    """Capture an element screenshot as a numpy array.

    Args:
        page (Any): DrissionPage page instance used to locate the element.
        selector (str): Selector used to locate the target element.
        timeout (float): Timeout in seconds for element lookup.
        wait_for_rect (bool): Whether to wait for a usable rect before capture.
        check_blank (bool): Whether to retry when the capture looks blank.
        retry_interval (float): Seconds to wait between retries.

    Returns:
        np.ndarray: Cropped element image.

    Raises:
        ValueError: When capture fails within timeout.
    """
    deadline = time.monotonic() + timeout
    last_error: Optional[str] = None
    element: Optional[Any] = None

    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        if element is None:
            if wait_for_rect:
                try:
                    element = get_canvas_element_with_rect(
                        page, selector, timeout=remaining
                    )
                except ValueError as exc:
                    last_error = str(exc)
                    sleep(retry_interval)
                    continue
            else:
                element = page.ele(selector, timeout=min(0.5, remaining))
                if not element:
                    last_error = f"Element not found: {selector}"
                    sleep(retry_interval)
                    continue

        try:
            rect = element.rect
        except Exception as exc:
            last_error = f"Failed to read rect for element {selector}: {exc}"
            if wait_for_rect:
                element = None
            sleep(retry_interval)
            continue
        if not rect:
            last_error = f"No rect for element: {selector}"
            if wait_for_rect:
                element = None
            sleep(retry_interval)
            continue

        try:
            screenshot = page.get_screenshot(as_bytes=True)
        except Exception as exc:
            last_error = f"Failed to take screenshot: {exc}"
            sleep(retry_interval)
            continue
        if not screenshot:
            last_error = "Empty screenshot bytes."
            sleep(retry_interval)
            continue
        nparr = np.frombuffer(screenshot, np.uint8)
        full_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if full_img is None:
            last_error = "Failed to decode screenshot."
            sleep(retry_interval)
            continue

        box = rect_to_box(rect)
        if not box:
            last_error = "Failed to parse rect into a box."
            sleep(retry_interval)
            continue

        x, y, width, height = box
        if width <= 0 or height <= 0:
            last_error = "Invalid rect size for cropping."
            sleep(retry_interval)
            continue

        max_y, max_x = full_img.shape[:2]
        x0 = max(0, min(x, max_x))
        y0 = max(0, min(y, max_y))
        x1 = max(0, min(x + width, max_x))
        y1 = max(0, min(y + height, max_y))
        if x1 <= x0 or y1 <= y0:
            last_error = "Crop bounds collapsed after clamping."
            sleep(retry_interval)
            continue

        cropped = full_img[y0:y1, x0:x1]
        if check_blank and is_likely_blank_image(cropped):
            last_error = "Captured image appears blank."
            sleep(retry_interval)
            continue
        return cropped

    raise ValueError(f"Failed to capture element image for {selector}: {last_error}")


def get_element_rect(page: Any, selector: str, timeout: float = 8) -> Any:
    """Get element rect with fallbacks for dynamic class suffixes.

    Args:
        page (Any): DrissionPage page instance used to locate the element.
        selector (str): Selector used to locate the target element.
        timeout (float): Timeout in seconds for element lookup.

    Returns:
        Any: Element rect when found, or None if unavailable.
    """
    element = page.ele(selector, timeout=timeout)
    if not element:
        element = page.ele("xpath=//*[contains(@class,'geetest_bg')]", timeout=timeout)
    if not element:
        return None
    return element.rect


def rect_to_box(rect: Any) -> Optional[Tuple[int, int, int, int]]:
    """Convert a DrissionPage rect into a tuple of ints.

    Args:
        rect (Any): Rect object or dict from DrissionPage.

    Returns:
        Optional[Tuple[int, int, int, int]]: (x, y, width, height) or None.
    """
    if rect is None:
        return None

    # 尝试访问 location 和 size 属性（DrissionPage rect 对象）
    # 注意：访问这些属性时，如果元素没有位置会抛出 NoRectError
    # 我们不能使用 hasattr，因为它会触发 getter 并抛出异常
    try:
        x, y = rect.location
        width, height = rect.size
        return int(x), int(y), int(width), int(height)
    except (AttributeError, NoRectError, TypeError):
        pass

    # 尝试访问 x, y, width, height 属性
    try:
        x = rect.x
        y = rect.y
        width = rect.width
        height = rect.height
        return int(x), int(y), int(width), int(height)
    except (AttributeError, NoRectError, TypeError):
        pass

    # 尝试作为字典访问
    try:
        if isinstance(rect, dict):
            x = rect["x"]
            y = rect["y"]
            width = rect["width"]
            height = rect["height"]
            return int(x), int(y), int(width), int(height)
    except (KeyError, TypeError):
        pass

    return None


def _get_result_text(page: Any) -> str:
    result_tip = page.ele(
        "xpath=//*[contains(@class,'geetest_result_tips')]", timeout=1
    )
    if result_tip and result_tip.text:
        return result_tip.text.strip()
    return ""


def _is_success(page: Any) -> bool:
    success_el = page.ele("xpath=//*[contains(@class,'geetest_success')]", timeout=1)
    if success_el:
        return True
    text = _get_result_text(page).lower()
    return ("success" in text) or ("verified" in text) or ("验证通过" in text)


def _refresh_captcha(page: Any) -> bool:
    refresh_btn = page.ele("xpath=//*[contains(@class,'geetest_refresh')]", timeout=2)
    if not refresh_btn:
        refresh_btn = page.ele("css=.geetest_refresh_1", timeout=2)
    if refresh_btn:
        refresh_btn.click()
        sleep(1.5)
        return True
    return False
