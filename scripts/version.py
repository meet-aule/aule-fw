#!/usr/bin/env python3
"""Read, check and change Aule's firmware version, and cut releases.

Only this tool writes version numbers; RELEASING.md explains the rules.

  current            print the version
  check              exit 1 unless the version's copies and CHANGELOG.md agree
  set X.Y.Z          write the version everywhere it is kept
  next               print the next version, from the commits since the last release tag
  notes [X.Y.Z]      print a changelog section for the commits since the last release tag
  section [X.Y.Z]    print one version's section of CHANGELOG.md, heading included
  release [X.Y.Z]    set the version, add its section to CHANGELOG.md and commit both on a
                     new branch release/X.Y.Z; with --push, also push it and open the PR
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

# What is specific to this repository.
REPOSITORY = "meet-aule/aule-fw"
DEFAULT_BRANCH = "aule"
# Upstream xiaozhi-esp32 already tags its own releases v<version>.
TAG_PREFIX = "aule-v"
# Each place that keeps the version: a file, and a pattern for the one line holding it. The
# first is the source and any others are copies. The firmware has no copies: the build reads
# PROJECT_VER into the application descriptor.
VERSION_FILES = [
    ("CMakeLists.txt", r'^set\(PROJECT_VER "(?P<version>[^"]*)"\)  # x-aule-version$'),
]

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "origin"
CHANGELOG = "CHANGELOG.md"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"

# Digits only, without leading zeros. The device's update check compares versions as numbers,
# so a pre-release or build suffix would stop updates.
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
HEADING = re.compile(
    r"## (?:\[(?P<linked>[^\]]*)\]\((?P<url>[^)\s]*)\)|(?P<plain>\S+)) \((?P<date>[^)]*)\)"
)
# From Python 3.11, date.fromisoformat also reads 20261125 and 2026-W48-2, so the shape comes
# first.
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
BREAKING = "⚠ BREAKING CHANGES"
# Changelog sections in their fixed order, and the commit types listed in each.
SECTIONS = [
    ("Features", ("feat",)),
    ("Bug Fixes", ("fix",)),
    ("Performance", ("perf",)),
    ("Reverts", ("revert",)),
    ("Documentation", ("docs",)),
    ("Chores", ("chore", "refactor", "build", "ci", "test", "style")),
]
SECTION_NAMES = [BREAKING] + [name for name, _ in SECTIONS]
COMMIT_TYPES = {kind for _, kinds in SECTIONS for kind in kinds}
# A squash merge's subject is the PR title followed by " (#N)".
COMMIT = re.compile(
    r"(?P<kind>[a-z]+)(?:\((?P<scope>[^()]+)\))?(?P<bang>!)?: (?P<subject>.+?)"
    r"(?: \(#(?P<pr>[0-9]+)\))?"
)
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)


class Change(NamedTuple):
    kind: str
    scope: Optional[str]
    subject: str
    pr: Optional[str]
    breaking: bool


class Entry(NamedTuple):
    version: str
    url: Optional[str]
    line: int
    lines: list  # (line number, text) for each line under the heading


def parse_version(text: str) -> tuple:
    match = SEMVER.fullmatch(text)
    if not match:
        raise ValueError(f"{text!r} is not a version like 1.2.3 (digits only, no suffix)")
    return tuple(int(part) for part in match.groups())


def tag_name(version: str) -> str:
    return TAG_PREFIX + version


def compare_url(older: str, newer: str) -> str:
    return f"{REPOSITORY_URL}/compare/{tag_name(older)}...{tag_name(newer)}"


################################################################################
# The version and its copies
################################################################################


def read_versions(root: Path = ROOT) -> list:
    """Return (file, version) for each place in VERSION_FILES, the source first."""
    found = []
    for path, pattern in VERSION_FILES:
        matches = re.findall(pattern, (root / path).read_text(encoding="utf-8"), re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(
                f"{path}: expected one version line marked x-aule-version, found {len(matches)}"
            )
        found.append((path, matches[0]))
    return found


def current_version(root: Path = ROOT) -> str:
    return read_versions(root)[0][1]


def set_version(root: Path, version: str) -> list:
    """Write the version into every place that keeps it; return (file, old, new) for each."""
    parse_version(version)
    changed = []
    for (path, pattern), (_, old) in zip(VERSION_FILES, read_versions(root)):
        file = root / path
        text = file.read_text(encoding="utf-8")
        match = re.search(pattern, text, re.MULTILINE)
        start, end = match.span("version")
        file.write_text(text[:start] + version + text[end:], encoding="utf-8")
        changed.append((path, old, version))
    return changed


################################################################################
# CHANGELOG.md
################################################################################


def parse_changelog(text: str) -> tuple:
    """Split CHANGELOG.md into its versions, newest first, and list what is malformed."""
    lines = text.splitlines()
    errors = []
    if not lines or lines[0] != "# Changelog":
        errors.append(f"{CHANGELOG}: the first line must be '# Changelog'")
    entries = []
    for number, line in enumerate(lines[1:], start=2):
        if line.startswith("## "):
            match = HEADING.fullmatch(line)
            # None without a match, and empty for a link without text, as in '## [](url)'.
            version = match and (match["linked"] or match["plain"])
            if not version or not SEMVER.fullmatch(version):
                errors.append(
                    f"{CHANGELOG}:{number}: write version headings as '## X.Y.Z (YYYY-MM-DD)' "
                    "or '## [X.Y.Z](compare link) (YYYY-MM-DD)'"
                )
                continue
            if not is_date(match["date"]):
                errors.append(f"{CHANGELOG}:{number}: {match['date']!r} is not a YYYY-MM-DD date")
            entries.append(Entry(version, match["url"], number, []))
        elif line.startswith("# "):
            errors.append(f"{CHANGELOG}:{number}: only the first line is a '# ' heading")
        elif entries:
            entries[-1].lines.append((number, line))
        elif line.strip():
            errors.append(f"{CHANGELOG}:{number}: only blank lines go before the first version")
    if not entries:
        errors.append(f"{CHANGELOG}: no version headings")

    for newer, older in zip(entries, entries[1:]):
        if parse_version(newer.version) <= parse_version(older.version):
            errors.append(
                f"{CHANGELOG}:{older.line}: {older.version} must be older than {newer.version} "
                "above it: newest first, each version once"
            )
    for index, entry in enumerate(entries):
        if entry.url is None:
            pass
        elif index + 1 == len(entries):
            errors.append(f"{CHANGELOG}:{entry.line}: the oldest version has nothing to compare")
        elif entry.url != compare_url(entries[index + 1].version, entry.version):
            expected = compare_url(entries[index + 1].version, entry.version)
            errors.append(f"{CHANGELOG}:{entry.line}: the link should be {expected}")
        errors += check_entry(entry)
    return entries, errors


def is_date(text: str) -> bool:
    """True for a real day written YYYY-MM-DD, and for nothing else."""
    if not DATE.fullmatch(text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def check_entry(entry: Entry) -> list:
    """Check one version: known sections in order, each listing at least one change."""
    errors = []
    bullets = 0
    section = None  # [name, line number, bullets]
    seen = []

    def close_section():
        if section and not section[2]:
            errors.append(f"{CHANGELOG}:{section[1]}: the {section[0]} section is empty")

    for number, line in entry.lines:
        if line.startswith("### "):
            close_section()
            name = line[4:]
            if name not in SECTION_NAMES:
                errors.append(
                    f"{CHANGELOG}:{number}: unknown section {name!r}; use "
                    + ", ".join(SECTION_NAMES)
                )
            elif seen and SECTION_NAMES.index(name) <= SECTION_NAMES.index(seen[-1]):
                errors.append(
                    f"{CHANGELOG}:{number}: sections go in this order, each once: "
                    + ", ".join(SECTION_NAMES)
                )
            else:
                seen.append(name)
            section = [name, number, 0]
        elif line.rstrip() in ("*", "-"):
            errors.append(f"{CHANGELOG}:{number}: empty bullet")
        elif line.startswith("- "):
            errors.append(f"{CHANGELOG}:{number}: start bullets with '* '")
        elif line.startswith("* "):
            bullets += 1
            if section:
                section[2] += 1
    close_section()
    if not bullets:
        errors.append(f"{CHANGELOG}:{entry.line}: {entry.version} lists no changes")
    return errors


def check(root: Path = ROOT) -> list:
    """Return what is wrong with the version's copies and CHANGELOG.md; empty when they agree."""
    try:
        versions = read_versions(root)
    except (OSError, ValueError) as error:
        return [str(error)]
    errors = []
    source_path, source = versions[0]
    if not SEMVER.fullmatch(source):
        errors.append(f"{source_path}: {source!r} is not a version like 1.2.3 (digits only)")
    for path, version in versions[1:]:
        if version != source:
            errors.append(f"{path}: {version} disagrees with {source} in {source_path}")
    try:
        text = (root / CHANGELOG).read_text(encoding="utf-8")
    except OSError as error:
        return errors + [f"{CHANGELOG}: {error.strerror}"]
    entries, changelog_errors = parse_changelog(text)
    errors += changelog_errors
    if entries and entries[0].version != source:
        errors.append(
            f"{CHANGELOG}: the newest version is {entries[0].version}, "
            f"but {source_path} says {source}"
        )
    return errors


def changelog_section(text: str, version: str) -> str:
    """Return one version's section, heading included, as a GitHub Release body. The heading
    carries the date and the compare link, as in aule-sw's and aule-store's releases."""
    for entry in parse_changelog(text)[0]:
        if entry.version == version:
            heading = text.splitlines()[entry.line - 1]
            body = "\n".join(line for _, line in entry.lines).strip("\n")
            return f"{heading}\n\n{body}\n"
    raise ValueError(f"{CHANGELOG} has no section for {version}")


def add_to_changelog(root: Path, section: str) -> None:
    """Put a new version's section first, right under the '# Changelog' line."""
    file = root / CHANGELOG
    header, _, rest = file.read_text(encoding="utf-8").partition("\n")
    rest = rest.lstrip("\n")
    file.write_text(f"{header}\n\n{section}\n{rest}", encoding="utf-8")


################################################################################
# Commits
################################################################################


def parse_commit(subject: str, body: str = "") -> Optional[Change]:
    """Read a Conventional Commit; None for any other subject and for release commits."""
    match = COMMIT.fullmatch(subject.strip())
    if not match or match["kind"] not in COMMIT_TYPES:
        return None
    # A release PR is titled with its version alone, as pr-title.yml allows only for it. Other
    # chore(release) changes, such as one to the release workflow, are listed like any chore.
    if (match["kind"] == "chore" and match["scope"] == "release"
            and SEMVER.fullmatch(match["subject"])):
        return None
    breaking = bool(match["bang"] or BREAKING_FOOTER.search(body))
    return Change(match["kind"], match["scope"], match["subject"], match["pr"], breaking)


def next_version(current: str, changes: list) -> str:
    """Before 1.0, a breaking change bumps the minor, and feat or fix the patch. From 1.0 on,
    a breaking change bumps the major, feat the minor and fix the patch. Reaching 1.0.0 is
    never automatic. Without any of them, the version stays."""
    major, minor, patch = parse_version(current)
    breaking = any(change.breaking for change in changes)
    kinds = {change.kind for change in changes}
    if major == 0:
        if breaking:
            return f"0.{minor + 1}.0"
        if kinds & {"feat", "fix"}:
            return f"0.{minor}.{patch + 1}"
    elif breaking:
        return f"{major + 1}.0.0"
    elif "feat" in kinds:
        return f"{major}.{minor + 1}.0"
    elif "fix" in kinds:
        return f"{major}.{minor}.{patch + 1}"
    return current


def format_notes(version: str, previous: Optional[str], changes: list,
                 date: datetime.date) -> str:
    """Write a version's CHANGELOG.md section, heading included."""
    parse_version(version)
    if previous:
        heading = f"## [{version}]({compare_url(previous, version)}) ({date.isoformat()})"
    else:
        heading = f"## {version} ({date.isoformat()})"
    groups = [(BREAKING, [change for change in changes if change.breaking])]
    groups += [
        (name, [c for c in changes if not c.breaking and c.kind in kinds])
        for name, kinds in SECTIONS
    ]
    parts = [heading]
    for name, members in groups:
        if not members:
            continue
        # Scoped changes first, sorted by scope, then the rest.
        members = sorted(members, key=lambda c: (c.scope is None, c.scope or "",
                                                 c.subject.casefold()))
        parts.append(f"### {name}")
        parts.append("\n".join(bullet(change) for change in members))
    if len(parts) == 1:
        raise ValueError("nothing to list: no Conventional Commits since the last release")
    return "\n\n".join(parts) + "\n"


def bullet(change: Change) -> str:
    text = f"**{change.scope}:** {change.subject}" if change.scope else change.subject
    if change.pr:
        text += f" ([#{change.pr}]({REPOSITORY_URL}/pull/{change.pr}))"
    return f"* {text}"


################################################################################
# Git and GitHub
################################################################################


def run(root: Path, *command: str, stdin: Optional[str] = None) -> str:
    result = subprocess.run(command, cwd=root, input=stdin, capture_output=True,
                            encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def last_release(root: Path) -> tuple:
    """Return the newest release tag in HEAD's history, and its version."""
    released = []
    for tag in run(root, "git", "tag", "--list", f"{TAG_PREFIX}*", "--merged", "HEAD").split():
        version = tag[len(TAG_PREFIX):]
        if SEMVER.fullmatch(version):
            released.append((parse_version(version), tag, version))
    if not released:
        raise RuntimeError(
            f"no {TAG_PREFIX}X.Y.Z tag in this branch's history; fetch the tags with "
            f"'git fetch --tags {REMOTE}', or, if GitHub has none either, tag the first "
            "release as RELEASING.md says"
        )
    _, tag, version = max(released)
    return tag, version


def changes_since(root: Path, tag: str) -> list:
    log = run(root, "git", "log", "--first-parent", "--format=%s%x1f%b%x1e", f"{tag}..HEAD")
    changes = []
    for record in log.split("\x1e"):
        subject, _, body = record.strip("\n").partition("\x1f")
        change = parse_commit(subject, body)
        if change:
            changes.append(change)
    return changes


def release(root: Path, version: Optional[str], push: bool) -> None:
    errors = check(root)
    if errors:
        raise RuntimeError("fix these first:\n" + "\n".join(errors))
    # Start from the default branch exactly as it is on GitHub, with every release tag, so
    # that the notes list the right commits.
    if run(root, "git", "status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("commit or stash your changes first")
    branch = run(root, "git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != DEFAULT_BRANCH:
        raise RuntimeError(f"switch to {DEFAULT_BRANCH} first (this is {branch})")
    run(root, "git", "fetch", "--quiet", "--tags", REMOTE)
    remote_head = run(root, "git", "rev-parse", f"{REMOTE}/{DEFAULT_BRANCH}").strip()
    if run(root, "git", "rev-parse", "HEAD").strip() != remote_head:
        raise RuntimeError(f"bring {DEFAULT_BRANCH} up to date with {REMOTE} first")

    tag, released = last_release(root)
    changes = changes_since(root, tag)
    version = version or next_version(released, changes)
    current = current_version(root)
    if parse_version(version) <= max(parse_version(current), parse_version(released)):
        raise RuntimeError(
            f"nothing to release: {version} is not newer than {current} (last tag {tag}); "
            "name a newer version to release anyway"
        )
    section = format_notes(version, released, changes, datetime.date.today())

    name = f"release/{version}"
    run(root, "git", "switch", "--quiet", "-c", name)
    set_version(root, version)
    add_to_changelog(root, section)
    errors = check(root)
    if errors:
        raise RuntimeError(f"the uncommitted release on {name} fails the check:\n"
                           + "\n".join(errors))
    run(root, "git", "add", "--", CHANGELOG, *(path for path, _ in VERSION_FILES))
    run(root, "git", "commit", "--quiet", "-m", f"chore(release): {version}")
    print(f"Committed chore(release): {version} on {name}.")
    if not push:
        print(f"Next: git push -u {REMOTE} {name}, then open a PR into {DEFAULT_BRANCH} titled "
              f"'chore(release): {version}' with the new {CHANGELOG} section as its description.")
        return
    run(root, "git", "push", "--quiet", "-u", REMOTE, name)
    print(run(root, "gh", "pr", "create", "--repo", REPOSITORY, "--base", DEFAULT_BRANCH,
              "--head", name, "--title", f"chore(release): {version}", "--body-file", "-",
              stdin=section).strip())


################################################################################
# Command line
################################################################################


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("current")
    commands.add_parser("check")
    commands.add_parser("set").add_argument("version")
    commands.add_parser("next")
    commands.add_parser("notes").add_argument("version", nargs="?")
    commands.add_parser("section").add_argument("version", nargs="?")
    release_command = commands.add_parser("release")
    release_command.add_argument("version", nargs="?")
    release_command.add_argument("--push", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "current":
            print(current_version())
        elif args.command == "check":
            errors = check()
            if errors:
                print("\n".join(errors), file=sys.stderr)
                sys.exit(1)
            files = " and ".join(path for path, _ in VERSION_FILES)
            print(f"{current_version()}: {files} and {CHANGELOG} agree")
        elif args.command == "set":
            for path, old, new in set_version(ROOT, args.version):
                print(f"{path}: {old} -> {new}")
        elif args.command == "next":
            tag, released = last_release(ROOT)
            changes = changes_since(ROOT, tag)
            version = next_version(released, changes)
            if version == released:
                print(f"No feat, fix or breaking change since {tag}.", file=sys.stderr)
            print(version)
        elif args.command == "notes":
            tag, released = last_release(ROOT)
            changes = changes_since(ROOT, tag)
            version = args.version or next_version(released, changes)
            print(format_notes(version, released, changes, datetime.date.today()), end="")
        elif args.command == "section":
            text = (ROOT / CHANGELOG).read_text(encoding="utf-8")
            print(changelog_section(text, args.version or current_version()), end="")
        elif args.command == "release":
            release(ROOT, args.version, args.push)
    except (OSError, RuntimeError, ValueError) as error:
        sys.exit(f"version.py: {error}")


if __name__ == "__main__":
    main()
