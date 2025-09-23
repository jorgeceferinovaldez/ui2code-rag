from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from src.agents.visual_a2a_agent.visual_a2a_agent import VisualA2AAgent

from a2a.types import (
    InvalidParamsError,
    Message,
)

from src.agents.visual_agent import VisualAgent
from PIL import Image

from io import BytesIO
import base64


class VisualA2AAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = VisualAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Executing Visual Agent")
        base64_image = self._get_base64_image_from_context(context)
        if not base64_image:
            raise InvalidParamsError("No image found in message parts")

        logger.success(f"Base 64 Image: {base64_image[:30]}...")

        image: Image = self._load_image_from_base64(base64_image)
        if image is None:
            raise InvalidParamsError("Failed to load image from base64 data")

        result = self.agent.analyze_image(image)
        logger.debug(f"Visual Agent result: {result}")
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.debug("Canceling Visual Agent")
        raise Exception("cancel not supported")

    def _get_base64_image_from_context(self, context: RequestContext) -> str:
        message: Message = context.message
        if not message:
            raise Exception("No message found in context")

        for part in message.parts:
            root = part.root
            if root.kind == "file" and root.file.mime_type in ["image/png", "image/jpeg", "image/jpg"]:
                return root.file.bytes

        raise Exception("No image found in message parts")

    def _load_image_from_base64(self, base64_image: str) -> Image:
        try:
            image_data = base64.b64decode(base64_image)
            image = Image.open(BytesIO(image_data))
            image = image.convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Error loading image from base64: {e}")
            raise InvalidParamsError("Failed to load image from base64 data") from e
