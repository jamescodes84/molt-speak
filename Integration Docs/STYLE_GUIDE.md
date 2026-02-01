# Production-Ready Python Style Guide

This style guide documents patterns and conventions for transforming prototype codebases into production-ready systems. 
Based on a RAG (Retrieval-Augmented Generation) system deployed to AWS.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Code Style & Syntax](#2-code-style--syntax)
3. [Parallelization Patterns](#3-parallelization-patterns)
4. [Demonolithed Architecture](#4-demonolithed-architecture)
5. [Error Handling & Resilience](#5-error-handling--resilience)
6. [Configuration Management](#6-configuration-management)
7. [Logging Best Practices](#7-logging-best-practices)
8. [Testing Patterns](#8-testing-patterns)
9. [Code Smells & Anti-Patterns to Avoid](#9-code-smells--anti-patterns-to-avoid)
10. [Deployment Readiness](#10-deployment-readiness)

---

## 1. Project Structure

### Layered Architecture

> **Note:** The directory structure below is an example, not a prescriptive rule. Adapt it to fit your project's needs and existing conventions. The key principles are separation of concerns and unidirectional dependency flow—how you organize the folders is flexible.

Organize code in clear layers with unidirectional dependency flow:

```
/project
├── main.py                      # Application entry point (thin layer)
├── src/
│   ├── __init__.py
│   ├── models/                  # Pydantic data models (request/response)
│   │   └── models.py
│   ├── services/                # Business logic & external integrations
│   │   ├── core_engine.py       # Primary business logic
│   │   └── clients.py           # External client factories
│   ├── agent/                   # Domain-specific logic (if applicable)
│   │   └── agent.py
│   ├── utils/                   # Cross-cutting utilities
│   │   ├── __init__.py
│   │   ├── logging_utils.py
│   │   └── text_utils.py
│   ├── assets/                  # Static data, templates, queries
│   │   └── queries.py
│   └── data/                    # Runtime data storage
├── tests/
│   ├── unit/                    # Isolated unit tests
│   └── integration/             # Full system tests
├── pyproject.toml               # Modern Python project config
├── pytest.ini                   # Test configuration
├── requirements.txt             # Dependencies
├── Dockerfile                   # Container configuration
├── Makefile                     # Development commands
└── .env.example                 # Environment variable template
```

### Dependency Flow

```
models → services → API handlers
          ↓
        utils (cross-cutting)
```

**Guideline**: Lower layers should not import from higher layers. Services don't know about HTTP; models don't know about services.

---

## 2. Code Style & Syntax

### Naming Conventions

| Element              | Convention        | Example                              |
|----------------------|-------------------|--------------------------------------|
| Classes              | PascalCase        | `RAGEngine`, `AWSClientProvider`     |
| Functions            | snake_case        | `generate_narrative`, `invoke_model` |
| Constants            | UPPER_SNAKE_CASE  | `MAX_TOKENS`, `DEFAULT_TIMEOUT`      |
| Private functions    | _prefix           | `_build_prompt`, `_call_llm`         |
| Environment vars     | UPPER_SNAKE_CASE  | `AWS_REGION`, `MAX_WORKERS`          |

### Type Annotations

Use comprehensive type hints throughout. Modern Python 3.10+ syntax preferred:

```python
# GOOD: Modern union syntax
def create_client(region_name: str | None = None) -> Any:
    ...

# GOOD: Generic types
async def retrieve_context(query: str, top_k: int = 30) -> List[Dict]:
    ...

# GOOD: Optional with defaults
async def invoke_model(
    client: Any,
    model_id: str,
    prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    semaphore: Optional[asyncio.Semaphore] = None
) -> tuple[str, bool]:
    ...
```

### Docstrings

Use Google/NumPy style with Args, Returns, and Raises:

```python
def invoke_model(client, model_id: str, prompt: str, max_tokens: int) -> tuple[str, bool]:
    """
    Invoke an LLM model with configurable parameters.

    Args:
        client: Boto3 client for model invocation
        model_id: The model identifier to invoke
        prompt: Input prompt for the model
        max_tokens: Maximum tokens for response

    Returns:
        tuple: (response_text, is_complete)
            - response_text: The generated text response
            - is_complete: True if response was not truncated

    Raises:
        RuntimeError: If model invocation fails after retries
    """
```

### Import Organization

Follow PEP 8 ordering: standard library → third-party → local:

```python
# Standard library
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

# Third-party
import aiofiles
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

# Local imports
from ..models.models import NarrativeRequest
from ..utils.logging_utils import log_thought
```

### Module-Level Logger

Always create a module-level logger:

```python
logger = logging.getLogger(__name__)
```

---

## 3. Parallelization Patterns

### Async/Await Foundation

Use `asyncio.gather()` for concurrent operations:

```python
async def process_all_items(items: List[Dict]) -> List[Dict]:
    """Process multiple items concurrently."""
    tasks = [
        process_single_item(item)
        for item in items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Semaphore-Based Rate Limiting

Control concurrent access to rate-limited resources:

```python
class ServiceEngine:
    def __init__(self):
        # Limit concurrent LLM calls to prevent throttling
        self.llm_semaphore = asyncio.Semaphore(
            int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))
        )

    async def call_llm(self, prompt: str) -> str:
        async with self.llm_semaphore:
            # Only N concurrent calls allowed
            return await self._invoke_model(prompt)
```

### ThreadPoolExecutor for Blocking I/O

Prevent blocking the event loop with synchronous operations:

```python
async def invoke_blocking_client(client, request_body: str) -> dict:
    """Wrap synchronous client call in executor."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,  # Use default ThreadPoolExecutor
        lambda: client.invoke(body=request_body)
    )
    return response
```

### Error Collection in Parallel Operations

Use `return_exceptions=True` to collect errors without halting:

```python
async def process_batch(items: List[Dict]) -> Dict[str, Any]:
    """Process batch with error aggregation."""
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append(f"Item {i}: {result}")
        else:
            successes.append(result)

    if errors:
        logger.error(f"Batch had {len(errors)} failures:\n" + "\n".join(errors))

    return {"successes": successes, "errors": errors}
```

### Configuration for Parallelization

Make parallelization configurable via environment:

```python
# At module level
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))
BATCH_MAX_WORKERS = int(os.getenv("BATCH_MAX_WORKERS", "10"))
PROCESSING_MAX_WORKERS = int(os.getenv("PROCESSING_MAX_WORKERS", "10"))
```

---

## 4. Demonolithed Architecture

### Dependency Injection

Inject dependencies rather than using global singletons:

```python
# BAD: Global singleton
class RAGEngine:
    def __init__(self):
        self.client = boto3.client('bedrock-runtime')  # Hardcoded

# GOOD: Dependency injection
class RAGEngine:
    def __init__(
        self,
        opensearch_client: Any,
        bedrock_client: Any,
        dynamodb_resource: Any | None = None,
        use_cache: bool = True
    ):
        self.opensearch_client = opensearch_client
        self.bedrock_client = bedrock_client
        self.dynamodb_resource = dynamodb_resource
        self.use_cache = use_cache
```

### Factory Pattern for Clients

Create client factories for testability:

```python
class AWSClientProvider:
    """Factory for AWS clients with optional DI for testing."""

    def __init__(
        self,
        region_name: str | None = None,
        bedrock_client: Any | None = None,
        dynamodb_resource: Any | None = None
    ):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self._bedrock_client = bedrock_client
        self._dynamodb_resource = dynamodb_resource

    def get_bedrock_client(self) -> Any:
        if self._bedrock_client is None:
            self._bedrock_client = self._create_bedrock_client()
        return self._bedrock_client

    def _create_bedrock_client(self) -> Any:
        config = Config(
            region_name=self.region_name,
            retries={'max_attempts': 5, 'mode': 'adaptive'},
            max_pool_connections=50,
            connect_timeout=10,
            read_timeout=60,
        )
        return boto3.client('bedrock-runtime', config=config)
```

### Protocol-Based Abstractions

Use Protocols for duck typing and testability:

```python
from typing import Protocol

class BedrockClient(Protocol):
    """Protocol for Bedrock Runtime client."""
    def invoke_model(
        self, *, modelId: str, body: str, contentType: str, accept: str
    ) -> dict:
        ...

class OpenSearchClientProtocol(Protocol):
    """Protocol for OpenSearch client."""
    def search(self, *, index: str, body: dict) -> dict:
        ...

# Usage: Type hints accept any object with matching methods
def query_search(client: OpenSearchClientProtocol, query: dict) -> dict:
    return client.search(index="my-index", body=query)
```

### FastAPI Lifespan for Initialization

Use modern lifespan context managers:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize dependencies
    logger.info("Initializing services...")

    aws_provider = AWSClientProvider()
    bedrock_client = aws_provider.get_bedrock_client()
    opensearch_client = create_opensearch_client()

    app.state.engine = RAGEngine(
        opensearch_client=opensearch_client,
        bedrock_client=bedrock_client,
    )

    logger.info("Services initialized")
    yield

    # Shutdown: Cleanup
    logger.info("Shutting down services...")

app = FastAPI(lifespan=lifespan)
```

### Pydantic Models for Data Contracts

Define clear data contracts between layers:

```python
from pydantic import BaseModel, ConfigDict, field_validator

class NarrativeRequest(BaseModel):
    model_config = ConfigDict(frozen=False)

    assessment_name: str
    assessment_id: str
    scores: Dict[str, int]

    @field_validator('scores')
    @classmethod
    def validate_scores(cls, v):
        for score_code, score_value in v.items():
            if not 0 <= score_value <= 150:
                raise ValueError(f"Score {score_code} must be 0-150")
        return v

class NarrativeResponse(BaseModel):
    model_config = ConfigDict(frozen=False)

    assessment_id: str
    narrative: str
    processing_time_seconds: float
```

---

## 5. Error Handling & Resilience

### Exponential Backoff Retry

Implement retries with exponential backoff and jitter:

```python
async def execute_with_retry(
    operation,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Any:
    """Execute operation with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            error_str = str(e).lower()

            # Classify error
            is_retryable = any(keyword in error_str for keyword in [
                'throttling', 'rate limit', 'timeout',
                'connection reset', 'service unavailable', '503'
            ])

            if is_retryable and attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait_time = base_delay * (2 ** attempt) + (time.time() % 0.1)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
            elif is_retryable:
                logger.error(f"Failed after {max_retries} retries: {e}")
                raise RuntimeError(f"Operation failed after {max_retries} retries")
            else:
                # Non-retryable error - raise immediately
                logger.error(f"Non-retryable error: {e}")
                raise
```

### Error Classification

Differentiate retryable vs non-retryable errors:

```python
def is_retryable_error(error: Exception) -> bool:
    """Classify whether an error is retryable."""
    error_str = str(error).lower()

    # AWS throttling errors
    if hasattr(error, 'response'):
        error_code = error.response.get('Error', {}).get('Code', '')
        if error_code in ('ThrottlingException', 'ServiceUnavailable'):
            return True

    # Network/transient errors
    retryable_keywords = [
        'throttling', 'rate limit', 'timeout',
        'connection reset', 'connection aborted',
        'service unavailable', '503', '429'
    ]

    return any(keyword in error_str for keyword in retryable_keywords)
```

### Graceful Degradation

Handle missing optional services gracefully:

```python
def __init__(self, dynamodb_resource=None, use_cache: bool = True):
    self.use_cache = use_cache

    if self.use_cache and dynamodb_resource is not None:
        try:
            self.cache_table = dynamodb_resource.Table("cache")
            logger.info("Cache enabled")
        except Exception as e:
            logger.warning(f"Cache unavailable, running without: {e}")
            self.use_cache = False
    else:
        self.use_cache = False
```

### HTTP Exception Mapping

Map internal errors to appropriate HTTP status codes:

```python
@app.post("/api/generate")
async def generate_endpoint(request: Request):
    try:
        result = await engine.generate(request.data)
        return result
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        logger.exception("Unexpected error in generate endpoint")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
```

---

## 6. Configuration Management

### Environment Variable Loading

Load at module level with sensible defaults:

```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file once at startup

# Model configuration
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "titan-embed-text-v2")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# Parallelization configuration
MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))
BATCH_MAX_WORKERS = int(os.getenv("BATCH_MAX_WORKERS", "10"))

# Path configuration
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
```

### Hierarchical Defaults

Support parameter → env var → hardcoded default:

```python
def create_client(region_name: str | None = None) -> Any:
    """Create client with hierarchical config resolution."""
    region = region_name or os.getenv("AWS_REGION", "us-east-1")
    return boto3.client('service', region_name=region)
```

### Environment Template

Provide `.env.example` for documentation:

```bash
# .env.example
# AWS Configuration
AWS_REGION=us-east-1

# Model Configuration
LLM_MODEL=claude-sonnet-4-5-20250929
EMBEDDING_MODEL=titan-embed-text-v2
MAX_TOKENS=4096

# Parallelization
MAX_CONCURRENT_LLM_CALLS=5
BATCH_MAX_WORKERS=10

# Feature Flags
USE_CACHE=true
DEBUG_MODE=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=              # Optional: path to log file (empty = stdout only)
```

---

## 7. Logging Best Practices

### Why Logging Over Print

**Never use `print()` statements in production code.** Use the `logging` module instead:

```python
# BAD: Print statements
print(f"Processing request: {request_id}")
print(f"Error: {e}")

# GOOD: Structured logging
logger.info(f"Processing request: {request_id}")
logger.error(f"Request failed: {e}", exc_info=True)
```

**Key reasons to prefer logging:**

| Aspect | `print()` | `logging` |
|--------|-----------|-----------|
| Output control | stdout only | Configurable handlers (file, stdout, remote) |
| Log levels | None | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| Production filtering | Must remove/comment | Configure level per environment |
| Context | Manual | Automatic timestamp, module, line number |
| Performance | Always executes | Can disable by level |
| Async safety | Not thread-safe | Thread-safe by design |

### Module-Level Logger Setup

Every module should create its own logger at the top level:

```python
import logging

logger = logging.getLogger(__name__)
```

Using `__name__` creates a hierarchical logger (e.g., `src.services.engine`) that inherits configuration from parent loggers.

### Log Levels and When to Use Them

```python
# DEBUG: Detailed diagnostic information for debugging
logger.debug(f"Cache lookup for key: {cache_key}")
logger.debug(f"Raw API response: {response}")

# INFO: Confirmation that things are working as expected
logger.info(f"Processing request {request_id}")
logger.info(f"Successfully generated narrative in {elapsed:.2f}s")

# WARNING: Something unexpected happened, but the application continues
logger.warning(f"Cache miss for {cache_key}, falling back to API")
logger.warning(f"Retry attempt {attempt} of {max_retries}")

# ERROR: A serious problem occurred, but the application can recover
logger.error(f"Failed to process item {item_id}: {e}")
logger.error(f"API call failed", exc_info=True)  # Include stack trace

# CRITICAL: A serious error indicating the program may not continue
logger.critical(f"Database connection lost: {e}")
logger.critical(f"Required service unavailable, shutting down")
```

### Logging Configuration

Configure logging once at application startup:

```python
import logging
import sys

def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

# In main.py or application entry point
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
```

### Environment-Based Log Levels

```python
# Load from environment for different deployment contexts
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Development: DEBUG for verbose output
# Production: INFO or WARNING to reduce log volume
```

### Configurable Log Output Paths

Make log destinations configurable via environment variables:

```python
import logging
import sys
import os
from logging.handlers import RotatingFileHandler

def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5
) -> None:
    """Configure logging with optional file output."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]

    # Add file handler if path is configured
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )

# Usage with environment variables
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE")  # e.g., "/var/log/app/app.log"
)
```

Add to `.env.example`:

```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=              # Optional: /var/log/app/app.log (empty = stdout only)
```

### Structured Logging for Production

For production systems, consider structured (JSON) logging:

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    """Format log records as JSON for log aggregation systems."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

# Usage
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

### Logging Best Practices

```python
# DO: Include relevant context
logger.info(f"Processing assessment {assessment_id} with {len(scores)} scores")

# DON'T: Log without context
logger.info("Processing assessment")

# DO: Use exc_info for exceptions
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed for {item_id}", exc_info=True)
    raise

# DON'T: Lose stack trace information
except Exception as e:
    logger.error(f"Error: {e}")  # Stack trace lost!

# DO: Log at appropriate entry/exit points
async def generate_narrative(self, request: NarrativeRequest) -> str:
    logger.info(f"Starting narrative generation for {request.assessment_id}")
    # ... processing ...
    logger.info(f"Completed narrative generation in {elapsed:.2f}s")
    return result

# DON'T: Over-log inside tight loops
for item in items:
    logger.debug(f"Processing {item}")  # Floods logs with large lists

# DO: Log summary instead
logger.info(f"Processing {len(items)} items")
# ... process ...
logger.info(f"Processed {success_count}/{len(items)} items successfully")
```

### Sensitive Data

Never log sensitive information:

```python
# BAD: Logging sensitive data
logger.info(f"User authenticated: {username}, password: {password}")
logger.debug(f"API key: {api_key}")

# GOOD: Redact or omit sensitive fields
logger.info(f"User authenticated: {username}")
logger.debug(f"API key: {api_key[:4]}****")
```

---

## 8. Testing Patterns

### Test Organization

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_models.py       # Pydantic validation
│   ├── test_engine.py       # Business logic
│   └── test_utils.py        # Utility functions
├── integration/             # Full system tests
│   └── test_api.py          # API endpoint tests
└── conftest.py              # Shared fixtures
```

### Pytest Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Async support
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

# Markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, full system)
    asyncio: Async tests
```

### Unit Test Pattern

```python
class TestExecuteWithRetry:
    """Test retry logic."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test success on first attempt."""
        mock_operation = AsyncMock(return_value={"status": "ok"})

        result = await execute_with_retry(mock_operation, max_retries=3)

        assert result == {"status": "ok"}
        assert mock_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_throttling(self):
        """Test retry on throttling error."""
        mock_operation = AsyncMock(side_effect=[
            Exception("ThrottlingException"),
            {"status": "ok"}
        ])

        result = await execute_with_retry(
            mock_operation, max_retries=3, base_delay=0.01
        )

        assert result == {"status": "ok"}
        assert mock_operation.call_count == 2
```

### Mocking External Services

```python
from unittest.mock import Mock, patch, AsyncMock

class TestRAGEngine:
    @pytest.mark.asyncio
    @patch('src.services.engine.boto3')
    async def test_generate_with_mock_client(self, mock_boto3):
        mock_client = Mock()
        mock_client.invoke_model.return_value = {
            'body': Mock(read=Mock(return_value=b'{"content": [{"text": "result"}]}'))
        }
        mock_boto3.client.return_value = mock_client

        engine = RAGEngine(bedrock_client=mock_client)
        result = await engine.generate("test prompt")

        assert "result" in result
```

### Integration Test Pattern

```python
from httpx import AsyncClient, ASGITransport
from main import app

class TestAPIEndpoints:
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
```

---

## 9. Code Smells & Anti-Patterns to Avoid

### Global Mutable State

```python
# BAD: Global mutable state
_cache = {}
def get_data(key):
    if key not in _cache:
        _cache[key] = fetch_data(key)
    return _cache[key]

# GOOD: Encapsulated state
class DataService:
    def __init__(self):
        self._cache = {}

    def get_data(self, key):
        if key not in self._cache:
            self._cache[key] = self._fetch_data(key)
        return self._cache[key]
```

### Hardcoded Configuration

```python
# BAD: Hardcoded values
def call_api():
    client = boto3.client('bedrock', region_name='us-east-1')
    response = client.invoke(max_tokens=4096)

# GOOD: Configurable
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def call_api(client):
    return client.invoke(max_tokens=MAX_TOKENS)
```

### Blocking Async

```python
# BAD: Blocking call in async function
async def get_data():
    response = requests.get(url)  # Blocks event loop!
    return response.json()

# GOOD: Non-blocking async
async def get_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# GOOD: Blocking call in executor
async def get_data_from_sync_client(client):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.get(url))
    return response
```

### Swallowed Exceptions

```python
# BAD: Swallowed exception
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure!

# GOOD: Log and handle appropriately
try:
    result = risky_operation()
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    raise  # Or return sensible default with warning
```

### God Functions

```python
# BAD: One function doing everything
async def process_request(request):
    # 200 lines of validation, processing, formatting, saving...

# GOOD: Single responsibility
async def process_request(request):
    validated = validate_request(request)
    processed = await process_data(validated)
    formatted = format_response(processed)
    await save_result(formatted)
    return formatted
```

### Missing Type Hints

```python
# BAD: No types
def process(data, options):
    return data.get('value') * options['multiplier']

# GOOD: Full typing
def process(data: Dict[str, Any], options: ProcessOptions) -> float:
    return data.get('value', 0) * options.multiplier
```

### Inconsistent Error Handling

```python
# BAD: Inconsistent patterns
def operation_a():
    return None  # Returns None on error

def operation_b():
    raise Exception("error")  # Raises on error

def operation_c():
    return {"error": "message"}  # Returns error dict

# GOOD: Consistent pattern throughout
def operation_a() -> Result:
    raise OperationError("Failed to complete operation A")

def operation_b() -> Result:
    raise OperationError("Failed to complete operation B")
```

---

## 10. Deployment Readiness

### Dockerfile Best Practices

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing bytecode and buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {
        "status": "healthy",
        "service": "rag-engine",
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Makefile Commands

```makefile
.PHONY: help build test lint run

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-15s %s\n", $$1, $$2}'

build:  ## Build Docker image
	docker build -t $(IMAGE_NAME):latest .

test:  ## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:  ## Run linters
	ruff check src/ tests/
	mypy src/

run:  ## Run development server
	uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Quick Reference Checklist

Before declaring code production-ready, verify:

- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] No hardcoded configuration values
- [ ] All async operations use proper patterns (no blocking)
- [ ] Rate limiting implemented for external APIs
- [ ] Retry logic with exponential backoff for network calls
- [ ] Errors classified as retryable vs non-retryable
- [ ] Logging used instead of print statements
- [ ] Logging at appropriate levels (debug/info/warning/error)
- [ ] Dependencies injected, not hardcoded
- [ ] Unit tests for business logic
- [ ] Integration tests for API endpoints
- [ ] Health check endpoint implemented
- [ ] Dockerfile follows security best practices
- [ ] Environment variables documented in `.env.example`

---

*This style guide is designed to be referenced by LLMs when transforming prototype codebases into production-ready systems.*
