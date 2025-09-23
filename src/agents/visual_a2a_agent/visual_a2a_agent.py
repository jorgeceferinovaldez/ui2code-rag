from loguru import logger

class VisualA2AAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    async def invoke(self):
        logger.debug("Visual Agent invoked")
        return "Visual Agent invoked"
