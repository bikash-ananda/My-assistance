from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .knowledge import contains_secret


EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next", ".runtime"}
SENSITIVE_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"}
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".toml", ".yaml",
    ".yml", ".ini", ".css", ".html", ".sql", ".ps1", ".sh", ".xml", ".csv", ".gitignore",
}

CATALOG = [
    {"id": "files.list", "name": "List project files", "risk_level": 0, "description": "List safe text files under the selected project."},
    {"id": "files.read", "name": "Read a project file", "risk_level": 0, "description": "Read a small text file, excluding credentials and generated folders."},
    {"id": "files.search", "name": "Search project text", "risk_level": 0, "description": "Search safe text files under the selected project."},
    {"id": "git.status", "name": "Git status", "risk_level": 0, "description": "Read Git status without running a shell command."},
    {"id": "system.version", "name": "Python version", "risk_level": 0, "description": "Read the running Python version."},
    {"id": "files.create", "name": "Create a project file", "risk_level": 2, "description": "Create one new text file after owner approval; never overwrite."},
]
BY_ID = {tool["id"]: tool for tool in CATALOG}


class ToolInputError(ValueError):
    pass


def project_root(value: str | None) -> Path:
    if not value:
        raise ToolInputError("Choose a project and set its local folder first.")
    try:
        root = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise ToolInputError("The selected project folder is unavailable.")
    if not root.is_dir():
        raise ToolInputError("The selected project path is not a folder.")
    return root


def safe_path(root: Path, raw: str) -> Path:
    if not raw or len(raw) > 300:
        raise ToolInputError("Enter a relative project file path.")
    candidate = Path(raw)
    if candidate.is_absolute() or any(part in {"..", ""} for part in candidate.parts):
        raise ToolInputError("The path must stay inside the selected project.")
    if any(part.lower() in EXCLUDED or part.lower() in SENSITIVE_NAMES for part in candidate.parts):
        raise ToolInputError("That path is excluded from project tools.")
    resolved = (root / candidate).resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ToolInputError("The path must stay inside the selected project.")
    if any(part.lower() in EXCLUDED or part.lower() in SENSITIVE_NAMES for part in resolved.relative_to(root).parts):
        raise ToolInputError("That path is excluded from project tools.")
    return resolved


def validate(tool_id: str, args: dict) -> dict:
    if tool_id not in BY_ID:
        raise ToolInputError("Unknown tool.")
    rules = {
        "files.list": ({"path"}, set()),
        "files.read": ({"path"}, {"path"}),
        "files.search": ({"query", "path"}, {"query"}),
        "git.status": (set(), set()),
        "system.version": (set(), set()),
        "files.create": ({"path", "content"}, {"path", "content"}),
    }
    allowed, required = rules[tool_id]
    if set(args) - allowed or not required.issubset(args):
        raise ToolInputError("Tool arguments do not match the action preview.")
    clean = dict(args)
    if tool_id == "files.search":
        query = clean["query"]
        if not isinstance(query, str) or not query.strip() or len(query) > 160:
            raise ToolInputError("Search text must be 1 to 160 characters.")
        if "path" in clean and (not isinstance(clean["path"], str) or len(clean["path"]) > 300):
            raise ToolInputError("Search folder is invalid.")
    elif "path" in clean:
        if not isinstance(clean["path"], str):
            raise ToolInputError("File path must be text.")
    if tool_id == "files.create":
        if not isinstance(clean["content"], str) or len(clean["content"]) > 20_000:
            raise ToolInputError("New files are limited to 20,000 characters.")
        if contains_secret(clean["content"]):
            raise ToolInputError("Remove credentials from the proposed file content.")
    return clean


def preview_text(tool_id: str, project_name: str, args: dict) -> str:
    if tool_id == "files.list":
        return f"List safe files in {project_name}/{args.get('path', '.')}"
    if tool_id == "files.read":
        return f"Read {project_name}/{args['path']}"
    if tool_id == "files.search":
        return f"Search {project_name}/{args.get('path', '.')} for {args['query']!r}"
    if tool_id == "git.status":
        return f"Read Git status for {project_name}"
    if tool_id == "system.version":
        return "Read the running Python version"
    return f"Create new file {project_name}/{args['path']} (owner approval required); exact content is stored with this preview ({len(args['content'])} characters)."


def execute(tool_id: str, root: Path | None, args: dict) -> dict:
    if tool_id == "system.version":
        return {"text": sys.version.splitlines()[0]}
    if root is None:
        raise ToolInputError("Select a project folder first.")
    if tool_id == "git.status":
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"], cwd=root, shell=False,
            capture_output=True, text=True, timeout=8, check=False,
        )
        if completed.returncode:
            raise ToolInputError("Git status is unavailable for this project.")
        return {"text": completed.stdout[:16_000]}
    if tool_id == "files.list":
        folder = safe_path(root, args.get("path", "."))
        if not folder.is_dir():
            raise ToolInputError("That folder does not exist.")
        entries = []
        for base, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = [name for name in dirs if name.lower() not in EXCLUDED and not (Path(base) / name).is_symlink()]
            for name in names:
                path = Path(base) / name
                if name.lower() in SENSITIVE_NAMES or path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                entries.append(path.relative_to(root).as_posix())
                if len(entries) >= 300:
                    break
            if len(entries) >= 300:
                break
        return {"files": entries, "truncated": len(entries) == 300}
    if tool_id in {"files.read", "files.create"}:
        path = safe_path(root, args["path"])
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise ToolInputError("Only recognized text files are available to this tool.")
        if tool_id == "files.create":
            if path.exists():
                raise ToolInputError("The destination already exists; this tool never overwrites files.")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as output:
                output.write(args["content"])
            return {"created": path.relative_to(root).as_posix()}
        if not path.is_file() or path.stat().st_size > 256_000:
            raise ToolInputError("The file is unavailable or exceeds the 256 KB read limit.")
        content = path.read_text(encoding="utf-8", errors="strict")
        if contains_secret(content):
            raise ToolInputError("This file appears to contain credentials and was not opened.")
        return {"path": path.relative_to(root).as_posix(), "text": content[:16_000], "truncated": len(content) > 16_000}
    if tool_id == "files.search":
        folder = safe_path(root, args.get("path", "."))
        if not folder.is_dir():
            raise ToolInputError("That folder does not exist.")
        query, hits = args["query"].casefold(), []
        for base, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = [name for name in dirs if name.lower() not in EXCLUDED and not (Path(base) / name).is_symlink()]
            for name in names:
                path = Path(base) / name
                if name.lower() in SENSITIVE_NAMES or path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    if path.stat().st_size > 256_000:
                        continue
                    for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if query in line.casefold() and not contains_secret(line):
                            hits.append({"path": path.relative_to(root).as_posix(), "line": number, "text": line[:300]})
                            if len(hits) >= 50:
                                return {"matches": hits, "truncated": True}
                except OSError:
                    continue
        return {"matches": hits, "truncated": False}
    raise ToolInputError("Tool is not available.")
