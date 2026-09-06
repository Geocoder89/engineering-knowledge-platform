from fastapi import APIRouter

from app.api.dependencies import AuthenticatedUserDependency
from app.models.user import User
from app.schemas.authentication import AuthenticatedUserResponse

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get(
    "/me",
    response_model=AuthenticatedUserResponse,
)
def get_current_user(
    authenticated_user: AuthenticatedUserDependency,
) -> User:
    return authenticated_user.user
