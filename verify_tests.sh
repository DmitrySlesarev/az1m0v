#!/bin/bash
# Simple script to verify tests can run

set -e

echo "=========================================="
echo "Running pytest tests"
echo "=========================================="

# Run pytest with verbose output
poetry run pytest tests/ -v --tb=short

echo "=========================================="
echo "Tests completed"
echo "=========================================="

