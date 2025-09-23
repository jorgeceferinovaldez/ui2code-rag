import json
from typing import Any, Dict
from guardrails import Guard, OnFailAction
from guardrails.hub import ValidJson
from agents.valid_schema_json import ValidSchemaJson
from src.logging_config import logger

class VisualAgentProxy:
    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "components": {
            "type": "array",
            "items": { "type": "string" }
            },
            "layout": { "type": "string" },
            "style": { "type": "string" },
            "analysis_text": { "type": "string" },
            "raw_response": { "type": "string" },
            "image_metadata": {
            "type": "object",
            "properties": {
                "image_path": { "type": "string" },
                "dimensions": { "type": "object" },
                "dominant_colors": { "type": "array", "items": {} },
                "layout_hints": { "type": "object" },
                "file_size": { "type": "integer" },
                "format": { "type": "string" }
            },
            "required": ["image_path", "dimensions", "dominant_colors", "layout_hints", "file_size", "format"]
            },
            "model_used": { "type": "string" },
            "analysis_timestamp": { "type": ["string", "null"] }
        },
        "required": [
            "components",
            "layout",
            "style",
            "analysis_text",
            "raw_response",
            "image_metadata",
            "model_used",
            "analysis_timestamp"
        ]
    }
    
    def __init__(self, agent):
        logger.info("Inicializando VisualAgentProxy")
        self.agent = agent

       
        self.output_guard = Guard.for_string(
            validators=[
               ValidJson(on_fail=OnFailAction.EXCEPTION),      
               ValidSchemaJson(json_schema=self.OUTPUT_SCHEMA, on_fail=OnFailAction.EXCEPTION),    

        ]
        )

        

    def analyze_image(self, image_path):
        logger.info("Mensaje de prueba")

        logger.info(f"Llamada a analyze_image con image_path={image_path}")
        result = self.agent.analyze_image(image_path)

        try:
            validated_output = self.output_guard.parse(json.dumps(result))
            logger.info(f"Resultado validado: {validated_output}")
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None
            raise e


        

        #if not validated_output.valid:
        #    raise ValueError(f"Análisis inválido: {validated_output.error}")

        return result
    
    def save_analysis_result(self, analysis_result: Dict[str, Any], filename: str = None) -> str:
        logger.info(f"Llamada a save_analysis_result con filename={filename}")
        return self.agent.save_analysis_result(analysis_result, filename)
