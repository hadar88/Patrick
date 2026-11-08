from datetime import datetime, timedelta, timezone

from fastapi import status

from app.db.models import GitLabConnection


class FakeGitLabClient:
    def projects(self, search=None):
        return [{"id": 7, "name": search or "patrick"}]

    def authored_merge_requests(self, project_id=None):
        return [{
            "mr_link": "https://gitlab.example/team/patrick/-/merge_requests/8",
            "title": "Improve review flow",
            "author": {"id": 1, "username": "alice", "name": "Alice"},
            "reviewers": [],
            "repository": "team/patrick",
            "iid": 8,
            "state": "opened",
        }]

    def merge_request(self, project_id, merge_request_iid):
        return {
            "project_id": project_id,
            "iid": merge_request_iid,
            "title": "Improve review flow",
            "state": "opened",
        }


def test_gitlab_lookup_routes_return_data_for_task_creation(
    client, monkeypatch, user_factory, session, login_as
):
    user = user_factory()
    session.add(GitLabConnection(user_id=user.user_id, access_token="token"))
    session.flush()
    login_as(user)
    tokens = []

    def fake_from_token(token):
        tokens.append(token)
        return FakeGitLabClient()

    monkeypatch.setattr(
        "app.endpoints.gitlab.GitLabClient.from_token",
        fake_from_token,
    )

    projects_response = client.get("/api/gitlab/projects", params={"search": "pat"})
    merge_requests_response = client.get("/api/gitlab/merge-requests")
    project_merge_requests_response = client.get(
        "/api/gitlab/merge-requests", params={"project_id": 7}
    )
    detail_response = client.get("/api/gitlab/projects/7/merge-requests/8")

    assert projects_response.status_code == status.HTTP_200_OK
    assert projects_response.json() == [{"id": 7, "name": "pat"}]
    assert tokens[0] == "token"
    assert merge_requests_response.status_code == status.HTTP_200_OK
    assert merge_requests_response.json()[0]["iid"] == 8
    assert project_merge_requests_response.status_code == status.HTTP_200_OK
    assert project_merge_requests_response.json()[0]["iid"] == 8
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.json() == {
        "project_id": 7,
        "iid": 8,
        "title": "Improve review flow",
        "state": "opened",
    }


def test_gitlab_projects_are_scoped_to_the_authenticated_user(
    client, monkeypatch, user_factory, session, login_as
):
    first_user = user_factory(gitlab_id=1, username="alice")
    second_user = user_factory(gitlab_id=2, username="bob")
    session.add_all(
        [
            GitLabConnection(user_id=first_user.user_id, access_token="alice-token"),
            GitLabConnection(user_id=second_user.user_id, access_token="bob-token"),
        ]
    )
    session.flush()

    class UserGitLabClient(FakeGitLabClient):
        def __init__(self, token):
            self.token = token

        def projects(self, search=None):
            return [{"id": self.token, "name": search or self.token}]

    tokens = []

    def fake_from_token(token):
        tokens.append(token)
        return UserGitLabClient(token)

    monkeypatch.setattr(
        "app.endpoints.gitlab.GitLabClient.from_token",
        fake_from_token,
    )

    login_as(first_user)
    first_response = client.get("/api/gitlab/projects")

    login_as(second_user)
    second_response = client.get("/api/gitlab/projects")

    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json() == [{"id": "alice-token", "name": "alice-token"}]
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json() == [{"id": "bob-token", "name": "bob-token"}]
    assert tokens == ["alice-token", "bob-token"]


def test_expired_gitlab_access_token_is_refreshed(
    client, monkeypatch, user_factory, session, login_as
):
    user = user_factory()
    connection = GitLabConnection(
        user_id=user.user_id,
        access_token="expired-token",
        refresh_token="refresh-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    session.add(connection)
    session.flush()
    login_as(user)
    refreshed_tokens = []

    class RefreshingClient:
        def refresh_access_token(self, refresh_token):
            refreshed_tokens.append(refresh_token)
            return {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

    def fake_from_settings():
        return RefreshingClient()

    def fake_from_token(token):
        assert token == "new-token"
        return FakeGitLabClient()

    monkeypatch.setattr(
        "app.endpoints.gitlab.GitLabClient.from_settings",
        fake_from_settings,
    )
    monkeypatch.setattr(
        "app.endpoints.gitlab.GitLabClient.from_token",
        fake_from_token,
    )

    response = client.get("/api/gitlab/projects")

    assert response.status_code == status.HTTP_200_OK
    assert refreshed_tokens == ["refresh-token"]
    session.refresh(connection)
    assert connection.access_token == "new-token"
    assert connection.refresh_token == "new-refresh-token"
    assert connection.expires_at is not None
    refreshed_expires_at = connection.expires_at
    if refreshed_expires_at.tzinfo is None:
        refreshed_expires_at = refreshed_expires_at.replace(tzinfo=timezone.utc)
    assert refreshed_expires_at > datetime.now(timezone.utc)