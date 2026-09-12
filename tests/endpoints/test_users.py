def test_list_users_is_empty(client):
    response = client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == []


def test_user_crud_flow(client):
    create_response = client.post(
        "/api/users",
        json={"gitlab_id": 42, "username": "alice", "display_name": "Alice"},
    )

    assert create_response.status_code == 201
    user = create_response.json()
    assert user["gitlab_id"] == 42
    assert user["username"] == "alice"

    user_id = user["user_id"]
    get_response = client.get(f"/api/users/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json() == user

    update_response = client.patch(
        f"/api/users/{user_id}",
        json={"display_name": "Alice Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "Alice Updated"

    delete_response = client.delete(f"/api/users/{user_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/users/{user_id}").status_code == 404


def test_duplicate_user_returns_conflict(client):
    payload = {"gitlab_id": 42, "username": "alice"}
    assert client.post("/api/users", json=payload).status_code == 201

    response = client.post("/api/users", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "User already exists"}


def test_get_missing_user_returns_not_found(client):
    response = client.get("/api/users/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_invalid_user_payload_returns_validation_error(client):
    response = client.post("/api/users", json={"gitlab_id": 42})

    assert response.status_code == 422
    assert any(error["loc"][-1] == "username" for error in response.json()["detail"])


def test_null_username_update_returns_validation_error(client, user_factory):
    user = user_factory()

    response = client.patch(
        f"/api/users/{user.user_id}",
        json={"username": None},
    )

    assert response.status_code == 422