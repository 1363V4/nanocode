This project is managed with uv (Python 3.14, see `pyproject.toml` and `uv.lock`).

The main program is a single file: `nanocode.py`.

Runtime configuration lives in `settings.json`; keys may be overridden by environment variables (e.g. `MODEL`).

Key dependencies: `openai` (OpenRouter client) and `python-dotenv`.

Run with `uv run nanocode.py`. API key is read from `.env` (`OPENROUTER_API_KEY`).

Use `git status` and read the diff before large edits. Keep the codebase a single file and minimal.