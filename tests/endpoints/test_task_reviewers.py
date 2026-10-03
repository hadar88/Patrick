def test_task_reviewer_crud_and_filter_routes(
    client, user_factory, task_factory, login_as
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
    assert reviewer["status"] == "WAITING FOR REVIEW"
    assert reviewer["source"] == "MANUAL"

    reviewer_id = reviewer["reviewer_entry_id"]
    assert client.get(f"/api/task-reviewers/{reviewer_id}").json() == reviewer
    assert client.get(f"/api/task-reviewers/by-task/{task.task_id}").json() == [
        reviewer
    ]
    assert client.get(
        f"/api/task-reviewers/by-user/{assigned_user.user_id}"
    ).json() == [reviewer]
    login_as(assigned_user)
    reviewer_rows = client.post(
        "/api/review-tasks/my-reviews",
        json={},
        params={"offset": 0, "limit": 10},
    ).json()
    assert reviewer_rows[0]["mr_title"] == task.mr_title
    assert reviewer_rows[0]["mr_web_url"] == task.mr_web_url
    assert reviewer_rows[0]["status"] == "WAITING FOR REVIEW"
    assert reviewer_rows[0]["priority"] == task.priority
    assert reviewer_rows[0]["jira_ticket_url"] is None
    assert reviewer_rows[0]["developer"]["user_id"] == str(author.user_id)
    filtered_reviewer_rows = client.post(
        "/api/review-tasks/my-reviews",
        json={"status": {"operator": "EQUALS", "values": ["WAITING_FOR_REVIEW"]}},
    ).json()
    assert [row["mr_title"] for row in filtered_reviewer_rows] == [task.mr_title]
    assert client.get(
        f"/api/task-reviewers/status-counts/reviewer/{assigned_user.user_id}"
    ).json() == {
        "WAITING_FOR_REVIEW": 1,
        "REVIEW": 0,
        "CHANGES_NEEDED": 0,
        "APPROVED": 0,
        "CLOSED": 0,
    }
    assert client.get(
        f"/api/task-reviewers/status-counts/assignee/{author.user_id}"
    ).json() == {
        "WAITING_FOR_REVIEW": 1,
        "REVIEW": 0,
        "CHANGES_NEEDED": 0,
        "APPROVED": 0,
        "CLOSED": 0,
    }

    task_without_reviewer = task_factory(
        author=author,
        repo_gitlab_id=11,
        gitlab_mr_id=21,
    )
    assert client.get(
        f"/api/task-reviewers/status-counts/assignee/{author.user_id}"
    ).json()["WAITING_FOR_REVIEW"] == 2

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


def test_my_reviews_supports_reviewer_status_sorting_and_pagination(
    client, user_factory, task_factory, reviewer_factory, login_as
):
    author = user_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    waiting_task = task_factory(
        author=author,
        repo_gitlab_id=30,
        gitlab_mr_id=31,
        mr_title="Waiting task",
    )
    approved_task = task_factory(
        author=author,
        repo_gitlab_id=32,
        gitlab_mr_id=33,
        mr_title="Approved task",
    )
    reviewer_factory(
        task=waiting_task,
        assigned_user=assigned_user,
        status="WAITING_FOR_REVIEW",
    )
    reviewer_factory(
        task=approved_task,
        assigned_user=assigned_user,
        status="APPROVED",
    )
    login_as(assigned_user)

    response = client.post(
        "/api/review-tasks/my-reviews",
        json={},
        params={"sort_by": "status", "sort_order": "asc", "limit": 1},
    )
    assert response.status_code == 200
    assert [row["mr_title"] for row in response.json()] == ["Approved task"]

    response = client.post(
        "/api/review-tasks/my-reviews",
        json={},
        params={"sort_by": "title", "sort_order": "desc"},
    )
    assert [row["mr_title"] for row in response.json()] == [
        "Waiting task",
        "Approved task",
    ]

    response = client.post(
        "/api/review-tasks/my-reviews",
        json={},
        params={"sort_order": "sideways"},
    )
    assert response.status_code == 422


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