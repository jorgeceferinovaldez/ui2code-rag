"""Main entry point for the RAG Agent application."""

from src.logging_config import logger
import sys
import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import BasePushNotificationSender, InMemoryPushNotificationConfigStore, InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from src.agents.rag_agent.rag_a2a_agent_executor import RAGAgentExecutor


# TODO: Make this agent A2A compatible
@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10002)
def main(host: str, port: int):
    logger.info(f"Starting RAG Agent on {host}:{port}")
    try:
        capabilities = AgentCapabilities()
        skills = [
            AgentSkill(
                id="rag-agent",
                name="RAG Agent",
                description="A Retrieval-Augmented Generation (RAG) agent that can retrieve information based on a provided context.",
                tags=["RAG", "retrieval", "generation", "QA"],
                examples=["Retrieve information about a specific topic."],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ]
        agent_card = AgentCard(
            name="RAG Agent",
            description="An agent that uses retrieval-augmented generation to retrieve information.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            capabilities=capabilities,
            skills=skills,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=RAGAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        app = A2AStarletteApplication(
            agent_card=agent_card,
            request_handler=request_handler,
            push_notification_sender=BasePushNotificationSender(config_store=InMemoryPushNotificationConfigStore()),
        )

        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Failed to start RAG Agent: {e}")
        sys.exit(1)
