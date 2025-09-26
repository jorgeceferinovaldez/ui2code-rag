"""Orchestrator Agent that coordinates between Visual and Code Agents, and integrates RAG for context."""

import base64, json, httpx
from pathlib import Path
from PIL import Image
from typing import Any
from uuid import uuid4
from src.logging_config import logger
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    Message,
    SendMessageSuccessResponse,
)
from a2a.utils import get_message_text, get_text_parts
from src.agents.rag_agent.rag_agent import RAGAgent
from src.config import visual_agent_url, code_agent_url

VISUAL_AGENT_URL = visual_agent_url
CODE_AGENT_URL = code_agent_url


class OrchestratorAgent:
    def __init__(self):
        self.visual_url: str = VISUAL_AGENT_URL
        self.code_url: str = CODE_AGENT_URL
        self.rag_agent: RAGAgent = RAGAgent()
        self.httpx_client: httpx.AsyncClient | None = None

        # Diccionario para guardar info de cada agente
        self.agents: dict[str, dict[str, object]] = {
            "visual": {"url": self.visual_url, "card": None, "client": None},
            "code": {"url": self.code_url, "card": None, "client": None},
            "rag": {"url": None, "card": None, "client": self.rag_agent},
        }

    async def initialize(self) -> None:
        """Inicializa el cliente HTTP y obtiene las cards de ambos agentes."""
        timeout = httpx.Timeout(60.0, connect=10.0)
        self.httpx_client = httpx.AsyncClient(timeout=timeout)

        for agent_name, agent_info in self.agents.items():
            url = agent_info["url"]
            if url:
                resolver = A2ACardResolver(
                    httpx_client=self.httpx_client,
                    base_url=url,
                )
                try:
                    card: AgentCard = await resolver.get_agent_card()
                    self.agents[agent_name]["card"] = card
                    self.agents[agent_name]["client"] = A2AClient(
                        httpx_client=self.httpx_client,
                        agent_card=card,
                    )
                except Exception as e:
                    logger.error(
                        f"Critical error fetching {agent_name} agent card: {e}",
                        exc_info=True,
                    )
                    raise RuntimeError(f"Failed to fetch {agent_name} agent card. Cannot continue.") from e

    def get_agent_client(self, agent_name: str) -> A2AClient | RAGAgent:
        """Devuelve el cliente A2A de un agente."""
        client = self.agents.get(agent_name, {}).get("client")
        if client is None:
            raise RuntimeError(f"Agent '{agent_name}' not initialized.")
        return client

    async def close(self) -> None:
        """Cierra el cliente HTTP compartido."""
        if self.httpx_client:
            await self.httpx_client.aclose()

    def _get_analysis_result_from_response(self, response: SendMessageResponse) -> dict[str, Any]:
        """
        Extract and parse analysis result from a SendMessageResponse object.
        This function retrieves text parts from the response and attempts to parse
        the last part as JSON to extract analysis results.
        Args:
            response (SendMessageResponse): The response object containing the analysis result
                                        with parts that include text data.
        Returns:
            dict[str, Any]: A dictionary containing the parsed analysis result.
                        Returns an empty dictionary if no parts are found.
        Raises:
            ValueError: If the JSON in the visual analysis response is invalid or cannot be decoded.
        Note:
            This function assumes the analysis result is contained in the last text part
            of the response as a JSON string.
        """

        parts_list = get_text_parts(response.root.result.parts)
        try:
            return json.loads(parts_list[-1]) if parts_list else {}
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from visual analysis response")
            raise ValueError("Invalid JSON in visual analysis response")

    def _validate_response(self, response: SendMessageResponse) -> bool:
        """
        Validates the structure and content of a SendMessageResponse object.
        This function performs comprehensive validation to ensure the response has the expected
        structure with all required nested components.
        Args:
            response (SendMessageResponse): The response object to validate. Expected to have
                a nested structure with root.result containing a Message with parts.
        Returns:
            bool: True if the response passes all validation checks.
        Raises:
            ValueError: If any of the following conditions are met:
                - Response is None, empty, or missing root/result attributes
                - Root is not an instance of SendMessageSuccessResponse
                - Result is not an instance of Message
                - Message has no parts
        Example:
            >>> response = get_api_response()
            >>> is_valid = _validate_response(response)
            >>> print(is_valid)  # True if valid
        """

        if not response or not response.root or not response.root.result:
            raise ValueError("Invalid response structure")
        if not isinstance(response.root, SendMessageSuccessResponse):
            raise ValueError(f"Non-success response: {response.root}")
        if not isinstance(response.root.result, Message):
            raise ValueError(f"Non-message result: {response.root.result}")
        if not response.root.result.parts:
            raise ValueError("No parts in message result")
        return True

    async def _send_message_to_agent(
        self,
        agent_name: str,
        message_payload: dict[str, Any],
    ) -> SendMessageResponse:
        """Envía un mensaje a un agente específico y devuelve la respuesta."""
        client = self.get_agent_client(agent_name)
        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**message_payload))
        response: SendMessageResponse = await client.send_message(request)
        return response

    async def send_message_to_visual_agent(self, img_path: Path) -> dict[str, Any]:
        """Envía una imagen al Visual Agent y devuelve el resultado del análisis."""
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "file",
                        "file": {
                            "name": img_path.name,
                            "mimeType": "image/png",
                            "bytes": base64_image,
                        },
                    },
                ],
                "messageId": uuid4().hex,
            },
        }

        response = await self._send_message_to_agent("visual", send_message_payload)
        if self._validate_response(response):
            analysis_result = self._get_analysis_result_from_response(response)
            return analysis_result
        else:
            raise RuntimeError("Invalid response from Visual Agent")

    async def send_message_to_code_agent(
        self,
        patterns: list[tuple],
        analysis_result: dict[str, Any],
        custom_instructions: str = "",
    ) -> dict[str, Any]:
        """Envía el resultado del análisis visual y los patrones al Code Agent y devuelve el código generado."""
        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "metadata": {"type": "analysis_result"},
                        "text": json.dumps(analysis_result),
                    },
                    {
                        "kind": "text",
                        "metadata": {"type": "patterns"},
                        "text": json.dumps(patterns),
                    },
                    {
                        "kind": "text",
                        "metadata": {"type": "custom_instructions"},
                        "text": f"{custom_instructions}",
                    },
                ],
                "messageId": uuid4().hex,
            },
        }

        response = await self._send_message_to_agent("code", send_message_payload)
        if self._validate_response(response):
            code_result = get_message_text(response.root.result)
            return json.loads(code_result)
        else:
            raise RuntimeError("Invalid response from Code Agent")

    async def test_process() -> None:
        """Función de prueba para enviar mensajes a ambos agentes y procesar las respuestas."""
        orchestrator = OrchestratorAgent(
            visual_url=VISUAL_AGENT_URL,
            code_url=CODE_AGENT_URL,
        )
        await orchestrator.initialize()
        visual_agent: A2AClient = orchestrator.get_agent_client("visual")
        code_agent: A2AClient = orchestrator.get_agent_client("code")
        rag_agent: RAGAgent = orchestrator.get_agent_client("rag")

        logger.info("Sending test messages to both agents")

        logger.info("Sending test message to Visual Agent...")
        image_uri = "E:/Documentos/Git Repositories/ui2code-rag/tests/test_image.png"
        with open(image_uri, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read())

        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "file",
                        "file": {"name": "test_image.png", "mimeType": "image/png", "bytes": base64_image},
                    },
                ],
                "messageId": uuid4().hex,
            },
        }
        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**send_message_payload))

        response: SendMessageResponse = await visual_agent.send_message(request)
        logger.info("Received response from Visual Agent")
        logger.debug("Response details:")
        logger.debug(response.model_dump(mode="json", exclude_none=True))

        assert orchestrator._validate_response(response)

        analysis_result: dict[str, Any] = orchestrator._get_analysis_result_from_response(response)
        logger.debug(f"Extracted visual analysis: {analysis_result}")

        logger.info("Executing RAG Agent with visual analysis...")
        patterns: list[tuple] = rag_agent.invoke(analysis_result, top_k=5)
        logger.debug(f"RAG Agent retrieved patterns: {patterns}")

        custom_instructions = "Usar tema oscuro con acentos púrpura y efectos hover."

        logger.info("Sending test message to Code Agent...")
        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {"kind": "text", "metadata": {"type": "analysis_result"}, "text": json.dumps(analysis_result)},
                    {"kind": "text", "metadata": {"type": "patterns"}, "text": json.dumps(patterns)},
                    {"kind": "text", "metadata": {"type": "custom_instructions"}, "text": f"{custom_instructions}"},
                ],
                "messageId": uuid4().hex,
            },
        }

        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**send_message_payload))
        response = await code_agent.send_message(request)
        logger.info("Received response from Code Agent")
        logger.debug("Response details:")
        logger.debug(response.model_dump(mode="json", exclude_none=True))

        assert orchestrator._validate_response(response)

        code_result = get_message_text(response.root.result)
        logger.info(f"Code Agent result: {code_result}")

        await orchestrator.close()
