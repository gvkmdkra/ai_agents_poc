#!/usr/bin/env python3
"""
Script to run the Calling Agent server
"""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """Run the server"""
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    reload = os.getenv("DEBUG", "true").lower() == "true"

    print(f"Starting Calling Agent on {host}:{port}")
    print(f"Debug mode: {reload}")
    print("-" * 50)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if reload else "info"
    )


if __name__ == "__main__":
    main()
