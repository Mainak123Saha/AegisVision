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
