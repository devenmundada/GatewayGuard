"""Tasks CRUD, including ownership isolation between users."""


class TestTasks:
    async def test_create_and_list(self, client, auth_headers):
        created = await client.post(
            "/api/v1/tasks",
            json={"title": "Write tests", "description": "all of them"},
            headers=auth_headers,
        )
        assert created.status_code == 201
        task = created.json()
        assert task["title"] == "Write tests"
        assert task["completed"] is False

        listing = await client.get("/api/v1/tasks", headers=auth_headers)
        assert [t["id"] for t in listing.json()] == [task["id"]]

    async def test_get_update_delete(self, client, auth_headers):
        task = (
            await client.post("/api/v1/tasks", json={"title": "A"}, headers=auth_headers)
        ).json()
        url = f"/api/v1/tasks/{task['id']}"

        assert (await client.get(url, headers=auth_headers)).json()["title"] == "A"

        patched = await client.patch(url, json={"completed": True}, headers=auth_headers)
        assert patched.status_code == 200
        assert patched.json()["completed"] is True
        assert patched.json()["title"] == "A"  # untouched fields stay

        assert (await client.delete(url, headers=auth_headers)).status_code == 204
        assert (await client.get(url, headers=auth_headers)).status_code == 404

    async def test_filter_by_completed(self, client, auth_headers):
        for title, done in (("open", False), ("done", True)):
            t = (
                await client.post("/api/v1/tasks", json={"title": title}, headers=auth_headers)
            ).json()
            if done:
                await client.patch(
                    f"/api/v1/tasks/{t['id']}", json={"completed": True}, headers=auth_headers
                )
        done_only = await client.get("/api/v1/tasks?completed=true", headers=auth_headers)
        assert [t["title"] for t in done_only.json()] == ["done"]

    async def test_pagination(self, client, auth_headers):
        for i in range(5):
            await client.post("/api/v1/tasks", json={"title": f"t{i}"}, headers=auth_headers)
        page = await client.get("/api/v1/tasks?limit=2&offset=2", headers=auth_headers)
        assert [t["title"] for t in page.json()] == ["t2", "t3"]
        bad = await client.get("/api/v1/tasks?limit=0", headers=auth_headers)
        assert bad.status_code == 422

    async def test_users_cannot_see_or_touch_each_others_tasks(
        self, client, auth_headers, other_auth_headers
    ):
        mine = (
            await client.post("/api/v1/tasks", json={"title": "mine"}, headers=auth_headers)
        ).json()
        url = f"/api/v1/tasks/{mine['id']}"

        assert (await client.get("/api/v1/tasks", headers=other_auth_headers)).json() == []
        assert (await client.get(url, headers=other_auth_headers)).status_code == 404
        assert (
            await client.patch(url, json={"title": "hacked"}, headers=other_auth_headers)
        ).status_code == 404
        assert (await client.delete(url, headers=other_auth_headers)).status_code == 404

        # and the owner's task is intact
        assert (await client.get(url, headers=auth_headers)).json()["title"] == "mine"

    async def test_validation(self, client, auth_headers):
        empty = await client.post("/api/v1/tasks", json={"title": ""}, headers=auth_headers)
        assert empty.status_code == 422
        null_title = await client.post("/api/v1/tasks", json={}, headers=auth_headers)
        assert null_title.status_code == 422

    async def test_requires_authentication(self, client):
        assert (await client.post("/api/v1/tasks", json={"title": "x"})).status_code == 401
        assert (await client.get("/api/v1/tasks/1")).status_code == 401
