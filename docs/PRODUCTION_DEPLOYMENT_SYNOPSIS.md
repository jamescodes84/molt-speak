# Production Deployment Synopsis

A reference guide for deploying FastAPI applications to production, based on the patterns established in this codebase.

---

## Project Structure

```
project/
├── main.py                    # FastAPI entrypoint
├── src/
│   ├── models/models.py       # Pydantic request/response models
│   ├── services/              # Business logic
│   ├── agent/                 # Agent orchestration (if applicable)
│   └── utils/                 # Shared utilities
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyrightconfig.json
└── pytest.ini
```

---

## 1. FastAPI Patterns

### Lifespan for Resource Management

Use the `lifespan` context manager to initialize expensive resources once at startup (not per-request):

```python
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# Global instances (initialized at startup)
rag_engine: RAGEngine | None = None
aws_provider: AWSClientProvider | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_engine, aws_provider

    # Validate required env vars at startup (fail fast)
    OPENSEARCH_ENDPOINT = os.getenv('OPENSEARCH_ENDPOINT_KEY')
    if not OPENSEARCH_ENDPOINT:
        raise ValueError("OPENSEARCH_ENDPOINT_KEY environment variable is not set")

    # Initialize expensive resources ONCE
    aws_provider = AWSClientProvider()
    rag_engine = RAGEngine(
        opensearch_client=aws_provider.create_opensearch_client(OPENSEARCH_ENDPOINT),
        bedrock_client=aws_provider.get_bedrock_client(),
        dynamodb_resource=aws_provider.get_dynamodb_resource(),
    )

    logger.info("Application initialized")
    yield
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)
```

### Error Handling Pattern

Catch specific exceptions and map them to appropriate HTTP status codes:

```python
@app.post('/generate-narrative')
async def generate_narrative(input_data: NarrativeRequest) -> NarrativeResponse:
    try:
        if rag_engine is None:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # ... business logic ...
        return response

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
```

### Health Check Endpoint

```python
@app.get("/health", include_in_schema=False)  # Hidden from OpenAPI docs
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=[ServiceStatus(service_name="api", status="healthy", message="API is running")],
    )
```

---

## 2. Pydantic Models

### Request/Response Models with Validation

```python
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

class NarrativeRequest(BaseModel):
    """Request model with field validation."""

    assessment_name: str = Field(
        ...,  # Required
        description="Assessment name (e.g., 'PAI')",
        min_length=1
    )
    assessment_id: str = Field(
        ...,
        description="Unique identifier for the assessment",
        min_length=1
    )
    scores: Dict[str, float] = Field(
        ...,
        description="Dictionary of score codes to numerical values"
    )

    @field_validator('scores')
    @classmethod
    def validate_scores(cls, v):
        if not v:
            raise ValueError("Scores cannot be empty")
        for code, value in v.items():
            if not 0 <= value <= 150:
                raise ValueError(f"Score {code}={value} out of valid range (0-150)")
        return v


class NarrativeResponse(BaseModel):
    """Response model."""
    model_config = ConfigDict(frozen=False)

    assessment_id: str
    assessment_name: str
    narrative: str
    scores_included: List[str]
    generation_timestamp: str


class ServiceStatus(BaseModel):
    """Health status of a service."""
    model_config = ConfigDict(frozen=False)

    service_name: str
    status: str
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    model_config = ConfigDict(frozen=False)

    status: str
    timestamp: str
    services: List[ServiceStatus]
```

**Key Patterns:**
- `Field(...)` for required fields with descriptions and constraints
- `@field_validator` for custom validation logic
- `ConfigDict` for model behavior configuration
- Full type annotations (`Dict[str, float]`, `List[str]`, `Optional[str]`)

---

## 3. Dockerfile

```dockerfile
# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1    # Prevent .pyc files
ENV PYTHONUNBUFFERED=1           # Real-time log output
ENV PYTHONPATH=/app:$PYTHONPATH  # Python import paths

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies (layer caching - deps change less often than code)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user (security)
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key Patterns:**
- `python:3.11-slim` - Minimal base image
- Layer caching - Copy `requirements.txt` before code
- Non-root user - Security hardening
- Built-in health check - Container orchestration support
- `--no-cache-dir` - Smaller image size

---

## 4. docker-compose.yml

```yaml
version: '3.8'

services:
  rag-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rag-assessment-api
    ports:
      - "8000:8000"

    environment:
      # AWS credentials (loaded from .env file)
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
      - OPENSEARCH_ENDPOINT_KEY=${OPENSEARCH_ENDPOINT_KEY}
    env_file:
      - .env
    networks:
      - app-network
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"    # Log rotation - max 10MB per file
        max-file: "3"      # Keep 3 log files

networks:
  app-network:
    driver: bridge
```

**Key Patterns:**
- `env_file: .env` - Load secrets from file (not committed to git)
- `restart: unless-stopped` - Auto-restart on failure
- Log rotation - Prevent disk fill
- Isolated network bridge

---

## 5. requirements.txt

```txt
# Core Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0

# AWS Services
boto3>=1.28.0
requests-aws4auth>=1.2.4

# Search & Vector Database
opensearch-py>=2.3.0

# Environment & Configuration
python-dotenv>=1.0.0

# Async File I/O
aiofiles>=23.0.0

# Testing & Coverage
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
httpx>=0.25.0

# Standard Library (documentation only)
# asyncio, concurrent.futures, json, os, sys, time, re, random, typing, datetime
```

**Key Patterns:**
- Minimum version pinning (`>=`) - Allows compatible updates
- Grouped by purpose with comments
- Test dependencies included (or separate into `requirements-dev.txt` for production)

---

## 6. pyrightconfig.json

```json
{
  "typeCheckingMode": "basic",
  "include": ["."],
  "exclude": ["venv", "build", "dist"],
  "reportMissingImports": true
}
```

**Modes:**
- `off` - No type checking
- `basic` - Reasonable strictness (recommended for most projects)
- `standard` - Stricter checking
- `strict` - Full type safety enforcement

---

## 7. pytest.ini

```ini
[pytest]
# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# CLI options
addopts =
    -v
    --strict-markers
    --tb=short
    --disable-warnings
    --color=yes

# Async support (pytest-asyncio)
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

# Test categorization markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    asyncio: Async tests

# Coverage configuration
[coverage:run]
source = src
omit =
    */tests/*
    */test_*
    */__pycache__/*
    */site-packages/*
    */venv/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False

[coverage:html]
directory = htmlcov
```

**Usage:**
```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run with coverage
pytest --cov=src --cov-report=html
```

---

## 8. Environment Variables

### Loading Pattern

```python
from dotenv import load_dotenv
import os

# Load once at module level
load_dotenv()

# Access with defaults for optional vars
MAX_TOKENS = int(os.getenv('MAX_TOKENS', '4096'))
TOP_K_RESULTS = int(os.getenv('TOP_K_RESULTS', '30'))
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4-5')
```

### Validation Pattern

Validate required vars at startup (fail fast):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail immediately if required vars are missing
    required_vars = ['OPENSEARCH_ENDPOINT_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"{var} environment variable is not set")

    # ... rest of initialization
    yield
```

### Example .env File

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# Service Endpoints
OPENSEARCH_ENDPOINT_KEY=your-opensearch-endpoint

# Model Configuration
LLM_MODEL=claude-sonnet-4-5
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
MAX_TOKENS=4096
TOP_K_RESULTS=30

# Performance Tuning
MAX_CONCURRENT_LLM_CALLS=5
MAX_WORKERS=10
```

---

## Quick Reference

| Area | Pattern |
|------|---------|
| **Startup** | `lifespan` context manager for init/cleanup |
| **Validation** | Pydantic models with `Field()` and `@field_validator` |
| **Errors** | Catch specific exceptions, map to HTTP status codes |
| **Docker** | Slim image, non-root user, layer caching, health check |
| **Compose** | `restart: unless-stopped`, log rotation, `env_file` |
| **Dependencies** | `>=` pinning, grouped by purpose |
| **Types** | `pyrightconfig.json` with `basic` mode |
| **Tests** | `asyncio_mode = auto`, markers for categorization |
| **Env Vars** | Load once at module level, validate required at startup |

---

## Checklist for New Projects

- [ ] Create `src/` directory structure with `models/`, `services/`, `utils/`
- [ ] Set up `main.py` with lifespan context manager
- [ ] Define Pydantic models for all request/response types
- [ ] Add `/health` endpoint
- [ ] Create `Dockerfile` with non-root user and health check
- [ ] Create `docker-compose.yml` with log rotation and restart policy
- [ ] Set up `requirements.txt` with version pinning
- [ ] Configure `pyrightconfig.json` for type checking
- [ ] Configure `pytest.ini` with async support and markers
- [ ] Create `.env.example` documenting required variables
- [ ] Add `.env` to `.gitignore`
