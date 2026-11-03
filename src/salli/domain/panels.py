"""
Panels: a server-driven screen document (`salli.panel/1`), so a deployment's
extension can show a screen in the phone app and the console without core
knowing its words (docs/design/panels.md).

Pure: the model that checks a document and no more. Core never builds one and
never computes a figure in one: every amount is a string the extension supplies.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

SCHEMA = "salli.panel/1"
MAX_SECTIONS = 8
MAX_ROWS = 24
MAX_TEXT = 280

#: A panel's id, as it appears in `/v1/panels/{id}`.
PANEL_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")

Text = Annotated[str, StringConstraints(max_length=MAX_TEXT)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT)]
Then = Literal["refresh", "close"]


def _api_path(value: str) -> str:
    """A path on this server's own API: `/v1/...`, never another host or a way up."""
    if (
        not value.startswith("/v1/")
        or len(value) > 2048
        or "//" in value
        or "\\" in value
        or any(c.isspace() or ord(c) < 32 for c in value)
        or ".." in value.split("?")[0].split("/")
    ):
        raise ValueError("a path must start with /v1/ and stay on this server")
    return value


def _https_url(value: str) -> str:
    if (
        not value.startswith("https://")
        or len(value) > 2048
        or any(c.isspace() or ord(c) < 32 for c in value)
        or len(value) == len("https://")
    ):
        raise ValueError("a link must be an https URL")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextRow(_Strict):
    kind: Literal["text"]
    label: Label
    value: Text | None = None


class LinkRow(_Strict):
    kind: Literal["link"]
    label: Label
    detail: Text | None = None
    url: str

    _https = field_validator("url")(_https_url)


class Action(_Strict):
    method: Literal["POST", "DELETE"]
    path: str
    body: dict[str, Any] | None = None
    then: Then

    _api = field_validator("path")(_api_path)


class ActionRow(_Strict):
    kind: Literal["action"]
    label: Label
    detail: Text | None = None
    #: Asked before it runs, when set.
    confirm: Text | None = None
    action: Action


class Option(_Strict):
    value: Annotated[str, StringConstraints(max_length=MAX_TEXT)]
    label: Label


class Field_(_Strict):
    name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
    label: Label
    type: Literal["text", "number", "select"]
    options: list[Option] | None = None
    required: bool = False

    @model_validator(mode="after")
    def _options_only_for_select(self) -> Field_:
        if (self.type == "select") != bool(self.options):
            raise ValueError("a select has options, and no other field does")
        return self


class Submit(_Strict):
    label: Label
    method: Literal["POST"]
    path: str
    then: Then

    _api = field_validator("path")(_api_path)


class FormRow(_Strict):
    kind: Literal["form"]
    label: Label
    fields: Annotated[list[Field_], Field(min_length=1, max_length=MAX_ROWS)]
    submit: Submit


Row = Annotated[TextRow | LinkRow | ActionRow | FormRow, Field(discriminator="kind")]


class Section(_Strict):
    heading: Text | None = None
    rows: Annotated[list[Row], Field(max_length=MAX_ROWS)]
    footnote: Text | None = None


class Panel(_Strict):
    schema_: Literal["salli.panel/1"] = Field(alias="schema")
    id: Annotated[str, StringConstraints(pattern=f"^{PANEL_ID.pattern}$")]
    title: Label
    sections: Annotated[list[Section], Field(max_length=MAX_SECTIONS)]
    note: Text | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def check_panel(document: Any) -> dict[str, Any]:
    """The document as a plain dict, or ValueError if it is not a valid
    `salli.panel/1`."""
    try:
        return Panel.model_validate(document).model_dump(by_alias=True, mode="json")
    except Exception as exc:
        raise ValueError(f"not a valid {SCHEMA} panel: {exc}") from exc
