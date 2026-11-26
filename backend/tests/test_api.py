from fastapi.testclient import TestClient

from app.main import app


def test_health_and_public_capabilities():
    with TestClient(app) as client:
        health = client.get("/api/health")
        config = client.get("/api/config")

    assert health.status_code == 200
    assert health.json()["database"] == "ok"
    assert config.status_code == 200
    assert "api_key" not in config.json()
    assert config.json()["supported_languages"] == ["hi", "mr"]


def test_unsafe_chemical_question_is_refused():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "सोयाबीन पर कीटनाशक का कितना डोस छिड़कूं?",
                "language": "hi",
            },
        )
        payload = response.json()
        history = client.get(f"/api/sessions/{payload['session_id']}")

    assert response.status_code == 200
    assert payload["verification"] == "unavailable"
    assert payload["reason"] == "chemical_advice_requires_expert"
    assert "KVK" in payload["answer"]
    assert payload["entities"]["crop"] == "soybean"
    assert history.status_code == 200
    assert [message["role"] for message in history.json()["messages"]] == ["user", "assistant"]


def test_weather_request_without_location_asks_follow_up():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"question": "Will it rain tomorrow?", "language": "hi"},
        )

    assert response.status_code == 200
    assert response.json()["verification"] == "uncertain"
    assert response.json()["reason"] == "missing_required_detail"


def test_weather_answer_uses_live_data_and_names_location(monkeypatch):
    async def fake_weather(location):
        assert location == "Pune"
        return {
            "provider": "Open-Meteo",
            "location": "Pune, Maharashtra, India",
            "observed_at": "2026-11-25T10:00",
            "current": {"temperature_2m": 27, "precipitation": 0.0},
            "daily": {},
            "attribution": "Open-Meteo",
        }

    monkeypatch.setattr("app.api.routes.weather_for_location", fake_weather)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "What is the weather today?",
                "language": "hi",
                "location": "Pune",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verification"] == "verified"
    assert "Pune" in payload["answer"]
    assert "2026-11-25T10:00" in payload["answer"]
    assert payload["live_data"]["provider"] == "Open-Meteo"


def test_voice_endpoint_explains_missing_transcription_configuration():
    with TestClient(app) as client:
        response = client.post(
            "/api/voice",
            data={"language": "hi"},
            files={"file": ("sample.wav", b"sample audio bytes", "audio/wav")},
        )

    assert response.status_code == 503
    assert "TRANSCRIPTION_MODEL_ID" in response.json()["detail"]


def test_uploaded_document_requires_approval_before_retrieval():
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/documents/upload",
            data={"source": "Test publisher", "language": "hi"},
            files={"file": ("sample.txt", b"Approved test knowledge for soybean farming.", "text/plain")},
        )
        assert uploaded.status_code == 200
        document = uploaded.json()
        assert document["approved"] is False

        approved = client.post(f"/api/documents/{document['id']}/approve")

    assert approved.status_code == 200
    assert approved.json()["approved"] is True


def test_evaluation_reports_measured_case_counts_and_unmeasured_fields():
    with TestClient(app) as client:
        response = client.post("/api/evaluation/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cases"] >= 5
    assert payload["answerable_cases"] >= 1
    assert payload["correct_refusal_rate"] is not None
    assert payload["answer_faithfulness"] is None
    assert payload["api_reliability"]["database_probe"] == "passed"
