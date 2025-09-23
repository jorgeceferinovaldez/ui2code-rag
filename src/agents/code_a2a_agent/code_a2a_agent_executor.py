from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from src.agents.code_a2a_agent.code_a2a_agent import CodeA2AAgent


class CodeA2AAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CodeA2AAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Executing Code Agent")
        result = await self.agent.invoke()
        logger.debug(f"Code Agent result: {result}")
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Canceling Code Agent")
        raise Exception("cancel not supported")
