# FastAPI Docker AI Agent - Process Intelligence API

Production-ready Python AI Agent service built with FastAPI, Docker, and Docker Model Runner. It processes structured process analysis tasks using local LLM inference (`ai/smollm2`), enforces strict JSON response validation using Pydantic, and provides hot-reload capabilities for rapid containerized development.

## Business Problem

Modern enterprise automation pipelines need local or air-gapped AI processing to analyze operational tasks without exposing sensitive data to external cloud APIs or introducing high API operational costs. Standard LLM integration approaches often suffer from unstructured, unpredictable text outputs that break downstream software systems and lack standardized containerization.

This architecture addresses:
* **Data Privacy & Cost Control:** Eliminates external cloud dependencies by hosting lightweight instruction-tuned LLMs locally inside Docker.
* **Unstructured Response Failures:** Forces strict JSON output schemas with Pydantic validation to prevent downstream parsing errors.
* **Deployment Inconsistency:** Enforces container-level environment isolation, ensuring identical execution across local development and production servers.

## Key Architectural Features

### 1. Production FastAPI Architecture
* **Structured Request/Response Schemas:** Utilizes Pydantic models (`AgentRequest`, `AgentAnalysisResponse`) with field validation and automatic OpenAPI documentation.
* **Determined System Prompts:** Implements system-level role conditioning and low inference temperature (`0.2`) for deterministic and repeatable structured analysis.
* **Robust Error Handling:** Encapsulates local model runner connection states with specific HTTP exceptions and stacktrace chaining.

### 2. Docker & Local LLM Runtime Integration

* **Docker Model Runner Integration:** Connects directly to local Docker LLM engines using Docker internal DNS (`model-runner.docker.internal`).
* **Environment-Driven Configuration:** Separates runtime behavior using `.env` files with defensive fallback values across all service endpoints.
* **Live-Reload Development Loop:** Integrates Docker bind mounts to reflect Python code changes in real time without container rebuilds.

## Architecture & Stack

* **Python 3.11+:** Core runtime environment
* **FastAPI:** High-performance REST API framework
* **Pydantic v2:** Data validation and JSON schema enforcement
* **Docker & Docker Compose:** Container orchestration & environment isolation
* **Docker Model Runner / OpenAI SDK:** Local LLM inference engine (`ai/smollm2`)
* **Ruff:** Code linting and formatting standardization

## Repository Structure

```text
.
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI application & AI Agent endpoints
├── .dockerignore
├── .env.example         # Environment template for repository setup
├── .gitignore
├── compose.yaml         # Docker Compose service specification
├── Dockerfile           # Python container image build instructions
├── README.md            # Project documentation
└── requirements.txt     # Python dependencies

```

## How to Setup and Run

To run this AI Agent service in your local Docker environment:

1. **Clone the repository:**
```bash
git clone https://github.com/dear28/fastapi-docker-ai-agent.git
cd fastapi-docker-ai-agent
```
2. **Configure Environment Variables:**
Copy the example environment template:
```bash
cp .env.example .env
```
3. **Enable and Pull the Local LLM Model:**
Ensure Docker Model Runner is enabled in Docker Desktop, then pull the target model:
```bash
docker model pull ai/smollm2
```
4. **Run Container with Live Reloading:**
```bash
docker run -d -p 8000:8000 -v "${PWD}/app:/app/app" --env-file .env --name ai-agent-app python-ai-agent
```
5. **Verify and Test API:**
Navigate to the Swagger UI interactive documentation at [http://localhost:8000/docs](http://localhost:8000/docs) and test the POST /analyze endpoint with a custom prompt payload.

---

## Technical Notes

* JSON Output Enforcement: The SYSTEM_PROMPT enforces raw JSON output without markdown codeblocks, validated immediately via AgentAnalysisResponse.model_validate_json().
* Container Isolation: Dependencies and standard OpenAI API bindings are locked inside the container, avoiding local Python version conflicts.