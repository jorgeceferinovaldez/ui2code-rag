.PHONY: help install install-dev clean lint test format run-server build-index demo setup-dirs check-config check-deps ui-to-code-demo
.DEFAULT_GOAL := help

# Variables
PROJECT_NAME = ui-to-code-system
ifeq ($(OS),Windows_NT)
    PYTHON_INTERPRETER = py
else
    PYTHON_INTERPRETER = /opt/anaconda3/envs/uicode312/bin/python
endif
VENV_NAME = venv
PORT = 8501

WEBSIGHT_OFFSET = 0
WEBSIGHT_LENGTH = 1000
WEBSIGHT_STEPS=100

WEBSIGHT_LOADER_PATH = src/rag/ingestion/websight_loader.py
WEBSIGHT_MAX_EXAMPLES = 1000

## Display help information
help:
	@echo "UI-to-Code Multi-Agent System - Available Commands"
	@echo "=================================================="
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  quick-start       - Show complete setup guide"
	@echo "  install           - Install project dependencies"
	@echo "  check-deps        - Check if all dependencies are installed"
	@echo "  setup-dirs        - Create project directory structure"
	@echo "  run-server        - Run Streamlit UI-to-Code application"
	@echo ""
	@echo "🔧 Setup & Configuration:"
	@echo "  install-dev       - Install with development dependencies"
	@echo "  setup-venv        - Create virtual environment"
	@echo "  check-config      - Check configuration and paths"
	@echo ""
	@echo "🎨 UI-to-Code Features:"
	@echo "  ui-to-code-demo   - Run UI-to-Code system demo"
	@echo "  build-index       - Build HTML/CSS examples index"
	@echo ""
	@echo "🧪 Development:"
	@echo "  test              - Run tests"
	@echo "  lint              - Run code linting"
	@echo "  format            - Format code with black and isort"
	@echo "  clean             - Clean compiled files and cache"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  docs              - Generate documentation"
	@echo "  help              - Show this help"

## Install project dependencies
install:
	$(PYTHON_INTERPRETER) -m pip install --upgrade pip setuptools wheel
	$(PYTHON_INTERPRETER) -m pip install -e .

## Download a subset of the WebSight dataset for testing
download-websight:
	@echo "Descargando WebSight dataset en pasos de $(WEBSIGHT_STEPS) desde $(WEBSIGHT_OFFSET) hasta $(WEBSIGHT_LENGTH)..."
	mkdir -p data/websight
	@for step in $(shell seq $(WEBSIGHT_OFFSET) $(WEBSIGHT_STEPS) $(WEBSIGHT_LENGTH)); do \
		echo "Descargando offset $$step..."; \
		curl -X GET "https://datasets-server.huggingface.co/rows?dataset=HuggingFaceM4%2FWebSight&config=v0.2&split=train&offset=$$step&length=$(WEBSIGHT_STEPS)" -o data/websight/websight_$$step.json; \
		echo "Guardado en data/websight/websight_$$step.json"; \
	done

download-websight-win:
	@echo Descargando WebSight dataset (train, offset $(WEBSIGHT_OFFSET), length $(WEBSIGHT_LENGTH))...
	if not exist data\websight mkdir data\websight
	@for step in $(shell seq $(WEBSIGHT_OFFSET) $(WEBSIGHT_STEPS) $(WEBSIGHT_LENGTH)); do \
		echo "Descargando offset $$step..."; \
		curl -X GET "https://datasets-server.huggingface.co/rows?dataset=HuggingFaceM4%2FWebSight&config=v0.2&split=train&offset=$$step&length=$(WEBSIGHT_STEPS)" -o data/websight/websight_$$step.json; \
		echo "Guardado en data/websight/websight_$$step.json"; \
	done


## Install project with development dependencies
install-dev:
	$(PYTHON_INTERPRETER) -m pip install --upgrade pip setuptools wheel
	$(PYTHON_INTERPRETER) -m pip install -e ".[dev]"

## Create project directory structure
setup-dirs:
	@echo "Creating project directories..."
	$(PYTHON_INTERPRETER) -c "from src.config import create_all_directories; create_all_directories()"
	@echo "✅ Project directories created successfully"

## Check configuration and paths
check-config:
	@echo "Checking project configuration..."
	$(PYTHON_INTERPRETER) -c "from src.config import project_dir, corpus_dir, config; print(f'✅ Project root: {project_dir()}'); print(f'✅ Corpus dir: {corpus_dir()}'); print('✅ Configuration loaded successfully')"

run-visual-agent:
	@echo "Running Visual Agent..."
	$(PYTHON_INTERPRETER) -m src.agents.visual_agent.src.server.main

run-code-agent:
	@echo "Running Code Agent..."
	$(PYTHON_INTERPRETER) -m src.agents.code_agent.src.server.main

## Run Streamlit web app
run-server:
	@echo "Starting UI-to-Code Streamlit app on port $(PORT)..."
	$(PYTHON_INTERPRETER) -m streamlit run app/streamlit_app.py --server.port $(PORT) --server.address 0.0.0.0

## Build Pinecone vector index from HTML/CSS examples
build-html:
	@echo "Building Pinecone vector index for HTML/CSS examples..."
	$(PYTHON_INTERPRETER) $(WEBSIGHT_LOADER_PATH) --max-examples=$(WEBSIGHT_MAX_EXAMPLES)

## Run UI-to-Code demo  
ui-to-code-demo:
	@echo "Running UI-to-Code system demo..."
	$(PYTHON_INTERPRETER) -c "from quick_start import run_ui_to_code_demo; run_ui_to_code_demo()" || echo "Demo requires proper .env configuration with API keys"

## Check dependencies for UI-to-Code system
check-deps:
	@echo "Checking UI-to-Code system dependencies..."
	$(PYTHON_INTERPRETER) check_deps.py

## Run tests
test:
	@echo "Running tests..."
	$(PYTHON_INTERPRETER) -m pytest tests/ -v --tb=short || echo "No tests found in tests/ directory"

## Run code linting
lint:
	@echo "Running code linting..."
	-$(PYTHON_INTERPRETER) -m flake8 src/ app/ --max-line-length=100 --ignore=E203,W503 || echo "flake8 not installed"
	@echo "Linting completed"

## Format code with black and isort
format:
	@echo "Formatting code..."
	-$(PYTHON_INTERPRETER) -m black src/ app/ --line-length=100 || echo "black not installed"
	-$(PYTHON_INTERPRETER) -m isort src/ app/ --profile black --line-length=100 || echo "isort not installed"
	@echo "Code formatting completed"

## Clean compiled files and cache
clean:
	@echo "Cleaning compiled files and cache..."
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	rm -rf build/
	rm -rf dist/
	@echo "Cleanup completed"

## Create and setup virtual environment
setup-venv:
	@echo "Creating virtual environment..."
	$(PYTHON_INTERPRETER) -m venv $(VENV_NAME)
	@echo "Virtual environment created at ./$(VENV_NAME)"
	@echo "Activate with: source $(VENV_NAME)/bin/activate"
	@echo "Then run: make install"

## Generate documentation
docs:
	@echo "Generating documentation..."
	-$(PYTHON_INTERPRETER) -m sphinx-build -b html docs/ docs/_build/html || echo "Sphinx not configured"

## Development workflow - setup everything
dev-setup: setup-venv
	@echo "Setting up development environment..."
	@echo "Please run the following commands:"
	@echo "  source $(VENV_NAME)/bin/activate"
	@echo "  make install-dev"
	@echo "  make setup-dirs"
	@echo "  cp .env.example .env  # and edit with your API keys"
	@echo "  make check-config"

## Quick start for new users
quick-start:
	@echo "UI-to-Code Multi-Agent System Quick Start"
	@echo "========================================="
	@echo ""
	@echo "1. Setup virtual environment:"
	@echo "   make setup-venv"
	@echo "   source venv/bin/activate"
	@echo ""
	@echo "2. Install dependencies:"
	@echo "   make install"
	@echo ""
	@echo "3. Check dependencies:"
	@echo "   make check-deps"
	@echo ""
	@echo "4. Setup project directories:"
	@echo "   make setup-dirs"
	@echo ""
	@echo "5. Configure environment:"
	@echo "   cp .env.example .env"
	@echo "   # Edit .env with your OpenRouter/OpenAI API keys"
	@echo ""
	@echo "6. Start the visual and code agents in separate terminals:"
	@echo "   make run-visual-agent"
	@echo "   make run-code-agent"
	@echo ""
	@echo "7. Start the UI-to-Code system:"
	@echo "   make run-server"
	@echo ""
	@echo "Visit http://localhost:8501 for the UI-to-Code interface"
	@echo ""
	@echo "🎨 Features:"
	@echo "   - Upload UI images for analysis"
	@echo "   - Generate HTML/Tailwind CSS code"  
	@echo "   - Custom Spanish/English instructions"
	@echo "   - Visual AI + RAG pattern matching"

# Environment verification
verify-env:
	@echo "Verifying environment..."
	$(PYTHON_INTERPRETER) --version
	$(PYTHON_INTERPRETER) -c "import sys; print(f'Python executable: {sys.executable}')"
	@echo "Current directory: $(PWD)"
	@echo "Environment verification completed"


evaluate-retrieval:
	$(PYTHON_INTERPRETER) -m src.rag.evaluators.evaluate_retrieval --docs data/evaluate/docs_ui_code_en.jsonl --qrels data/evaluate/qrels_ui_code_en.csv --ks 3,5 --top_retrieve 10 --top_final 5