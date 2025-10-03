import json
from typing import Any, Dict, List, Optional
from guardrails import OnFailAction
from loguru import logger

from ..utils.spec_utils import compute_coverage

class ConfidenceCoverageValidator:
    """
    Valida umbral de confianza media y cobertura total de bboxes.
    Compatible con Guardrails: define rail_alias, name y validate(value, metadata=None).
    """
    rail_alias = "confidence_coverage"
    name = "confidence_coverage"

    def __init__(self, min_conf: float = 0.75, min_cov: float = 0.35, on_fail: OnFailAction = OnFailAction.EXCEPTION):
        self.min_conf = float(min_conf)
        self.min_cov = float(min_cov)
        self.on_fail = on_fail

    def _fail(self, msg: str):
        if self.on_fail == OnFailAction.EXCEPTION:
            # Guardrails espera que se lance una excepción en modo EXCEPTION
            raise ValueError(msg)
        logger.warning(msg)

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Guardrails llamará con (value[, metadata]). Debe devolver el mismo string si pasa."""
        try:
            data: Dict[str, Any] = json.loads(value)
        except Exception as e:
            self._fail(f"[ConfidenceCoverage] JSON inválido: {e}")
            return value

        comps: List[Dict[str, Any]] = data.get("components", [])
        if not comps:
            self._fail("[ConfidenceCoverage] Spec sin 'components'.")
            return value

        confidences = [float(c.get("confidence", 0.0)) for c in comps if "confidence" in c]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

        meta = data.get("image_meta", {})
        cov = compute_coverage(comps, int(meta.get("w", 0)), int(meta.get("h", 0)))

        if mean_conf < self.min_conf:
            self._fail(f"[ConfidenceCoverage] Confianza media {mean_conf:.2f} < {self.min_conf:.2f}")
        if cov < self.min_cov:
            self._fail(f"[ConfidenceCoverage] Cobertura {cov:.2f} < {self.min_cov:.2f}")

        return value
