"""
Extensions — how a deployment adds to Salli without Salli knowing about it.

An extension is a Python package that registers an `ExtensionSpec` under the
`salli.extensions` entry-point group:

    [project.entry-points."salli.extensions"]
    example = "example_package.extension:spec"

A spec has two halves, because they are needed at different times:

- Static parts — API routers and CLI command groups. They are mounted when the
  FastAPI app or the `salli` CLI is created, before any service exists; their
  handlers reach services through the usual request/command plumbing.
- `build(ctx)` — returns an `Extension` with the runtime parts: a `UsageMeter`,
  an `EntitlementPolicy`, extra services, and purgers for its own per-user
  tables. Called by `build_services`, before Salli's own services are built so
  the meter and policy can be injected into them.

Installing a package is not enough to activate it. Only the extensions named in
`SALLI_EXTENSIONS` (comma-separated) are loaded, and a named extension that is
missing or fails to load stops startup. That is deliberate: a deployment that
relies on an extension to meter usage must never come up silently without it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Any, cast

from salli.application.defaults import FullAccess, UnmeteredUsage
from salli.application.ports import EntitlementPolicy, UsageMeter

ENTRY_POINT_GROUP = "salli.extensions"

#: Deletes one user's rows from an extension's own tables, inside the same
#: database session (and so the same transaction) as Salli's account deletion.
#: Receives the SQLAlchemy `AsyncSession` and the user id; returns
#: {table_name: rows_deleted}.
UserDataPurger = Callable[[Any, str], Awaitable[dict[str, int]]]

#: Returns one user's data from an extension's own tables, for "export my
#: data". Receives the user id; returns top-level keys merged into the export.
UserDataExporter = Callable[[str], Awaitable[dict[str, Any]]]


class ExtensionError(RuntimeError):
    """An enabled extension could not be loaded, or two extensions conflict."""


@dataclass(frozen=True)
class ExtensionContext:
    """What `ExtensionSpec.build` may build on. Everything here is already
    constructed."""

    settings: Any
    session_factory: Any
    uow_factory: Callable[[], Any]
    llm_credentials: Any
    storage: Any = None
    #: Every enabled extension's purgers. Live: empty while `build` runs, filled
    #: once all extensions are built. An extension that opens its own units of
    #: work over `session_factory` passes this along so account deletion through
    #: them still reaches every extension's tables.
    user_data_purgers: Sequence[UserDataPurger] = ()


@dataclass
class Extension:
    """The runtime half of an extension."""

    name: str
    usage_meter: UsageMeter | None = None
    entitlements: EntitlementPolicy | None = None
    #: Extra services, reachable as `services.extensions.services[key]`.
    services: dict[str, Any] = field(default_factory=dict[str, Any])
    user_data_purgers: list[UserDataPurger] = field(default_factory=list[UserDataPurger])
    user_data_exporters: list[UserDataExporter] = field(default_factory=list[UserDataExporter])


@dataclass(frozen=True)
class ExtensionSpec:
    """What an entry point resolves to."""

    name: str
    build: Callable[[ExtensionContext], Extension]
    #: FastAPI `APIRouter`s, mounted after Salli's own routers.
    api_routers: tuple[Any, ...] = ()
    #: (name, typer.Typer) pairs, added to the `salli` CLI as sub-commands.
    cli_groups: tuple[tuple[str, Any], ...] = ()
    #: The extension's own Alembic script directory, if it owns tables. Its
    #: env.py must use its own version table (see salli.migrations.support).
    #: `salli db upgrade` runs it after Salli's.
    migrations: str | None = None


@dataclass(frozen=True)
class Contributions:
    """Every enabled extension's runtime contributions, merged, with Salli's
    defaults filled in where no extension provided one."""

    usage_meter: UsageMeter
    entitlements: EntitlementPolicy
    services: dict[str, Any]
    user_data_purgers: list[UserDataPurger]
    user_data_exporters: list[UserDataExporter] = field(default_factory=list[UserDataExporter])
    names: tuple[str, ...] = ()


def parse_enabled(raw: str | None) -> list[str]:
    """`"a, b,,c"` -> `["a", "b", "c"]`, preserving order, dropping repeats."""
    names: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def _discover() -> Iterable[EntryPoint]:
    return entry_points(group=ENTRY_POINT_GROUP)


def load_specs(
    names: list[str],
    *,
    discover: Callable[[], Iterable[EntryPoint]] = _discover,
) -> list[ExtensionSpec]:
    """Import each named extension's spec, in order. Raises ExtensionError on
    the first one that is not installed, fails to import, or is not a spec."""
    if not names:
        return []
    available = {ep.name: ep for ep in discover()}
    specs: list[ExtensionSpec] = []
    for name in names:
        ep = available.get(name)
        if ep is None:
            installed = ", ".join(sorted(available)) or "none"
            raise ExtensionError(
                f"Extension {name!r} is enabled in SALLI_EXTENSIONS but not installed "
                f"(installed: {installed})."
            )
        try:
            # `object`: a third-party entry point can resolve to anything.
            spec: object = ep.load()
        except Exception as exc:
            raise ExtensionError(f"Extension {name!r} failed to import: {exc}") from exc
        if not isinstance(spec, ExtensionSpec):
            raise ExtensionError(
                f"Extension {name!r} resolved to {type(spec).__name__}, not an ExtensionSpec."
            )
        specs.append(spec)
    return specs


def enabled_specs(settings: Any) -> list[ExtensionSpec]:
    """The specs named in `settings.salli_extensions`."""
    return load_specs(parse_enabled(settings.salli_extensions))


def build_extensions(specs: list[ExtensionSpec], ctx: ExtensionContext) -> list[Extension]:
    """Build each spec's runtime half. Raises ExtensionError on the first failure."""
    built: list[Extension] = []
    for spec in specs:
        try:
            # `object`, not Extension: a third-party build can return anything,
            # whatever its own annotation claims.
            build = cast(Callable[[ExtensionContext], object], spec.build)
            extension = build(ctx)
        except Exception as exc:
            raise ExtensionError(f"Extension {spec.name!r} failed to build: {exc}") from exc
        if not isinstance(extension, Extension):
            raise ExtensionError(
                f"Extension {spec.name!r} built {type(extension).__name__}, not an Extension."
            )
        built.append(extension)
    return built


def combine(extensions: list[Extension]) -> Contributions:
    """Merge runtime contributions. A meter or a policy may come from at most one
    extension — two would leave it ambiguous which one is in force."""
    meter: tuple[str, UsageMeter] | None = None
    policy: tuple[str, EntitlementPolicy] | None = None
    services: dict[str, Any] = {}
    purgers: list[UserDataPurger] = []
    exporters: list[UserDataExporter] = []

    for ext in extensions:
        if ext.usage_meter is not None:
            if meter is not None:
                raise ExtensionError(f"Both {meter[0]!r} and {ext.name!r} provide a usage meter.")
            meter = (ext.name, ext.usage_meter)
        if ext.entitlements is not None:
            if policy is not None:
                raise ExtensionError(
                    f"Both {policy[0]!r} and {ext.name!r} provide an entitlement policy."
                )
            policy = (ext.name, ext.entitlements)
        for key, service in ext.services.items():
            if key in services:
                raise ExtensionError(f"Service {key!r} is provided by two extensions.")
            services[key] = service
        purgers.extend(ext.user_data_purgers)
        exporters.extend(ext.user_data_exporters)

    return Contributions(
        usage_meter=meter[1] if meter else UnmeteredUsage(),
        entitlements=policy[1] if policy else FullAccess(),
        services=services,
        user_data_purgers=purgers,
        user_data_exporters=exporters,
        names=tuple(ext.name for ext in extensions),
    )
