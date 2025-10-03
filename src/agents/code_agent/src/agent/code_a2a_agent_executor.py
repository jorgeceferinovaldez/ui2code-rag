import json
from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import InvalidParamsError
from a2a.utils import new_agent_text_message

from .code_agent_with_guardrails import CodeAgentWithGuardrails
from .code_agent import CodeAgent


class CodeA2AAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CodeAgentWithGuardrails(CodeAgent())

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        if not message or not message.parts:
            raise InvalidParamsError("No message parts")

        patterns = []
        analysis_result = {}
        custom_instructions = ""

        # 1) Parse por metadata.type
        for p in message.parts:
            if getattr(p, "kind", None) != "text":
                continue
            meta = getattr(p, "metadata", {}) or {}
            text = getattr(p, "text", "") or ""
            if meta.get("type") == "analysis_result":
                try:
                    analysis_result = json.loads(text)
                except Exception:
                    logger.warning("analysis_result no es JSON válido")
            elif meta.get("type") == "patterns":
                try:
                    patterns = json.loads(text)
                except Exception:
                    logger.warning("patterns no es JSON válido")
            elif meta.get("type") == "custom_instructions":
                custom_instructions = text

        # 2) Fallback heurístico si metadata no vino
        if not analysis_result:
            for p in message.parts:
                if getattr(p, "kind", None) != "text":
                    continue
                t = getattr(p, "text", "") or ""
                try:
                    obj = json.loads(t)
                    if isinstance(obj, dict) and ("components" in obj or "layout" in obj or "style" in obj):
                        analysis_result = obj
                        break
                except Exception:
                    pass

        if not patterns:
            for p in message.parts:
                if getattr(p, "kind", None) != "text":
                    continue
                t = getattr(p, "text", "") or ""
                try:
                    obj = json.loads(t)
                    if isinstance(obj, list):
                        patterns = obj
                        break
                except Exception:
                    pass

        result = self.agent.invoke(patterns, analysis_result, custom_instructions)
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(result, ensure_ascii=False)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")
