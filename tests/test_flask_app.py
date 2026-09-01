import json
import pytest
from src.server.flask_app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_flask_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["backend"] == "flask"


def test_flask_macros_endpoint(client):
    res = client.get("/api/macros")
    assert res.status_code == 200
    data = res.get_json()
    assert "macros" in data
    assert len(data["macros"]) > 0


def test_flask_tts_speak_telephony(client):
    payload = {
        "text": "Tazocin 3.375g IV q8h. Patient has HFrEF.",
        "voice": "af_heart",
        "mode": "dictation",
        "sink": "telephony_8k",
        "mrn": "123456"
    }
    res = client.post("/api/tts/speak", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["sink"] == "telephony_8k"
    assert "file_path" in data


def test_flask_tts_speak_fluency(client):
    payload = {
        "text": "Normal cardiac exam. S1 and S2 present.",
        "voice": "af_heart",
        "mode": "dictation",
        "sink": "fluency",
        "mrn": "987654",
        "provider_id": "DR_DOC"
    }
    res = client.post("/api/tts/speak", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["sink"] == "fluency"
    assert "job_package" in data
