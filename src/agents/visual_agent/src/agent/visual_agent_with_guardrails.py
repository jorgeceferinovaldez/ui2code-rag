# src/agents/visual_agent/src/agent/visual_agent_with_guardrails.py

"""Proxy para el agente visual que maneja la validación de salidas usando Guardrails."""
import json
from typing import Any, Dict
from guardrails import Guard, OnFailAction
from PIL import Image
from loguru import logger

from guardrails_grhub_valid_json import ValidJson
from ..guardrails.validators.valid_schema_json import ValidSchemaJson
from ..guardrails.schemas.visual_agent_schema import OUTPUT_SCHEMA

from .visual_agent import VisualAgent


class VisualAgentWithGuardrails:
    output_schema = OUTPUT_SCHEMA

    def __init__(self, agent: VisualAgent, on_fail: OnFailAction = OnFailAction.EXCEPTION):
        logger.debug("Inicializando VisualAgentWithGuardrails")
        self.agent = agent
        self.on_fail = on_fail

    def _build_guard(self) -> Guard:
        return Guard.for_string(
            validators=[
                ValidJson(on_fail=OnFailAction.EXCEPTION),
                ValidSchemaJson(json_schema=self.output_schema, on_fail=OnFailAction.EXCEPTION),
            ]
        )

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza claves para que el schema acepte las variantes actuales."""
        if not isinstance(raw, dict):
            return raw

        # Asegurar analysis_text presente (aunque sea vacío)
        raw.setdefault("analysis_text", "")

        # Si sólo tenemos image_meta {w,h}, opcionalmente materializamos image_metadata
        if "image_meta" in raw and "image_metadata" not in raw:
            try:
                w = int(raw["image_meta"]["w"])
                h = int(raw["image_meta"]["h"])
                raw["image_metadata"] = {
                    "dimensions": {"width": w, "height": h, "aspect_ratio": (w / h) if h else 0.0},
                    "dominant_colors": [],        # si no tenés, dejalo vacío
                    "layout_hints": {},
                    "file_size": 0,
                    "format": "unknown",
                }
            except Exception:
                # Si falla, el schema igual acepta image_meta por anyOf
                pass

        return raw

    @staticmethod
    def _coerce_guard_output_to_str(validated_output: Any) -> str:
        """
        Guardrails puede devolver str o ValidationOutcome.
        Extraemos la cadena JSON independientemente de la versión.
        """
        if isinstance(validated_output, str):
            return validated_output

        # Duck-typing sobre atributos típicos
        for attr in ("output", "validated_output", "value", "raw_output"):
            s = getattr(validated_output, attr, None)
            if isinstance(s, str):
                return s

        # Último intento: repr → NO ideal, pero mejor mensaje de error
        raise TypeError(
            f"Guard.parse() devolvió {type(validated_output).__name__} y no pude extraer una cadena JSON."
        )

    def invoke(self, image: Image) -> Dict[str, Any]:
        logger.debug(f"Llamada a invoke con imagen de tamaño {image.size}")

        # 1) Ejecutar el agente "crudo"
        raw: Dict[str, Any] = self.agent.invoke(image)

        # 2) Normalización leve
        raw = self._normalize(raw)

        # 3) Validación con Guardrails
        try:
            logger.debug(f"Resultado sin validar (normalizado): {raw}")
            validated = self._build_guard().parse(json.dumps(raw))
            validated_str = self._coerce_guard_output_to_str(validated)
            spec: Dict[str, Any] = json.loads(validated_str)
            logger.debug(f"Resultado validado: {spec}")
            return spec

        except Exception as e:
            logger.error(f"Error durante la validación del Visual Agent: {e}")
            if self.on_fail == OnFailAction.EXCEPTION:
                raise
            logger.warning("Devolviendo salida cruda por política on_fail != EXCEPTION.")
            return raw
