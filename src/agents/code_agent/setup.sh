#!/bin/bash

ENV_FILE="src/.env"

if [ -f "$ENV_FILE" ]; then
    echo "Cargando variables de entorno desde $ENV_FILE..."
    set -a
    source "$ENV_FILE"
    set +a
else 
    echo "Advertencia: Archivo $ENV_FILE no encontrado. Continuando sin cargar variables."
fi

echo "Instalando dependencias con Poetry..."
poetry install

echo "Ejecutando la configuración post-instalación de Guardrails..."
poetry run guardrails hub install hub://guardrails/regex_match hub://guardrails/valid_json hub://guardrails/web_sanitization

echo "Configuración completa."