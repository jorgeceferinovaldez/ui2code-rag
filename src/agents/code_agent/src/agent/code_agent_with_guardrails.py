import json, html
from typing import Any
from guardrails import Guard, OnFailAction
from guardrails_grhub_valid_json import ValidJson
from guardrails_grhub_web_sanitization import WebSanitization
from loguru import logger

# Custom dependencies
from .code_agent import CodeAgent
from ..guardrails.shemas.code_agent_schema import OUTPUT_SCHEMA
from ..guardrails.validators.valid_html import IsHTMLField
from ..guardrails.validators.valid_schema_json import ValidSchemaJson


class CodeAgentWithGuardrails:
    output_schema = OUTPUT_SCHEMA

    def __init__(self, agent: CodeAgent):
        logger.debug("Inicializando CodeAgentWithGuardrails")
        self.agent = agent

        self.output_guard = Guard.for_string(
            validators=[
                ValidJson(on_fail=OnFailAction.NOOP),
                ValidSchemaJson(json_schema=self.output_schema, on_fail=OnFailAction.EXCEPTION),
                IsHTMLField(on_fail=OnFailAction.EXCEPTION, property="html_code"),
            ]
        )

        self.sanitization_guard = Guard().use(WebSanitization, on_fail="exception")

    def invoke(self, patterns, visual_analysis, custom_instructions=""):
        logger.debug(
            f"Llamada a invoke con patterns={patterns}, visual_analysis={visual_analysis}, custom_instructions={custom_instructions}"
        )
        result = self.agent.invoke(patterns, visual_analysis, custom_instructions)

        try:
            logger.debug(f"Resultado sin validar: {result}")
            validated_output = self.output_guard.parse(json.dumps(result))
            logger.debug(f"Resultado validado: {validated_output}")
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None
            raise e

        try:
            html_code = result["html_code"]
            encoded_html = html.escape(html_code)

            self.sanitization_guard.validate(encoded_html)
        except Exception as e:
            raise e

        logger.info(f"Generación de código: {result}")
        logger.info(f"Generación de código validada: {validated_output}")

        return result
