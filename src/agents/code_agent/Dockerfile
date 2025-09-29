FROM python:3.11-slim

SHELL ["/bin/bash", "-c"]

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Expose port (adjust if needed)
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.agents.code_agent"]