from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import mount_frontend


def test_mount_frontend_serves_index_for_root_and_spa_routes(tmp_path: Path):
    dist_dir = tmp_path / "frontend_dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>cocoon</body></html>", encoding="utf-8")
    (dist_dir / "app.js").write_text("console.log('ok')", encoding="utf-8")

    app = FastAPI()
    mount_frontend(app, dist_dir)

    client = TestClient(app)

    root_response = client.get("/")
    route_response = client.get("/workspace")
    asset_response = client.get("/app.js")
    api_response = client.get("/api/v1/unknown")

    assert root_response.status_code == 200
    assert "cocoon" in root_response.text
    assert route_response.status_code == 200
    assert "cocoon" in route_response.text
    assert asset_response.status_code == 200
    assert "console.log" in asset_response.text
    assert api_response.status_code == 404
