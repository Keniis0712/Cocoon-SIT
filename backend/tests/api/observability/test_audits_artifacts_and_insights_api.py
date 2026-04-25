from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import AuditArtifact, AuditRun, AuditStep


def test_audit_artifact_and_insight_routes_cover_summary_and_manual_cleanup(client, auth_headers):
    container = client.app.state.container

    with container.session_factory() as session:
        run = AuditRun(operation_type="api-observability", status="completed")
        session.add(run)
        session.flush()

        step = AuditStep(run_id=run.id, step_name="seed-audit", status="completed")
        session.add(step)
        session.flush()

        storage_path = container.artifact_store.write_text("api/observability.json", '{"source": "api"}')
        artifact = AuditArtifact(
            run_id=run.id,
            step_id=step.id,
            kind="prompt_snapshot",
            storage_backend="filesystem",
            storage_path=storage_path,
            summary="seeded artifact",
            metadata_json={"seeded": True},
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        )
        session.add(artifact)
        session.commit()
        run_id = run.id
        artifact_id = artifact.id

    audits = client.get("/api/v1/audits", headers=auth_headers)
    assert audits.status_code == 200, audits.text
    assert any(item["id"] == run_id for item in audits.json())

    detail = client.get(f"/api/v1/audits/{run_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["run"]["id"] == run_id
    assert any(item["id"] == artifact_id for item in detail.json()["artifacts"])

    artifacts = client.get("/api/v1/admin/artifacts", headers=auth_headers)
    assert artifacts.status_code == 200, artifacts.text
    assert any(item["id"] == artifact_id for item in artifacts.json())

    manual_cleanup = client.post(
        "/api/v1/admin/artifacts/cleanup/manual",
        headers=auth_headers,
        json={"artifact_ids": [artifact_id]},
    )
    assert manual_cleanup.status_code == 200, manual_cleanup.text
    assert manual_cleanup.json()["job_type"] == "artifact_cleanup"
    assert manual_cleanup.json()["payload_json"] == {"mode": "manual", "artifact_ids": [artifact_id]}

    dashboard = client.get("/api/v1/insights/dashboard?range=30d&interval=day", headers=auth_headers)
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()
    assert {
        "generated_at",
        "range",
        "interval",
        "summary",
        "token_usage",
        "memory",
        "runtime",
    } == set(payload.keys())
    assert payload["range"] == "30d"
    assert payload["interval"] == "day"
    assert {"total_messages", "total_runs", "total_tokens", "error_rate", "average_latency_ms", "active_cocoons", "pending_wakeup_count"} == set(payload["summary"].keys())
    assert {"series", "by_provider", "by_model", "by_operation"} == set(payload["token_usage"].keys())
    assert {"total_memories", "growth", "by_source_kind", "by_memory_type", "top_cocoons"} == set(payload["memory"].keys())
    assert {"request_series", "decision_distribution", "status_distribution", "node_latency", "latency_p50_ms", "latency_p95_ms", "silence_rate", "wakeup_rate", "error_rate", "top_error_cocoons"} == set(payload["runtime"].keys())


def test_audit_detail_returns_404_for_unknown_run(client, auth_headers):
    response = client.get("/api/v1/audits/missing-run-id", headers=auth_headers)
    assert response.status_code == 404, response.text
    payload = response.json()
    assert payload["code"] == "AUDIT_RUN_NOT_FOUND"
    assert payload["msg"] == "Audit run not found"
    assert payload["data"] is None
