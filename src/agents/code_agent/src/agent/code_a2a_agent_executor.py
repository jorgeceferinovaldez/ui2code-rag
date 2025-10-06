from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from .code_agent_mock import CodeAgentMock
from .code_agent_with_guardrails import CodeAgentWithGuardrails
from .code_agent import CodeAgent


def _asdict(obj: Any) -> Dict[str, Any]:
    """Convert part object (pydantic model or plain dict) to a plain dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    out: Dict[str, Any] = {}
    # Common attributes on A2A Part
    for attr in ("kind", "text", "metadata", "meta", "file", "mimeType"):
        if hasattr(obj, attr):
            out[attr] = getattr(obj, attr)
    # Some implementations nest payloads differently
    if not out and hasattr(obj, "model_dump"):
        try:
            out = obj.model_dump()  # type: ignore[attr-defined]
        except Exception:
            pass
    return out


def _normalize_parts(parts: List[Any]) -> List[Dict[str, Any]]:
    """Normalize incoming parts so we can read them consistently."""
    norm: List[Dict[str, Any]] = []
    for p in parts or []:
        d = _asdict(p)
        # unify metadata key
        meta = d.get("metadata", None)
        if meta is None:
            meta = d.get("meta", None)
        if not isinstance(meta, dict):
            meta = {}
        norm.append(
            {
                "kind": d.get("kind"),
                "text": d.get("text"),
                "metadata": meta,
                "file": d.get("file"),
                "mimeType": d.get("mimeType"),
            }
        )
    return norm


class CodeA2AAgentExecutor(AgentExecutor):
    """A2A executor for the Code Agent supporting:
       - Prompt → HTML (prompt-only)
       - Visual + patterns → HTML
    """

    def __init__(self) -> None:
        self.agent = CodeAgentWithGuardrails(CodeAgentMock())

    async def cancel(self, context: RequestContext) -> None:
        """Required by AgentExecutor; this agent has no long-running tasks."""
        logger.debug("Cancel called (no-op).")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        raw_parts = getattr(msg, "parts", []) or []
        parts = _normalize_parts(raw_parts)

        # Debug: show what actually arrived
        try:
            dbg = [{"kind": p.get("kind"), "meta": p.get("metadata"), "has_text": bool(p.get("text"))} for p in parts]
            logger.debug("Incoming message parts (normalized): {}", dbg)
        except Exception:
            logger.debug("Could not log normalized parts.")

        def pick_text(meta_type: Optional[str]) -> Optional[str]:
            """Pick the first text part, optionally filtered by metadata.type."""
            for p in parts:
                if p.get("kind") != "text":
                    continue
                meta = p.get("metadata") or {}
                if meta_type is None or meta.get("type") == meta_type:
                    t = p.get("text")
                    if t:
                        return t
            return None

        # Try to extract inputs
        analysis_result_raw = pick_text("analysis_result")
        patterns_raw = pick_text("patterns")
        custom_instr = pick_text("custom_instructions") or ""

        # Prompt: first try the labeled part…
        prompt_text = pick_text("prompt")
        # …then any text part…
        if not prompt_text:
            prompt_text = pick_text(None)
        # …finally, fall back to message-level text if the transport placed it there
        if not prompt_text:
            prompt_text = getattr(msg, "text", None)

        # Parse patterns safely
        patterns: List[Any] = []
        if patterns_raw:
            try:
                patterns = json.loads(patterns_raw)
            except Exception:
                logger.warning("Failed to parse 'patterns' JSON. Continuing with empty list.")
                patterns = []

        # Parse analysis safely
        analysis_result: Optional[Dict[str, Any]] = None
        if analysis_result_raw:
            try:
                analysis_result = json.loads(analysis_result_raw)
            except Exception:
                logger.warning("Failed to parse 'analysis_result' JSON. Using empty dict.")
                analysis_result = {}

        # Route 1: Prompt-only
        if prompt_text and not analysis_result:
            logger.debug("CodeAgentExecutor: prompt-only mode")
            result = self.agent.invoke_from_prompt(
                prompt_text=prompt_text,
                patterns=patterns,
                custom_instructions=custom_instr,
            )
            await event_queue.enqueue_event(new_agent_text_message(json.dumps(result, ensure_ascii=False)))
            return

        # Route 2: Visual + patterns
        if analysis_result is not None:
            logger.debug("CodeAgentExecutor: visual+patterns mode")
            result = self.agent.invoke(
                patterns=patterns,
                visual_analysis=analysis_result,
                custom_instructions=custom_instr,
            )
            await event_queue.enqueue_event(new_agent_text_message(json.dumps(result, ensure_ascii=False)))
            return

        # If we reach here, nothing usable arrived. Return JSON error payload (don’t raise).
        err = "Missing 'analysis_result' or 'prompt' input"
        logger.error("Agent execution failed: {}", err)
        await event_queue.enqueue_event(new_agent_text_message(json.dumps({"error": err}, ensure_ascii=False)))
