# TODO: Posibles mejoras
# - Tests
# - Los returns tendrían que ser objetos.
from loguru import logger
from io import BytesIO
import os, json, base64, sys
from typing import Any
import openai
from PIL import Image
import cv2
import numpy as np

# Custom dependencies
from ..config import settings
from ..texts.prompts import ANALYSIS_PROMPT
from ..texts.types import COMMON_COMPONENTS

OPENROUTER_API_KEY = settings.openrouter_api_key
OPENROUTER_BASE_URL = settings.openrouter_base_url
CODE_MODEL = settings.openrouter_model
OPENAI_KEY = settings.openai_key
OPENAI_MODEL = settings.openai_model


class VisualAgent:
    """
    Agent responsible for analyzing UI design images and extracting structural information
    """

    def __init__(self):
        if not (OPENROUTER_API_KEY or OPENAI_KEY):
            raise ValueError("No API key found for available providers. Please set one in the environment.")
        if OPENROUTER_API_KEY:
            self.client = openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
            self.model = CODE_MODEL
            self.use_openrouter = True
        else:
            if OPENAI_KEY:
                self.client = openai.OpenAI(api_key=OPENAI_KEY)
                self.model = OPENAI_MODEL
                self.use_openrouter = False

    def invoke(self, img: Image) -> dict[str, Any]:
        """
        Analyze a UI image and extract component information using vision model.
        This method processes an input image through the visual analysis pipeline:
        1. Preprocesses the image to extract metadata
        2. Encodes the image to base64 format
        3. Sends the image to a vision model for analysis
        4. Parses the model response into structured data
        5. Combines analysis results with image metadata
        Args:
            img (Image): PIL Image object to be analyzed
        Returns:
            dict[str, Any]: Dictionary containing analysis results with the following structure:
                - components: List of UI components detected in the image
                - layout: Layout type identified (or "unknown" if parsing fails)
                - style: Style classification (defaults to "modern" if parsing fails)
                - analysis_text: Raw text response from the vision model
                - raw_response: Original unprocessed response
                - image_metadata: Technical metadata about the processed image
                - model_used: Name of the vision model used for analysis
                - analysis_timestamp: Timestamp of the analysis (currently None)
                - error: Error message if analysis fails (only present on failure)
        Raises:
            Returns error dict instead of raising exceptions. Error conditions include:
            - Image preprocessing failures
            - Vision model API failures
            - JSON parsing errors (handled gracefully with fallback structure)
            - General processing exceptions
        """
        try:
            # Preprocess image
            image_metadata = self._preprocess_image(img)

            if "error" in image_metadata:
                return image_metadata

            # Prepare the analysis prompt
            prompt = self._get_analysis_prompt()

            # Encode image
            base64_image = self._encode_image_to_base64(img)

            # Prepare messages for vision model
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ]

            # Call vision model
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=1000, temperature=0.1
            )

            # Parse response
            analysis_text = response.choices[0].message.content
            try:
                # Try to parse as JSON
                analysis_result = json.loads(analysis_text)
            except json.JSONDecodeError:
                # If not valid JSON, create structured response
                analysis_result = {
                    "components": self._extract_components_from_text(analysis_text),
                    "layout": "unknown",
                    "style": "modern",
                    "analysis_text": analysis_text,
                }

            # Combine with metadata
            final_result = {
                **analysis_result,
                "image_metadata": image_metadata,
                "model_used": self.model,
                "analysis_timestamp": None,
            }

            return final_result
        except Exception as e:
            return {
                "error": f"Image analysis failed: {str(e)}",
                "image_metadata": image_metadata if "image_metadata" in locals() else None,
            }

    def _preprocess_image(self, image: Image) -> dict[str, Any]:
        """Extract basic metadata and features from the image."""
        try:
            width, height = image.size

            # Basic color analysis
            dominant_colors = self._extract_dominant_colors(image)

            # Basic layout detection (simple grid detection)
            layout_info = self._detect_basic_layout(image)

            # Estimate file size in memory
            memory_size = sys.getsizeof(image.tobytes())

            return {
                "dimensions": {"width": width, "height": height, "aspect_ratio": width / height},
                "dominant_colors": dominant_colors,
                "layout_hints": layout_info,
                "file_size": memory_size,
                "format": image.format or "unknown",
            }

        except Exception as e:
            return {"error": f"Image preprocessing failed: {str(e)}"}

    def _extract_dominant_colors(self, image: np.ndarray, k: int = 5) -> list:
        """Extract dominant colors using k-means clustering"""
        try:
            # Reshape image to be a list of pixels
            data = image.reshape((-1, 3))
            data = np.float32(data)

            # Apply k-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            # Convert back to uint8 and return as list
            centers = np.uint8(centers)
            return [{"r": int(c[2]), "g": int(c[1]), "b": int(c[0])} for c in centers]
        except Exception:
            return []

    def _detect_basic_layout(self, image: np.ndarray) -> dict[str, Any]:
        """Detect basic layout patterns using edge detection"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Edge detection
            edges = cv2.Canny(gray, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Basic layout metrics
            total_contours = len(contours)
            large_contours = [c for c in contours if cv2.contourArea(c) > 1000]

            return {
                "total_elements": total_contours,
                "major_elements": len(large_contours),
                "complexity": "high" if total_contours > 50 else "medium" if total_contours > 20 else "low",
            }
        except Exception:
            return {"complexity": "unknown"}

    def _encode_image_to_base64(self, image: Image) -> str:
        """Encode image to base64 for API transmission"""
        try:
            buffered = BytesIO()

            # Validate input
            if image is None:
                raise ValueError("Image cannot be None")
            if not hasattr(image, "mode") or not hasattr(image, "size"):
                raise ValueError("Invalid PIL Image object")
            if image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Image has invalid dimensions")

            # Handle different image modes
            try:
                if image.mode in ("RGBA", "LA", "P"):
                    # Convert RGBA/LA to RGB by compositing against white background
                    # Or convert palette mode to RGB
                    if image.mode == "P":
                        image = image.convert("RGBA")

                    # Create white background
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "RGBA":
                        background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                    else:  # LA mode
                        background.paste(image, mask=image.split()[-1])
                    image = background
                elif image.mode not in ("RGB", "L"):
                    # Convert other modes to RGB
                    image = image.convert("RGB")
            except Exception as e:
                logger.warning(f"Image mode conversion failed: {e}, attempting direct RGB conversion")
                image = image.convert("RGB")

            try:
                image.save(buffered, format="JPEG", quality=85, optimize=True)
            except Exception as e:
                # Fallback: try without optimization
                logger.warning(f"JPEG save with optimization failed: {e}, trying without optimization")
                buffered = BytesIO()  # Reset buffer
                image.save(buffered, format="JPEG", quality=85)

            # Encode to base64
            image_data = buffered.getvalue()
            if len(image_data) == 0:
                raise ValueError("No image data was generated")

            encoded_string = base64.b64encode(image_data).decode("utf-8")

            if not encoded_string:
                raise ValueError("Base64 encoding resulted in empty string")
            return encoded_string
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e}")
            raise ValueError(f"Image encoding failed: {str(e)}")
        finally:
            # Ensure buffer is closed
            if "buffered" in locals():
                buffered.close()

    def _get_analysis_prompt(self) -> str:
        """Get the structured prompt for UI analysis"""
        return ANALYSIS_PROMPT

    def _extract_components_from_text(self, text: str) -> list:
        """Extract UI components from text analysis when JSON parsing fails"""
        found_components = []
        text_lower = text.lower()

        for component in COMMON_COMPONENTS:
            if component in text_lower:
                found_components.append(component)

        return found_components if found_components else ["container", "content"]
