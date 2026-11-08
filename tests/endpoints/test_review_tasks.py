from datetime import datetime

from fastapi import status

from app.core.time import JERUSALEM_TIMEZONE, now_in_jerusalem
from app.db.models import GitLabConnection, TaskReviewer, User


class FakeGitLabClient:
    def merge_request(self, project_id, merge_request_iid):
        return {
            "project_id": project_id,
            "iid": merge_request_iid,
            "title": "Improve review flow",
            "state": "opened",
            "web_url": "https://gitlab.example/team/patrick/-/merge_requests/8",
            "references": {"full": "team/patrick!8"},
            "reviewers": [{
                "id": 40094048,
                "username": "reviewer",
                "name": "Alice",
                "avatar_url": "https://gitlab.example/uploads/reviewer.png",
            }],
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

    assert create_response.status_code == status.HTTP_201_CREATED
    task = create_response.json()
    assert task["mr_state"] == "opened"
    assert task["priority"] == "MEDIUM"
    assert task["status"] == "WAITING FOR REVIEW"
    assert task["repo_url"] == "https://gitlab.example/patrick"
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
    assert client.post("/api/review-tasks/my-merge-requests", json={}).json() == [task]
    assert client.post(
        "/api/review-tasks/my-merge-requests",
        json={},
        params={"offset": 1, "limit": 1},
    ).json() == []

    update_response = client.patch(
        f"/api/review-tasks/{task_id}",
        json={
            "priority": "HIGH",
            "description": "Updated review instructions",
            "jira_ticket_url": "https://jira.example/browse/PAT-1",
        },
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["priority"] == "HIGH"
    assert update_response.json()["description"] == "Updated review instructions"
    assert update_response.json()["jira_ticket_url"] == "https://jira.example/browse/PAT-1"

    remove_reviewers_response = client.patch(
        f"/api/review-tasks/{task_id}",
        json={"reviewer_user_ids": []},
    )
    assert remove_reviewers_response.status_code == status.HTTP_200_OK
    assert remove_reviewers_response.json()["reviewers"] == []
    assert remove_reviewers_response.json()["status"] == "WAITING FOR REVIEW"

    delete_response = client.delete(f"/api/review-tasks/{task_id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert client.get(f"/api/review-tasks/{task_id}").status_code == status.HTTP_404_NOT_FOUND


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
    assert client.post("/api/review-tasks", json=payload).status_code == status.HTTP_201_CREATED

    response = client.post("/api/review-tasks", json=payload)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "This review task already exists"}


def test_my_merge_requests_supports_sorting_and_pagination(client, user_factory, login_as):
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
        assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/review-tasks/my-merge-requests",
        json={},
        params={"sort_by": "mr_title", "sort_order": "asc", "limit": 1},
    )
    assert response.status_code == status.HTTP_200_OK
    assert [task["mr_title"] for task in response.json()] == ["Alpha change"]

    response = client.post(
        "/api/review-tasks/my-merge-requests",
        json={},
        params={"sort_by": "priority", "sort_order": "desc"},
    )
    assert [task["priority"] for task in response.json()] == ["HIGH", "LOW"]

    response = client.post(
        "/api/review-tasks/my-merge-requests",
        json={},
        params={"sort_by": "unsupported"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    response = client.post(
        "/api/review-tasks/my-merge-requests",
        json={},
        params={"sort_by": "title"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_my_merge_requests_supports_equals_and_created_at_range_filters(
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
        "/api/review-tasks/my-merge-requests",
        json={"priority": {"operator": "EQUALS", "values": ["HIGH"]}},
    )
    assert [task["mr_title"] for task in response.json()] == ["Filtered task"]

    response = client.post(
        "/api/review-tasks/my-merge-requests",
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


def test_table_routes_filter_by_merge_request_state(
    client, user_factory, task_factory, reviewer_factory, login_as
):
    author = user_factory()
    reviewer = user_factory(gitlab_id=2, username="reviewer")
    opened_task = task_factory(author=author, mr_state="opened", gitlab_mr_id=41)
    closed_task = task_factory(author=author, mr_state="closed", gitlab_mr_id=42)
    reviewer_factory(task=opened_task, assigned_user=reviewer)
    reviewer_factory(task=closed_task, assigned_user=reviewer)

    login_as(author)
    assert [
        task["task_id"]
        for task in client.get("/api/review-tasks").json()
    ] == [str(opened_task.task_id)]
    assert [
        task["task_id"]
        for task in client.get(
            "/api/review-tasks", params={"mr_state": "closed"}
        ).json()
    ] == [str(closed_task.task_id)]
    assert [
        task["task_id"]
        for task in client.post(
            "/api/review-tasks/my-merge-requests",
            params={"mr_state": "opened"},
            json={},
        ).json()
    ] == [str(opened_task.task_id)]

    login_as(reviewer)
    assert [
        task["task_id"]
        for task in client.get(
            "/api/review-tasks/assigned", params={"mr_state": "closed"}
        ).json()
    ] == [str(closed_task.task_id)]
    assert [
        task["mr_title"]
        for task in client.post(
            "/api/review-tasks/my-reviews",
            params={"mr_state": "opened"},
            json={},
        ).json()
    ] == [opened_task.mr_title]


def test_my_merge_requests_rejects_invalid_created_at_range(client, user_factory, login_as):
    author = user_factory()
    login_as(author)

    response = client.post(
        "/api/review-tasks/my-merge-requests",
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

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_missing_review_task_requires_authentication(client):
    response = client.get(
        "/api/review-tasks/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
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

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


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
            "reviewer_gitlab_ids": [40094048],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["description"] == "Please review the API changes"
    assert response.json()["mr_web_url"] == (
        "https://gitlab.example/team/patrick/-/merge_requests/8"
    )
    assert response.json()["repo_url"] == "https://gitlab.example/team/patrick"
    assert response.json()["author_user_id"] == str(author.user_id)
    created_reviewer = (
        session.query(User).filter(User.gitlab_id == 40094048).one()
    )
    assert response.json()["reviewers"][0]["assigned_user_id"] == str(
        created_reviewer.user_id
    )
    assert response.json()["reviewers"][0]["username"] == "reviewer"
    assert response.json()["reviewers"][0]["display_name"] == "Alice"
    assert response.json()["reviewers"][0]["avatar_url"] == (
        "https://gitlab.example/uploads/reviewer.png"
    )
    assert created_reviewer.avatar_url == (
        "https://gitlab.example/uploads/reviewer.png"
    )
    task_reviewers = session.query(TaskReviewer).all()
    assert len(task_reviewers) == 1
    assert task_reviewers[0].assigned_user_id == created_reviewer.user_id


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

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["reviewers"][0]["assigned_user_id"] == str(author.user_id)
    assert client.get(
        f"/api/task-reviewers/status-counts/reviewer/{author.user_id}"
    ).json()["WAITING_FOR_REVIEW"] == 1


def test_task_gitlab_reviewers_refreshes_current_reviewers(
    client, user_factory, task_factory, login_as, session, monkeypatch
):
    author = user_factory()
    task = task_factory(author=author, repo_gitlab_id=7, gitlab_mr_id=8)
    session.add(GitLabConnection(user_id=author.user_id, access_token="token"))
    session.commit()
    login_as(author)

    class CurrentReviewersClient:
        def merge_request(self, project_id, merge_request_iid):
            return {
                "reviewers": [{
                    "id": 42,
                    "username": "new-reviewer",
                    "name": "New Reviewer",
                    "avatar_url": "https://gitlab.example/new-reviewer.png",
                }],
            }

    monkeypatch.setattr(
        "app.endpoints.gitlab.GitLabClient.from_token",
        lambda token: CurrentReviewersClient(),
    )

    response = client.get(
        f"/api/review-tasks/{task.task_id}/gitlab-reviewers"
    )

    assert response.status_code == status.HTTP_200_OK
    reviewer = response.json()[0]
    assert reviewer["gitlab_id"] == 42
    assert reviewer["username"] == "new-reviewer"
    assert reviewer["avatar_url"] == "https://gitlab.example/new-reviewer.png"
    assert session.query(User).filter(User.gitlab_id == 42).one().display_name == (
        "New Reviewer"
    )