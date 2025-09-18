# src/core/style_tokens.py
from __future__ import annotations
from typing import Dict, Set

def nearest_tailwind_name(hex_color: str) -> str:
    return "teal"

def tokens_to_tailwind_config(tokens: Dict) -> str:
    colors = tokens.get("colors", [])
    brand = nearest_tailwind_name(colors[0]) if colors else "teal"

    #  tokens["spacing_scale"] mapped
    spacing = {
        0:'0px', 2:'2px', 4:'4px', 6:'6px', 8:'8px', 12:'12px',
        16:'16px', 24:'24px', 32:'32px', 40:'40px', 48:'48px', 64:'64px'
    }
    spacing_str = ", ".join(f"{k}:'{v}'" for k,v in spacing.items())

    return f"""module.exports = {{
  content: ["./data/generated_code/**/*.html"],
  theme: {{
    extend: {{
      colors: {{
        brand: {{
          600: '#14b8a6',
          700: '#0d9488'
        }}
      }},
      fontFamily: {{ sans: ["Inter","ui-sans-serif","system-ui"] }},
      spacing: {{{spacing_str}}},
      borderRadius: {{ none:'0px', md:'6px', lg:'12px' }},
      boxShadow: {{ sm:'0 1px 2px rgba(0,0,0,0.05)', md:'0 4px 6px rgba(0,0,0,0.1)' }}
    }}
  }},
  plugins: [require("@tailwindcss/typography")]
}}"""

def inline_tailwind_config_js(tokens: Dict) -> str:
    return """<script>
        tailwind.config = {
            theme: {
            extend: {
                colors: { brand: { 600: '#14b8a6', 700: '#0d9488' } },
                fontFamily: { sans: ["Inter","ui-sans-serif","system-ui"] },
                spacing: {0:'0px',2:'2px',4:'4px',6:'6px',8:'8px',12:'12px',16:'16px',24:'24px',32:'32px',40:'40px',48:'48px',64:'64px'},
                borderRadius: {none:'0px', md:'6px', lg:'12px'},
                boxShadow: {sm:'0 1px 2px rgba(0,0,0,0.05)', md:'0 4px 6px rgba(0,0,0,0.1)'}
            }
            }
        }
        </script>"""

def build_allowed(tokens: Dict, retrieved_classes: Set[str]) -> Set[str]:
    base = {
      # layout
      "container","mx-auto","flex","grid","items-center","justify-between","justify-center",
      "w-full","h-full","max-w-7xl",
      # spacing
      "p-0","p-2","p-4","p-6","p-8","m-0","m-2","m-4","gap-2","gap-4","gap-6",
      # radius & shadows
      "rounded-none","rounded-md","rounded-lg","shadow-sm","shadow-md",
      # text
      "text-sm","text-base","text-lg","font-sans","font-semibold","font-bold",
      "text-gray-500","text-gray-600","text-gray-900",
      # bg & brand
      "bg-white","bg-gray-50","bg-gray-100","bg-brand-600","bg-brand-700",
      "text-white",
      # buttons utilitarias comunes
      "px-4","py-2","hover:bg-brand-700","hover:bg-blue-700"
    }
    # sumar las vistas en snippets (recorta la invención)
    base |= set([c for c in retrieved_classes if len(c) <= 40])
    return base
