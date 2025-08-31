"""
Test suite for the aicontextator script.

Setup & Execution Instructions:

1. Install dependencies (including test dependencies):
   uv pip install -e '.[test]'

2. Run the tests:
   uv run pytest

"""
# tests/test_aicontextator.py

import pytest
from pathlib import Path
from click.testing import CliRunner

# Import functions and the CLI command from your main script
import aicontextator

# Fixture to create a temporary file structure for tests
@pytest.fixture
def project_structure(tmp_path: Path) -> Path:
    """Creates a mock project structure for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.js").write_text("console.log('hello');")
    
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide")
    
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("// lib")
    
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / "config.json").write_text('{"key": "value"}')
    
    (tmp_path / ".gitignore").write_text(".env\n*.log\ndocs/")
    (tmp_path / ".contextignore").write_text("config.json")
    
    return tmp_path

def test_filter_project_files(project_structure: Path):
    """Tests the file filtering logic."""
    
    filtered = aicontextator.filter_project_files(
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
    """Tests the generation of the tree view."""
    
    files = [
        project_structure / "src" / "main.py",
        project_structure / "config.json"
    ]
    
    tree = aicontextator.generate_tree_view(project_structure, files)
    
    expected_tree = (
        f"{project_structure.name}/\n"
        f"├── config.json\n"
        f"└── src\n"
        f"    └── main.py"
    )
    assert tree == expected_tree

def test_generate_context_concatenation(project_structure: Path):
    """Tests the correct formatting and concatenation of the context."""
    files = [project_structure / "src" / "main.py"]
    
    parts, _ = aicontextator.generate_context(
        root_dir=project_structure,
        filtered_files=files,
        count_tokens=False,
        max_tokens=None, 
        warn_tokens=None, 
        prompt_no_header=True
    )
    
    expected_content = (
        "--- FILE: src/main.py ---\n\n"
        "print('hello')\n\n"
    )
    
    assert len(parts) == 1
    assert parts[0] == expected_content

def test_generate_context_token_splitting(project_structure: Path, mocker):
    """Tests context splitting when max_tokens is exceeded."""
    
    mock_encoding = mocker.Mock()
    # Simulate each text has 15 tokens
    mock_encoding.encode.return_value = [0] * 15
    mocker.patch('tiktoken.get_encoding', return_value=mock_encoding)
    
    files = [
        project_structure / "src" / "main.py",
        project_structure / "src" / "utils.js"
    ]
    
    parts, counts = aicontextator.generate_context(
        root_dir=project_structure,
        filtered_files=files,
        count_tokens=True, 
        max_tokens=35, 
        warn_tokens=None, 
        prompt_no_header=False
    )
    
    assert len(parts) == 2
    assert len(counts) == 2
    assert "main.py" in parts[0]
    assert "utils.js" in parts[1]
    assert parts[0].startswith("The following text")

def test_cli_tree_only(project_structure: Path):
    """Tests the --tree-only flag."""
    runner = CliRunner()
    result = runner.invoke(
        aicontextator.cli,
        [str(project_structure), "--tree-only"]
    )
    
    assert result.exit_code == 0
    assert "└── src" in result.output
    assert "main.py" in result.output
    assert "node_modules" not in result.output

def test_cli_file_output(project_structure: Path):
    """Tests writing the context to a file."""
    runner = CliRunner()
    output_filename = "output.txt"
    
    with runner.isolated_filesystem() as td:
        result = runner.invoke(
            aicontextator.cli,
            [str(project_structure), "-o", output_filename]
        )
        
        assert result.exit_code == 0
        output_file = Path(td) / output_filename
        assert output_file.exists()
        content = output_file.read_text()
        assert "--- FILE: src/main.py ---" in content

def test_cli_copy_to_clipboard(project_structure: Path, mocker):
    """Tests the --copy flag, using a mock for pyperclip."""
    
    mock_copy = mocker.patch("aicontextator.pyperclip.copy")
    
    runner = CliRunner()
    result = runner.invoke(
        aicontextator.cli,
        [str(project_structure), "--copy"]
    )
    
    assert result.exit_code == 0
    mock_copy.assert_called_once()
    copied_content = mock_copy.call_args[0][0]
    assert "--- FILE: src/main.py ---" in copied_content

def test_cli_default_has_header(project_structure: Path):
    """Tests that the default behavior includes the prompt header."""
    runner = CliRunner()
    
    with runner.isolated_filesystem() as td:
        result = runner.invoke(
            aicontextator.cli,
            [str(project_structure), "-o", "header_test.txt"]
        )
        assert result.exit_code == 0
        content = (Path(td) / "header_test.txt").read_text()
        assert content.startswith("The following text is a collection")

def test_cli_with_prompt_no_header_flag(project_structure: Path):
    """Tests that the --prompt-no-header flag correctly REMOVES the header."""
    runner = CliRunner()
    
    with runner.isolated_filesystem() as td:
        result = runner.invoke(
            aicontextator.cli,
            [str(project_structure), "--prompt-no-header", "-o", "no_header_test.txt"]
        )
        assert result.exit_code == 0
        content = (Path(td) / "no_header_test.txt").read_text()
        assert not content.startswith("The following text is a collection")
        assert content.startswith("--- FILE:")