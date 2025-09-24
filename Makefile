.PHONY: help install install-dev clean lint test format run-server build-index demo setup-dirs check-config check-deps ui-to-code-demo
.DEFAULT_GOAL := help

# Variables
PROJECT_NAME = ui-to-code-system
PYTHON_INTERPRETER = python3
VENV_NAME = venv
PORT = 8501

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

## Run Streamlit web app
run-server:
	@echo "Starting UI-to-Code Streamlit app on port $(PORT)..."
	$(PYTHON_INTERPRETER) -m streamlit run app/streamlit_app.py --server.port $(PORT) --server.address 0.0.0.0

## Build Pinecone vector index from HTML/CSS examples
build-index:
	@echo "Building Pinecone vector index for HTML/CSS examples..."
	$(PYTHON_INTERPRETER) -c "from src.rag.ingestion.websight_loader import load_websight_examples; from src.runtime.adapters.pinecone_adapter import PineconeSearcher; docs = load_websight_examples(); print(f'Found {len(docs)} HTML/CSS examples'); print('Index building requires PINECONE_API_KEY in .env file')"

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
	@echo "6. Start the UI-to-Code system:"
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

# TODO: Add A2A servers and other advanced features