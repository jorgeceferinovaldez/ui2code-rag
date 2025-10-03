import json, html
from typing import Any, Dict
from guardrails import Guard, OnFailAction
from guardrails_grhub_valid_json import ValidJson
from guardrails_grhub_web_sanitization import WebSanitization
from loguru import logger

from .code_agent import CodeAgent
from ..guardrails.schemas.code_agent_schema import OUTPUT_SCHEMA
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

    def _coerce_visual(self, visual_analysis: Dict[str, Any]) -> Dict[str, Any]:
        va = dict(visual_analysis or {})
        va.setdefault("components", [])
        va.setdefault("layout", "unknown")
        va.setdefault("style", "modern")
        return va

    def invoke(self, patterns, visual_analysis, custom_instructions=""):
        logger.debug(
            "Llamada a invoke con patterns={}, visual_analysis keys={}, custom_instructions={}",
            len(patterns) if patterns else 0,
            list((visual_analysis or {}).keys()),
            (custom_instructions or "")[:120],
        )

        va = self._coerce_visual(visual_analysis)

        # Llamamos SIEMPRE al agente (deja fallback interno si algo falla)
        result = self.agent.invoke(patterns or [], va, custom_instructions or "")

        # Si vino vacío, fuerza fallback antes de validar
        if not result.get("html_code") or not str(result["html_code"]).strip():
            logger.warning("html_code vacío recibido; forzando FALLBACK_HTML antes de validar")
            try:
                result["html_code"] = self.agent._get_fallback_html()
            except Exception:
                result["html_code"] = "<!doctype html><html><head><meta charset='utf-8'><title>Fallback</title></head><body><p>Fallback</p></body></html>"
            result.setdefault("status", "FALLBACK_HTML")

        # Validación de salida
        try:
            va_sum = result.get("visual_analysis_summary", {}) or {}
            if isinstance(va_sum.get("components"), list) and not va_sum["components"]:
                va_sum["components"] = [{"id": "auto_0", "type": "container"}]
            result["visual_analysis_summary"] = va_sum
            validated_output = self.output_guard.parse(json.dumps(result))
            logger.debug("Resultado validado OK", validated_output)
        except Exception as e:
            logger.error("Error durante validación de salida del Code Agent: {}", e, exc_info=True)
            raise

        # Sanitización de HTML
        try:
            self.sanitization_guard.validate(html.escape(result["html_code"]))
        except Exception as e:
            logger.error("Error de sanitización: {}", e, exc_info=True)
            raise

        logger.info("Generación de código validada")
        return result
