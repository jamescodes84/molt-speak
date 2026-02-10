.PHONY: help install test lint run clean format

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-15s %s\n", $$1, $$2}'

install:  ## Install dependencies
	./scripts/quick_install.sh

run:  ## Run ultra-fast mode
	./scripts/run.sh

test:  ## Run tests with coverage
	pytest tests/ -v --cov=openclaw-ears/openclaw_ears --cov-report=term-missing

lint:  ## Run linters
	ruff check openclaw-ears/openclaw_ears/ *.py || true
	mypy openclaw-ears/openclaw_ears/ || true

format:  ## Format code
	black openclaw-ears/openclaw_ears/ *.py || true
	ruff check --fix openclaw-ears/openclaw_ears/ *.py || true

clean:  ## Clean generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage .pytest_cache || true
	rm -rf build dist *.egg-info || true

benchmark:  ## Run performance benchmark
	python3 scripts/benchmark_performance.py

demo:  ## Run complete pipeline demo
	python3 scripts/demo_complete_pipeline.py
