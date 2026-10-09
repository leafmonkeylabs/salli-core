"""
`salli skills` — install the Claude Code skills that teach an agent to drive
this CLI (src/salli/skills), so "add this month's statement" works from the
user's own agent.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from salli.interfaces.cli.support import console, emit

skills_app = typer.Typer(help="Agent skills for driving the salli CLI")

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def available() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


@skills_app.command("list")
def skills_list():
    """List the bundled skills."""
    names = [p.name for p in available()]
    if emit({"skills": names, "source": str(SKILLS_DIR)}):
        return
    for name in names:
        console.print(name)


@skills_app.command("install")
def skills_install(
    project: bool = typer.Option(
        False, "--project", help="Install into ./.claude/skills instead of ~/.claude/skills"
    ),
    force: bool = typer.Option(False, help="Overwrite skills that are already installed"),
):
    """Copy the skills where Claude Code finds them."""
    target = (Path.cwd() if project else Path.home()) / ".claude" / "skills"
    target.mkdir(parents=True, exist_ok=True)
    installed, kept = [], []
    for skill in available():
        dest = target / skill.name
        if dest.exists() and not force:
            kept.append(skill.name)
            continue
        shutil.copytree(skill, dest, dirs_exist_ok=True)
        installed.append(skill.name)
    emit({"target": str(target), "installed": installed, "kept": kept})
    console.print(f"[green]Installed to {target}:[/green] {', '.join(installed) or 'nothing'}")
    if kept:
        console.print(f"[dim]Already there (use --force to overwrite): {', '.join(kept)}[/dim]")
