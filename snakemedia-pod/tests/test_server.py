import importlib

from fastapi.testclient import TestClient


def test_api_with_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAKEPOD_DATA", str(tmp_path))
    from snakepod import config
    importlib.reload(config)
    from snakepod import db, demo, jobs, server
    for m in (db, demo, jobs, server):
        importlib.reload(m)
    demo.main()
    with TestClient(server.app) as c:
        stats = c.get("/api/stats").json()
        assert stats["total"] > 0
        sap = c.get("/api/videos", params={"label": "sap_win"}).json()["items"]
        assert sap and all(v["label"] == "sap_win" for v in sap)
        detail = c.get(f"/api/videos/{sap[0]['cid']}").json()
        assert detail["ads"] and detail["checks"]
        assert c.get(f"/thumbs/{detail['thumb']}").status_code == 200
        assert c.get("/thumbs/..%2F..%2Fsnakepod.db").status_code == 404
        assert c.post("/api/scan", json={"keyword": "  "}).status_code == 400
        assert "SNAKEMEDIA POD" in c.get("/").text
