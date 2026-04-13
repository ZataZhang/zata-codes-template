"""Captcha recognizer exports."""

from .drissionpage import (
    DrissionPageSliderSolver,
    SliderGapResult,
    SliderSolveResult,
)
from .slider import Slider

__all__ = [
    "DrissionPageSliderSolver",
    "Slider",
    "SliderGapResult",
    "SliderSolveResult",
]
