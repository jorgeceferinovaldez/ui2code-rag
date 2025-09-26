"""Executor for the RAG A2A Agent."""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from src.agents.rag_agent.rag_agent import RAGAgent


class RAGAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = RAGAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Here you would implement the logic to interact with the RAG agent
        # For demonstration, we will just send a placeholder message
        await event_queue.enqueue_event(new_agent_text_message("RAG Agent executed successfully."))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")
