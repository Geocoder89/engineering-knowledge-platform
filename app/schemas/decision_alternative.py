from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)

AlternativeTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=200,
    ),
]

AlternativeDescription = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=10,
        max_length=4000,
    ),
]


class DecisionAlternativeCreate(BaseModel):
    title: AlternativeTitle
    description: AlternativeDescription

    model_config = ConfigDict(
        extra="forbid",
    )


class DecisionAlternativeResponse(
    DecisionAlternativeCreate,
):
    id: UUID
    decision_id: UUID
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class DecisionAlternativeUpdate(BaseModel):
    title: AlternativeTitle | None = None
    description: AlternativeDescription | None = None

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_update_fields(
        self,
    ) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one alternative field must be provided")

        if any(
            getattr(self, field_name) is None for field_name in self.model_fields_set
        ):
            raise ValueError("Alternative fields cannot be null")

        return self
