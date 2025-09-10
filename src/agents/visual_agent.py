"""
Visual Agent for UI Design Analysis
Analyzes uploaded images of UI designs and extracts structural information
"""

import os
import json
import base64
from typing import Dict, Any, Optional
from pathlib import Path
import openai
from PIL import Image
import cv2
import numpy as np

from src.config import temp_images_dir, project_dir


class VisualAgent:
    """
    Agent responsible for analyzing UI design images and extracting structural information
    """
    
    def __init__(self):
        """Initialize the Visual Agent with OpenRouter configuration"""
        # Load environment variables
        from dotenv import load_dotenv
        env_path = project_dir() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        
        # Configure OpenRouter client
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        if openrouter_api_key:
            self.client = openai.OpenAI(
                base_url=openrouter_base_url,
                api_key=openrouter_api_key
            )
            self.model = os.getenv("VISUAL_MODEL", "google/gemini-flash-1.5")
            self.use_openrouter = True
        else:
            # Fallback to OpenAI if available
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                self.client = openai.OpenAI(api_key=openai_key)
                self.model = "gpt-4-vision-preview"
                self.use_openrouter = False
            else:
                raise ValueError("Neither OPENROUTER_API_KEY nor OPENAI_API_KEY found in environment")
    
    def preprocess_image(self, image_path: str) -> Dict[str, Any]:
        """
        Preprocess image and extract basic visual metrics
        
        Args:
            image_path: Path to the UI design image
            
        Returns:
            Dictionary with image metadata and basic analysis
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image from {image_path}")
            
            # Get image dimensions
            height, width, channels = image.shape
            
            # Convert to PIL for additional processing
            pil_image = Image.open(image_path)
            
            # Basic color analysis
            dominant_colors = self._extract_dominant_colors(image)
            
            # Basic layout detection (simple grid detection)
            layout_info = self._detect_basic_layout(image)
            
            return {
                "image_path": image_path,
                "dimensions": {
                    "width": width,
                    "height": height,
                    "aspect_ratio": width / height
                },
                "dominant_colors": dominant_colors,
                "layout_hints": layout_info,
                "file_size": os.path.getsize(image_path),
                "format": pil_image.format
            }
            
        except Exception as e:
            return {
                "error": f"Image preprocessing failed: {str(e)}",
                "image_path": image_path
            }
    
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
    
    def _detect_basic_layout(self, image: np.ndarray) -> Dict[str, Any]:
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
                "complexity": "high" if total_contours > 50 else "medium" if total_contours > 20 else "low"
            }
            
        except Exception:
            return {"complexity": "unknown"}
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 for API transmission"""
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze UI design image using vision model
        
        Args:
            image_path: Path to the UI design image
            
        Returns:
            Analysis results with components, layout, and style information
        """
        try:
            # Preprocess image
            image_metadata = self.preprocess_image(image_path)
            
            if "error" in image_metadata:
                return image_metadata
            
            # Prepare the analysis prompt
            prompt = self._get_analysis_prompt()
            
            # Encode image
            base64_image = self.encode_image_to_base64(image_path)
            
            # Prepare messages for vision model
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Call vision model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.1
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
                    "raw_response": analysis_text
                }
            
            # Combine with metadata
            final_result = {
                **analysis_result,
                "image_metadata": image_metadata,
                "model_used": self.model,
                "analysis_timestamp": None
            }
            
            return final_result
            
        except Exception as e:
            return {
                "error": f"Image analysis failed: {str(e)}",
                "image_path": image_path,
                "image_metadata": image_metadata if 'image_metadata' in locals() else None
            }
    
    def _get_analysis_prompt(self) -> str:
        """Get the structured prompt for UI analysis"""
        return """Analiza esta imagen de diseño de interfaz de usuario. Identifica y describe:

1. Componentes principales (header, navbar, buttons, forms, cards, etc.)
2. Layout y estructura (grid, flexbox, columnas, filas)
3. Estilo visual (colores, tipografía, spacing, sombras)
4. Elementos interactivos (botones, enlaces, campos de entrada)

IMPORTANTE: 
- Describe la FUNCIÓN de los elementos, no íconos específicos
- Enfócate en la estructura y organización
- Identifica patrones de diseño comunes

Responde en formato JSON válido:
{
    "components": ["lista", "de", "componentes", "identificados"],
    "layout": "descripción del sistema de layout (grid, flexbox, etc.)",
    "style": "descripción del estilo visual",
    "color_scheme": "esquema de colores dominante",
    "typography": "características tipográficas",
    "interactive_elements": ["lista", "de", "elementos", "interactivos"],
    "design_patterns": ["patrones", "de", "diseño", "identificados"],
    "analysis_text": "descripción detallada y completa para búsqueda RAG - incluye todos los detalles técnicos y estructurales que podrían ser útiles para encontrar ejemplos similares de código HTML/CSS"
}"""
    
    def _extract_components_from_text(self, text: str) -> list:
        """Extract UI components from text analysis when JSON parsing fails"""
        common_components = [
            "header", "navbar", "button", "form", "input", "card", "modal", 
            "sidebar", "footer", "menu", "dropdown", "table", "list", "grid",
            "container", "section", "article", "div", "span"
        ]
        
        found_components = []
        text_lower = text.lower()
        
        for component in common_components:
            if component in text_lower:
                found_components.append(component)
        
        return found_components if found_components else ["container", "content"]
    
    def save_analysis_result(self, analysis_result: Dict[str, Any], filename: str = None) -> str:
        """
        Save analysis result to temporary directory
        
        Args:
            analysis_result: Analysis result dictionary
            filename: Optional filename, auto-generated if not provided
            
        Returns:
            Path to saved file
        """
        try:
            # Ensure temp directory exists
            temp_dir = temp_images_dir()
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analysis_{timestamp}.json"
            
            # Save to file
            output_path = temp_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            
            return str(output_path)
            
        except Exception as e:
            raise ValueError(f"Failed to save analysis result: {str(e)}")