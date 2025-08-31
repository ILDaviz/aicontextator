"""
Test suite for the context_builder script.

Setup & Execution Instructions:

1. Install dependencies (including test dependencies):
   uv pip install -e '.[test]'

2. Run the tests with the command defined in pyproject.toml:
   uv run pytest

"""
# tests/test_context_builder.py

import pytest
from pathlib import Path
from click.testing import CliRunner
import tiktoken

# Importa le funzioni e il comando CLI dal tuo script principale
import context_builder

# Fixture per creare una struttura di file temporanea per i test
@pytest.fixture
def project_structure(tmp_path: Path) -> Path:
    """Crea una struttura di progetto fittizia per i test."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.js").write_text("console.log('hello');")
    
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guida")
    
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("// lib")
    
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / "config.json").write_text('{"key": "value"}')
    
    (tmp_path / ".gitignore").write_text(".env\n*.log\ndocs/")
    (tmp_path / ".contextignore").write_text("config.json")
    
    return tmp_path

# --- Test per le funzioni individuali ---

def test_filter_project_files(project_structure: Path):
    """Testa la logica di filtraggio dei file."""
    
    filtered = context_builder.filter_project_files(
        root_dir=project_structure,
        exclude_cli_patterns=["src/utils.js"],
        include_extensions=[]
    )
    
    filtered_names = {p.name for p in filtered}
    
    assert "main.py" in filtered_names
    assert "utils.js" not in filtered_names
    assert "guide.md" not in filtered_names
    assert "lib.js" not in filtered_names
    assert "config.json" not in filtered_names
    assert len(filtered) == 1

def test_generate_tree_view(project_structure: Path):
    """Testa la generazione della vista ad albero. (CORRETTO)"""
    
    files = [
        project_structure / "src" / "main.py",
        project_structure / "config.json"
    ]
    
    tree = context_builder.generate_tree_view(project_structure, files)
    
    expected_tree = (
        f"{project_structure.name}/\n"
        f"├── config.json\n"
        f"└── src\n"  # Corretto: rimosso lo slash
        f"    └── main.py"
    )
    assert tree == expected_tree

def test_generate_context_concatenation(project_structure: Path):
    """Testa la corretta formattazione e concatenazione del contesto."""
    files = [project_structure / "src" / "main.py"]
    
    parts, _ = context_builder.generate_context(
        root_dir=project_structure,
        filtered_files=files,
        count_tokens=False, max_tokens=None, warn_tokens=None, model=""
    )
    
    expected_content = (
        "--- FILE: src/main.py ---\n\n"
        "print('hello')\n\n"
    )
    
    assert len(parts) == 1
    assert parts[0] == expected_content

def test_generate_context_token_splitting(project_structure: Path, mocker):
    """Testa la suddivisione del contesto quando max_tokens è superato. (CORRETTO)"""
    
    # Mock di tiktoken per rendere il test affidabile
    mock_encoding = mocker.Mock()
    # Simula che ogni testo abbia 15 token
    mock_encoding.encode.return_value = [0] * 15
    mocker.patch('tiktoken.get_encoding', return_value=mock_encoding)
    
    files = [
        project_structure / "src" / "main.py",
        project_structure / "src" / "utils.js"
    ]
    
    parts, counts = context_builder.generate_context(
        root_dir=project_structure,
        filtered_files=files,
        count_tokens=True, max_tokens=20, warn_tokens=None, model="gpt-4"
    )
    
    assert len(parts) == 2
    assert len(counts) == 2
    assert "main.py" in parts[0]
    assert "utils.js" in parts[1]

# --- Test per l'interfaccia a riga di comando (CLI) ---

def test_cli_tree_only(project_structure: Path):
    """Testa il flag --tree-only. (CORRETTO)"""
    runner = CliRunner()
    result = runner.invoke(
        context_builder.cli,
        [str(project_structure), "--tree-only"]
    )
    
    assert result.exit_code == 0
    # Corretto: verifica la formattazione esatta
    assert "└── src" in result.output
    assert "main.py" in result.output
    assert "node_modules" not in result.output

def test_cli_file_output(project_structure: Path):
    """Testa la scrittura del contesto su un file. (CORRETTO)"""
    runner = CliRunner()
    output_filename = "output.txt"
    
    with runner.isolated_filesystem() as td:
        # Passiamo il path della nostra struttura come argomento
        result = runner.invoke(
            context_builder.cli,
            [str(project_structure), "-o", output_filename]
        )
        
        assert result.exit_code == 0
        output_file = Path(td) / output_filename
        assert output_file.exists()
        content = output_file.read_text()
        assert "--- FILE: src/main.py ---" in content

def test_cli_copy_to_clipboard(project_structure: Path, mocker):
    """Testa il flag --copy, usando un mock per pyperclip."""
    
    mock_copy = mocker.patch("context_builder.pyperclip.copy")
    
    runner = CliRunner()
    result = runner.invoke(
        context_builder.cli,
        [str(project_structure), "--copy"]
    )
    
    assert result.exit_code == 0
    mock_copy.assert_called_once()
    copied_content = mock_copy.call_args[0][0]
    assert "--- FILE: src/main.py ---" in copied_content

