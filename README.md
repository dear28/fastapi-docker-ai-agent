# AI Process Assessment & Orchestration Pipeline (FastAPI + n8n + MongoDB)

![AI Assessment Pipeline](assets/ai_assessment_pipeline_main.png)
![Notify Error Subworkflow Diagram](assets/notify_error_subworkflow.png)

Production-ready Python AI Agent service built with FastAPI, Docker, and Docker Model Runner. It processes structured process analysis tasks using local LLM inference (`ai/smollm2`), enforces strict JSON response validation using Pydantic, and provides hot-reload capabilities for rapid containerized development.

## Table of Contents

- [Business Problem](#business-problem)
- [Key Architectural Features](#key-architectural-features)
- [Orchestration & Resilience Architecture (n8n)](#orchestration--resilience-architecture-n8n)
- [Architecture & Stack](#architecture--stack)
- [Repository Structure](#repository-structure)
- [Environment Variables](#environment-variables)
- [How to Setup and Run](#how-to-setup-and-run)
- [Technical Notes](#technical-notes)
- [License](#license)
- [Contributing](#contributing)

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

## Orchestration & Resilience Architecture (n8n)

The pipeline uses **n8n** to coordinate the ingestion, validation, AI evaluation, persistent auditing, and failure notification:

1. **Main Assessment Workflow (`workflows/ai-assessment-pipeline.json`):**
   - **Healthcheck & Pre-validation:** Verifies FastAPI service availability and validates request payload structure before triggering LLM inference.
   - **AI Analysis Execution:** Calls the local FastAPI endpoint to perform structured process feasibility analysis.
   - **Data Normalization & Audit Storage:** Sanitizes the output and persists evaluation logs directly into **MongoDB**.

2. **Error Handling Strategy (System Settings + Subworkflow):**
   - **Global Error Workflow:** Linked via n8n Workflow Settings to automatically catch unhandled system exceptions and execution failures across the main pipeline.
   - **Centralized Error Subworkflow (`workflows/notify-error.json`):** Formats error context and generates rich Slack alerts using Block Kit layout, complete with node details and direct links to the n8n execution log for rapid debugging.
   - **Resilient HTTP Calls:** Retry-on-fail enabled on all outbound HTTP nodes to absorb transient network or timeout issues without triggering false-positive alerts.
   - **Severity-Tiered Alerting:** Failures are classified as `critical` (service unreachable, data-loss risk on save) or `warning` (recoverable business-logic issues, e.g. invalid payload or empty AI response), so on-call response is proportional to actual risk.

### 2. Docker & Local LLM Runtime Integration

* **Docker Model Runner Integration:** Connects directly to local Docker LLM engines using Docker internal DNS (`model-runner.docker.internal`).
* **Environment-Driven Configuration:** Separates runtime behavior using `.env` files with defensive fallback values across all service endpoints.
* **Live-Reload Development Loop:** Integrates Docker bind mounts to reflect Python code changes in real time without container rebuilds.

## Architecture & Stack

* **Python 3.13+ & FastAPI:** Core LLM assessment microservice & data validation
* **n8n:** Workflow orchestration & business process automation
* **MongoDB:** Document store for historical process evaluation audits
* **Slack API (Block Kit):** Real-time alerting & centralized subworkflow error management — see [notify-error.json](workflows/notify-error.json)
* **Docker & Docker Compose:** Container orchestration & environment isolation
* **Docker Model Runner / OpenAI SDK:** Local LLM inference engine (`ai/smollm2`)
* **Pydantic v2:** Data validation and JSON schema enforcement

## Repository Structure

```text
.
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI application & AI Agent endpoints
├── assets/              # Workflow diagrams & architecture screenshots
│   ├── ai_assessment_pipeline_main.png
│   └── notify_error_subworkflow.png
├── workflows/           # Exported n8n workflows (JSON)
│   ├── ai-assessment-pipeline.json
│   └── notify-error.json
├── .dockerignore
├── .env.example         # Environment template for repository setup
├── .gitignore
├── docker-compose.yaml  # Docker Compose service specification
├── Dockerfile           # Python container image build instructions
├── README.md            # Project documentation
└── requirements.txt     # Python dependencies

```

## Environment Variables

This project uses a `.env` file (see `.env.example`) to configure the FastAPI service:

| Variable | Description | Example |
|---|---|---|
| `APP_ENV` | Runtime environment mode (affects logging/debug behavior) | `development` |
| `LLM_MODEL` | Docker Model Runner model identifier to use for inference | `ai/smollm2` |
| `LLM_URL` | Docker Model Runner internal API endpoint (OpenAI-compatible) | `http://model-runner.docker.internal/v1/` |
| `API_KEY` | API key for the LLM endpoint; not required for local Docker Model Runner | `not-needed` |
| `WEBHOOK_URL` | Base URL for the n8n container (`N8N_EDITOR_BASE_URL`/`WEBHOOK_URL`), used only by n8n — not read by the FastAPI app — to correctly build direct execution links (`/workflow/.../executions/...`) sent by the `notifyError` subworkflow to Slack | `http://localhost:5678` |

> **Note:** MongoDB and Slack credentials are configured directly in n8n's credential manager, not in this repository's `.env` file, since persistence and alerting are handled by the orchestration layer.

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