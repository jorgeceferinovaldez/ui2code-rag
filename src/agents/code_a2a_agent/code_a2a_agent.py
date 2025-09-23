from loguru import logger


class CodeA2AAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    async def invoke(self):
        logger.debug("Code Agent invoked")
        return "Code Agent invoked"
