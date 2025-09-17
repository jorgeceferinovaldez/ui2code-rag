from guardrails import Guard, OnFailAction
from guardrails.hub import ValidJson
from src.logging_config import logger

from typing import Dict, Any, List, Optional, Tuple


class CodeRAGAgentProxy:
    def __init__(self, agent):
        self.agent = agent
        
        self.output_guard = Guard.for_string(
            validators=[
               ValidJson(on_fail=OnFailAction.NOOP),      
        ]
        )

    def generate_code(self, patterns, visual_analysis, custom_instructions=""):
        result = self.agent.generate_code(patterns, visual_analysis, custom_instructions)
     
        try:
            validated_output = self.output_guard.parse(result)
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None


        logger.info(f"Generación de código: {result}")
        logger.info(f"Generación de código validada: {validated_output}")

        return result
        #if not validated_output.valid:
        #    raise ValueError(f"HTML inválido: {validated_output.error}")

        return result
    
    def get_rag_status(self):
        return self.agent.get_rag_status()
    
    def retrieve_patterns(self, visual_analysis: Dict[str, Any], top_k: int = 5) -> List[Tuple]:
        return self.agent.retrieve_patterns(visual_analysis, top_k)

    def save_generated_code(self, code_result: Dict[str, Any], filename: str = None) -> str:
        return self.agent.save_generated_code(code_result, filename)
