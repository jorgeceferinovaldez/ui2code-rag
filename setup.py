"""
Setup script for UI-to-Code Multi-Agent System
Convert UI designs to HTML/Tailwind CSS using Visual AI and RAG technology
"""

from setuptools import find_packages, setup
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith('#') and not line.startswith('-')
        ]
else:
    requirements = [
        # Core system
        "numpy>=1.24.0",
        "pandas>=2.0.0", 
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.0",
        "pyprojroot>=0.3.0",
        
        # Web interface
        "streamlit>=1.28.0",
        
        # AI and RAG
        "openai>=1.0.0",
        "sentence-transformers>=2.2.0",
        "rank-bm25>=0.2.2",
        "pinecone>=3.0.0",
        
        # Image processing for UI-to-Code
        "opencv-python>=4.8.0",
        "pillow>=10.1.0",
        "beautifulsoup4>=4.12.0",
        
        # Dataset and HTTP
        "datasets>=2.14.0",
        "requests>=2.31.0",
        
        # Legacy PDF support
        "pdfplumber>=0.11.0",
    ]

setup(
    name='ui-to-code-system',
    version='1.0.0',
    description='Multi-Agent UI-to-Code System: Convert UI designs to HTML/Tailwind CSS using Visual AI and RAG technology',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='UI-to-Code Development Team',
    author_email='dev@uitocode.com',
    url='https://github.com/your-org/ui-to-code-system',
    license='MIT',
    packages=find_packages(where="."),
    package_dir={"": "."},
    include_package_data=True,
    package_data={
        'src': ['config.yaml'],
        'app': ['models/openai-model/config.json'],
        '': ['*.yaml', '*.yml', '*.json', '*.md']
    },
    python_requires='>=3.8',
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.0.0',
            'black>=23.0.0',
            'flake8>=6.0.0',
            'isort>=5.12.0',
            'mypy>=1.0.0',
            'jupyter>=1.0.0',
        ],
        'performance': [
            'torch>=2.0.0',          # GPU acceleration
            'transformers>=4.30.0',  # Local models
        ],
        'docs': [
            'sphinx>=4.0.0',
            'sphinx-rtd-theme>=1.0.0',
            'myst-parser>=0.18.0',
        ]
    },
    entry_points={
        'console_scripts': [
            'ui-to-code=run_streamlit:main',
            'quick-start=quick_start:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Multimedia :: Graphics',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Text Processing :: Markup :: HTML',
    ],
    keywords='ui-to-code html css tailwind visual-ai computer-vision rag multi-agent streamlit openrouter code-generation',
    project_urls={
        'Bug Reports': 'https://github.com/your-org/ui-to-code-system/issues',
        'Source': 'https://github.com/your-org/ui-to-code-system',
        'Documentation': 'https://ui-to-code-system.readthedocs.io/',
    },
)