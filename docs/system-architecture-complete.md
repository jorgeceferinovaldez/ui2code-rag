# 📊 Arquitectura Completa del Sistema UI-to-Code Multi-Agente

## 🎯 Visión General del Sistema

El sistema **UI-to-Code** es una plataforma compleja de múltiples agentes que convierte diseños de interfaz de usuario (capturas de pantalla, wireframes, mockups) en código HTML/CSS funcional utilizando inteligencia artificial avanzada y tecnología RAG (Retrieval-Augmented Generation). La arquitectura está diseñada siguiendo principios de microservicios, donde cada componente tiene responsabilidades específicas y se comunica a través de APIs bien definidas.

## 🏗️ Arquitectura de Componentes Principales

### 1. **Capa de Interfaz de Usuario**
- **Streamlit Interface** (`app/streamlit_app.py`): Interfaz web principal para usuarios finales
- **FastAPI Interface** (`src/interfaces/fastapi_app/`): API REST para integración con otros sistemas
- **Punto de Entrada**: `run_streamlit.py` y `quick_start.py` para inicialización rápida

### 2. **Agente Orquestador Central** 
El [`OrchestratorAgent`](src/agents/orchestator_agent/orchestator_agent.py) actúa como el **cerebro coordinador** del sistema:

#### Responsabilidades:
- **Coordinación de Flujo**: Gestiona la comunicación entre todos los agentes especializados
- **Gestión de Estado**: Mantiene el estado de la conversación y el contexto entre llamadas
- **Manejo de Errores**: Implementa lógica de reintento y fallback para garantizar robustez
- **Validación de Respuestas**: Verifica la integridad de las respuestas de cada agente

#### Protocolo de Comunicación:
```python
# Flujo típico del Orchestrator
1. Recibe imagen del usuario
2. Envía imagen → Visual Agent (análisis)
3. Envía análisis → RAG Agent (búsqueda de patrones)
4. Envía análisis + patrones → Code Agent (generación)
5. Retorna código final al usuario
```

### 3. **Agentes Especializados**

#### 👁️ **Visual Agent** (`src/agents/visual_agent/`)
- **Puerto**: 10000
- **Función**: Análisis de imágenes UI utilizando modelos de visión por computadora
- **Tecnologías**: GPT-4 Vision, Claude Vision, modelos multimodales
- **Salida**: Descripción estructurada de elementos UI, layouts, colores, tipografías

#### ⚙️ **Code Agent** (`src/agents/code_agent/`)
- **Puerto**: 10001  
- **Función**: Generación de código HTML/CSS basado en análisis visual y patrones RAG
- **Tecnologías**: LLMs especializados en código (GPT-4, Claude, CodeLlama)
- **Salida**: Código HTML/CSS con Tailwind CSS funcional y responsive

#### 🧠 **RAG Agent** (`src/agents/rag_agent/`)
- **Función**: Búsqueda semántica de patrones de código relevantes
- **Capacidades**: 
  - Búsqueda por similitud semántica
  - Recuperación de ejemplos de código relevantes
  - Ranking y filtrado de resultados

## 🔄 Sistema RAG (Retrieval-Augmented Generation)

### Componentes del Pipeline RAG:

#### 📊 **RAG Pipeline** (`src/rag/core/`)
- **Coordinación**: Orquesta todo el proceso de recuperación y generación
- **Optimización**: Gestiona caché y optimizaciones de rendimiento
- **Métricas**: Recopila estadísticas de uso y efectividad

#### 🔍 **Retrievers** (`src/rag/retrievers/`)
- **Semantic Retriever**: Búsqueda basada en embeddings vectoriales
- **Keyword Retriever**: Búsqueda tradicional basada en palabras clave
- **Hybrid Retriever**: Combina múltiples estrategias de búsqueda

#### 📈 **Evaluators** (`src/rag/evaluators/`)
- **Relevance Scoring**: Evalúa la relevancia de los resultados recuperados
- **Quality Assessment**: Mide la calidad de las respuestas generadas
- **Performance Metrics**: Latencia, throughput, accuracy

#### 📥 **Ingestion** (`src/rag/ingestion/`)
- **Document Processing**: Procesa y prepara documentos para indexación
- **Websight Loader**: Carga datos del dataset Websight para entrenamiento
- **Chunking Strategy**: Divide documentos en chunks óptimos para recuperación

## 🗄️ Capa de Almacenamiento

### **Pinecone Vector Database**
- **Propósito**: Base de datos vectorial en la nube para búsquedas semánticas
- **Escalabilidad**: Maneja millones de embeddings con latencia baja
- **Namespace**: Organización por dominios (`html-css-examples`)

### **ChromaDB** (`src/vectorstore/chroma/`)
- **Propósito**: Base de datos vectorial local para desarrollo y testing
- **Ventajas**: Sin dependencias externas, fácil setup
- **Uso**: Fallback cuando Pinecone no está disponible

### **Almacenamiento de Datos**
- **UI Examples** (`ui_examples/`): Patrones de código HTML/CSS curados
- **Websight Data** (`data/websight/`): Dataset de entrenamiento de interfaces
- **Generated Code** (`data/generated_code/`): Historial de código generado

## 🤖 Integración con LLMs

### **OpenRouter Provider** (`src/runtime/providers/`)
- **Abstracción**: Interfaz unificada para múltiples proveedores de LLM
- **Modelos Soportados**: GPT-4, Claude-3, Gemini, LLaMA, Mistral
- **Balanceador**: Distribuye carga entre diferentes modelos según disponibilidad

### **Estrategia Multi-Modelo**
```python
# Configuración típica de modelos
Visual_Analysis: GPT-4V, Claude-3-Vision
Code_Generation: GPT-4-Turbo, Claude-3-Sonnet  
RAG_Embeddings: sentence-transformers/all-MiniLM-L6-v2
```

## ⚡ Runtime y Adaptadores

### **Runtime System** (`src/runtime/`)
- **Adapters**: Conectores para servicios externos (Pinecone, OpenAI, etc.)
- **Pipelines**: Flujos de procesamiento reutilizables
- **Providers**: Abstracción de servicios de terceros

### **Tools System** (`src/tools/`)
- **Builtin Tools**: Herramientas nativas del sistema
- **External Tools**: Integraciones con herramientas externas
- **Plugin Architecture**: Sistema extensible de plugins

## 🔧 Configuración y Gestión

### **Sistema de Configuración** (`src/config.py` + `config.yaml`)
```yaml
# Estructura de configuración
agents_endpoints:
  visual_agent_url: "http://localhost:10000"
  code_agent_url: "http://localhost:10001"

ui_to_code:
  ui_examples_dir: "ui_examples"
  temp_images_dir: "data/temp_images"
  generated_code_dir: "data/generated_code"
```

### **Gestión Dinámica de Rutas**
- **pyprojroot**: Detección automática de la raíz del proyecto
- **Configuración YAML**: Centralización de todas las rutas y configuraciones
- **Validación**: Verificación automática de existencia de directorios

## 🌊 Flujo de Datos Completo

### **Flujo Principal Usuario → Código**

1. **Entrada del Usuario**:
   ```
   Usuario carga imagen → Streamlit Interface
   ```

2. **Orquestación**:
   ```
   Streamlit → OrchestratorAgent (coordinación central)
   ```

3. **Análisis Visual**:
   ```
   OrchestratorAgent → Visual Agent
   Imagen (base64) → GPT-4V → Análisis estructurado
   ```

4. **Recuperación RAG**:
   ```
   Análisis → RAG Agent → RAG Pipeline
   Consulta semántica → Pinecone/ChromaDB → Patrones relevantes
   ```

5. **Generación de Código**:
   ```
   Análisis + Patrones → Code Agent
   LLM Generation → HTML/CSS con Tailwind
   ```

6. **Entrega al Usuario**:
   ```
   Código generado → OrchestratorAgent → Streamlit → Usuario
   ```

### **Flujos de Datos Secundarios**

#### **Ingesta de Conocimiento**:
```
UI Examples + Websight → Ingestion Pipeline
→ Document Processing → Vectorization 
→ Pinecone/ChromaDB Storage
```

#### **Evaluación y Mejora**:
```
Generated Code → Quality Evaluators
→ Metrics Collection → Performance Analytics
→ Model Fine-tuning
```

## 🔐 Seguridad y Robustez

### **Manejo de Errores**
- **Graceful Degradation**: El sistema funciona con capacidades reducidas si fallan componentes
- **Circuit Breakers**: Prevención de cascadas de fallos
- **Timeout Management**: Gestión de timeouts configurables por servicio

### **Validación de Datos**
- **Schema Validation**: Validación estricta de estructuras de respuesta
- **Content Filtering**: Filtros de seguridad para contenido generado
- **Input Sanitization**: Limpieza de entradas de usuario

### **Monitoreo y Logging**
```python
# Sistema de logging estructurado
loguru.logger → Archivos rotatorios
Métricas de rendimiento → Analytics dashboard
Error tracking → Alertas automáticas
```

## 🚀 Escalabilidad y Deployment

### **Arquitectura de Microservicios**
- **Independencia**: Cada agente puede escalarse independientemente
- **Load Balancing**: Distribución de carga entre instancias
- **Service Discovery**: Descubrimiento automático de servicios

### **Containerización**
```dockerfile
# Cada agente puede ejecutarse en su propio contenedor
Visual Agent → Docker container (puerto 10000)
Code Agent → Docker container (puerto 10001)
RAG Agent → Embebido o containerizado
```

### **Deployment Options**
- **Local Development**: Todos los componentes en una máquina
- **Distributed**: Agentes en diferentes servidores
- **Cloud Native**: Kubernetes, Docker Swarm, servicios gestionados

## 📈 Métricas y Optimización

### **KPIs del Sistema**
- **Latencia**: Tiempo total de UI → Código
- **Accuracy**: Calidad del código generado
- **User Satisfaction**: Feedback de usuarios
- **System Reliability**: Uptime y disponibilidad

### **Optimizaciones Implementadas**
- **Caching**: Caché de análisis visuales y búsquedas RAG
- **Batching**: Procesamiento en lotes cuando es posible
- **Model Selection**: Selección dinámica del modelo óptimo por tarea
- **Resource Pooling**: Reutilización de conexiones y recursos

## 🔄 Extensibilidad y Mantenimiento

### **Plugin Architecture**
- **Agent Plugins**: Nuevos agentes especializados pueden agregarse fácilmente
- **Tool Extensions**: Sistema extensible de herramientas
- **Provider Integrations**: Nuevos proveedores de LLM/servicios

### **Testing Strategy**
```python
# Estrategia de testing multicapa
Unit Tests → Componentes individuales
Integration Tests → Comunicación entre agentes  
End-to-End Tests → Flujo completo usuario → código
Performance Tests → Benchmarks de rendimiento
```

### **Continuous Integration**
- **Automated Testing**: Tests automáticos en cada commit
- **Quality Gates**: Verificación de calidad de código
- **Deployment Pipelines**: Despliegue automatizado por ambientes

---

Esta arquitectura representa un sistema robusto, escalable y mantenible que aprovecha las mejores prácticas de ingeniería de software moderna, inteligencia artificial distribuida y sistemas de recuperación de información avanzados para resolver el complejo problema de convertir diseños UI en código funcional.