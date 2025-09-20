from guardrails import Guard, OnFailAction
from guardrails.hub import ValidJson
from src.logging_config import logger

class VisualAgentProxy:
    def __init__(self, agent):
        self.agent = agent

       
        self.output_guard = Guard.for_string(
            validators=[
               ValidJson(on_fail=OnFailAction.NOOP),      
        ]
        )

    def analyze_image(self, image_path):
        logger.info("Mensaje de prueba")

        result = self.agent.analyze_image(image_path)

        try:
            validated_output = self.output_guard.parse(result)
            print("Validated output:", validated_output)
        except Exception as e:
            logger.error(f"Error during output validation: {e}")
            validated_output = None

        logger.info(f"Análisis de imagen: {result}")

        logger.info(f"Análisis validado: {validated_output}")


        #if not validated_output.valid:
        #    raise ValueError(f"Análisis inválido: {validated_output.error}")

        return result