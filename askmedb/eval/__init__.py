"""Evaluation harness for AskMeDB — measures accuracy, correction rate, and latency."""

from .runner import EvalRunner
from .metrics import compute_metrics

__all__ = ["EvalRunner", "compute_metrics"]
