import pytest
from sqlalchemy.exc import IntegrityError

from app.db.dals import ReviewTaskDAL, TaskReviewerDAL, UserDAL


def test_base_dal_crud(session):
    dal = UserDAL(session)
    user = dal.create({"gitlab_id": 1, "username": "alice"})

    assert dal.get(user.user_id) is user
    assert dal.list() == [user]

    dal.update(user, {"display_name": "Alice"})
    assert user.display_name == "Alice"

    dal.delete(user)
    assert dal.get(user.user_id) is None


def test_base_dal_list_is_empty_for_new_session(session):
    assert UserDAL(session).list() == []


def test_user_dal_finds_users_by_gitlab_id_and_username(session, user_factory):
    user = user_factory(gitlab_id=42, username="alice")
    dal = UserDAL(session)

    assert dal.get_by_gitlab_id(42) is user
    assert dal.get_by_username("alice") is user
    assert dal.get_by_gitlab_id(404) is None
    assert dal.get_by_username("missing") is None


def test_review_task_dal_filters_by_merge_request_and_author(
    session, user_factory, task_factory
):
    author = user_factory()
    task = task_factory(author=author, repo_gitlab_id=7, gitlab_mr_id=8)
    other_task = task_factory(author=author, repo_gitlab_id=7, gitlab_mr_id=9)
    dal = ReviewTaskDAL(session)

    assert dal.get_by_gitlab_mr_id(7, 8) is task
    assert dal.get_by_gitlab_mr_id(7, 404) is None
    assert dal.list_by_author(author.user_id) == [task, other_task]


def test_review_task_dal_does_not_mix_repositories_or_authors(
    session, user_factory, task_factory
):
    first_author = user_factory()
    second_author = user_factory(gitlab_id=2, username="bob")
    first_task = task_factory(
        author=first_author, repo_gitlab_id=7, gitlab_mr_id=8
    )
    same_mr_in_other_repo = task_factory(
        author=second_author, repo_gitlab_id=9, gitlab_mr_id=8
    )
    dal = ReviewTaskDAL(session)

    assert dal.get_by_gitlab_mr_id(7, 8) is first_task
    assert dal.get_by_gitlab_mr_id(9, 8) is same_mr_in_other_repo
    assert dal.list_by_author(first_author.user_id) == [first_task]
    assert dal.list_by_author(second_author.user_id) == [same_mr_in_other_repo]


def test_review_task_defaults_are_applied(session, task_factory):
    task = task_factory()

    assert task.mr_state == "opened"
    assert task.priority == "NORMAL"
    assert task.status == "WAITING_FOR_REVIEW"
    assert task.jira_ticket_key is None


def test_task_reviewer_dal_filters_by_task_and_user(
    session, task_factory, user_factory, reviewer_factory
):
    task = task_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    reviewer = reviewer_factory(task=task, assigned_user=assigned_user)
    dal = TaskReviewerDAL(session)

    assert dal.get_for_task_and_user(task.task_id, assigned_user.user_id) is reviewer
    assert dal.list_by_task(task.task_id) == [reviewer]
    assert dal.list_by_user(assigned_user.user_id) == [reviewer]
    assert (
        dal.get_for_task_and_user(task.task_id, user_factory(gitlab_id=3).user_id)
        is None
    )


def test_task_reviewer_dal_does_not_mix_tasks(
    session, task_factory, user_factory, reviewer_factory
):
    first_task = task_factory()
    second_author = user_factory(gitlab_id=3, username="carol")
    second_task = task_factory(
        author=second_author, repo_gitlab_id=11, gitlab_mr_id=21
    )
    assigned_user = user_factory(gitlab_id=2, username="bob")
    first_reviewer = reviewer_factory(task=first_task, assigned_user=assigned_user)
    second_reviewer = reviewer_factory(task=second_task, assigned_user=assigned_user)
    dal = TaskReviewerDAL(session)

    assert dal.list_by_task(first_task.task_id) == [first_reviewer]
    assert dal.list_by_task(second_task.task_id) == [second_reviewer]
    assert dal.list_by_user(assigned_user.user_id) == [first_reviewer, second_reviewer]


def test_deleting_task_cascades_to_reviewers(
    session, task_factory, reviewer_factory
):
    task = task_factory()
    reviewer = reviewer_factory(task=task)
    task_dal = ReviewTaskDAL(session)
    reviewer_dal = TaskReviewerDAL(session)

    task_dal.delete(task)

    assert task_dal.get(task.task_id) is None
    assert reviewer_dal.get(reviewer.reviewer_entry_id) is None


def test_duplicate_reviewers_for_task_and_user_are_rejected(
    session, task_factory, user_factory, reviewer_factory
):
    task = task_factory()
    assigned_user = user_factory(gitlab_id=2, username="bob")
    reviewer_factory(task=task, assigned_user=assigned_user)

    with pytest.raises(IntegrityError):
        reviewer_factory(task=task, assigned_user=assigned_user)

    session.rollback()