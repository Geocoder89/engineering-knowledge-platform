from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    email: str = Field(
        min_length=1,
        max_length=320,
    )
    password: str = Field(
        min_length=1,
        max_length=128,
    )


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    email: str
    display_name: str
    status: str
