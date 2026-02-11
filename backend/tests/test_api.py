from fastapi.testclient import TestClient

import local_review_copilot.server as server

app = server.app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_config_round_trip(local_tmp_dir, monkeypatch) -> None:
    config_path = local_tmp_dir / "config.yaml"
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)

    client = TestClient(app)
    current = client.get("/config")
    assert current.status_code == 200

    update_payload = {
        "workspace_root_dir": str(local_tmp_dir),
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
    assert body["workspace_root_dir"] == str(local_tmp_dir.resolve())
    assert body["llm"]["max_context_tokens"] == 8000


def test_runtime_config_rejects_missing_workspace(monkeypatch, local_tmp_dir) -> None:
    config_path = local_tmp_dir / "config.yaml"
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)
    missing = local_tmp_dir / "missing-dir"

    client = TestClient(app)
    response = client.post("/config", json={"workspace_root_dir": str(missing)})

    assert response.status_code == 400
    assert "Workspace root not found" in response.json()["detail"]


def test_runtime_config_rejects_invalid_llm_provider(monkeypatch, local_tmp_dir) -> None:
    config_path = local_tmp_dir / "config.yaml"
    monkeypatch.setattr(server, "CONFIG_PATH", config_path)

    client = TestClient(app)
    response = client.post("/config", json={"llm": {"provider": "unsupported"}})

    assert response.status_code == 422

