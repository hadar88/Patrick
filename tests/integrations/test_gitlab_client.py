import io
import json
from urllib.error import HTTPError

import pytest

from app.integrations.gitlab import GitLabClient, GitLabError


class FakeResponse:
    def __init__(self, payload: object):
        self.body = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self.body.read(*args)


def test_projects_request_uses_gitlab_v4_and_private_token(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(
            [{
                "id": 7,
                "name": "patrick",
                "path_with_namespace": "team/patrick",
                "web_url": "https://gitlab.example/team/patrick",
            }]
        )

    monkeypatch.setattr("app.integrations.gitlab.urlopen", fake_urlopen)

    result = GitLabClient("https://gitlab.example", "secret").projects("pat")

    assert result == [{"id": 7, "path_with_namespace": "team/patrick"}]
    request, timeout = requests[0]
    assert request.full_url == (
        "https://gitlab.example/api/v4/projects?membership=true&simple=true&search=pat"
    )
    assert request.get_header("Private-token") == "secret"
    assert timeout == 10


def test_authored_merge_requests_uses_created_by_me_scope(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(
            [{
                "iid": 8,
                "title": "Improve review flow",
                "state": "opened",
                "web_url": "https://gitlab.example/team/patrick/-/merge_requests/8",
                "references": {"full": "team/patrick!8"},
                "author": {"id": 1, "username": "alice", "name": "Alice"},
                "reviewers": [
                    {"id": 2, "username": "bob", "name": "Bob"},
                ],
            }]
        )

    monkeypatch.setattr("app.integrations.gitlab.urlopen", fake_urlopen)

    result = GitLabClient("https://gitlab.example", None).authored_merge_requests()

    assert result == [{
        "pr_link": "https://gitlab.example/team/patrick/-/merge_requests/8",
        "title": "Improve review flow",
        "author": {"id": 1, "username": "alice", "name": "Alice"},
        "reviewers": [{"id": 2, "username": "bob", "name": "Bob"}],
        "repository": "team/patrick",
        "iid": 8,
        "state": "opened",
    }]
    assert requests[0].full_url == (
        "https://gitlab.example/api/v4/merge_requests?scope=created_by_me&state=opened"
    )
    assert requests[0].get_header("Private-token") is None


def test_authored_merge_requests_can_be_scoped_to_project(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(
            [{"iid": 8, "title": "Improve review flow", "reviewers": []}]
        )

    monkeypatch.setattr("app.integrations.gitlab.urlopen", fake_urlopen)

    result = GitLabClient("https://gitlab.example", None).authored_merge_requests(7)

    assert result[0]["iid"] == 8
    assert result[0]["reviewers"] == []
    assert requests[0].full_url == (
        "https://gitlab.example/api/v4/projects/7/merge_requests?"
        "scope=created_by_me&state=opened"
    )


def test_merge_request_uses_project_id_and_iid(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse({"project_id": 7, "iid": 8, "state": "opened"})

    monkeypatch.setattr("app.integrations.gitlab.urlopen", fake_urlopen)

    result = GitLabClient("https://gitlab.example", "secret").merge_request(7, 8)

    assert result == {"project_id": 7, "iid": 8, "state": "opened"}
    assert requests[0].full_url == (
        "https://gitlab.example/api/v4/projects/7/merge_requests/8"
    )


def test_unauthorized_gitlab_response_is_mapped_to_application_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO())

    monkeypatch.setattr("app.integrations.gitlab.urlopen", fake_urlopen)

    with pytest.raises(GitLabError, match="GitLab authentication failed"):
        GitLabClient("https://gitlab.example", "secret").projects()