> I forked this tool to make it compatible with OpenRouter (it's cheaper than Claude Code).

> I also added some QoL improvements, like settings, system prompt, and memory.

# nanocode

Minimal Claude Code alternative. 

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

1. `git clone` this repo
2. Add a `.env` file with your OpenRouter API key: `OPENROUTER_API_KEY="your-key"`
3. (Optional) Modify `settings.json` and `SYSTEM.md` to your convenience.
4. Run `uv run nanocode.py`

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool | Description |
|------
|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Glob(**/*.py)
  ⎿  nanocode.py

⏺ There's one Python file: nanocode.py
```

## Using nanocode from another directory

Let's say for example that you cloned nanocode repository on your home folder.

To use it on a project in another folder, simply call:

```bash
uv run --project ~/nanocode/ ~/nanocode/nanocode.py
```

from your folder.

By default, nanocode will look for the `.env` file in its own folder, and for a SYSTEM and MEMORY file in the current folder.

This can be changed via creating a `settings.json` in your project. For example:

```json
{
  "model": "deepseek/deepseek-v4-flash-0731",
  "system_file": "~/skills/WEBDEV.md",
  "memory_file": "NANO_MEMORY.md"
}
```

will load a different model, use a skill from your folder and write in the specified file in your folder.
