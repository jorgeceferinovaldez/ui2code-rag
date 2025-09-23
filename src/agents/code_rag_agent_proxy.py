import json
from guardrails import Guard, OnFailAction
from guardrails.hub import ValidJson
from src.agents.valid_schema_json import ValidSchemaJson
from src.agents.valid_html import IsHTMLField
from src.logging_config import logger

from typing import Dict, Any, List, Optional, Tuple


class CodeRAGAgentProxy:

    OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "html_code": { "type": "string" },
        "generation_metadata": {
        "type": "object",
        "properties": {
            "model_used": { "type": "string" },
            "patterns_used": { "type": "integer" },
            "visual_components": { "type": "array", "items": { "type": "string" } },
            "custom_instructions": { "type": "string" },
            "timestamp": { "type": "string", "format": "date-time" }
        },
        "required": ["model_used", "patterns_used", "visual_components", "custom_instructions", "timestamp"]
        },
        "visual_analysis_summary": {
        "type": "object",
        "properties": {
            "components": { "type": "array", "items": { "type": "string" } },
            "layout": { "type": "string" },
            "style": { "type": "string" }
        },
        "required": ["components", "layout", "style"]
        }
    },
    "required": ["html_code", "generation_metadata", "visual_analysis_summary"]
    }
    

    def __init__(self, agent):
        logger.info("Inicializando CodeRAGAgentProxy")
        self.agent = agent
        
        self.output_guard = Guard.for_string(
            validators=[
               ValidJson(on_fail=OnFailAction.NOOP),  
               ValidSchemaJson(json_schema=self.OUTPUT_SCHEMA, on_fail=OnFailAction.EXCEPTION),    
               IsHTMLField(on_fail=OnFailAction.EXCEPTION, property="html_code"),
        ]
        )

    def generate_code(self, patterns, visual_analysis, custom_instructions=""):
        logger.info(f"Llamada a generate_code con patterns={patterns}, visual_analysis={visual_analysis}, custom_instructions={custom_instructions}")
        result = self.agent.generate_code(patterns, visual_analysis, custom_instructions)
     
        try:
            validated_output = self.output_guard.parse(json.dumps(result))
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None
            raise e
        

        logger.info(f"Generación de código: {result}")
        logger.info(f"Generación de código validada: {validated_output}")

        return result

       
    def get_rag_status(self):
        logger.info("Llamada a get_rag_status")
        return self.agent.get_rag_status()
    
    def retrieve_patterns(self, visual_analysis: Dict[str, Any], top_k: int = 5) -> List[Tuple]:
        logger.info(f"Llamada a retrieve_patterns con visual_analysis={visual_analysis}, top_k={top_k}")
        return self.agent.retrieve_patterns(visual_analysis, top_k)

    def save_generated_code(self, code_result: Dict[str, Any], filename: str = None) -> str:
        logger.info(f"Llamada a save_generated_code con filename={filename}")
        return self.agent.save_generated_code(code_result, filename)
