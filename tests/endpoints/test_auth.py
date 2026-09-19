from dataclasses import dataclass

from app.db.models import User


@dataclass
class FakeGitLabClient:
    @classmethod
    def from_settings(cls):
        return cls()

    @classmethod
    def from_token(cls, token):
        return cls()

    def oauth_authorization_url(self, state):
        return f"https://gitlab.example/oauth?state={state}"

    def exchange_code(self, code):
        return {"access_token": "access-token"}

    def current_user(self):
        return {"id": 123, "username": "admin", "name": "Admin"}


def test_gitlab_login_promotes_configured_admin(client, session, monkeypatch):
    monkeypatch.setattr("app.endpoints.auth.GitLabClient", FakeGitLabClient)
    monkeypatch.setattr("app.endpoints.auth.settings.admin_gitlab_id", 123)

    login_response = client.get("/api/auth/gitlab/login", follow_redirects=False)
    state = login_response.headers["location"].split("state=", 1)[1]
    callback_response = client.get(
        f"/api/auth/gitlab/callback?code=code&state={state}",
        follow_redirects=False,
    )

    assert callback_response.status_code == 307
    created_user = session.query(User).one()
    assert created_user.is_admin is True


def test_logout_clears_authentication_session(client, monkeypatch):
    monkeypatch.setattr("app.endpoints.auth.GitLabClient", FakeGitLabClient)

    login_response = client.get("/api/auth/gitlab/login", follow_redirects=False)
    state = login_response.headers["location"].split("state=", 1)[1]
    client.get(
        f"/api/auth/gitlab/callback?code=code&state={state}",
        follow_redirects=False,
    )

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 204
    assert client.get("/api/users").status_code == 401
