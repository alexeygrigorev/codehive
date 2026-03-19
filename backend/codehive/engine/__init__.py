"""Engine adapters: protocol and implementations."""

from codehive.engine.base import EngineAdapter
from codehive.engine.claude_code_engine import ClaudeCodeEngine
from codehive.engine.codex_cli_engine import CodexCLIEngine
from codehive.engine.copilot_cli_engine import CopilotCLIEngine
from codehive.engine.gemini_cli_engine import GeminiCLIEngine
from codehive.engine.zai_engine import ZaiEngine

__all__ = [
    "ClaudeCodeEngine",
    "CodexCLIEngine",
    "CopilotCLIEngine",
    "EngineAdapter",
    "GeminiCLIEngine",
    "ZaiEngine",
]
