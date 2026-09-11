"""nanocode - minimal claude code alternative (1363V4 fork)"""

import json, os, re, select, subprocess, time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIError


# --- Settings ---

NANOCODE_FOLDER = Path(__file__).resolve().parent
DEFAULT_ENV_PATH = (NANOCODE_FOLDER / ".env").as_posix()

DEFAULT_SYSTEM_PATH = (Path.cwd() / "SYSTEM.md").as_posix()
DEFAULT_MEMORY_PATH = (Path.cwd() / "MEMORY.md").as_posix()

DEFAULT_SETTINGS = {
    "model": "anthropic/claude-sonnet-5",
    "show_cost": True,
    "show_tokens": True,
    "max_tokens": 8192,
    "system_file": DEFAULT_SYSTEM_PATH,
    "memory_file": DEFAULT_MEMORY_PATH,
    "memory_max_chars": 4000,
    ".env": DEFAULT_ENV_PATH,
    "bash_timeout": 30, # s
}

def load_settings():
    defaults = {}
    try:
        defaults.update(json.loads(Path("settings.json").read_text()))
    except FileNotFoundError:
        pass
    return DEFAULT_SETTINGS | defaults


SETTINGS = load_settings()


def build_system_prompt():
    parts = []
    system_file = SETTINGS.get("system_file")
    if system_file:
        path = Path(system_file).expanduser()
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
        except (OSError, UnicodeDecodeError):
            pass
    memory_file = SETTINGS.get("memory_file")
    if memory_file:
        path = Path(memory_file).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
            cap = SETTINGS.get("memory_max_chars", 4000)
            if len(text) > cap:
                text = text[:cap] + "\n...(truncated)"
            if text.strip():
                parts.append(
                    f"Agent memory ({memory_file}) - you may update this file "
                    "when you learn durable facts:\n" + text
                )
        except (OSError, UnicodeDecodeError):
            pass
    if parts:
        return "\n\n".join(parts)
    return f"Concise coding assistant. OS: {os.name}. cwd: {Path.cwd()}"


# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

load_dotenv(Path(SETTINGS[".env"]))

MODEL = os.environ.get("MODEL", SETTINGS["model"])
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


# --- Tool implementations ---


def read(args):
    lines = Path(args["path"]).read_text(encoding="utf-8").splitlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    Path(args["path"]).write_text(args["content"], encoding="utf-8")
    return "ok"


def edit(args):
    path = Path(args["path"])
    text = path.read_text(encoding="utf-8")
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    path.write_text(replacement, encoding="utf-8")
    return "ok"


def glob(args):
    pattern = (Path(args.get("path", ".")) / args["pat"]).as_posix()
    files = sorted(
        Path(".").glob(pattern),
        key=lambda p: p.stat().st_mtime if p.is_file() else 0,
        reverse=True,
    )
    return "\n".join(map(str, files)) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in Path(args.get("path", ".")).rglob("*"):
        try:
            if not filepath.is_file():
                continue
            for line_num, line in enumerate(
                filepath.read_text(encoding="utf-8").splitlines(), 1
            ):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    start = time.time()
    timeout = SETTINGS.get("bash_timeout", 30)

    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            proc.kill()
            output_lines.append("\n(timed out after %ds)" % timeout)
            break
        ready, _, _ = select.select([proc.stdout], [], [], remaining)
        if ready:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        elif proc.poll() is not None:
            break

    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return result


def call_api(messages):
    return client.chat.completions.create(
        model=MODEL,
        max_tokens=SETTINGS["max_tokens"],
        messages=messages,
        tools=make_schema(),
        extra_body={"usage": {"include": True}},
    )


def print_usage(response, session):
    usage = getattr(response, "usage", None)
    if not usage:
        return
    session["tokens"] += usage.total_tokens
    cost = getattr(usage, "cost", None)
    if cost is not None:
        session["cost"] += cost

    bits = []
    if SETTINGS["show_tokens"]:
        bits.append(f"{usage.total_tokens} tok")
    if SETTINGS["show_cost"] and cost is not None:
        bits.append(f"${cost:.4f}")
    if bits:
        print(f"  {DIM}({' · '.join(bits)}){RESET}")


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    loaded = [
        f
        for f in (SETTINGS.get("system_file"), SETTINGS.get("memory_file"))
        if f
    ]
    banner = f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (OpenRouter)"
    if loaded:
        banner += f" | {DIM}{', '.join(loaded)}{RESET}"
    print(banner + "\n")
    messages = [{"role": "system", "content": build_system_prompt()}]
    session = {"tokens": 0, "cost": 0.0}

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = [{"role": "system", "content": build_system_prompt()}]  # rebuild prompt, memory may have changed
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                try:
                    response = call_api(messages)
                except APIError as err:
                    print(f"{RED}⏺ API error: {err}{RESET}")
                    messages.pop()  # drop the message that caused the failed round
                    break

                print_usage(response, session)
                msg = response.choices[0].message
                tool_calls = msg.tool_calls or []

                if msg.content:
                    print(f"\n{CYAN}⏺{RESET} {render_markdown(msg.content)}")

                assistant_entry = {"role": "assistant", "content": msg.content}
                if tool_calls:
                    assistant_entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ]
                messages.append(assistant_entry)

                if not tool_calls:
                    break

                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
                    print(f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})")

                    result = run_tool(tool_name, tool_args)
                    result_lines = result.split("\n")
                    preview = result_lines[0][:60]
                    if len(result_lines) > 1:
                        preview += f" ... +{len(result_lines) - 1} lines"
                    elif len(result_lines[0]) > 60:
                        preview += "..."
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": result}
                    )

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")

    if SETTINGS["show_cost"] or SETTINGS["show_tokens"]:
        print(f"\n{DIM}session: {session['tokens']} tokens · ${session['cost']:.4f}{RESET}")


if __name__ == "__main__":
    main()
