import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app, ProcessAutomationAssessment


# Initialize the test client bound to our FastAPI app
# Allows making simulated requests like client.get() or client.post()
client = TestClient(app)


def _mock_completion(content: str):
    """
    Builds a minimal fake object mimicking the OpenAI ChatCompletion response shape
    (completion.choices[0].message.content), without hitting the real network.
    """
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


def test_health_check_success():
    """
    Test GET /health returns 200 OK and expected keys when LLM is connected.
    """
    # 'patch' intercepts the LLM network call (openai_client.models.list) inside app/main.py
    # to avoid reaching real external network endpoints during unit test execution
    with patch("app.main.openai_client.models.list") as mock_models_list:
        # Define the mocked function to simulate a successful response returning an empty list
        mock_models_list.return_value = []

        # Execute a simulated GET request to the /health endpoint
        response = client.get("/health")

        # 'assert' validates that conditions evaluate to True; fails the test otherwise
        assert response.status_code == 200  # Verify HTTP status code is 200 OK
        data = response.json()  # Parse JSON response body into a Python dictionary
        assert data["status"] == "ok"
        assert data["llm_connectivity"] == "connected"
        assert "environment" in data
        assert "model_used" in data


def test_health_check_llm_disconnected():
    """
    Test GET /health handles LLM connection failure gracefully.
    """
    # Intercept the LLM client call again
    with patch("app.main.openai_client.models.list") as mock_models_list:
        # 'side_effect' simulates an exception raised by the network call (e.g., service down)
        mock_models_list.side_effect = Exception("Connection refused")

        # Execute simulated GET request to /health
        response = client.get("/health")

        # Confirm the API stays operational (200 OK) while reporting disconnection status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Verify the 'llm_connectivity' string contains "disconnected"
        assert "disconnected" in data["llm_connectivity"]


def test_analyze_process_validation_error():
    """
    Test POST /analyze returns 422 Unprocessable Entity when payload is too short (<10 chars).
    """
    # Payload with a task description deliberately shorter than 10 characters
    payload = {"task_description": "Short"}

    # Send a simulated POST request with the invalid JSON body
    response = client.post("/analyze", json=payload)

    # FastAPI/Pydantic automatically returns HTTP 422 (Unprocessable Entity) on validation errors
    assert response.status_code == 422
    # Extract validation error details returned by FastAPI
    errors = response.json()["detail"]
    # Confirm the error targets the 'task_description' field inside the request body
    assert errors[0]["loc"] == ["body", "task_description"]


def test_analyze_process_success():
    """
    Test POST /analyze returns 200 and a well-formed assessment when the LLM
    responds with valid, schema-compliant JSON.
    """
    valid_payload = json.dumps(
        {
            "automation_potential": "High",
            "recommended_tech_stack": ["Python", "RPA"],
            "key_bottlenecks": ["Manual data entry"],
            "estimated_complexity": "Medium",
            "summary": "Highly automatable process with clear ROI.",
        }
    )

    with patch("app.main.openai_client.chat.completions.create") as mock_create:
        mock_create.return_value = _mock_completion(valid_payload)

        response = client.post(
            "/analyze",
            json={"task_description": "Manual invoice data entry into ERP daily."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["assessment"]["automation_potential"] == "High"
        assert data["assessment"]["recommended_tech_stack"] == ["Python", "RPA"]


def test_analyze_process_strips_markdown_fences():
    """
    Test that /analyze correctly strips ```json ... ``` fences some LLMs add
    despite the system prompt explicitly forbidding them.
    """
    fenced_payload = (
        "```json\n"
        + json.dumps(
            {
                "automation_potential": "Low",
                "recommended_tech_stack": ["Zapier"],
                "key_bottlenecks": ["Approval delays"],
                "estimated_complexity": "Low",
                "summary": "Simple process, low automation priority.",
            }
        )
        + "\n```"
    )

    with patch("app.main.openai_client.chat.completions.create") as mock_create:
        mock_create.return_value = _mock_completion(fenced_payload)

        response = client.post(
            "/analyze",
            json={"task_description": "Weekly approval of vacation requests."},
        )

        assert response.status_code == 200
        assert response.json()["assessment"]["automation_potential"] == "Low"


def test_analyze_process_invalid_llm_json():
    """
    Test POST /analyze returns 502 Bad Gateway when the LLM output is not
    valid JSON or doesn't match the expected schema.
    """
    with patch("app.main.openai_client.chat.completions.create") as mock_create:
        mock_create.return_value = _mock_completion("this is not valid json")

        response = client.post(
            "/analyze",
            json={"task_description": "Process description long enough."},
        )

        assert response.status_code == 502
        assert "invalid structured output" in response.json()["detail"]


def test_analyze_process_empty_choices():
    """
    Test POST /analyze returns 502 Bad Gateway when the LLM response contains
    no completion choices at all, instead of raising an unhandled IndexError.
    """
    empty_completion = MagicMock()
    empty_completion.choices = []

    with patch("app.main.openai_client.chat.completions.create") as mock_create:
        mock_create.return_value = empty_completion

        response = client.post(
            "/analyze",
            json={"task_description": "Process description long enough."},
        )

        assert response.status_code == 502
        assert "no completion choices" in response.json()["detail"]


def test_analyze_process_llm_connection_error():
    """
    Test POST /analyze returns 500 Internal Server Error when the local
    Docker Model Runner is unreachable.
    """
    with patch("app.main.openai_client.chat.completions.create") as mock_create:
        mock_create.side_effect = Exception("Connection refused")

        response = client.post(
            "/analyze",
            json={"task_description": "Process description long enough."},
        )

        assert response.status_code == 500
        assert "Error connecting" in response.json()["detail"]


def test_automation_potential_normalizes_numeric_values():
    """
    Unit test for the field_validator that coerces numeric or messy LLM
    outputs into standard 'High' / 'Medium' / 'Low' levels, independent
    of the /analyze endpoint or any network call.
    """
    low = ProcessAutomationAssessment(
        automation_potential=2,
        estimated_complexity="9",
        recommended_tech_stack=["Python"],
        key_bottlenecks=["Manual review"],
        summary="Edge case numeric normalization.",
    )
    assert low.automation_potential == "Low"
    assert low.estimated_complexity == "High"
