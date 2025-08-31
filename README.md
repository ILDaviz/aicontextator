# aicontextator
A smart CLI tool that bundles project files into a single, LLM-ready context string. It respects .gitignore, counts tokens, and handles large projects by splitting the output.

## Say Goodbye to Manual Copy-Pasting
Stop manually finding, copying, and pasting code into your AI prompts. aicontextator automates the entire process, letting you build a comprehensive context from your project files with a single command, right from your terminal.

### Key Features
- 🧠 Smart File Filtering: Automatically respects rules from your .gitignore file, so you only include the code that matters.
- ✂️ Custom Ignore Rules: Use a .contextignore file to add specific exclusions without modifying your main .gitignore.
- 🤖 Token-Aware: Counts tokens using tiktoken to give you an accurate estimate of your context size before sending it to an LLM.
- 🧩 Automatic Splitting: Automatically splits the output into multiple parts if it exceeds a --max-tokens limit, perfect for models with smaller context windows.
- 📋 Clipboard-Ready: Use the --copy flag to send the entire context directly to your clipboard.
- 🌲 Tree View: Preview which files will be included with the --tree-only flag before generating the full context.
- ⚙️ Highly Configurable: Fine-tune the output with options to exclude specific files, include certain extensions, and more.

## Basic usage

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
1. Copy the entire project context to your clipboard:
(This is the most common use case)

```bash
aicontextator --copy
```

2. Save the context to a file:

```bash
aicontextator -o context.txt
```

3. Preview the included files as a tree:

```bash
aicontextator --tree-only
```

### Advanced Usage with Token Management
1. Generate the context and get a token count report:

```bash
aicontextator --count-tokens --copy
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
aicontextator --exclude "tests/" --copy
```

2. Only include Python and Markdown files:

```bash
aicontextator --ext .py --ext .md --copy
```

For a full list of commands and options, run:

```bash
aicontextator --help
```

### License
This project is licensed under the 0BSD License. See the LICENSE file for details. This means you are free to use, modify, and distribute it with almost no restrictions.

### Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

Built by David Galet.