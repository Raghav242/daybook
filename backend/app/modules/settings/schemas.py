from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from app.core.schemas import Input, Output


class SettingsInput(Input):
    timezone: str = Field(default="America/New_York", max_length=80)
    default_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    enabled_modules: list[Literal["tasks", "calendar", "groceries", "bills"]] = Field(
        default_factory=lambda: ["tasks", "calendar", "groceries", "bills"]
    )

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use an IANA timezone, such as America/New_York.") from None
        return value

    @field_validator("enabled_modules")
    @classmethod
    def unique_modules(cls, value):
        return list(dict.fromkeys(value))


class SettingsOutput(SettingsInput, Output):
    pass
