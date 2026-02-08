from fastapi.testclient import TestClient

import local_review_copilot.server as server

app = server.app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_config_round_trip(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(server, "CONFIG_PATH", str(config_path))

    client = TestClient(app)
    current = client.get("/config")
    assert current.status_code == 200

    update_payload = {
        "workspace_root_dir": str(tmp_path),
        "llm": {
            "provider": "echo",
            "endpoint": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_seconds": 20,
            "max_context_tokens": 8000,
        },
    }
    updated = client.post("/config", json=update_payload)
    assert updated.status_code == 200
    assert config_path.exists()
    body = updated.json()
    assert body["workspace_root_dir"] == str(tmp_path)
    assert body["llm"]["max_context_tokens"] == 8000

