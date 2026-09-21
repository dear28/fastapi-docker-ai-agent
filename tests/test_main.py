from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


# Initialize the test client bound to our FastAPI app
# Allows making simulated requests like client.get() or client.post()
client = TestClient(app)


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
