# aicontextator.py

import io
import os
from pathlib import Path
import click
import pyperclip
from tqdm import tqdm
import pathspec
import tiktoken

CONTEXT_IGNORE_FILE = '.contextignore'
GIT_IGNORE_FILE = '.gitignore'
DEFAULT_EXCLUDE_PATTERNS = [
    '.git/', 'node_modules/', 'vendor/', '__pycache__/', '.venv/',
    'storage/', 'public/build/', '.idea/', '.vscode/', '.env', '.env.*'
]

def load_ignore_patterns(root_dir: Path) -> list[str]:
    """Loads exclusion patterns from .gitignore, .contextignore, and defaults."""
    patterns = list(DEFAULT_EXCLUDE_PATTERNS)
    for fname in (GIT_IGNORE_FILE, CONTEXT_IGNORE_FILE):
        p = root_dir / fname
        if p.is_file():
            with open(p, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
                cleaned = [line for line in lines if line and not line.startswith('#')]
                patterns.extend(cleaned)
                click.echo(f"Found and loaded '{fname}'.")
    return patterns

def filter_project_files(
    root_dir: Path,
    exclude_cli_patterns: list[str],
    include_extensions: list[str]
) -> list[Path]:
    """
    Applies all exclusion and inclusion rules to return the list
    of files to be included in the context.
    """
    all_patterns = load_ignore_patterns(root_dir)
    all_patterns.extend(exclude_cli_patterns)
    spec = pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)
    
    final_include_extensions = include_extensions or [
        '.py', '.js', '.vue', '.php', '.md', '.json', '.blade.php',
        '.css', '.scss', '.sql', '.sh', 'Dockerfile', '.env.example',
        'composer.json', 'package.json', 'readme.md'
    ]
    
    click.echo("Analyzing files...")
    all_files = [p for p in root_dir.rglob('*') if p.is_file()]
    
    filtered_files = []
    for path in tqdm(all_files, desc="Filtering files"):
        relative_path_str = path.relative_to(root_dir).as_posix()
        if not spec.match_file(relative_path_str) and any(path.name.endswith(ext) for ext in final_include_extensions):
            filtered_files.append(path)
            
    return filtered_files

def generate_tree_view(root_dir: Path, filtered_files: list[Path]) -> str:
    """
    Generates a string representing the tree structure of the filtered files.
    """
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

    tree_lines.append(f"{root_dir.name}.")
    build_tree_lines(tree)
    return "\n".join(tree_lines)


def generate_context(
    root_dir: Path,
    filtered_files: list[Path],
    count_tokens: bool,
    max_tokens: int,
    warn_tokens: int,
    prompt_no_header: bool,
    tree: bool
) -> tuple[list[str], list[int]]:
    """Generates the context string, handling token counting and splitting if needed."""
    if count_tokens:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            _count = lambda text: len(encoding.encode(text, disallowed_special=()))
        except Exception as e:
            click.secho(f"Error initializing tiktoken: {e}. Disabling token counting.", fg='red')
            _count = lambda text: 0
    else:
        _count = lambda text: 0
    
    context_parts = []
    token_counts = []
    current_part_builder = io.StringIO()
    current_token_count = 0
    warn_triggered = False

    if not prompt_no_header:
        header_text = (
            "The following text is a collection of source code files from a software project. "
            "Each file is delimited by a '--- FILE: [filepath] ---' header.\n"
            "Please use this code as the primary source of truth to answer questions about the project.\n\n"
        )
        current_part_builder.write(header_text)
        current_token_count += _count(header_text)

        if tree:
            tree_view = generate_tree_view(root_dir, filtered_files)
            tree_header = f"The project structure is as follows:\n{tree_view}\n\n"
            current_part_builder.write(tree_header)
            current_token_count += _count(tree_header)

    click.echo(f"Found {len(filtered_files)} files to include. Building context...")

    for file_path in tqdm(filtered_files, desc="Processing files"):
        try:
            relative_path = file_path.relative_to(root_dir)
            header = f"--- FILE: {relative_path.as_posix()} ---\n\n"
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_block = header + content + "\n\n"
            block_tokens = _count(file_block)

            if max_tokens and (current_token_count + block_tokens) > max_tokens and current_token_count > 0:
                context_parts.append(current_part_builder.getvalue())
                token_counts.append(current_token_count)
                click.echo(f"\nToken limit of {max_tokens} reached. Creating a new part (Part {len(context_parts) + 1}).")
                current_part_builder = io.StringIO()
                current_token_count = 0
            
            current_part_builder.write(file_block)
            current_token_count += block_tokens

            if warn_tokens and current_token_count > warn_tokens and not warn_triggered:
                click.secho(f"\nWarning: Token threshold of {warn_tokens} exceeded.", fg='yellow')
                warn_triggered = True

        except Exception as e:
            click.secho(f"Error reading {file_path}: {e}", fg='yellow')
            
    if current_part_builder.getvalue():
        context_parts.append(current_part_builder.getvalue())
        token_counts.append(current_token_count)
        
    return context_parts, token_counts


@click.command()
@click.argument('root_dir', default='.', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option('--output', '-o', default='context.txt', help='Output filename. Will be numbered if the output is split.')
@click.option('--exclude', '-e', multiple=True, help='Additional exclusion patterns in .gitignore style.')
@click.option('--ext', multiple=True, help='Extensions to include.')
@click.option('--copy', '-c', is_flag=True, help='Copy the context to the clipboard (only the first part if split).')
@click.option('--count-tokens', is_flag=True, help='Enable token counting.')
@click.option('--max-tokens', type=int, default=None, help='Maximum number of tokens per output part (split if exceeded).')
@click.option('--warn-tokens', type=int, default=None, help='Show a warning when tokens exceed this threshold.')
@click.option('--tree-only', is_flag=True, help='Only show the tree structure of included files and exit.')
@click.option('--tree', is_flag=True, help='Add tree view of the project structure to the context.')
@click.option('--prompt-no-header', is_flag=True, help='Not prepend a meta-prompt header to the context for the AI.')
def cli(root_dir: Path, output: str, exclude: tuple, ext: tuple, copy: bool, count_tokens: bool, max_tokens: int, warn_tokens: int, tree_only: bool, tree: bool, prompt_no_header: bool):
    """
    A tool to generate a context file from a project, with support for token counting.
    """
    click.secho(f"Starting context-builder in directory: {root_dir.resolve()}", fg='green', bold=True)
    
    filtered_files = filter_project_files(root_dir, list(exclude), list(ext))

    if not filtered_files:
        click.secho("\nNo files found for the specified criteria.", fg='yellow')
        return

    if tree_only:
        click.echo("\n--- Tree Structure of Included Files ---")
        tree_view = generate_tree_view(root_dir, filtered_files)
        click.echo(tree_view)
        return

    context_parts, token_counts = generate_context(
        root_dir, filtered_files, count_tokens, max_tokens, warn_tokens, prompt_no_header, tree
    )
    
    total_tokens = sum(token_counts)

    if copy:
        pyperclip.copy(context_parts[0])
        click.secho("\nSuccess! The first part of the context has been copied to the clipboard.", fg='green')
        if len(context_parts) > 1:
            click.secho(f"Warning: The output was split into {len(context_parts)} parts. Only the first part was copied.", fg='yellow')
    else:
        if len(context_parts) == 1:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(context_parts[0])
            click.secho(f"\nSuccess! Context saved to '{output}'", fg='green')
        else:
            base_name, extension = os.path.splitext(output)
            for i, part in enumerate(context_parts):
                part_filename = f"{base_name}-part-{i+1}{extension}"
                with open(part_filename, 'w', encoding='utf-8') as f:
                    f.write(part)
                click.secho(f"Success! Part {i+1} saved to '{part_filename}'", fg='green')

    if count_tokens:
        click.echo("\n--- Token Report ---")
        if len(token_counts) > 1:
            for i, count in enumerate(token_counts):
                click.echo(f"Part {i+1}: ~{count} tokens")
        click.secho(f"Total estimated tokens: ~{total_tokens}", fg='cyan', bold=True)


if __name__ == '__main__':
    cli()

