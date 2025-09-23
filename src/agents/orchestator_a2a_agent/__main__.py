import base64
from PIL import Image
from pathlib import Path
from typing import Any
from loguru import logger
from uuid import uuid4
import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import AgentCard

from loguru import logger

from typing import Any
from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    EXTENDED_AGENT_CARD_PATH,
)

VISUAL_AGENT_URL = "http://localhost:10000"
CODE_AGENT_URL = "http://localhost:10001"


class OrchestratorAgent:
    def __init__(self, visual_url: str, code_url: str):
        self.visual_url = visual_url
        self.code_url = code_url
        self.httpx_client: httpx.AsyncClient | None = None

        # Diccionario para guardar info de cada agente
        self.agents: dict[str, dict[str, object]] = {
            "visual": {"url": self.visual_url, "card": None, "client": None},
            "code": {"url": self.code_url, "card": None, "client": None},
        }

    async def initialize(self) -> None:
        """Inicializa el cliente HTTP y obtiene las cards de ambos agentes."""
        logger.debug("Initializing Orchestrator Agent")
        timeout = httpx.Timeout(60.0, connect=10.0)
        self.httpx_client = httpx.AsyncClient(timeout=timeout)

        for agent_name, agent_info in self.agents.items():
            url = agent_info["url"]
            logger.debug(f"Resolving {agent_name} agent card from {url}")
            resolver = A2ACardResolver(
                httpx_client=self.httpx_client,
                base_url=url,
            )
            try:
                card: AgentCard = await resolver.get_agent_card()
                logger.debug(f"Resolved {agent_name} agent card: {card}")
                self.agents[agent_name]["card"] = card
                self.agents[agent_name]["client"] = A2AClient(
                    httpx_client=self.httpx_client,
                    agent_card=card,
                )
                logger.info(f"Successfully initialized {agent_name} agent")
                logger.debug(card.model_dump_json(indent=2, exclude_none=True))
            except Exception as e:
                logger.error(
                    f"Critical error fetching {agent_name} agent card: {e}",
                    exc_info=True,
                )
                raise RuntimeError(f"Failed to fetch {agent_name} agent card. Cannot continue.") from e

    def get_client(self, agent_name: str) -> A2AClient:
        """Devuelve el cliente A2A de un agente."""
        client = self.agents.get(agent_name, {}).get("client")
        if client is None:
            raise RuntimeError(f"Agent '{agent_name}' not initialized.")
        return client

    async def close(self) -> None:
        """Cierra el cliente HTTP compartido."""
        if self.httpx_client:
            await self.httpx_client.aclose()


if __name__ == "__main__":
    import asyncio

    async def main():
        orchestrator = OrchestratorAgent(
            visual_url=VISUAL_AGENT_URL,
            code_url=CODE_AGENT_URL,
        )
        await orchestrator.initialize()
        visual_client = orchestrator.get_client("visual")
        code_client = orchestrator.get_client("code")

        logger.info("Sending test messages to both agents")

        logger.info("Sending test message to Visual Agent...")
        image_uri = "E:/Documentos/Git Repositories/ui2code-rag/tests/test_image.png"
        with open(image_uri, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read())

        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {"kind": "text", "text": "Dummy message"},
                    {
                        "kind": "file",
                        "file": {"name": "test_image.png", "mimeType": "image/png", "bytes": base64_image},
                    },
                ],
                "messageId": uuid4().hex,
            },
        }
        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**send_message_payload))

        response = await visual_client.send_message(request)
        logger.info("Received response from Visual Agent")
        print(response.model_dump(mode="json", exclude_none=True))

        logger.info("Sending test message to Code Agent...")
        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Dummy message2"}],
                "messageId": uuid4().hex,
            },
        }

        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**send_message_payload))
        response = await code_client.send_message(request)
        logger.info("Received response from Code Agent")
        print(response.model_dump(mode="json", exclude_none=True))

        await orchestrator.close()

    asyncio.run(main())
