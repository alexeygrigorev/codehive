"""Context compaction engine: summarizes older messages when context is full."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = (
    "Summarize the following conversation, preserving:\n"
    "- Key decisions made\n"
    "- Current task context and goals\n"
    "- Files being worked on and their state\n"
    "- Any pending actions or unresolved questions\n"
    "- Tool call results that are still relevant\n\n"
    "Be concise but preserve all information needed to continue the work."
)


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    messages: list[dict[str, Any]]
    messages_compacted: int
    messages_preserved: int
    summary_text: str
    compacted: bool = True


class SummarizationCallable(Protocol):
    """Protocol for the summarization function passed to the compactor."""

    async def __call__(self, messages_text: str, model: str) -> str: ...


class ContextCompactor:
    """Summarizes older messages to free context window space."""

    def __init__(self, summarize_fn: SummarizationCallable) -> None:
        self._summarize = summarize_fn

    async def compact(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        preserve_last_n: int = 4,
    ) -> CompactionResult:
        """Compact message history by summarizing older messages.

        Args:
            messages: Full message history (excluding system prompt).
            model: Model name to use for summarization.
            preserve_last_n: Number of recent message turns to keep verbatim.

        Returns:
            CompactionResult with the new message list and metadata.
        """
        if len(messages) < preserve_last_n + 1:
            return CompactionResult(
                messages=messages,
                messages_compacted=0,
                messages_preserved=len(messages),
                summary_text="",
                compacted=False,
            )

        # Split into messages to compact and messages to preserve
        to_compact = messages[: len(messages) - preserve_last_n]
        to_preserve = messages[len(messages) - preserve_last_n :]

        # Build text representation of messages to summarize
        conversation_text = _format_messages_for_summary(to_compact)

        # Call the LLM to summarize
        summary = await self._summarize(conversation_text, model)

        # Build the new message list: summary + preserved messages
        summary_message: dict[str, Any] = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}",
        }

        new_messages = [summary_message] + to_preserve

        return CompactionResult(
            messages=new_messages,
            messages_compacted=len(to_compact),
            messages_preserved=len(to_preserve),
            summary_text=summary,
        )


def _format_messages_for_summary(messages: list[dict[str, Any]]) -> str:
    """Format messages into a text representation for summarization."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if isinstance(content, str):
            parts.append(f"{role}: {content}")
        elif isinstance(content, list):
            # Handle structured content blocks (tool_use, tool_result, etc.)
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif block_type == "tool_use":
                        text_parts.append(
                            f"[Tool call: {block.get('name', '?')}({block.get('input', {})})]"
                        )
                    elif block_type == "tool_result":
                        text_parts.append(f"[Tool result: {block.get('content', '')[:500]}]")
                    elif block_type == "function_call":
                        text_parts.append(
                            f"[Function call: {block.get('name', '?')}({block.get('arguments', '')})]"
                        )
                    elif block_type == "function_call_output":
                        text_parts.append(f"[Function output: {block.get('output', '')[:500]}]")
                else:
                    # Handle Anthropic SDK content block objects
                    block_type = getattr(block, "type", "")
                    if block_type == "text":
                        text_parts.append(getattr(block, "text", ""))
                    elif block_type == "tool_use":
                        text_parts.append(
                            f"[Tool call: {getattr(block, 'name', '?')}({getattr(block, 'input', {})})]"
                        )
                    else:
                        text_parts.append(str(block))
            if text_parts:
                parts.append(f"{role}: {' '.join(text_parts)}")
        else:
            parts.append(f"{role}: {content}")

    return "\n".join(parts)


async def create_anthropic_summarizer(client: Any) -> SummarizationCallable:
    """Create a summarization function using the Anthropic client.

    Returns a callable, not a coroutine -- call it to get the coroutine.
    """

    async def summarize(messages_text: str, model: str) -> str:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": f"{SUMMARIZATION_PROMPT}\n\n---\n\n{messages_text}",
                }
            ],
        )
        # Extract text from response
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return " ".join(text_parts)

    return summarize  # type: ignore[return-value]


async def create_openai_summarizer(client: Any) -> SummarizationCallable:
    """Create a summarization function using the OpenAI client.

    Returns a callable, not a coroutine -- call it to get the coroutine.
    """

    async def summarize(messages_text: str, model: str) -> str:
        response = await client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": f"{SUMMARIZATION_PROMPT}\n\n---\n\n{messages_text}",
                }
            ],
        )
        # Extract text from response output
        text_parts = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for block in getattr(item, "content", []) or []:
                    if getattr(block, "type", None) == "output_text":
                        text_parts.append(getattr(block, "text", ""))
        return " ".join(text_parts) if text_parts else getattr(response, "output_text", "")

    return summarize  # type: ignore[return-value]


def should_compact(
    input_tokens: int,
    context_window: int,
    threshold: float = 0.80,
) -> bool:
    """Check if compaction should be triggered based on token usage."""
    if context_window <= 0:
        return False
    return (input_tokens / context_window) >= threshold
