import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator


# Configure structured logging to output clean, trace-friendly log messages to the container console (stdout)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application with metadata used for automatic OpenAPI/Swagger generation
app = FastAPI(
    title="Process Intelligence AI Agent API",
    description="Production-ready AI agent service for process automation assessment.",
    version="1.0.0",
)

# Load environment configuration variables following the 12-Factor App standard (decoupling config from code)
LLM_URL = os.getenv("LLM_URL", "http://model-runner.docker.internal:12434/v1").rstrip(
    "/"
)
LLM_MODEL = os.getenv("LLM_MODEL", "ai/smollm2:latest")
API_KEY = os.getenv("API_KEY", "not-needed")

# Initialize OpenAI client pointed to local Docker Model Runner (Ollama/vLLM compatible endpoint)
openai_client = OpenAI(
    base_url=LLM_URL,
    api_key=API_KEY,
)

# System prompt forcing strictly valid JSON responses without conversational filler
SYSTEM_PROMPT = (
    "You are an expert Process Intelligence AI Agent specializing in business process optimization and workflow analysis.\n"
    "Your primary goal is to analyze operational task descriptions and produce strictly valid JSON outputs.\n\n"
    "CRITICAL OUTPUT RULES:\n"
    "1. You MUST respond ONLY with a raw, valid JSON object matching the requested schema.\n"
    "2. DO NOT wrap the JSON in markdown code blocks (e.g., do NOT use ```json or ```).\n"
    "3. DO NOT include introductory text, conversational pleasantries, or postscript notes.\n"
    "4. Ensure all JSON keys and values are properly formatted and escaped."
)


# Pydantic Schemas for Request/Response Data Validation
class HealthCheckResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    environment: str = Field(..., examples=["development"])
    llm_connectivity: str = Field(..., examples=["connected"])
    model_used: str = Field(..., examples=["ai/smollm2:latest"])


class AgentRequest(BaseModel):
    task_description: str = Field(
        ...,
        min_length=10,  # Rejects inputs shorter than 10 characters (HTTP 422)
        description="Detailed description of the business process or operational task to analyze.",
        examples=[
            "Manual processing of vendor invoices received via email, manual data entry into ERP, and approval routing via email."
        ],
    )


class ProcessAutomationAssessment(BaseModel):
    """
    Schema for structuring and validating the LLM's process assessment output.
    Ensures that the fields returned by the model conform to expected types.
    """

    automation_potential: str = Field(
        ...,
        description="Potential level of automation (e.g., High, Medium, Low).",
    )
    recommended_tech_stack: list[str] = Field(
        ...,
        description="Recommended technologies or tools (e.g., Python, RPA, Power Automate, OCR).",
    )
    key_bottlenecks: list[str] = Field(
        ...,
        description="Identified operational friction points or bottlenecks.",
    )
    estimated_complexity: str = Field(
        ...,
        description="Complexity level of implementation (e.g., Low, Medium, High).",
    )
    summary: str = Field(
        ...,
        description="Executive summary of the process analysis and next steps.",
    )

    @field_validator("automation_potential", "estimated_complexity", mode="before")
    @classmethod
    def normalize_level_values(cls, v: Any) -> str:
        """
        Coimages numeric or messy LLM inputs into standard 'High', 'Medium', or 'Low'.
        """
        if v is None:
            return "Medium"

        val_str = str(v).strip().lower()

        if val_str.isdigit():
            num = int(val_str)
            if num <= 3 or num == 1:
                return "Low"
            elif num <= 7:
                return "Medium"
            else:
                return "High"

        if "high" in val_str:
            return "High"
        if "low" in val_str:
            return "Low"
        if "med" in val_str:
            return "Medium"

        return "Medium"  # Predetermined Fallback


class AgentAnalysisResponse(BaseModel):
    status: str = Field(default="success", description="Response status.")
    model_used: str = Field(..., description="Local LLM model identifier executed.")
    assessment: ProcessAutomationAssessment = Field(
        ...,
        description="Structured automation assessment.",
    )


# API Endpoints
@app.get("/health", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
def health_check() -> HealthCheckResponse:
    """
    Healthcheck endpoint to verify API state and LLM service connectivity.
    """
    env = os.getenv("APP_ENV", "development")

    try:
        # Perform a lightweight ping to verify LLM service network availability
        openai_client.models.list()
        llm_status = "connected"
    except Exception as e:
        # Capture connection failure without crashing the service
        llm_status = f"disconnected: {e!s}"

    return {
        "status": "ok",
        "environment": env,
        "llm_connectivity": llm_status,
        "model_used": LLM_MODEL,
    }


@app.post(
    "/analyze",
    response_model=AgentAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_process(request: AgentRequest) -> AgentAnalysisResponse:
    """
    Analyze an operational task or business process description using a local LLM
    and return a structured assessment detailing automation potential, bottlenecks,
    tech stack, and estimated complexity.
    """
    # Construct the user prompt enforcing schema structure expectations
    prompt = (
        "Analyze the following operational process description and return an assessment JSON with keys: "
        "'automation_potential' (MUST be 'High', 'Medium', or 'Low'), "
        "'recommended_tech_stack' (list of tools), "
        "'key_bottlenecks' (list of bottlenecks), "
        "'estimated_complexity' (MUST be 'High', 'Medium', or 'Low'), "
        "and 'summary'.\n\n"
        f"Process Description:\n{request.task_description}"
    )

    try:
        # Send the analysis prompt and context rules to the local LLM engine
        completion = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,  # Low temperature reduces randomness to ensure consistent, deterministic JSON structures
        )

        raw_content = completion.choices[0].message.content or ""
        logger.info(f"Raw LLM Output received: {raw_content!r}")

        # Clean potential markdown block formatting (e.g., ```json ... ```) if emitted by the LLM
        cleaned_content = raw_content.strip()
        if cleaned_content.startswith("```"):
            lines = cleaned_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_content = "\n".join(lines).strip()

        # Parse the raw JSON string and validate its key-value data types against the Pydantic v2 schema
        assessment_data = ProcessAutomationAssessment.model_validate_json(
            cleaned_content
        )

        return AgentAnalysisResponse(
            status="success",
            model_used=LLM_MODEL,
            assessment=assessment_data,
        )

    except ValidationError as err:
        # Handle cases where the LLM generated invalid JSON structure or missing fields
        logger.error(f"Pydantic Validation Error: {err!s}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Local LLM generated invalid structured output schema: {err!s}",
        ) from err
    except Exception as err:
        # Handle general communication errors with the local Docker Model Runner
        logger.error(f"LLM Runner Execution Error: {err!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to local Docker Model Runner: {err!s}",
        ) from err
