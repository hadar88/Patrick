from app.db.models import GitLabConnection


class FakeGitLabClient:
    def projects(self, search=None):
        return [{"id": 7, "path_with_namespace": search or "team/patrick"}]

    def authored_merge_requests(self, project_id=None):
        return [{
            "pr_link": "https://gitlab.example/team/patrick/-/merge_requests/8",
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

    assert projects_response.status_code == 200
    assert projects_response.json() == [{"id": 7, "path_with_namespace": "pat"}]
    assert tokens[0] == "token"
    assert merge_requests_response.status_code == 200
    assert merge_requests_response.json()[0]["iid"] == 8
    assert project_merge_requests_response.status_code == 200
    assert project_merge_requests_response.json()[0]["iid"] == 8
    assert detail_response.status_code == 200
    assert detail_response.json() == {
        "project_id": 7,
        "iid": 8,
        "title": "Improve review flow",
        "state": "opened",
    }