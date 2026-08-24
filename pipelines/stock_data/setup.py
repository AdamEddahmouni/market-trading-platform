"""
Market Data Pipeline - Setup Script
Install with: pip install -e .
"""

from setuptools import setup, find_packages

setup(
    name="market-data-pipeline",
    version="2.0.0",
    description="Stealth web scraper suite for financial market data",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Market Data Pipeline",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=[
        "yfinance>=0.2.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "requests>=2.28.0",
        "sqlalchemy>=2.0.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "pyarrow>=12.0.0",
    ],
    extras_require={
        "stealth": ["curl_cffi>=0.7.0"],
        "full": [
            "curl_cffi>=0.7.0",
            "matplotlib>=3.7.0",
            "jupyter>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stock-data=scripts.run:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
