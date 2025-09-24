"""Executor for the Visual A2A Agent."""

import json, base64
from loguru import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_file_parts
from src.agents.visual_agent.visual_agent_mock import VisualAgentMock
from a2a.types import InvalidParamsError, Message
from PIL import Image
from io import BytesIO
from a2a.types import Message


class VisualA2AAgentExecutor(AgentExecutor):
    """Executor for the Visual A2A Agent."""

    def __init__(self):
        self.agent = VisualAgentMock()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        base64_image = self._get_base64_image_from_context(context)
        if not base64_image:
            raise InvalidParamsError("No image found in message parts")

        image: Image = self._load_image_from_base64(base64_image)
        if image is None:
            raise InvalidParamsError("Failed to load image from base64 data")

        result = self.agent.invoke(image)
        # TODO: Change to structured message with data part
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(result, indent=2)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.error("Canceling Visual Agent")
        raise Exception("cancel not supported")

    def _get_base64_image_from_context(self, context: RequestContext) -> str:
        """
        Extract base64-encoded image data from a request context message.
        This method searches through the file parts of a message within the provided
        context to find and return the first image file (PNG or JPEG format) as
        base64-encoded bytes.
        Args:
            context (RequestContext): The request context containing the message
                                    with potential file parts.
        Returns:
            str: Base64-encoded image data from the first image file found.
        Raises:
            Exception: If no message is found in the context.
            Exception: If no file parts are found in the message.
            Exception: If no image files (PNG/JPEG) are found in the message parts.
        Note:
            This method only processes images with MIME types: image/png, image/jpeg,
            or image/jpg. Other file types are ignored.
        """

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
        """
        Load an image from a base64 encoded string.
        This method decodes a base64 string, converts it to an image object,
        and ensures the image is in RGB format.
        Args:
            base64_image (str): Base64 encoded image data as a string.
        Returns:
            Image: PIL Image object in RGB format.
        Raises:
            InvalidParamsError: If the base64 data cannot be decoded or converted
                               to a valid image format.
        Example:
            >>> base64_str = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            >>> image = self._load_image_from_base64(base64_str)
            >>> isinstance(image, Image.Image)
            True
        """
        try:
            image_data = base64.b64decode(base64_image)
            image = Image.open(BytesIO(image_data))
            image = image.convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Error loading image from base64: {e}")
            raise InvalidParamsError("Failed to load image from base64 data") from e
