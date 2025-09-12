#!/usr/bin/env python3
"""
Script to run the Streamlit RAG application
"""

import subprocess
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
from src.config import project_dir

def main():
    """Run the Streamlit app"""
    
    # Get the app path
    app_path = Path(__file__).parent / "app" / "streamlit_app.py"
    
    if not app_path.exists():
        print(f"Error: Streamlit app not found at {app_path}")
        sys.exit(1)
    
    # Load environment variables
    env_path = project_dir() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)

    streamlit_port = os.getenv("STREAMLIT_PORT", "8501")
    
    print("Starting Streamlit RAG application...")
    print(f"Access the app at: http://localhost:{streamlit_port}")
    print("Press Ctrl+C to stop the application")
    
    # Run streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.headless", "false",
            "--server.port", streamlit_port,
            "--server.address", "0.0.0.0"
        ])
    except KeyboardInterrupt:
        print("\nApplication stopped.")
    except Exception as e:
        print(f"Error running application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()