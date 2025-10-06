SYSTEM_PROMPT = "You are an expert HTML/CSS developer specializing in modern, clean, artisanal web design."

GENERATION_PROMPT_TEMPLATE = """Basándote en este análisis visual:
- Componentes identificados: {components}
- Layout: {layout}
- Estilo: {style}
- Esquema de colores: {color_scheme}

Y estos ejemplos similares encontrados:
{pattern_context}
{custom_instructions}

Genera código HTML limpio y moderno con Tailwind CSS que implemente el diseño analizado.

ESTILO ARTESANAL - INSTRUCCIONES ESPECÍFICAS:
- EVITAR completamente íconos de librerías externas (FontAwesome, Heroicons, etc.)
- NO usar símbolos Unicode decorativos (→, ★, ✓, etc.)
- EVITAR gradientes muy llamativos y efectos "AI-looking"
- PREFERIR elementos geométricos simples creados con CSS/Tailwind
- USAR texto descriptivo plano en lugar de íconos
- MANTENER diseño limpio y profesional
- APLICAR principios de tipografía como elemento de diseño

REQUISITOS TÉCNICOS:
- Solo HTML y clases Tailwind CSS
- Sin JavaScript
- Responsive design (mobile-first)
- Estructura semántica correcta
- Accesibilidad básica (alt texts, labels apropiados)

ESTRUCTURA ESPERADA:
- DOCTYPE html completo
- Head con meta tags apropiados
- CDN de Tailwind CSS incluido
- Estructura de body organizada

IMPORTANTE: Si el usuario proporcionó instrucciones adicionales, asegúrate de incorporarlas en el código generado.

Responde SOLO con el código HTML, sin explicaciones adicionales.
"""
