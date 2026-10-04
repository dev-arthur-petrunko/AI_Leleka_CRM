"""Задачі: завершення/видалення + ізоляція тенантів."""

from tests.conftest import make_tenant, make_user, auth_headers


def test_task_complete_and_delete(client, db):
    t = make_tenant(db)
    u = make_user(db, t, role="manager")
    h = auth_headers(u)
    r = client.post("/tasks", json={"title": "Подзвонити"}, headers=h)
    assert r.status_code == 200
    tid = r.json()["id"]
    r = client.patch(f"/tasks/{tid}", json={"status": "done"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert r.json()["completed_at"] is not None
    r = client.patch(f"/tasks/{tid}", json={"status": "open"}, headers=h)
    assert r.json()["completed_at"] is None
    assert client.patch(f"/tasks/{tid}", json={"status": "wtf"}, headers=h).status_code == 400
    # чужий тенант — 404
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="manager")
    assert client.patch(f"/tasks/{tid}", json={"status": "done"},
                        headers=auth_headers(u2)).status_code == 404
    assert client.delete(f"/tasks/{tid}", headers=auth_headers(u2)).status_code == 404
    assert client.delete(f"/tasks/{tid}", headers=h).status_code == 200
    # без токена — 401
    assert client.patch(f"/tasks/{tid}", json={"status": "done"}).status_code == 401
