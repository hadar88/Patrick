def test_task_reviewer_crud_and_filter_routes(
    client, user_factory, task_factory
):
    author = user_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    task = task_factory(author=author)
    payload = {
        "task_id": str(task.task_id),
        "assigned_user_id": str(assigned_user.user_id),
    }

    create_response = client.post("/api/task-reviewers", json=payload)

    assert create_response.status_code == 201
    reviewer = create_response.json()
    assert reviewer["status"] == "WAITING_FOR_REVIEW"
    assert reviewer["source"] == "MANUAL"

    reviewer_id = reviewer["reviewer_entry_id"]
    assert client.get(f"/api/task-reviewers/{reviewer_id}").json() == reviewer
    assert client.get(f"/api/task-reviewers/by-task/{task.task_id}").json() == [
        reviewer
    ]
    assert client.get(
        f"/api/task-reviewers/by-user/{assigned_user.user_id}"
    ).json() == [reviewer]

    update_response = client.patch(
        f"/api/task-reviewers/{reviewer_id}",
        json={"status": "APPROVED", "source": "AUTOMATIC"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "APPROVED"
    assert update_response.json()["source"] == "AUTOMATIC"

    delete_response = client.delete(f"/api/task-reviewers/{reviewer_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/task-reviewers/{reviewer_id}").status_code == 404


def test_duplicate_task_reviewer_returns_conflict(
    client, user_factory, task_factory
):
    author = user_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    task = task_factory(author=author)
    payload = {
        "task_id": str(task.task_id),
        "assigned_user_id": str(assigned_user.user_id),
    }
    assert client.post("/api/task-reviewers", json=payload).status_code == 201

    response = client.post("/api/task-reviewers", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Reviewer is already assigned to this task"}


def test_get_missing_task_reviewer_returns_not_found(client):
    response = client.get(
        "/api/task-reviewers/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Reviewer not found"}


def test_null_reviewer_status_update_returns_validation_error(
    client, user_factory, task_factory
):
    author = user_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    task = task_factory(author=author)
    reviewer = client.post(
        "/api/task-reviewers",
        json={
            "task_id": str(task.task_id),
            "assigned_user_id": str(assigned_user.user_id),
        },
    ).json()

    response = client.patch(
        f"/api/task-reviewers/{reviewer['reviewer_entry_id']}",
        json={"status": None},
    )

    assert response.status_code == 422