from app.db.models import GitLabConnection


class FakeGitLabClient:
    def merge_request(self, project_id, merge_request_iid):
        return {
            "project_id": project_id,
            "iid": merge_request_iid,
            "title": "Improve review flow",
            "state": "opened",
            "web_url": "https://gitlab.example/team/patrick/-/merge_requests/8",
            "references": {"full": "team/patrick!8"},
            "reviewers": [],
        }


def test_review_task_crud_and_lookup_routes(client, user_factory, login_as):
    author = user_factory()
    login_as(author)
    payload = {
        "author_user_id": str(author.user_id),
        "repo_gitlab_id": 7,
        "repo_name": "patrick",
        "repo_web_url": "https://gitlab.example/patrick",
        "gitlab_mr_id": 8,
        "mr_title": "Improve review flow",
    }

    create_response = client.post("/api/review-tasks", json=payload)

    assert create_response.status_code == 201
    task = create_response.json()
    assert task["mr_state"] == "opened"
    assert task["priority"] == "NORMAL"
    assert task["status"] == "WAITING_FOR_REVIEW"

    task_id = task["task_id"]
    assert client.get(f"/api/review-tasks/{task_id}").json() == task
    assert client.get("/api/review-tasks/by-mr", params={
        "repo_gitlab_id": 7,
        "gitlab_mr_id": 8,
    }).json() == task
    assert client.get(
        "/api/review-tasks", params={"author_user_id": author.user_id}
    ).json() == [task]

    update_response = client.patch(
        f"/api/review-tasks/{task_id}",
        json={"priority": "HIGH", "jira_ticket_key": "PAT-1"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["priority"] == "HIGH"
    assert update_response.json()["jira_ticket_key"] == "PAT-1"

    delete_response = client.delete(f"/api/review-tasks/{task_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/review-tasks/{task_id}").status_code == 404


def test_duplicate_review_task_returns_conflict(client, user_factory, login_as):
    author = user_factory()
    login_as(author)
    payload = {
        "author_user_id": str(author.user_id),
        "repo_gitlab_id": 7,
        "repo_name": "patrick",
        "repo_web_url": "https://gitlab.example/patrick",
        "gitlab_mr_id": 8,
        "mr_title": "Improve review flow",
    }
    assert client.post("/api/review-tasks", json=payload).status_code == 201

    response = client.post("/api/review-tasks", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Review task already exists"}


def test_get_missing_review_task_requires_authentication(client):
    response = client.get(
        "/api/review-tasks/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "GitLab authentication required"}


def test_null_review_task_status_update_returns_validation_error(
    client, user_factory, task_factory, login_as
):
    author = user_factory()
    login_as(author)
    task = task_factory(author=author)

    response = client.patch(
        f"/api/review-tasks/{task.task_id}",
        json={"status": None},
    )

    assert response.status_code == 422


def test_create_review_task_from_gitlab(
    client, user_factory, login_as, session, monkeypatch
):
    author = user_factory()
    login_as(author)
    session.add(GitLabConnection(user_id=author.user_id, access_token="token"))
    session.commit()
    monkeypatch.setattr(
        "app.endpoints.review_tasks.GitLabClient.from_token",
        lambda token: FakeGitLabClient(),
    )

    response = client.post(
        "/api/review-tasks/from-gitlab",
        json={
            "project_id": 7,
            "merge_request_iid": 8,
            "description": "Please review the API changes",
        },
    )

    assert response.status_code == 201
    assert response.json()["description"] == "Please review the API changes"
    assert response.json()["author_user_id"] == str(author.user_id)