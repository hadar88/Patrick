from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.endpoints.auth import get_current_user
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.queriers import UserQuerier

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    return UserQuerier(db).list()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    return UserQuerier(db).create(payload.model_dump())


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    return UserQuerier(db).get(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
) -> UserResponse:
    return UserQuerier(db).update(user_id, payload.model_dump(exclude_unset=True))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_db)) -> None:
    UserQuerier(db).delete(user_id)