from datetime import datetime

from app.core.time import JERUSALEM_TIMEZONE, now_in_jerusalem
from app.db.models import GitLabConnection, TaskReviewer


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
        "mr_web_url": "https://gitlab.example/patrick/-/merge_requests/8",
        "gitlab_mr_id": 8,
        "mr_title": "Improve review flow",
    }

    create_response = client.post("/api/review-tasks", json=payload)

    assert create_response.status_code == 201
    task = create_response.json()
    assert task["mr_state"] == "opened"
    assert task["priority"] == "NORMAL"
    assert task["status"] == "WAITING FOR REVIEW"
    created_at = datetime.fromisoformat(task["created_at"])
    assert isinstance(created_at, datetime)

    task_id = task["task_id"]
    assert client.get(f"/api/review-tasks/{task_id}").json() == task
    assert client.get("/api/review-tasks/by-mr", params={
        "repo_gitlab_id": 7,
        "gitlab_mr_id": 8,
    }).json() == task
    assert client.get(
        "/api/review-tasks", params={"author_user_id": author.user_id}
    ).json() == [task]
    assert client.post("/api/review-tasks/my-prs", json={}).json() == [task]
    assert client.post(
        "/api/review-tasks/my-prs",
        json={},
        params={"offset": 1, "limit": 1},
    ).json() == []

    update_response = client.patch(
        f"/api/review-tasks/{task_id}",
        json={"priority": "HIGH", "jira_ticket_url": "https://jira.example/browse/PAT-1"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["priority"] == "HIGH"
    assert update_response.json()["jira_ticket_url"] == "https://jira.example/browse/PAT-1"

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
        "mr_web_url": "https://gitlab.example/patrick/-/merge_requests/8",
        "gitlab_mr_id": 8,
        "mr_title": "Improve review flow",
    }
    assert client.post("/api/review-tasks", json=payload).status_code == 201

    response = client.post("/api/review-tasks", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Review task already exists"}


def test_my_prs_supports_sorting_and_pagination(client, user_factory, login_as):
    author = user_factory()
    login_as(author)

    for project_id, mr_id, title, priority in [
        (7, 8, "Zebra change", "LOW"),
        (8, 9, "Alpha change", "HIGH"),
    ]:
        response = client.post(
            "/api/review-tasks",
            json={
                "author_user_id": str(author.user_id),
                "repo_gitlab_id": project_id,
                "repo_name": "patrick",
                "mr_web_url": f"https://gitlab.example/patrick/-/merge_requests/{mr_id}",
                "gitlab_mr_id": mr_id,
                "mr_title": title,
                "priority": priority,
            },
        )
        assert response.status_code == 201

    response = client.post(
        "/api/review-tasks/my-prs",
        json={},
        params={"sort_by": "title", "sort_order": "asc", "limit": 1},
    )
    assert response.status_code == 200
    assert [task["mr_title"] for task in response.json()] == ["Alpha change"]

    response = client.post(
        "/api/review-tasks/my-prs",
        json={},
        params={"sort_by": "priority", "sort_order": "desc"},
    )
    assert [task["priority"] for task in response.json()] == ["LOW", "HIGH"]

    response = client.post(
        "/api/review-tasks/my-prs",
        json={},
        params={"sort_by": "unsupported"},
    )
    assert response.status_code == 422


def test_my_prs_supports_equals_and_created_at_range_filters(
    client, user_factory, login_as
):
    author = user_factory()
    login_as(author)
    response = client.post(
        "/api/review-tasks",
        json={
            "author_user_id": str(author.user_id),
            "repo_gitlab_id": 40,
            "repo_name": "patrick",
            "mr_web_url": "https://gitlab.example/patrick/-/merge_requests/40",
            "gitlab_mr_id": 40,
            "mr_title": "Filtered task",
            "priority": "HIGH",
        },
    )
    created_task = response.json()

    response = client.post(
        "/api/review-tasks/my-prs",
        json={"priority": {"operator": "EQUALS", "values": ["HIGH"]}},
    )
    assert [task["mr_title"] for task in response.json()] == ["Filtered task"]

    response = client.post(
        "/api/review-tasks/my-prs",
        json={
            "created_at": {
                "operator": "RANGE",
                "values": {
                    "from": created_task["created_at"],
                    "to": created_task["created_at"],
                },
            }
        },
    )
    assert [task["mr_title"] for task in response.json()] == ["Filtered task"]


def test_my_prs_rejects_invalid_created_at_range(client, user_factory, login_as):
    author = user_factory()
    login_as(author)

    response = client.post(
        "/api/review-tasks/my-prs",
        json={
            "created_at": {
                "operator": "RANGE",
                "values": {
                    "from": "2026-10-01T00:00:00xxx",
                    "to": "2026-10-03T23:59:59+03:00",
                },
            }
        },
    )

    assert response.status_code == 422


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
    reviewer = user_factory(gitlab_id=40094048, username="reviewer")
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
            "reviewer_gitlab_ids": [reviewer.gitlab_id],
        },
    )

    assert response.status_code == 201
    assert response.json()["description"] == "Please review the API changes"
    assert response.json()["mr_web_url"] == (
        "https://gitlab.example/team/patrick/-/merge_requests/8"
    )
    assert response.json()["author_user_id"] == str(author.user_id)
    assert response.json()["reviewers"][0]["assigned_user_id"] == str(
        reviewer.user_id
    )
    task_reviewers = session.query(TaskReviewer).all()
    assert len(task_reviewers) == 1
    assert task_reviewers[0].assigned_user_id == reviewer.user_id


def test_task_creation_time_uses_jerusalem_timezone():
    assert now_in_jerusalem().tzinfo == JERUSALEM_TIMEZONE


def test_create_review_task_from_gitlab_can_assign_author_as_reviewer(
    client, user_factory, login_as, session, monkeypatch
):
    author = user_factory(gitlab_id=40094048, username="author")
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
            "project_id": 9,
            "merge_request_iid": 10,
            "reviewer_gitlab_ids": [40094048],
        },
    )

    assert response.status_code == 201
    assert response.json()["reviewers"][0]["assigned_user_id"] == str(author.user_id)
    assert client.get(
        f"/api/task-reviewers/status-counts/reviewer/{author.user_id}"
    ).json()["WAITING_FOR_REVIEW"] == 1