import os

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Enterprise AI Agent API",
    description="Production-ready FastAPI service with structured LLM responses.",
    version="1.0.0",
)

# Initialize OpenAI client pointing to Docker Model Runner or custom endpoint
llm_url = os.getenv(
    "LLM_URL", "http://model-runner.docker.internal/v1/"
)  # Fallback to local Docker DNS
api_key = os.getenv("API_KEY", "not-needed")
client = OpenAI(base_url=llm_url, api_key=api_key)


# --- Pydantic Schemas ---
class AgentRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="The query or task description for the AI agent.",
        example="Analyze the invoice process for missing validation steps.",
    )


class AgentAnalysisResponse(BaseModel):
    summary: str = Field(..., description="Brief summary of the prompt or task.")
    complexity: str = Field(
        ...,
        description="Estimated process complexity: Low, Medium, or High.",
    )
    key_takeaways: list[str] = Field(
        ..., description="List of 2-3 key findings or actionable steps."
    )


# --- System Prompt Definition ---
SYSTEM_PROMPT = """
You are an expert Automation & Process Intelligence AI Agent.
Analyze the user's input and provide a structured assessment.

You MUST respond strictly in raw JSON format with no markdown syntax, no ```json codeblocks, and no extra text.
The JSON must follow this exact structure:
{
    "summary": "Short 1-sentence summary of the input",
    "complexity": "Low" | "Medium" | "High",
    "key_takeaways": ["Point 1", "Point 2", "Point 3"]
}
"""


# --- Endpoints ---
@app.get("/", tags=["Health"])
def health_check():
    # Health check endpoint to verify container status.
    return {
        "status": "ok",
        "environment": os.getenv("APP_ENV", "development"),
        "model": os.getenv("LLM_MODEL", "ai/smollm2"),
    }


@app.post(
    "/analyze",
    response_model=AgentAnalysisResponse,
    tags=["Agent Operations"],
)
def analyze_process(request: AgentRequest):
    """Analyzes a process request using the local LLM and returns a structured evaluation."""
    try:
        model_name = os.getenv("LLM_MODEL", "ai/smollm2")

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request.prompt},
            ],
            temperature=0.2,  # Low temperature for deterministic/consistent structured outputs
            max_tokens=250,
        )

        raw_content = response.choices[0].message.content.strip()

        # Parse and validate the response against our Pydantic model
        return AgentAnalysisResponse.model_validate_json(raw_content)

    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Failed to process agent analysis: {err!s}"
        ) from err


# @app.get("/ask")
# def ask_agent(prompt: str = "What is Docker?"):
#     # Sends a prompt to the local LLM running in Docker.
#     try:
#         model_name = os.getenv("LLM_MODEL", "ai/smollm2")
#         response = client.chat.completions.create(
#             model=model_name,
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=150,
#         )
#         return {
#             "prompt": prompt,
#             "answer": response.choices[0].message.content,
#             "model_used": model_name,
#         }
#     except Exception as err:
#         raise HTTPException(
#             status_code=500, detail=f"Failed to connect to LLM: {err!s}"
#         ) from err
