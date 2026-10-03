import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=40)
    password: SecretStr

    @field_validator("username")
    @classmethod
    def username_format(cls, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", value):
            raise ValueError("Use 3–40 letters, numbers, dots, underscores or hyphens.")
        return value

    @field_validator("password")
    @classmethod
    def password_length(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Password must contain 1–128 characters.")
        return value


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str


class AuthOutput(BaseModel):
    user: UserOutput
    csrf_token: str
