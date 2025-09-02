Aicontextator
=============

Aicontextator is a simple, practical CLI that bundles a project's files into a single LLM-ready context string. It respects `.gitignore` and a `.contextignore` file, estimates tokens with `tiktoken`, and can split large outputs into multiple parts.

## Say goodbye to manual copy-pasting
Stop manually finding, copying, and pasting code into your AI prompts. aicontextator automates the entire process, letting you build a comprehensive context from your project files with a single command, right from your terminal.

Key features
------------

*   🧠 Smart file filtering: respects `.gitignore` automatically.
*   ✂️ Custom ignore rules: use a `.contextignore` file for project-specific exclusions.
*   📝 Structured JSON Output: Generate a detailed JSON file with project structure, file contents, token counts, and security warnings for programmatic use with `--format json`.
*   🎛 Interactive Mode: Select or deselect files interactively using arrow keys.
*   🛡️ **Built-in Secret Scanning**: Proactively scans the content of included files using the detect-secrets engine to identify and warn about potential secrets (like API keys) before they are added to the context
*   🔒 Secure defaults: excludes `.env` and `.env.*` files by default to reduce secret leakage.
*   🤖 Token-aware: estimates tokens using `tiktoken`.
*   🧩 Automatic splitting: splits output into multiple parts when a per-part token limit is reached.
*   📋 Clipboard-ready: copy the first part to the clipboard with `--copy`.
*   🌲 Tree view: preview included files with `--tree-only` or include the tree inside the context with `--tree`.
*   ⚙️ Configurable: add extra exclude patterns, restrict by extensions, and tune output.

* * *

Install
-------

Install and use easily with [uv](https://docs.astral.sh/uv/):
```
uv tool install git+https://github.com/ILDaviz/aicontextator
```
```
aicontextator /path/to/project
```
Manual (pip editable):
```
git clone https://github.com/ILDaviz/aicontextator
```
```
cd aicontextator
```
```
pip install -e .
```
```
aicontextator /path/to/project
```
* * *

Basic usage
-----------

#### Generate `context.txt` in the current directory:
```
aicontextator
```

#### Copy to the clipboard:
```
aicontextator --copy
```

#### Save to a custom file:
```
aicontextator -o custom.txt
```

#### Include the project tree at the top of the context:
```
aicontextator --tree
```

#### Show only the tree and exit (preview):
```
aicontextator --tree-only
```

#### Omit the meta header (only file blocks will be output):
```
aicontextator --prompt-no-header
```

#### The code includes a fully functional interactive mode, triggered by the --interactive flag, which allows the user to select files using a keyboard-navigable interface:
```
aicontextator --interactive
```

#### Generate a structured JSON output for scripts or advanced analysis:
```
aicontextator --format json -o context_data.json --count-tokens
```

* * *

CLI options (high level)
------------------------
*   ROOT_DIR: The project directory to analyze (defaults to current directory).
*   `--output, -o` : Output filename. If splitting, parts are numbered (e.g., context-part-1.txt). Defaults to context.txt or context.json.
*   `--format` : The output format. Can be text (default) or json.
*   `--exclude, -e` : extra exclusion patterns (gitignore-style). Can be repeated.
*   `--ext` : include only specific extensions (repeatable).
*   `--copy, -c` : copy to clipboard.
*   `--count-tokens` : enable token counting (uses `tiktoken`).
*   `--max-tokens` : maximum tokens _per output part_ (if exceeded, the output is split into parts).
*   Note: this does not perform hard splitting inside single files. If a single file exceeds `--max-tokens` by itself, it will still be placed whole into a part (and that part may exceed the limit).
*   `--warn-tokens` : print a warning when a part exceeds this token threshold.
*   `--interactive, -i` : Interactive Mode: Select or deselect files interactively using arrow keys, with the ability to quit immediately by pressing ESC.
*   `--tree` : include tree view in the generated context.
*   `--tree-only` : print only the tree and exit.
*   `--prompt-no-header` : do not prepend the descriptive header.

* * *

Token handling notes
--------------------

*   Token counting uses `tiktoken`, the library recommended for token estimates for OpenAI models. Consider `--count-tokens` to get a token report.
*   `--max-tokens` sets a per-part limit. The tool will aggregate files into a part until adding the next file would exceed the limit, then it starts a new part. It does not (by default) split file contents into multiple chunks.
*   For strategies and best practices on splitting text for LLMs, libraries like LangChain offer helpful patterns (e.g., document chunking and token-based splitters).

* * *

Examples (advanced)
-------------------
#### Count tokens and print a report:
```
aicontextator --count-tokens
```
#### Split into parts when the context exceeds 100000 tokens:
```
#### Creates context-part-1.txt, context-part-2.txt, ...
§aicontextator --count-tokens --max-tokens 100000 -o context.txt
```
#### Warn when a part gets larger than 80k tokens:
```
aicontextator --count-tokens --warn-tokens 80000
```
#### Exclude a folder:
```
aicontextator --exclude "tests/"
```
#### Only include Python and Markdown files:
```
aicontextator --ext .py --ext .md
```
* * *

Filtering & security
--------------------

*   The tool respects `.gitignore` and supports a `.contextignore` file for extra ignore patterns.
*   Default exclude patterns include `.env` and `.env.*` to avoid leaking environment secrets. Always double-check your `.gitignore` / `.contextignore` to be safe.


* * *

Development & testing
---------------------

1.  Clone:

```
git clone https://github.com/ILDaviz/aicontextator
```
```
cd aicontextator
```

2.  Create virtualenv and install dev deps:

```
uv venv
```
```
source .venv/bin/activate
```
```
uv pip install -e '.[dev]'
```

### Utility:

#### Run test
```
uv run test
```

#### Check code
```
uv run lint
```

#### Format the code
```
uv run format
```

* * *

Roadmap / ideas
---------------

*   Automatic summarization of long files to reduce token usage.

* * *

License
-------

This project is licensed under the [MIT license](https://opensource.org/licenses/MIT).

Contributing
------------

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.