"""
What changed between two versions of a rule set, for the review a person does
before activating one.

`diff_documents(old, new)` walks both documents as JSON and lists every value
that was added, removed or changed, each with a path into the document. The
review needs three things from it:

- **Paths that survive reordering.** A list whose items are named (blocks and
  lines by `key`, sources by `id`, accounts by `code`, examples by `name`) is
  matched by name, not by position, so moving a block is not reported as every
  block changing. Such a path reads `blocks[key=allowance].amount`. Lists of
  unnamed items (a table's bands) are matched by position: `bands[1].rate`.
- **Figures compared as numbers.** `"0.150"` and `"0.15"` are the same rate,
  as they are to the engine and the content hash, so respelling one is not a
  change.
- **The source behind each change.** Every change names the source its value
  cites: the `source` of the nearest object around it (a block, a line, a band
  table, an example). The sources themselves are returned alongside, so the
  review can show the URL a changed figure came from.

Pure: it reads two JSON values and returns data. It works on any JSON, so a
draft that doesn't match the schema can still be compared with what came
before it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

from salli.domain.taxrules.common import DECIMAL_PATTERN

ChangeKind = Literal["added", "removed", "changed"]

_DECIMAL = re.compile(DECIMAL_PATTERN)
_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLAIN_VALUE = re.compile(r"^[A-Za-z0-9_.-]+$")

#: The fields that name an item in a list, in the order they are tried.
_IDENTITIES = ("key", "id", "code", "name")


@dataclass(frozen=True)
class Change:
    path: str
    kind: ChangeKind
    #: The JSON value before (None when added) and after (None when removed).
    before: Any
    after: Any
    #: Whether either side is a figure: an amount, rate or limit written as a
    #: decimal string.
    figure: bool
    #: The id of the source the value cites, from the nearest object around it
    #: that has one (in the new document, or the old one for a removal).
    source: str | None


@dataclass(frozen=True)
class DocumentDiff:
    changes: tuple[Change, ...]
    #: Every source a change cites, by id, as the document declares it (the new
    #: document's declaration when both have one).
    sources: Mapping[str, Mapping[str, Any]]


def is_figure(value: object) -> bool:
    return isinstance(value, str) and bool(_DECIMAL.fullmatch(value))


def _same(a: object, b: object) -> bool:
    if is_figure(a) and is_figure(b):
        return Decimal(cast(str, a)) == Decimal(cast(str, b))
    # bool is an int in Python: True == 1 must not hide a change of type.
    if type(a) is not type(b):
        return False
    return a == b


def _field(path: str, name: str) -> str:
    if _PLAIN.fullmatch(name):
        return f"{path}.{name}" if path else name
    return f'{path}["{name}"]'


def _item(path: str, identity: str, value: str) -> str:
    shown = value if _PLAIN_VALUE.fullmatch(value) else '"' + value.replace('"', '\\"') + '"'
    return f"{path}[{identity}={shown}]"


def _identity(old: Sequence[Any], new: Sequence[Any]) -> str | None:
    """The field that names every item of both lists uniquely, if one does."""
    items = [*old, *new]
    if not items or not all(isinstance(i, dict) for i in items):
        return None
    for name in _IDENTITIES:
        if all(isinstance(cast(dict[str, Any], i).get(name), str) for i in items) and all(
            len({cast(dict[str, Any], i)[name] for i in side}) == len(side) for side in (old, new)
        ):
            return name
    return None


class _Walker:
    def __init__(self) -> None:
        self.changes: list[Change] = []

    def add(
        self,
        path: str,
        kind: ChangeKind,
        before: Any,
        after: Any,
        source: str | None,
    ) -> None:
        own = after if kind != "removed" else before
        if isinstance(own, dict) and isinstance(cast(dict[str, Any], own).get("source"), str):
            source = cast(dict[str, Any], own)["source"]
        self.changes.append(
            Change(path or "$", kind, before, after, is_figure(before) or is_figure(after), source)
        )

    def walk(
        self, path: str, old: Any, new: Any, old_source: str | None, new_source: str | None
    ) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            o, n = cast(dict[str, Any], old), cast(dict[str, Any], new)
            old_source = o["source"] if isinstance(o.get("source"), str) else old_source
            new_source = n["source"] if isinstance(n.get("source"), str) else new_source
            for key, value in n.items():
                where = _field(path, key)
                if key not in o:
                    self.add(where, "added", None, value, new_source)
                else:
                    self.walk(where, o[key], value, old_source, new_source)
            for key, value in o.items():
                if key not in n:
                    self.add(_field(path, key), "removed", value, None, old_source)
            return
        if isinstance(old, list) and isinstance(new, list):
            o_list, n_list = cast(list[Any], old), cast(list[Any], new)
            identity = _identity(o_list, n_list)
            if identity is None:
                for i in range(max(len(o_list), len(n_list))):
                    where = f"{path}[{i}]"
                    if i >= len(o_list):
                        self.add(where, "added", None, n_list[i], new_source)
                    elif i >= len(n_list):
                        self.add(where, "removed", o_list[i], None, old_source)
                    else:
                        self.walk(where, o_list[i], n_list[i], old_source, new_source)
                return
            before = {cast(dict[str, Any], i)[identity]: i for i in o_list}
            after = {cast(dict[str, Any], i)[identity]: i for i in n_list}
            for name, value in after.items():
                where = _item(path, identity, name)
                if name not in before:
                    self.add(where, "added", None, value, new_source)
                else:
                    self.walk(where, before[name], value, old_source, new_source)
            for name, value in before.items():
                if name not in after:
                    self.add(_item(path, identity, name), "removed", value, None, old_source)
            return
        before, after = cast(object, old), cast(object, new)
        if not _same(before, after):
            self.add(path, "changed", before, after, new_source)


def _declared_sources(doc: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(doc, dict):
        return {}
    sources = cast(dict[str, Any], doc).get("sources")
    if not isinstance(sources, list):
        return {}
    found: dict[str, Mapping[str, Any]] = {}
    for item in cast(list[Any], sources):
        if isinstance(item, dict) and isinstance(cast(dict[str, Any], item).get("id"), str):
            found[cast(dict[str, Any], item)["id"]] = cast(dict[str, Any], item)
    return found


def diff_documents(old: Any, new: Any) -> DocumentDiff:
    """Every difference from `old` to `new` (two JSON values). With `old` None,
    everything in `new` is added: the review of a first version."""
    walker = _Walker()
    if old is None:
        if isinstance(new, dict):
            for key, value in cast(dict[str, Any], new).items():
                walker.add(_field("", key), "added", None, value, None)
        else:
            walker.add("", "added", None, new, None)
    else:
        walker.walk("", old, new, None, None)
    declared = {**_declared_sources(old), **_declared_sources(new)}
    cited = {c.source for c in walker.changes if c.source is not None}
    return DocumentDiff(
        tuple(walker.changes), {key: declared[key] for key in sorted(cited) if key in declared}
    )
