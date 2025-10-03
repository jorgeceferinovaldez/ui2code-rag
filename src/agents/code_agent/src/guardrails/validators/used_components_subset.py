import json
from typing import Set, Dict, Any, Optional
from guardrails import OnFailAction
from loguru import logger

class UsedComponentsSubset:
    """Exige que used_component_ids sea subconjunto de los ids detectados por el Visual Agent."""
    rail_alias = "used_components_subset"
    name = "used_components_subset"

    def __init__(self, allowed_ids: Set[str], on_fail: OnFailAction = OnFailAction.EXCEPTION):
        self.allowed = set(allowed_ids)
        self.on_fail = on_fail

    def _fail(self, msg: str):
        if self.on_fail == OnFailAction.EXCEPTION:
            raise ValueError(msg)
        logger.warning(msg)

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        try:
            data: Dict[str, Any] = json.loads(value)
        except Exception:
            self._fail("[UsedComponentsSubset] Respuesta del Code Agent no es JSON.")
            return value

        used = set(data.get("used_component_ids", []))
        if not used.issubset(self.allowed):
            self._fail(f"[UsedComponentsSubset] used={used - self.allowed} no pertenecen a allowed={self.allowed}.")
        return value
