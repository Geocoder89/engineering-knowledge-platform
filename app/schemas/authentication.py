from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.password import validate_password
from app.domain.user import normalize_user_email


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    email: str = Field(
        min_length=1,
        max_length=320,
    )
    display_name: str = Field(
        min_length=1,
        max_length=200,
    )
    password: str = Field(
        min_length=1,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def validate_email(
        cls,
        email: str,
    ) -> str:
        return normalize_user_email(
            email,
        )

    @field_validator("display_name")
    @classmethod
    def validate_display_name(
        cls,
        display_name: str,
    ) -> str:
        normalized_display_name = display_name.strip()

        if not normalized_display_name:
            raise ValueError(
                "Display name cannot be blank",
            )

        return normalized_display_name

    @field_validator("password")
    @classmethod
    def validate_registration_password(
        cls,
        password: str,
    ) -> str:
        validate_password(
            password,
        )

        return password


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
