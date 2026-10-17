from tests.test_api import _cam, client  # noqa: F401  (client is a pytest fixture)


def test_overlay_toggles_and_stream_requires_running(client):  # noqa: F811
    cid = _cam(client).json()["id"]
    o = client.get(f"/api/cameras/{cid}/overlay").json()
    assert o["boxes"] and o["ids"] and o["confidence"] and not o["trails"]
    o = client.patch(f"/api/cameras/{cid}/overlay", json={"trails": True, "confidence": False}).json()
    assert o["trails"] and not o["confidence"] and o["boxes"]  # others untouched
    assert client.get(f"/api/cameras/{cid}/overlay").json() == o
    assert client.get(f"/api/cameras/{cid}/stream").status_code == 409  # not running
    assert client.get(f"/api/cameras/{cid}/live").json() == {"running": False, "seq": 0, "meta": None}
    assert client.get("/api/cameras/999/overlay").status_code == 404


def test_camera_zones_get_and_put(client):  # noqa: F811
    cid = _cam(client, name="zone_cam").json()["id"]
    z = client.get(f"/api/cameras/{cid}/zones").json()
    assert z["coords"] == "normalized" and "zones" in z and "lines" in z

    new_cfg = {
        "camera_id": str(cid),
        "coords": "normalized",
        "lines": [
            {"id": "door_line", "name": "Door", "points": [[0.1, 0.5], [0.9, 0.5]], "cooldown": 1.0}
        ],
        "zones": [
            {
                "id": "vault",
                "name": "Vault",
                "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                "rules": ["intrusion"],
                "loiter_seconds": 5.0,
            },
            {
                "id": "lobby",
                "name": "Lobby",
                "points": [[0.1, 0.6], [0.5, 0.6], [0.5, 0.9]],
                "rules": ["loitering"],
                "loiter_seconds": 8.0,
            },
        ],
    }
    res = client.put(f"/api/cameras/{cid}/zones", json=new_cfg)
    assert res.status_code == 200
    saved = res.json()
    assert len(saved["zones"]) == 2 and saved["zones"][0]["name"] == "Vault"
    assert saved["zones"][1]["loiter_seconds"] == 8.0
    assert len(saved["lines"]) == 1 and saved["lines"][0]["name"] == "Door"
    assert client.get(f"/api/cameras/{cid}/zones").json() == saved
