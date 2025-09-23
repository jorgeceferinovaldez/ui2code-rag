from loguru import logger
import os
import sys

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv

from src.agents.code_a2a_agent.code_a2a_agent import CodeA2AAgent
from src.agents.code_a2a_agent.code_a2a_agent_executor import CodeA2AAgentExecutor


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10001)
def main(host: str, port: int):
    print(f"Starting Code Agent on {host}:{port}")
    try:
        capabilities = AgentCapabilities()
        skills = [
            AgentSkill(
                id="code-generator",
                name="Code Generator",
                description="Generates code based on user requirements.",
                tags=["code", "generation", "programming"],
                examples=["Generate the code based on structured information."],
                input_modes=["text", "text/plain", "application/json"],
            )
        ]
        agent_card = AgentCard(
            name="Code Agent",
            description="Helps with generating code.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            default_input_modes=CodeA2AAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=CodeA2AAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=skills,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=CodeA2AAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)

        uvicorn.run(server.build(), host=host, port=port)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
