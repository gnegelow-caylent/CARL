"""
CARL MCP Server

AWS security and compliance assistant for Claude Desktop.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="carl-mcp-server",
    version="0.1.0",
    author="Caylent",
    author_email="noreply@caylent.com",
    description="CARL AWS Security & Compliance MCP Server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gnegelow-caylent/CARL",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "mcp>=0.9.0",
        "boto3>=1.34.0",
        "botocore>=1.34.0",
        "aiofiles>=23.0.0",
    ],
    entry_points={
        "console_scripts": [
            "carl-mcp=carl_mcp_server.__main__:main",
        ],
    },
)
