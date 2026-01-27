"""captcha-recognizer package exports."""

from captcha_recognizer.drissionpage import (
    DrissionPageSliderSolver,
    SliderGapResult,
    SliderSolveResult,
)
from captcha_recognizer.slider import Slider

__all__ = [
    "DrissionPageSliderSolver",
    "Slider",
    "SliderGapResult",
    "SliderSolveResult",
]
