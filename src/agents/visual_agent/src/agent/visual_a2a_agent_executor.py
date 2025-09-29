"""Executor for the Visual A2A Agent."""

import json, base64
from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_file_parts
from a2a.types import InvalidParamsError, Message
from PIL import Image
from io import BytesIO
from a2a.types import Message

from src.agent.visual_agent import VisualAgent


class VisualA2AAgentExecutor(AgentExecutor):
    """Executor for the Visual A2A Agent."""

    def __init__(self):
        self.agent = VisualAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        base64_image = self._get_base64_image_from_context(context)
        if not base64_image:
            raise InvalidParamsError("No image found in message parts")

        image = self._load_image_from_base64(base64_image)
        if image is None:
            raise InvalidParamsError("Failed to load image from base64 data")

        result = self.agent.invoke(image)
        # TODO: Change to structured message with data part
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(result, indent=2)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.error("Canceling Visual Agent")
        raise Exception("cancel not supported")

    def _get_base64_image_from_context(self, context: RequestContext) -> str:
        """Extract base64-encoded image data from a request context message."""
        message: Message = context.message
        if not message:
            raise Exception("No message found in context")

        file_parts = get_file_parts(message.parts)
        if not file_parts:
            raise Exception("No file parts found in message")

        for file_part in file_parts:
            if file_part.mime_type in ["image/png", "image/jpeg", "image/jpg"]:
                return file_part.bytes

        raise Exception("No image found in message parts")

    def _load_image_from_base64(self, base64_image: str) -> Image:
        """Load an image from a base64 encoded string."""
        try:
            image_data = base64.b64decode(base64_image)
            image = Image.open(BytesIO(image_data))
            image = image.convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Error loading image from base64: {e}")
            raise InvalidParamsError("Failed to load image from base64 data") from e
