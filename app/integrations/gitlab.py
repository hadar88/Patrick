from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.exceptions import ApplicationError


class GitLabError(ApplicationError):
    status_code = 502


@dataclass(frozen=True)
class GitLabClient:
    base_url: str
    token: str | None
    bearer_token: bool = False

    @classmethod
    def from_settings(cls) -> GitLabClient:
        settings = get_settings()
        return cls(settings.gitlab_url.rstrip("/"), None)

    @classmethod
    def from_token(cls, token: str) -> GitLabClient:
        settings = get_settings()
        return cls(settings.gitlab_url.rstrip("/"), token, bearer_token=True)

    def oauth_authorization_url(self, state: str) -> str:
        settings = get_settings()
        if not settings.gitlab_client_id:
            raise GitLabError("GitLab OAuth is not configured")
        params = {
            "client_id": settings.gitlab_client_id,
            "redirect_uri": settings.gitlab_redirect_uri,
            "response_type": "code",
            "scope": "read_user read_api",
            "state": state,
        }
        return f"{self.base_url}/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, object]:
        settings = get_settings()
        if not settings.gitlab_client_id or not settings.gitlab_client_secret:
            raise GitLabError("GitLab OAuth is not configured")
        payload = urlencode(
            {
                "client_id": settings.gitlab_client_id,
                "client_secret": settings.gitlab_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.gitlab_redirect_uri,
            }
        ).encode()
        request = Request(
            f"{self.base_url}/oauth/token",
            data=payload,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise GitLabError("GitLab OAuth token exchange failed") from error
        if not isinstance(result, dict) or not result.get("access_token"):
            raise GitLabError("GitLab OAuth returned an invalid token")
        return result

    def current_user(self) -> dict[str, object]:
        result = self._get("user")
        if not isinstance(result, dict) or not result.get("id"):
            raise GitLabError("GitLab returned an invalid user")
        return result

    def _get(self, path: str, params: dict[str, object] | None = None) -> object:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(f"{self.base_url}/api/v4/{path.lstrip('/')}{query}")
        request.add_header("Accept", "application/json")
        if self.token and self.bearer_token:
            request.add_header("Authorization", f"Bearer {self.token}")
        elif self.token:
            request.add_header("PRIVATE-TOKEN", self.token)
        try:
            with urlopen(request, timeout=10) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in (401, 403):
                raise GitLabError("GitLab authentication failed") from error
            if error.code == 404:
                raise GitLabError("GitLab resource not found") from error
            raise GitLabError("GitLab API request failed") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise GitLabError("GitLab API is unavailable") from error

    def projects(self, search: str | None = None) -> list[dict[str, object]]:
        params: dict[str, object] = {"membership": "true", "simple": "true"}
        if search:
            params["search"] = search
        result = self._get("projects", params)
        if not isinstance(result, list):
            return []
        return [
            {
                "id": project["id"],
                "path_with_namespace": project["path_with_namespace"],
            }
            for project in result
            if isinstance(project, dict)
            and "id" in project
            and "path_with_namespace" in project
        ]

    def authored_merge_requests(self, project_id: int | None = None) -> list[dict[str, object]]:
        path = "merge_requests"
        if project_id is not None:
            path = f"projects/{quote(str(project_id), safe='')}/merge_requests"
        result = self._get(path, {"scope": "created_by_me", "state": "opened"})
        if not isinstance(result, list):
            return []
        return [self._format_merge_request(merge_request) for merge_request in result]

    @staticmethod
    def _format_merge_request(
        merge_request: object,
    ) -> dict[str, object]:
        if not isinstance(merge_request, dict):
            return {}
        references = merge_request.get("references")
        repository = ""
        if isinstance(references, dict):
            full_reference = references.get("full")
            if isinstance(full_reference, str):
                repository = full_reference.rsplit("!", 1)[0]
        author = merge_request.get("author")
        author_data = GitLabClient._format_user(author)
        reviewers = merge_request.get("reviewers")
        reviewer_list = reviewers if isinstance(reviewers, list) else []
        reviewer_data = [
            GitLabClient._format_user(reviewer)
            for reviewer in reviewer_list
        ]
        return {
            "pr_link": merge_request.get("web_url"),
            "title": merge_request.get("title"),
            "author": author_data,
            "reviewers": reviewer_data,
            "repository": repository,
            "iid": merge_request.get("iid"),
            "state": merge_request.get("state"),
        }

    @staticmethod
    def _format_user(user: object) -> dict[str, object]:
        if not isinstance(user, dict):
            return {}
        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "name": user.get("name"),
        }

    def merge_request(self, project_id: int, merge_request_iid: int) -> dict[str, object]:
        project = quote(str(project_id), safe="")
        result = self._get(f"projects/{project}/merge_requests/{merge_request_iid}")
        if not isinstance(result, dict):
            raise GitLabError("GitLab returned an invalid merge request")
        return result