#!/usr/bin/env python3

import os
import re
from pathlib import Path


def parse_version(tag: str) -> tuple[int, ...]:
    version_str = tag.lstrip("v")
    return tuple(map(int, version_str.strip().split(".")))


def main():
    github_tag = os.environ.get("GITHUB_REF_NAME")
    if not github_tag:
        print("::error::GITHUB_REF_NAME not set.")
        exit(1)
    if not re.fullmatch(r"v\d+\.\d+\.\d+", github_tag):
        print(
            f"::error::Invalid GITHUB_REF_NAME '{github_tag}'. Expected format: vX.Y.Z"
        )
        exit(1)

    major, minor, patch = parse_version(github_tag)
    next_version_str = f"{major}.{minor + 1}.0"

    print(f"Bumping pyproject.toml to {next_version_str}")

    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    pyproject_content = pyproject_path.read_text()
    updated_pyproject = re.sub(
        r'version\s*=\s*"\d+\.\d+\.\d+"',
        f'version = "{next_version_str}"',
        pyproject_content,
    )
    pyproject_path.write_text(updated_pyproject)
    print(f"✔️ Bumped pyproject.toml version to {next_version_str}")


if __name__ == "__main__":
    main()
