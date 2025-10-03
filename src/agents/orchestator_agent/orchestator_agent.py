"""Orchestrator Agent that coordinates between Visual and Code Agents, and integrates RAG for context."""

from loguru import logger
import base64, json, httpx, asyncio, time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
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
from PIL import Image

from src.agents.rag_agent.rag_agent import RAGAgent
from src.config import visual_agent_url, code_agent_url

VISUAL_AGENT_URL = visual_agent_url
CODE_AGENT_URL = code_agent_url

# Objetivos de timeout (no se pasan a send_message; sirven para tunear transport/HTTPX)
TARGET_TIMEOUTS = {
    "visual": 180.0,
    "code": 120.0,
}

# Timeouts HTTPX amplios para requests largos/streaming
HTTPX_CONNECT_TIMEOUT = 10.0
HTTPX_READ_TIMEOUT    = 240.0
HTTPX_WRITE_TIMEOUT   = 240.0


class OrchestratorAgent:
    def __init__(self, visual_url: str = VISUAL_AGENT_URL, code_url: str = CODE_AGENT_URL) -> None:
        self.visual_url: str = visual_url
        self.code_url: str = code_url
        self.rag_agent: RAGAgent = RAGAgent()
        self.httpx_client: httpx.AsyncClient | None = None

        self.agents: dict[str, dict[str, object]] = {
            "visual": {"url": self.visual_url, "card": None, "client": None},
            "code": {"url": self.code_url, "card": None, "client": None},
            "rag": {"url": None, "card": None, "client": self.rag_agent},
        }

    async def initialize(self) -> None:
        """Inicializa el cliente HTTP y obtiene las cards de ambos agentes."""
        logger.info("Initializing HTTP client")
        timeout = httpx.Timeout(
            connect=HTTPX_CONNECT_TIMEOUT,
            read=HTTPX_READ_TIMEOUT,
            write=HTTPX_WRITE_TIMEOUT,
            pool=None,
        )
        self.httpx_client = httpx.AsyncClient(timeout=timeout)

        # Backoff para obtener agent cards (por si el server tarda en levantar)
        for agent_name, agent_info in self.agents.items():
            url = agent_info["url"]
            if not url:
                continue

            resolver = A2ACardResolver(httpx_client=self.httpx_client, base_url=url)
            last_err: Optional[Exception] = None

            for attempt in range(1, 8):
                try:
                    card: AgentCard = await resolver.get_agent_card()
                    client = A2AClient(httpx_client=self.httpx_client, agent_card=card)
                    self.agents[agent_name]["card"] = card
                    self.agents[agent_name]["client"] = client

                    # Intentar tunear el timeout del transport interno (si existe)
                    self._tune_a2a_transport_timeout(client, TARGET_TIMEOUTS.get(agent_name, 120.0))
                    logger.info(f"{agent_name} agent card fetched OK on attempt {attempt}")
                    break
                except Exception as e:
                    last_err = e
                    wait = min(0.5 * (2 ** (attempt - 1)), 5.0)
                    logger.warning(
                        f"Failed to fetch {agent_name} agent card (attempt {attempt}): {e}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
            else:
                logger.error(
                    f"Critical error fetching {agent_name} agent card: {last_err}",
                    exc_info=True,
                )
                raise RuntimeError(f"Failed to fetch {agent_name} agent card. Cannot continue.") from last_err

    @staticmethod
    def _tune_a2a_transport_timeout(client: A2AClient, seconds: float) -> None:
        """
        Ajusta (best-effort) el timeout del transport JSON-RPC interno del A2AClient.
        Algunas versiones exponen atributos privados distintos.
        """
        try:
            transport = getattr(client, "_transport", None) or getattr(client, "transport", None)
            if transport is None:
                logger.debug("A2AClient transport not found for timeout tuning.")
                return

            set_ok = False
            for attr in ("_timeout", "timeout", "_request_timeout", "request_timeout"):
                if hasattr(transport, attr):
                    setattr(transport, attr, float(seconds))
                    logger.debug(f"A2A transport timeout set via '{attr}' = {seconds}s")
                    set_ok = True
                    break
            if not set_ok and hasattr(transport, "set_timeout"):
                try:
                    transport.set_timeout(float(seconds))  # type: ignore[attr-defined]
                    logger.debug("A2A transport timeout set via set_timeout(...)")
                    set_ok = True
                except Exception:
                    pass

            if not set_ok:
                logger.debug("Could not set A2A transport timeout; relying on HTTPX timeouts only.")
        except Exception as e:
            logger.debug(f"Timeout tuning skipped due to: {e}")

    def _dump_response_safe(self, response) -> str:
        try:
            d = response.model_dump(mode="json", exclude_none=True)
            s = json.dumps(d)
            return s[:10000]
        except Exception:
            try:
                return str(response)[:10000]
            except Exception:
                return "<unprintable response>"

    def get_agent_client(self, agent_name: str) -> A2AClient | RAGAgent:
        client = self.agents.get(agent_name, {}).get("client")
        if client is None:
            raise RuntimeError(f"Agent '{agent_name}' not initialized.")
        return client

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()

    async def _send_message_to_agent(
        self,
        agent_name: str,
        message_payload: dict[str, Any],
    ) -> SendMessageResponse:
        """
        Envía un mensaje al agente indicado y devuelve la respuesta A2A.
        ¡No pasar timeout aquí! Algunas versiones de a2a no soportan ese kwarg.
        """
        client = self.get_agent_client(agent_name)
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_payload),
        )

        t0 = time.perf_counter()
        try:
            response: SendMessageResponse = await client.send_message(request)
            dt = time.perf_counter() - t0
            try:
                dump = response.model_dump(mode="json", exclude_none=True)
                root_keys = list(dump.get("root", {}).keys())
                logger.debug(f"[{agent_name}] send_message OK in {dt:.1f}s. Root keys: {root_keys}")
            except Exception:
                logger.debug(f"[{agent_name}] send_message OK in {dt:.1f}s (no dump)")
            return response
        except Exception as e:
            dt = time.perf_counter() - t0
            logger.error(f"[{agent_name}] send_message failed after {dt:.1f}s: {e}", exc_info=True)
            raise

    def _validate_response(self, response: SendMessageResponse) -> bool:
        try:
            if not response or not getattr(response, "root", None):
                raise ValueError("Invalid response structure")
            if not isinstance(response.root, SendMessageSuccessResponse):
                # ¡OJO! Nada de f-string con dicts/JSON dentro.
                logger.error("Non-success response root: {}", type(response.root))
                raise ValueError(f"Non-success response: {type(response.root).__name__}")
            if not isinstance(response.root.result, Message):
                raise ValueError("Non-message result")
            if not response.root.result.parts:
                raise ValueError("No parts in message result")
        except Exception as e:
            # Evita f-strings 
            logger.error("Response validation error: {}", e, exc_info=True)
            raise RuntimeError("Response validation failed") from e
        return True


    def _get_analysis_result_from_response(self, response: SendMessageResponse) -> dict[str, Any]:
        """
        Extrae dict JSON desde la respuesta del Visual Agent.
        Usa la última parte de texto (el executor manda heartbeats antes, el final es el payload real).
        """
        # 1) parts → último text
        try:
            parts_list = get_text_parts(response.root.result.parts)
            if parts_list:
                raw = parts_list[-1]
                return json.loads(raw)
        except Exception:
            pass

        # 2) fallback: texto directo
        try:
            raw = get_message_text(response.root.result)
            if raw and raw.strip():
                return json.loads(raw)
        except Exception:
            pass

        # 3) dump para diagnóstico
        dump = self._dump_response_safe(response)
        logger.error(f"Failed to decode JSON from visual analysis response. Dump: {dump[:1200]}")
        raise ValueError("Invalid JSON in visual analysis response")

    async def send_message_to_visual_agent(self, img_path: Path) -> dict[str, Any]:
        """Envía una imagen al Visual Agent y devuelve el resultado del análisis."""
        # Re-encode + downscale para bajar latencia
        try:
            from io import BytesIO
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                max_side = 1280
                w, h = im.size
                scale = min(1.0, max_side / max(w, h))
                if scale < 1.0:
                    im = im.resize((int(w * scale), int(h * scale)))
                buf = BytesIO()
                im.save(buf, format="JPEG", quality=85, optimize=True)
                base64_image = base64.b64encode(buf.getvalue()).decode("utf-8")
                buf.close()
                mime = "image/jpeg"
        except Exception:
            with open(img_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")
            mime = "image/png"

        send_message_payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "file",
                        "file": {
                            "name": img_path.name,
                            "mimeType": mime,
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
            dump = self._dump_response_safe(response)
            raise RuntimeError(f"Invalid response from Visual Agent. Dump: {dump[:1500]}")

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
                    {"kind": "text", "metadata": {"type": "analysis_result"}, "text": json.dumps(analysis_result)},
                    {"kind": "text", "metadata": {"type": "patterns"}, "text": json.dumps(patterns)},
                    {"kind": "text", "metadata": {"type": "custom_instructions"}, "text": f"{custom_instructions}"},
                ],
                "messageId": uuid4().hex,
            },
        }

        response = await self._send_message_to_agent("code", send_message_payload)
        if self._validate_response(response):
            code_result = get_message_text(response.root.result)
            return json.loads(code_result)
        else:
            dump = self._dump_response_safe(response)
            raise RuntimeError(f"Invalid response from Code Agent. Dump: {dump[:1500]}")

    @staticmethod
    async def test_process() -> None:
        """Función de prueba para enviar mensajes a ambos agentes y procesar las respuestas."""
        logger.info("Starting Orchestrator Agent test process")
        orchestrator = OrchestratorAgent(
            visual_url=VISUAL_AGENT_URL,
            code_url=CODE_AGENT_URL,
        )
        await orchestrator.initialize()
        rag_agent: RAGAgent = orchestrator.get_agent_client("rag")

        # VISUAL
        logger.info("Sending test message to Visual Agent...")
        image_uri = "E:/Documentos/Git Repositories/ui2code-rag/tests/test_image.png"
        with open(image_uri, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        send_message_payload_visual: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [
                    {"kind": "file", "file": {"name": "test_image.jpg", "mimeType": "image/jpeg", "bytes": base64_image}},
                ],
                "messageId": uuid4().hex,
            },
        }
        response_visual: SendMessageResponse = await orchestrator._send_message_to_agent("visual", send_message_payload_visual)
        logger.info("Received response from Visual Agent")
        logger.debug(response_visual.model_dump(mode="json", exclude_none=True))
        assert orchestrator._validate_response(response_visual)
        analysis_result: dict[str, Any] = orchestrator._get_analysis_result_from_response(response_visual)
        logger.debug(f"Extracted visual analysis: {analysis_result}")

        # RAG
        logger.info("Executing RAG Agent with visual analysis...")
        patterns: list[tuple] = rag_agent.invoke(analysis_result, top_k=5)
        logger.debug(f"RAG Agent retrieved patterns: {patterns}")

        # CODE
        custom_instructions = "Usar tema oscuro con acentos púrpura y efectos hover."
        logger.info("Sending test message to Code Agent...")
        send_message_payload_code: dict[str, Any] = {
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
        response_code = await orchestrator._send_message_to_agent("code", send_message_payload_code)
        logger.info("Received response from Code Agent")
        logger.debug(response_code.model_dump(mode="json", exclude_none=True))
        assert orchestrator._validate_response(response_code)
        code_result = get_message_text(response_code.root.result)
        logger.info(f"Code Agent result: {code_result}")

        await orchestrator.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(OrchestratorAgent.test_process())
