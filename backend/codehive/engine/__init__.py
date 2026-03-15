"""Engine adapters: protocol and implementations."""

from codehive.engine.base import EngineAdapter
from codehive.engine.native import NativeEngine

__all__ = [
    "EngineAdapter",
    "NativeEngine",
]
