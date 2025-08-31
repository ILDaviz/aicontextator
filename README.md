# Aicontextator
A smart CLI tool that bundles project files into a single, LLM-ready context string. It respects .gitignore, counts tokens, and handles large projects by splitting the output.

## Say goodbye to manual copy-pasting
Stop manually finding, copying, and pasting code into your AI prompts. aicontextator automates the entire process, letting you build a comprehensive context from your project files with a single command, right from your terminal.

### Key features
- 🧠 Smart File Filtering: Automatically respects rules from your .gitignore file, so you only include the code that matters.
- ✂️ Custom Ignore Rules: Use a .contextignore file to add specific exclusions without modifying your main .gitignore.
- 🤖 Token-Aware: Counts tokens using tiktoken to give you an accurate estimate of your context size before sending it to an LLM.
- 🧩 Automatic Splitting: Automatically splits the output into multiple parts if it exceeds a --max-tokens limit, perfect for models with smaller context windows.
- 📋 Clipboard-Ready: Use the --copy flag to send the entire context directly to your clipboard.
- 🌲 Tree View: Preview which files will be included with the --tree-only flag before generating the full context.
- ⚙️ Highly Configurable: Fine-tune the output with options to exclude specific files, include certain extensions, and more.

### Basic usage

Install and use easily with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/ILDaviz/aicontextator
aicontextator ../test_folder
```

Alternatively, more manual pip install example:

```bash
git clone https://github.com/ILDaviz/aicontextator
cd rendergit
pip install -e .
rendergit ../test_folder
```

### Usage
Using aicontextator is simple. Navigate to your project's root directory and run the command.

Basic Commands
1. Save the context to a standard file named `context.txt`:

```bash
aicontextator
```

2. Copy the entire project context to your clipboard:
(This is the most common use case)

```bash
aicontextator --copy
```

3. Save the context to a file:

```bash
aicontextator -o custom.txt
```

4. Preview the included files as a tree:

```bash
aicontextator --tree-only
```

5. Generate the context **WITHOUT** the instructional header:

```bash
aicontextator --prompt-no-header
```

### Advanced Usage with Token Management
1. Generate the context and get a token count report [Tiktoken](https://github.com/openai/tiktoken):

```bash
aicontextator --count-tokens
```

2. Automatically split the output if it exceeds 100,000 tokens:

```bash
aicontextator --count-tokens --max-tokens 100000 -o context.txt
# This will create context-part-1.txt, context-part-2.txt, etc.
```

3. Get a warning if the context size exceeds 80,000 tokens:

```bash
aicontextator --count-tokens --warn-tokens 80000
```

### Filtering
1. Exclude a specific folder (e.g., tests):

```bash
aicontextator --exclude "tests/"
```

2. Only include Python and Markdown files:

```bash
aicontextator --ext .py --ext .md
```

### For a full list of commands and options, run:

```bash
aicontextator --help
```

### Development & Testing
Interested in contributing? Setting up a development environment is straightforward.

1. Clone the repository:

```bash
git clone https://github.com/ILDaviz/aicontextator
cd aicontextator
```

2. Create a virtual environment and install dependencies:
It's recommended to create a virtual environment. Then, install the project in "editable" mode along with the testing dependencies.

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[test]'
```

3. Run the tests:
To ensure everything is working correctly, run the test suite using pytest.

```bash
uv run pytest
```

### License
This project is licensed under the [MIT license](https://opensource.org/licenses/MIT).

### Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.