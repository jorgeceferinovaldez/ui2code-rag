"""Proxy para el agente visual que maneja la validación de salidas usando Guardrails."""

import json
from typing import Any, Dict
from guardrails import Guard, OnFailAction
from PIL import Image
from guardrails_grhub_valid_json import ValidJson
from loguru import logger

from .visual_agent import VisualAgent
from ..guardrails.validators.valid_schema_json import ValidSchemaJson
from ..guardrails.schemas.visual_agent_schema import OUTPUT_SCHEMA


class VisualAgentWithGuardrails:
    output_schema = OUTPUT_SCHEMA

    def __init__(self, agent: VisualAgent):
        logger.debug("Inicializando VisualAgentWithGuardrails")
        self.agent = agent

        self.output_guard = Guard.for_string(
            validators=[
                ValidJson(on_fail=OnFailAction.EXCEPTION),
                ValidSchemaJson(json_schema=self.output_schema, on_fail=OnFailAction.EXCEPTION),
            ]
        )

    def invoke(self, image: Image):
        logger.debug(f"Llamada a invoke con imagen de tamaño {image.size}")
        result = self.agent.invoke(image)

        try:
            logger.debug(f"Resultado sin validar: {result}")
            validated_output = self.output_guard.parse(json.dumps(result))
            logger.debug(f"Resultado validado: {validated_output}")
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None
            raise e
        return result
