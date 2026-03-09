#!/bin/bash
# Script to verify Python interpreter is accessible
echo "Checking Python interpreter..."
echo "Interpreter path: /code/.venv/bin/python"
if [ -f "/code/.venv/bin/python" ]; then
    echo "✓ Python interpreter exists"
    /code/.venv/bin/python --version
    echo "✓ Python version check passed"
    /code/.venv/bin/python -c "import sys; print('Python executable:', sys.executable)"
    echo "✓ Python import test passed"
else
    echo "✗ Python interpreter not found at /code/.venv/bin/python"
    exit 1
fi
