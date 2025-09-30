# guardrails_html_validator.py
from guardrails.validators import (
    Validator,
    register_validator,
    PassResult,
    FailResult,
    ValidationResult,
)
from typing import Any, Dict
from bs4 import BeautifulSoup
import json


@register_validator(name="is-html-field", data_type=["string", "object", "list"])
class IsHTMLField(Validator):
    """
    Validador que verifica si una propiedad de un JSON
    contiene HTML válido.

    Se debe pasar como parámetro:
        IsHTMLField(on_fail="exception", property="html_code")
    """

    def __init__(self, **params):
        super().__init__(**params)
        self.params = params

    def validate(self, value: Any, metadata: Dict) -> ValidationResult:
        """Validates that a value is parseable as valid JSON and optionally validates against a JSON schema."""
        stringified = value
        parsed, error = (None, None)
        try:
            if not isinstance(value, str):
                stringified = json.dumps(value)

            parsed = json.loads(stringified)
        except json.decoder.JSONDecodeError as json_error:
            error = json_error
        except TypeError as type_error:
            error = type_error

        if error or not parsed:
            return FailResult(
                error_message=f"Value is not parseable as valid JSON! Reason: {str(error)}",
            )

        # Recupera la propiedad a validar desde los parámetros
        field_name = self.params.get("property")
        if not field_name:
            raise FailResult(error_message="No se especificó la propiedad a validar (param 'property').")

        if field_name not in parsed:
            raise FailResult(error_message=f"Falta la propiedad '{field_name}' en el JSON.")

        html_str = parsed[field_name]

        if not isinstance(html_str, str):
            raise FailResult(error_message=f"El campo '{field_name}' no es un string.")

        if "<" not in html_str or ">" not in html_str:
            raise FailResult(error_message=f"El campo '{field_name}' no contiene etiquetas HTML.")

        try:
            soup = BeautifulSoup(html_str, "html.parser")
        except Exception as e:
            raise FailResult(error_message=f"Error al parsear HTML en '{field_name}': {e}")

        if soup.find() is None:
            raise FailResult(error_message=f"No se encontraron etiquetas HTML en '{field_name}'.")

        return PassResult()
