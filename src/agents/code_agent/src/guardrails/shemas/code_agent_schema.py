OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "html_code": {"type": "string"},
        "generation_metadata": {
            "type": "object",
            "properties": {
                "model_used": {"type": "string"},
                "patterns_used": {"type": "integer"},
                "visual_components": {"type": "array", "items": {"type": "string"}},
                "custom_instructions": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
            },
            "required": ["model_used", "patterns_used", "visual_components", "custom_instructions", "timestamp"],
        },
        "visual_analysis_summary": {
            "type": "object",
            "properties": {
                "components": {"type": "array", "items": {"type": "string"}},
                "layout": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["components", "layout", "style"],
        },
    },
    "required": ["html_code", "generation_metadata", "visual_analysis_summary"],
}
