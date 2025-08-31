# context_builder.py

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
    'storage/', 'public/build/', '.idea/', '.vscode/'
]

def load_ignore_patterns(root_dir: Path) -> list[str]:
    patterns = list(DEFAULT_EXCLUDE_PATTERNS)
    gitignore_path = root_dir / GIT_IGNORE_FILE
    if gitignore_path.is_file():
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            patterns.extend(f.readlines())
            click.echo(f"Trovato e caricato '{GIT_IGNORE_FILE}'.")
    contextignore_path = root_dir / CONTEXT_IGNORE_FILE
    if contextignore_path.is_file():
        with open(contextignore_path, 'r', encoding='utf-8') as f:
            patterns.extend(f.readlines())
            click.echo(f"Trovato e caricato '{CONTEXT_IGNORE_FILE}'.")
    return patterns

def filter_project_files(
    root_dir: Path,
    exclude_cli_patterns: list[str],
    include_extensions: list[str]
) -> list[Path]:
    """
    Applica tutte le regole di esclusione e inclusione per restituire la lista
    dei file da includere nel contesto.
    """
    all_patterns = load_ignore_patterns(root_dir)
    all_patterns.extend(exclude_cli_patterns)
    spec = pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)
    
    final_include_extensions = include_extensions or [
        '.py', '.js', '.vue', '.php', '.md', '.json', '.blade.php',
        '.css', '.scss', '.sql', '.sh', 'Dockerfile', '.env.example',
        'composer.json', 'package.json', 'readme.md'
    ]
    
    click.echo("Analisi dei file in corso...")
    all_files = [p for p in root_dir.rglob('*') if p.is_file()]
    
    filtered_files = []
    for path in tqdm(all_files, desc="Filtraggio file"):
        relative_path_str = path.relative_to(root_dir).as_posix()
        if not spec.match_file(relative_path_str) and any(path.name.endswith(ext) for ext in final_include_extensions):
            filtered_files.append(path)
            
    return filtered_files

def generate_tree_view(root_dir: Path, filtered_files: list[Path]) -> str:
    """
    Genera una stringa che rappresenta la struttura ad albero dei file filtrati.
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

    tree_lines.append(f"{root_dir.name}/")
    build_tree_lines(tree)
    return "\n".join(tree_lines)


def generate_context(
    root_dir: Path,
    filtered_files: list[Path],
    count_tokens: bool,
    max_tokens: int,
    warn_tokens: int,
    model: str
) -> tuple[list[str], list[int]]:
    if count_tokens:
        try:
            encoding = tiktoken.get_encoding("cl10k_base")
            click.echo(f"Conteggio token abilitato (stima per '{model}' con 'cl10k_base').")
            _count = lambda text: len(encoding.encode(text, disallowed_special=()))
        except Exception as e:
            click.secho(f"Errore inizializzazione tiktoken: {e}. Disabilito il conteggio.", fg='red')
            _count = lambda text: 0
    else:
        _count = lambda text: 0
    
    context_parts = []
    token_counts = []
    current_part_builder = io.StringIO()
    current_token_count = 0
    warn_triggered = False

    click.echo(f"Trovati {len(filtered_files)} file da includere. Costruendo il contesto...")

    for file_path in tqdm(filtered_files, desc="Elaborazione file"):
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
                click.echo(f"\nLimite di {max_tokens} token raggiunto. Creo una nuova parte (Parte {len(context_parts) + 1}).")
                current_part_builder = io.StringIO()
                current_token_count = 0
            
            current_part_builder.write(file_block)
            current_token_count += block_tokens

            if warn_tokens and current_token_count > warn_tokens and not warn_triggered:
                click.secho(f"\nAttenzione: Superata la soglia di {warn_tokens} token.", fg='yellow')
                warn_triggered = True

        except Exception as e:
            click.secho(f"Errore nel leggere {file_path}: {e}", fg='yellow')
            
    if current_part_builder.getvalue():
        context_parts.append(current_part_builder.getvalue())
        token_counts.append(current_token_count)
        
    return context_parts, token_counts


@click.command()
@click.argument('root_dir', default='.', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option('--output', '-o', default='context.txt', help='Nome del file di output. Verrà numerato se l\'output è diviso.')
@click.option('--exclude', '-e', multiple=True, help='Pattern di esclusione aggiuntivi in stile .gitignore.')
@click.option('--ext', multiple=True, help='Estensioni da includere.')
@click.option('--copy', '-c', is_flag=True, help='Copia il contesto negli appunti (solo la prima parte se diviso).')
@click.option('--count-tokens', is_flag=True, help='Abilita il conteggio dei token.')
@click.option('--max-tokens', type=int, default=None, help='Numero massimo di token per file. Suddivide l\'output se superato.')
@click.option('--warn-tokens', type=int, default=None, help='Mostra un avviso quando i token superano questa soglia.')
@click.option('--model', default='gemini-1.5-pro', help='Modello di riferimento per la stima dei token.')
@click.option('--tree-only', is_flag=True, help='Mostra solo la struttura ad albero dei file inclusi ed esce.')
def cli(root_dir: Path, output: str, exclude: tuple, ext: tuple, copy: bool, count_tokens: bool, max_tokens: int, warn_tokens: int, model: str, tree_only: bool):
    """
    Un tool per generare un file di contesto da un progetto, con supporto per il conteggio dei token.
    """
    click.echo(f"Avvio di context-builder nella cartella: {root_dir.resolve()}")
    
    # MODIFICATO: La logica ora è separata
    filtered_files = filter_project_files(root_dir, list(exclude), list(ext))

    if not filtered_files:
        click.secho("\nNessun file trovato per i criteri specificati.", fg='yellow')
        return

    # NUOVO: Se il flag è attivo, mostra l'albero ed esci
    if tree_only:
        click.echo("\n--- Struttura ad Albero dei File Inclusi ---")
        tree_view = generate_tree_view(root_dir, filtered_files)
        click.echo(tree_view)
        return

    context_parts, token_counts = generate_context(
        root_dir, filtered_files, count_tokens, max_tokens, warn_tokens, model
    )
    
    total_tokens = sum(token_counts)

    # La logica di output (copia/salvataggio) e report token rimane invariata...
    if copy:
        pyperclip.copy(context_parts[0])
        click.secho("\nSuccesso! La prima parte del contesto è stata copiata negli appunti.", fg='green')
        if len(context_parts) > 1:
            click.secho(f"Attenzione: L'output è stato diviso in {len(context_parts)} parti. Solo la prima è stata copiata.", fg='yellow')
    else:
        if len(context_parts) == 1:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(context_parts[0])
            click.secho(f"\nSuccesso! Contesto salvato in '{output}'", fg='green')
        else:
            base_name, extension = os.path.splitext(output)
            for i, part in enumerate(context_parts):
                part_filename = f"{base_name}-part-{i+1}{extension}"
                with open(part_filename, 'w', encoding='utf-8') as f:
                    f.write(part)
                click.secho(f"Successo! Parte {i+1} salvata in '{part_filename}'", fg='green')

    if count_tokens:
        click.echo("\n--- Report Token ---")
        if len(token_counts) > 1:
            for i, count in enumerate(token_counts):
                click.echo(f"Parte {i+1}: ~{count} token")
        click.secho(f"Token totali stimati: ~{total_tokens}", fg='cyan', bold=True)


if __name__ == '__main__':
    cli()