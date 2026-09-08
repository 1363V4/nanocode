"""nanocode - minimal claude code alternative (1363V4 fork)"""

import glob as globlib, json, os, re, subprocess
from dotenv import load_dotenv
from openai import OpenAI, APIError


load_dotenv()

def load_settings():
    defaults = {
        "model": "anthropic/claude-sonnet-5",
        "show_cost": True,
        "show_tokens": True,
    }
    try:
        with open("settings.json") as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass
    return defaults


SETTINGS = load_settings()
MODEL = os.environ.get("MODEL", SETTINGS["model"])
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
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
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
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
        max_tokens=8192,
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
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (OpenRouter) | {os.getcwd()}{RESET}\n")
    messages = [{"role": "system", "content": f"Concise coding assistant. cwd: {os.getcwd()}"}]
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
                messages = messages[:1]  # keep system prompt, drop history
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