"""Executor for the Visual A2A Agent."""

import json, base64
from io import BytesIO
from typing import Optional

from loguru import logger
from PIL import Image

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_file_parts
from a2a.types import InvalidParamsError, Message

# Custom dependencies
from .visual_agent_with_guardrails import VisualAgentWithGuardrails
from .visual_agent import VisualAgent
from .visual_agent_mock import VisualAgentMock  # útil para pruebas locales

SUPPORTED_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


class VisualA2AAgentExecutor(AgentExecutor):
    """Executor for the Visual A2A Agent."""

    def __init__(self):
        # Cambiá a Mock si querés probar sin modelo:
        self.agent = VisualAgentWithGuardrails(VisualAgentMock())
        # self.agent = VisualAgentWithGuardrails(VisualAgent())

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Executing Visual Agent")

        # Heartbeat temprano para mantener viva la conexión en requests largos
        await event_queue.enqueue_event(
            new_agent_text_message(json.dumps({"status": "started", "stage": "loading_image"}))
        )

        try:
            base64_image, mime = self._get_base64_image_from_context(context)
            image = self._load_image_from_base64(base64_image)
        except Exception as e:
            logger.exception("Failed to load/parse image")
            # Devolvemos SUCCESS con error semántico (no JSONRPC error)
            await event_queue.enqueue_event(
                new_agent_text_message(json.dumps({"error": f"Image parsing error: {str(e)}"}))
            )
            return

        # (Opcional) enviar otro heartbeat
        await event_queue.enqueue_event(new_agent_text_message(json.dumps({"status": "running", "stage": "analyzing"})))

        # Ejecutar el agente y **no** romper la RPC si algo falla.
        try:
            # TIP: reducir la imagen para bajar latencia en el visual si viene gigante
            image = self._maybe_downscale(image, max_side=1280)

            result = self.agent.invoke(image)

            # Normalizamos resultado: debe ser dict JSON-serializable
            payload = result if isinstance(result, dict) else {"result": result}

            logger.success(f"Visual Agent result: {payload}")
            await event_queue.enqueue_event(new_agent_text_message(json.dumps(payload)))

        except Exception as e:
            logger.exception("Visual Agent execution failed")
            # IMPORTANTE: responder mensaje de éxito con campo error, no lanzar excepción
            await event_queue.enqueue_event(
                new_agent_text_message(json.dumps({"error": f"Visual agent failure: {str(e)}"}))
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.error("Canceling Visual Agent")
        raise Exception("cancel not supported")

    # -----------------------
    # Helpers
    # -----------------------
    def _get_base64_image_from_context(self, context: RequestContext) -> tuple[str, Optional[str]]:
        """Extract base64-encoded image data and mime from a request context message."""
        message: Message = context.message
        if not message:
            raise InvalidParamsError("No message found in context")

        file_parts = get_file_parts(message.parts)
        if not file_parts:
            raise InvalidParamsError("No file parts found in message")

        for fp in file_parts:
            mime = getattr(fp, "mime_type", None) or getattr(fp, "mimeType", None)
            if mime in SUPPORTED_MIMES:
                data = fp.bytes
                if not isinstance(data, str):
                    data = data.decode("utf-8")
                return data, mime

            # if data coming as bytes, convert to str
            data = fp.bytes
            if not isinstance(data, str):
                data = data.decode("utf-8")
            if data.startswith("data:image/"):
                # form: data:image/png;base64,AAA...
                try:
                    header, b64 = data.split(",", 1)
                    return b64, header.split(";")[0].split(":")[1]
                except Exception:
                    pass

        raise InvalidParamsError("No supported image found in message parts")

    def _load_image_from_base64(self, base64_image: str) -> Image.Image:
        """Load an image from a base64 encoded string (with or without data URL)."""
        try:
            if base64_image.startswith("data:image/"):
                base64_image = base64_image.split(",", 1)[-1]

            image_data = base64.b64decode(base64_image)
            image = Image.open(BytesIO(image_data))
            # normalize to RGB to avoid weird modes (P, LA, RGBA)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Error loading image from base64: {e}")
            raise InvalidParamsError("Failed to load image from base64 data") from e

    @staticmethod
    def _maybe_downscale(im: Image.Image, max_side: int = 1280) -> Image.Image:
        """Downscale large images to speed up the vision model."""
        try:
            w, h = im.size
            m = max(w, h)
            if m > max_side:
                scale = max_side / float(m)
                im = im.resize((int(w * scale), int(h * scale)))
            return im
        except Exception:
            return im
