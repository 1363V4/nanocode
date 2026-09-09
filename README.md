> I forked this tool to make it compatible with OpenRouter (it's cheaper than Claude Code).
> I also added some QoL improvements, like settings and memory.

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
4.. Run `uv run nanocode.py`

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool | Description |
|------|-------------|
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
