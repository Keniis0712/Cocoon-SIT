from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import _resolve_frontend_file, mount_frontend


def test_resolve_frontend_file_validates_path_and_returns_existing_file(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    asset = dist_dir / "assets" / "app.js"
    asset.parent.mkdir()
    asset.write_text("console.log('ok')", encoding="utf-8")

    assert _resolve_frontend_file(dist_dir, "") is None
    assert _resolve_frontend_file(dist_dir, "../secret.txt") is None
    assert _resolve_frontend_file(dist_dir, "assets/app.js") == asset.resolve()


def test_mount_frontend_returns_early_without_dist_or_index(tmp_path):
    app = FastAPI()
    missing_dist = tmp_path / "missing"
    mount_frontend(app, missing_dist)
    assert not any(route.path == "/" for route in app.router.routes)

    dist_without_index = tmp_path / "dist"
    dist_without_index.mkdir()
    mount_frontend(app, dist_without_index)
    assert not any(route.path == "/" for route in app.router.routes)


def test_mount_frontend_serves_index_assets_and_spa_fallback(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    index_file = dist_dir / "index.html"
    asset_file = dist_dir / "assets" / "app.js"
    asset_file.parent.mkdir()
    index_file.write_text("<html>index</html>", encoding="utf-8")
    asset_file.write_text("console.log('asset')", encoding="utf-8")
    app = FastAPI()
    mount_frontend(app, dist_dir)
    client = TestClient(app)

    index_response = client.get("/")
    asset_response = client.get("/assets/app.js")
    spa_response = client.get("/nested/path")
    api_response = client.get("/api/health")

    assert index_response.status_code == 200
    assert "<html>index</html>" in index_response.text
    assert asset_response.status_code == 200
    assert "console.log('asset')" in asset_response.text
    assert spa_response.status_code == 200
    assert spa_response.text == index_response.text
    assert api_response.status_code == 404
