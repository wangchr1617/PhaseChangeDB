from __future__ import annotations

from pydantic import Field

from .common import APIModel


class AppConfigRead(APIModel):
    app_title: str
    app_description: str
    app_logo: str


class AppConfigUpdate(APIModel):
    app_title: str | None = Field(default=None, min_length=1, max_length=64)
    app_description: str | None = Field(default=None, max_length=255)
    app_logo: str | None = Field(default=None, max_length=1000000)
