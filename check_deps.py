#!/usr/bin/env python3
"""
Dependency Checker for UI-to-Code System
Verifies all required packages are installed and working
"""

import sys
import importlib
from typing import List, Tuple

def check_dependency(package_name: str, import_name: str = None) -> Tuple[bool, str]:
    """
    Check if a dependency is installed and importable
    
    Args:
        package_name: Name of the package (for display)
        import_name: Actual import name (if different from package_name)
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if import_name is None:
        import_name = package_name.replace('-', '_')
    
    try:
        importlib.import_module(import_name)
        return True, f"✅ {package_name}"
    except ImportError as e:
        return False, f"❌ {package_name} - {str(e)}"

def main():
    """Check all dependencies for the UI-to-Code system"""
    print("🔍 UI-to-Code System Dependency Check")
    print("=" * 50)
    
    # Core dependencies with their import names
    dependencies = [
        # Core system
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("python-dotenv", "dotenv"),
        ("pyyaml", "yaml"),
        ("pyprojroot", "pyprojroot"),
        
        # Web interface
        ("streamlit", "streamlit"),
        
        # AI and RAG
        ("openai", "openai"),
        ("sentence-transformers", "sentence_transformers"),
        ("rank-bm25", "rank_bm25"),
        ("pinecone", "pinecone"),
        
        # Image processing
        ("opencv-python", "cv2"),
        ("pillow", "PIL"),
        ("beautifulsoup4", "bs4"),
        
        # Dataset and HTTP
        ("datasets", "datasets"),
        ("requests", "requests"),
        
        # Legacy PDF support
        ("pdfplumber", "pdfplumber"),
    ]
    
    print("\n📦 Core Dependencies:")
    failed = []
    
    for package_name, import_name in dependencies:
        success, message = check_dependency(package_name, import_name)
        print(f"  {message}")
        if not success:
            failed.append(package_name)
    
    # Check optional dependencies
    print("\n🔧 Optional Development Dependencies:")
    dev_dependencies = [
        ("pytest", "pytest"),
        ("black", "black"),
        ("flake8", "flake8"),
        ("isort", "isort"),
    ]
    
    for package_name, import_name in dev_dependencies:
        success, message = check_dependency(package_name, import_name)
        print(f"  {message}")
    
    # System summary
    print("\n" + "=" * 50)
    
    if not failed:
        print("🎉 All core dependencies are installed and working!")
        print("\n🚀 You're ready to run:")
        print("   python run_streamlit.py")
        print("   python quick_start.py")
        return 0
    else:
        print(f"⚠️  {len(failed)} dependencies are missing:")
        for dep in failed:
            print(f"   - {dep}")
        print("\n🔧 To install missing dependencies:")
        print("   pip install -r requirements.txt")
        print("   # or")
        print("   pip install -e .")
        return 1

if __name__ == "__main__":
    sys.exit(main())