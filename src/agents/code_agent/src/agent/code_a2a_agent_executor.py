"""Executor for the Code Agent using A2A framework."""

import json
from typing import Any
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import FileWithBytes, Part
from src.agent.code_agent import CodeAgent


class CodeA2AAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CodeAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        analysis_result, patterns, custom_instructions = self._get_content_from_context(context)

        result = self.agent.invoke(patterns, analysis_result, custom_instructions)
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(result)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")

    def _get_content_from_context(self, context: RequestContext) -> tuple[dict[str, Any] | None, list[tuple], str]:
        """Extract analysis_result, patterns, and custom_instructions from the context message parts"""
        message = context.message
        if not message:
            raise Exception("No message found in context")

        message_parts = message.parts
        if not message_parts:
            raise Exception("No parts found in message")

        analysis_result = None
        patterns = []
        custom_instructions = ""

        extracted_parts = self._extract_content(message_parts)
        for part, metadata, mime_type in extracted_parts:
            if mime_type != "text/plain":
                raise Exception(f"Unsupported MIME type: {mime_type}")
            if metadata and isinstance(metadata, dict) and "type" in metadata:
                if metadata["type"] == "analysis_result":
                    try:
                        analysis_result: dict[str, Any] = json.loads(part) if isinstance(part, str) else part
                    except json.JSONDecodeError as e:
                        raise Exception("Failed to decode analysis_result JSON") from e
                elif metadata["type"] == "patterns":
                    try:
                        patterns: list[tuple] = json.loads(part) if isinstance(part, str) else part
                    except json.JSONDecodeError as e:
                        raise Exception("Failed to decode patterns JSON") from e
                elif metadata["type"] == "custom_instructions":
                    custom_instructions: str = part

        return analysis_result, patterns, custom_instructions

    def _extract_content(
        self,
        message_parts: list[Part],
    ) -> list[tuple[str | dict[str, Any], str]]:
        """Extract text, file, and data parts from message parts"""
        parts: list[tuple[str | dict[str, Any], str]] = []
        if not message_parts:
            return []
        for part in message_parts:
            p = part.root
            if p.kind == "text":
                parts.append((p.text, p.metadata or None, "text/plain"))

            elif p.kind == "file":
                if isinstance(p.file, FileWithBytes):
                    parts.append((p.file.bytes, p.metadata or None, p.file.mime_type or ""))
                else:
                    parts.append((p.file.uri, p.metadata or None, p.file.mime_type or ""))
            elif p.kind == "data":
                try:
                    jsonData = json.dumps(p.data)
                    if "type" in p.data and p.data["type"] == "form":
                        parts.append((p.data, p.metadata or None, "form"))
                    else:
                        parts.append((jsonData, p.metadata or None, "application/json"))
                except Exception as e:
                    print("Failed to dump data", e)
                    parts.append(("<data>", "text/plain"))
        return parts
