# src/aicontextator.py

import io
import os
from pathlib import Path
import click
import pyperclip
from tqdm import tqdm
import pathspec
import tiktoken
import json
import hashlib
from typing import Any, Dict, List
from detect_secrets.core.secrets_collection import SecretsCollection
from detect_secrets.settings import default_settings
import questionary
from questionary import Style


# --- Utility Functions ---

_CONTEXT_IGNORE_FILE = ".contextignore"
_GIT_IGNORE_FILE = ".gitignore"

_DEFAULT_EXCLUDE_PATTERNS = [
    ".git/",
    "node_modules/",
    "vendor/",
    "__pycache__/",
    ".venv/",
    "package-lock.json",
    "storage/",
    "public/build/",
    ".idea/",
    ".vscode/",
    ".env",
    ".env.*",
    "*.pyc",
    "*.log",
]


def sha256_text(text: str) -> str:
    """Computes the SHA256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json_output(path: Path, data: Dict[str, Any]) -> None:
    """Writes a dictionary to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Core Logic ---


def build_and_write_json(
    root_path: Path,
    context_parts: List[str],
    token_counts: List[int],
    parts_meta: List[Dict],
    tree_str: str,
    out_path: Path,
):
    """Assembles and writes the final JSON output."""
    warnings = []
    total_file_count = 0
    # Recalculate warnings and file counts from the final metadata
    for i, part_meta in enumerate(parts_meta):
        files_in_part = part_meta.get("files", [])
        total_file_count += sum(
            1 for f in files_in_part if f["path"] != "_aicontext_header_"
        )
        for file_info in files_in_part:
            if file_info.get("potential_secrets"):
                warnings.append(
                    {
                        "part_index": i + 1,
                        "file_path": file_info["path"],
                        "reason": "Potential secrets detected in file",
                        "matches": file_info["potential_secrets"],
                    }
                )

    project_meta = {
        "root": str(root_path.resolve()),
        "file_count": total_file_count,
        "tree": tree_str,
    }

    json_obj = {
        "project": project_meta,
        "total_estimated_tokens": sum(token_counts),
        "warnings": warnings,
        "parts": [],
    }

    for idx, part_meta in enumerate(parts_meta):
        part_info = {
            "index": idx + 1,
            "estimated_tokens": token_counts[idx],
            "files": part_meta.get("files", []),
        }
        json_obj["parts"].append(part_info)

    write_json_output(out_path, json_obj)
    click.secho(f"Success! Wrote structured JSON output to '{out_path}'", fg="green")


def load_ignore_patterns(root_dir: Path) -> list[str]:
    """Loads exclusion patterns from .gitignore, .contextignore, and defaults."""
    patterns = list(_DEFAULT_EXCLUDE_PATTERNS)
    for fname in (_GIT_IGNORE_FILE, _CONTEXT_IGNORE_FILE):
        p = root_dir / fname
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines()]
                    cleaned = [
                        line for line in lines if line and not line.startswith("#")
                    ]
                    patterns.extend(cleaned)
                    click.echo(f"Found and loaded '{fname}'.")
            except Exception as e:
                click.secho(f"Warning: Could not read '{fname}': {e}", fg="yellow")
    return patterns


def filter_project_files(
    root_dir: Path, exclude_cli_patterns: list[str], include_extensions: list[str]
) -> list[Path]:
    """
    Applies all exclusion and inclusion rules to return the list
    of files to be included in the context.
    """
    all_patterns = load_ignore_patterns(root_dir)
    all_patterns.extend(exclude_cli_patterns)
    spec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)

    final_include_extensions = include_extensions or [
        ".py",
        ".js",
        ".vue",
        ".php",
        ".md",
        ".json",
        ".blade.php",
        ".css",
        ".scss",
        ".sql",
        ".sh",
        "Dockerfile",
        ".env.example",
        "composer.json",
        "package.json",
        "readme.md",
    ]

    all_files = [p for p in root_dir.rglob("*") if p.is_file()]

    filtered_files = []
    for path in tqdm(all_files, desc="Filtering files"):
        relative_path_str = path.relative_to(root_dir).as_posix()
        if not spec.match_file(relative_path_str) and any(
            path.name.endswith(ext) for ext in final_include_extensions
        ):
            filtered_files.append(path)

    return filtered_files


def generate_tree_view(root_dir: Path, filtered_files: list[Path]) -> str:
    """Generates a string representing the tree structure of the filtered files."""
    tree = {}
    for path in filtered_files:
        relative_path = path.relative_to(root_dir)
        parts = relative_path.parts
        current_level = tree
        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

    tree_lines = []

    def build_tree_lines(structure, prefix=""):
        items = sorted(structure.keys())
        for i, name in enumerate(items):
            connector = "└── " if i == len(items) - 1 else "├── "
            tree_lines.append(f"{prefix}{connector}{name}")
            if structure[name]:
                extension = "    " if i == len(items) - 1 else "│   "
                build_tree_lines(structure[name], prefix + extension)

    tree_lines.append(f"{root_dir.name}/")
    build_tree_lines(tree)
    return "\n".join(tree_lines)


def generate_context(
    root_dir: Path,
    filtered_files: list[Path],
    secrets_report: dict,
    count_tokens: bool,
    max_tokens: int,
    warn_tokens: int,
    prompt_no_header: bool,
    tree_view: str,
) -> tuple[list[str], list[int], list[dict]]:
    """Generates context parts and their corresponding metadata."""

    if count_tokens:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")

            def _count_tiktoken(text: str) -> int:
                """Counts tokens using the tiktoken library."""
                return len(encoding.encode(text, disallowed_special=()))

            _count = _count_tiktoken
        except Exception as e:
            click.secho(
                f"Error initializing tiktoken: {e}. Disabling token counting.", fg="red"
            )
    else:
        _count = lambda text: 0

    context_parts: List[str] = []
    token_counts: List[int] = []
    parts_meta: List[Dict] = []

    current_part_builder = io.StringIO()
    current_token_count = 0
    current_part_files_meta: List[Dict] = []
    warn_triggered = False

    preliminary_text = ""
    if not prompt_no_header:
        preliminary_text += (
            "The following text is a collection of source code files from a software project. "
            "Each file is delimited by a header line starting with \"--- FILE: [filepath]\".\n"
            "Use only this content as the source of truth when answering questions.\n\n"
        )
    if tree_view:
        preliminary_text += f"The project structure is as follows:\n{tree_view}\n\n"

    preliminary_text += (
        "<<<\n"
    )

    if preliminary_text:
        prelim_tokens = _count(preliminary_text)
        current_part_builder.write(preliminary_text)
        current_token_count += prelim_tokens
        current_part_files_meta.append(
            {
                "path": "_aicontext_header_",
                "size_bytes": len(preliminary_text.encode("utf-8")),
                "sha256": sha256_text(preliminary_text),
                "estimated_tokens": prelim_tokens,
                "potential_secrets": [],
            }
        )

    click.echo(f"Found {len(filtered_files)} files to include. Building context...")

    for file_path in tqdm(filtered_files, desc="Processing files"):
        try:
            relative_path = file_path.relative_to(root_dir)
            header = f"\n--- FILE: {relative_path.as_posix()} ---\n"
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            file_block = header + content + "\n"
            block_tokens = _count(file_block)

            if max_tokens and block_tokens > max_tokens:
                click.secho(
                    f"\nWarning: File '{relative_path}' (~{block_tokens} tokens) is larger than max_tokens ({max_tokens}). It will be placed in a part by itself if necessary.",
                    fg="yellow",
                )

            if (
                max_tokens
                and (current_token_count + block_tokens) > max_tokens
                and current_token_count > 0
            ):
                context_parts.append(current_part_builder.getvalue())
                token_counts.append(current_token_count)
                parts_meta.append({"files": current_part_files_meta})
                click.echo(
                    f"\nToken limit of {max_tokens} reached. Creating a new part (Part {len(context_parts) + 1})."
                )
                current_part_builder = io.StringIO()
                current_token_count = 0
                current_part_files_meta = []

            relative_path_str = relative_path.as_posix()

            potential_secrets = secrets_report.get(relative_path_str, [])

            file_meta = {
                "path": relative_path.as_posix(),
                "size_bytes": file_path.stat().st_size,
                "sha256": sha256_text(content),
                "estimated_tokens": block_tokens,
                "potential_secrets": potential_secrets,
                "content": content,
            }

            current_part_files_meta.append(file_meta)
            current_part_builder.write(file_block)
            current_token_count += block_tokens

            if warn_tokens and current_token_count > warn_tokens and not warn_triggered:
                click.secho(
                    f"\nWarning: Token threshold of {warn_tokens} exceeded.",
                    fg="yellow",
                )
                warn_triggered = True

        except Exception as e:
            click.secho(f"Error reading {file_path}: {e}", fg="yellow")

    current_part_builder.write(">>>\n")

    if current_part_builder.tell() > 0:
        context_parts.append(current_part_builder.getvalue())
        token_counts.append(current_token_count)
        parts_meta.append({"files": current_part_files_meta})

    return context_parts, token_counts, parts_meta


# --- CLI Interface ---


@click.command()
@click.argument(
    "root_dir",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--output", "-o", default="context.txt", help="Output filename.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json).",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Additional exclusion patterns (.gitignore style).",
)
@click.option("--ext", multiple=True, help="File extensions to include (e.g., .py).")
@click.option(
    "--copy", "-c", is_flag=True, help="Copy context to clipboard (text format only)."
)
@click.option(
    "--count-tokens", is_flag=True, help="Enable token counting via tiktoken."
)
@click.option(
    "--max-tokens",
    type=int,
    default=None,
    help="Split output into multiple parts if tokens exceed this.",
)
@click.option(
    "--warn-tokens",
    type=int,
    default=None,
    help="Warn when total tokens exceed this threshold.",
)
# reactive
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Enable interactive mode for file selection.",
)
@click.option(
    "--tree-only",
    is_flag=True,
    help="Only show the project tree of included files and exit.",
)
@click.option(
    "--tree", is_flag=True, help="Prepend a tree view of the project to the context."
)
@click.option(
    "--prompt-no-header",
    is_flag=True,
    help="Do not prepend the default meta-prompt header.",
)
def cli(
    root_dir: Path,
    output: str,
    output_format: str,
    exclude: tuple,
    ext: tuple,
    copy: bool,
    count_tokens: bool,
    max_tokens: int,
    warn_tokens: int,
    interactive: bool,
    tree_only: bool,
    tree: bool,
    prompt_no_header: bool,
):
    """
    A tool to consolidate project files into a single context,
    with support for token counting, JSON output, and secret scanning.
    """

    root_dir = root_dir.resolve()

    click.secho(
        f"Starting context build in: {root_dir.resolve()}", fg="green", bold=True
    )

    filtered_files = filter_project_files(root_dir, list(exclude), list(ext))

    if interactive:
        filtered_files = interactive_file_selector(filtered_files)

    if not filtered_files:
        click.secho("No files found for the specified criteria.", fg="yellow")
        return

    secrets_report = checkSecurityIssue(filtered_files)

    tree_view = (
        generate_tree_view(root_dir, filtered_files) if tree or tree_only else ""
    )

    if tree_only:
        click.echo("--- Tree Structure of Included Files ---")
        click.echo(tree_view)
        return

    context_parts, token_counts, parts_meta = generate_context(
        root_dir,
        filtered_files,
        secrets_report,
        count_tokens,
        max_tokens,
        warn_tokens,
        prompt_no_header,
        tree_view,
    )

    if not context_parts:
        click.secho("Context is empty after processing.", fg="red")
        return

    if output_format == "json":
        output_path = Path(output)

        if output == "context.txt":  # Default output name for text format
            output_path = Path("context.json")
        elif output_path.suffix != ".json":
            output_path = output_path.with_suffix(".json")

        build_and_write_json(
            root_dir, context_parts, token_counts, parts_meta, tree_view, output_path
        )

        if copy:
            click.secho(
                "Warning: --copy is ignored when using --format json.", fg="yellow"
            )
    else:  # text format
        if copy:
            pyperclip.copy(context_parts[0])
            click.secho(
                "Success! The first part of the context has been copied to the clipboard.",
                fg="green",
            )
            if len(context_parts) > 1:
                click.secho(
                    f"Warning: Output was split into {len(context_parts)} parts. Only the first was copied.",
                    fg="yellow",
                )

        if len(context_parts) == 1:
            with open(output, "w", encoding="utf-8") as f:
                f.write(context_parts[0])
            click.secho(f"Success! Context saved to '{output}'", fg="green")

        else:
            base_name, extension = os.path.splitext(output)
            for i, part in enumerate(context_parts):
                part_filename = f"{base_name}-part-{i + 1}{extension}"
                with open(part_filename, "w", encoding="utf-8") as f:
                    f.write(part)
                click.secho(
                    f"Success! Part {i + 1} saved to '{part_filename}'", fg="green"
                )

    if count_tokens:
        click.echo("--- Token Report ---")
        if len(token_counts) > 1:
            for i, count in enumerate(token_counts):
                click.echo(f"Part {i + 1}: ~{count} tokens")
        click.secho(
            f"Total estimated tokens: ~{sum(token_counts)}", fg="cyan", bold=True
        )


def checkSecurityIssue(filtered_files):
    secrets_report = {}

    click.secho("Pre-scanning for secrets with detect-secrets engine...", fg="yellow")

    try:
        secrets = SecretsCollection()
        with default_settings():
            filepaths_to_scan = [str(p) for p in filtered_files]
            secrets.scan_files(*filepaths_to_scan)
            secrets_found = secrets.data

        if secrets_found:
            click.secho(
                f"Scan complete. Populating report from {len(secrets_found)} files with potential secrets...",
                fg="yellow",
            )

            for file_path, secrets_set in secrets_found.items():
                rel_path = file_path

                if rel_path not in secrets_report:
                    secrets_report[rel_path] = []

                for secret in secrets_set:
                    click.secho(
                        f"!!! Potential secret {secret.type} in {rel_path} at line {secret.line_number} - {secret.secret_value}",
                        fg="red",
                    )

                    secrets_report[rel_path].append(
                        {
                            "type": secret.type,
                            "line": secret.line_number,
                        }
                    )
    except Exception as e:
        click.secho(
            f"An error occurred while running detect-secrets: {e}",
            fg="red",
        )

    return secrets_report


def interactive_file_selector(file_list: List[Path]) -> set[Path]:
    """
    Interactive file selector using the questionary library.
    Allows users to select files from a checklist.
    """
    if not file_list:
        return set()

    root_path = Path.cwd()
    try:
        file_map = {str(p.relative_to(root_path)): p for p in file_list}
    except ValueError:
        file_map = {str(p): p for p in file_list}

    sorted_choices = sorted(file_map.keys())

    custom_style = Style(
        [
            ("qmark", "fg:#cc5454 bold"),
            ("question", "bold"),
            ("pointer", "fg:#cc5454 bold"),
            ("highlighted", "fg:#cc5454 bold"),
            ("selected", "fg:#00a600 bold"),
            ("instruction", "fg:#858585 italic"),
            ("text", ""),
        ]
    )

    selected_paths_str = questionary.checkbox(
        "Select the files to add to the context.",
        choices=sorted_choices,
        instruction="Use ↑/↓/j/k to scroll, SPACE to toggle selection, 'a' to select all, ENTER to confirm, ESC to quit",
        style=custom_style,
    ).ask()

    if selected_paths_str is None:
        raise SystemExit("Interactive selection cancelled by the user. Bye!")

    return {file_map[path_str] for path_str in selected_paths_str}


if __name__ == "__main__":
    cli()
