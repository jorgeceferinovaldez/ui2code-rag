#!/usr/bin/env python3
"""
Quick start script for UI-to-Code System
Sets up sample data and launches the application
"""

import sys
import subprocess
from pathlib import Path

def main():
    print("🎨 UI-to-Code Multi-Agent System - Quick Start")
    print("=" * 50)
    
    # Add src to path
    sys.path.append('src')
    
    try:
        # 1. Create directories
        print("📁 Creating directories...")
        from src.config import create_all_directories
        create_all_directories()
        
        # 2. Load sample HTML/CSS data
        print("📄 Loading sample HTML/CSS examples...")
        from src.rag.ingestion.websight_loader import load_websight_documents
        documents = load_websight_documents(max_examples=50)
        print(f"✅ Loaded {len(documents)} sample documents")
        
        # 3. Test system
        print("🔧 Testing system components...")
        
        try:
            from src.agents import VisualAgent, CodeRAGAgent
            
            # Test agents (expect API key warnings)
            visual_agent = VisualAgent()
            print("✅ Visual Agent ready")
            
            code_agent = CodeRAGAgent()
            status = code_agent.get_rag_status()
            
            if status['status'] == 'ready':
                print(f"✅ RAG system ready: {status['total_documents']} docs, {status['total_chunks']} chunks")
            else:
                print("⚠️  RAG system needs API keys for full functionality")
            
        except Exception as e:
            print(f"⚠️  Agent initialization requires API keys: {e}")
        
        # 4. Launch Streamlit
        print("\n🚀 Launching Streamlit application...")
        print("📍 Application will be available at: http://localhost:8501")
        print("💡 Go to 'UI to Code' page to start converting images to HTML/CSS")
        print("\nPress Ctrl+C to stop the application\n")
        
        # Run streamlit
        subprocess.run([sys.executable, "run_streamlit.py"])
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped. Thanks for using UI-to-Code System!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure you have installed dependencies: pip install -e .")
        print("2. Copy .env.example to .env and add your API keys")
        print("3. For OpenRouter: https://openrouter.ai/")
        print("4. For Pinecone: https://pinecone.io/")
        sys.exit(1)

if __name__ == "__main__":
    main()