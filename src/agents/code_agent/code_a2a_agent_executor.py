"""Executor for the Code Agent using A2A framework."""

import json
from typing import Any
from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_text_parts
from a2a.types import FileWithBytes, Message, Part

from src.agents.code_agent.code_agent_mock import CodeAgentMock
from src.agents.code_agent.code_rag_agent import CodeAgent


class CodeA2AAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CodeAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Executing Code Agent")
        analysis_result, patterns, custom_instructions = self._get_content_from_context(context)
        logger.debug(f"Analysis Result: {analysis_result}")
        logger.debug(f"Patterns: {patterns}")
        logger.debug(f"Custom Instructions: {custom_instructions}")

        result = self.agent.invoke(patterns, analysis_result, custom_instructions)
        logger.debug(f"Code Agent result: {result}")
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(result)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Canceling Code Agent")
        raise Exception("cancel not supported")

    def _get_content_from_context(self, context: RequestContext) -> tuple[dict[str, Any] | None, list[tuple], str]:
        """Extract and parse content from the request context message parts.
        This method processes message parts from the context to extract analysis results,
        patterns, and custom instructions. It validates the content format and parses
        JSON data where applicable.
        Args:
            context (RequestContext): The request context containing the message with parts to process.
        Returns:
            tuple[dict[str, Any] | None, list[tuple], str]: A tuple containing:
                - analysis_result: Parsed JSON analysis result or None if not found
                - patterns: List of tuples containing pattern data
                - custom_instructions: String containing custom instructions
        Raises:
            Exception: If no message is found in context
            Exception: If no parts are found in message
            Exception: If unsupported MIME type is encountered (only text/plain is supported)
            Exception: If JSON decoding fails for analysis_result or patterns
        Note:
            The method expects message parts with specific metadata types:
            - "analysis_result": JSON-encoded analysis data
            - "patterns": JSON-encoded list of tuples
            - "custom_instructions": Plain text instructions
        """

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
        logger.debug(f"Extracted parts: {extracted_parts}")

        for part, metadata, mime_type in extracted_parts:
            logger.debug(f"Part: {part}, Metadata: {metadata}, MIME Type: {mime_type}")
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
        """
        Extract and process content from message parts into a standardized format.
        This method processes a list of Part objects and converts them into tuples containing
        the content, metadata, and MIME type. It handles different types of parts including
        text, files, and data objects.
        Args:
            message_parts (list[Part]): List of Part objects to extract content from.
                Each Part should have a 'root' attribute with 'kind', 'text', 'file',
                'data', and 'metadata' properties.
        Returns:
            list[tuple[str | dict[str, Any], str]]: List of tuples where each tuple contains:
                - Content (str or dict): The extracted content (text, file bytes/URI, or JSON data)
                - Metadata (str or None): Associated metadata from the part
                - MIME type (str): Content type ("text/plain", "application/json", "form", or file MIME type)
        Note:
            - For text parts: Returns (text_content, metadata, "text/plain")
            - For file parts: Returns (bytes_or_uri, metadata, mime_type)
            - For data parts: Returns (json_string_or_dict, metadata, "application/json" or "form")
            - If JSON serialization fails for data parts, returns ("<data>", "text/plain")
            - Returns empty list if message_parts is None or empty
        """
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
