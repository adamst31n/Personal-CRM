"""
Personal CRM agent test harness.

Connects to the find_contact MCP server as a stdio subprocess and runs a
single query against live Firestore data, proving the end-to-end agent loop.

WHERE THE LOOP HAPPENS
----------------------
query() (from claude_agent_sdk) spawns the bundled Claude Code CLI as a
subprocess. That CLI calls Anthropic's API, receives a tool-call response
for find_contact, routes the call to the "crm" MCP server subprocess
(python3.11 -m mcp_server.server), feeds the Firestore result back to the
API, and repeats until Claude delivers a final text answer or max_turns is
reached. This script just consumes the messages that come out of that loop
via an async generator -- it does not drive the loop itself.

Usage:
    python3.11 crm_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import sys

from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    query,
)

PROMPT = "Find the contact named Aaron."
MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 4
MCP_COMMAND = "python3.11"
MCP_ARGS = ["-m", "mcp_server.server"]

# Absolute path to the project root so both the CLI subprocess and the MCP
# server subprocess can find mcp_server/ as a package regardless of CWD drift.
PROJECT_ROOT = pathlib.Path(__file__).parent.resolve()


def cli_stderr(line: str) -> None:
    """Print Claude Code CLI stderr lines so failures surface immediately."""
    print(f"[cli] {line}", file=sys.stderr, flush=True)


def check_startup() -> tuple[str, str]:
    """Verify required env vars, command, and service account.

    Returns (sa_path, python_abs_path).  The absolute python path is passed
    as the MCP server command so the CLI subprocess can find it even when
    spawning with an env that has no PATH (Node.js child_process.spawn
    replaces the environment when an explicit env dict is provided).
    """
    required = ["ANTHROPIC_API_KEY", "CRM_SERVICE_ACCOUNT", "CRM_USER_UID"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        sys.exit(f"ERROR: missing env vars: {', '.join(missing)}")

    python_path = shutil.which(MCP_COMMAND)
    if not python_path:
        sys.exit(f"ERROR: {MCP_COMMAND!r} not found in PATH")

    sa_path = os.path.expanduser(os.environ["CRM_SERVICE_ACCOUNT"])
    if not os.path.isfile(sa_path):
        sys.exit(f"ERROR: service account not found: {sa_path}")

    mcp_pkg = PROJECT_ROOT / "mcp_server"
    if not mcp_pkg.is_dir():
        sys.exit(f"ERROR: mcp_server package not found at {mcp_pkg}")

    uid = os.environ["CRM_USER_UID"]
    print("=== CRM Agent ===")
    print(f"Model           : {MODEL}")
    print(f"Max turns       : {MAX_TURNS}")
    print(f"Permission mode : bypassPermissions")
    print(f"Disallowed tools: all built-ins (agent restricted to MCP only)")
    print(f"MCP server      : {python_path} {' '.join(MCP_ARGS)}")
    print(f"Project root    : {PROJECT_ROOT}")
    print(f"Service acct    : {sa_path}")
    print(f"User UID        : {uid[:8]}...")
    print(f"Status          : all checks passed")
    print()
    return sa_path, python_path


async def main() -> None:
    sa_path, python_path = check_startup()

    # Pass only the vars the MCP server actually needs, plus PYTHONPATH pinned
    # to the project root so `mcp_server` is importable.
    #
    # NOTE: do NOT pass PATH here.  The CLI spawns the MCP server subprocess
    # via Node.js child_process.spawn with an explicit env dict, which
    # *replaces* the environment entirely (no PATH inheritance).  Using the
    # absolute python_path (resolved above by shutil.which) means the command
    # is found without PATH, and these three vars are the only ones the server
    # actually reads.
    mcp_env = {
        "CRM_SERVICE_ACCOUNT": sa_path,
        "CRM_USER_UID": os.environ["CRM_USER_UID"],
        "PYTHONPATH": str(PROJECT_ROOT),
    }

    options = ClaudeAgentOptions(
        model=MODEL,
        max_turns=MAX_TURNS,
        allowed_tools=["mcp__crm__find_contact"],
        # Block every built-in tool so the agent can only call the MCP tool.
        # disallowed_tools removes tools from the model's context entirely,
        # which is what we need here.  tools=[] would also work conceptually
        # but was previously observed to cause issues.
        disallowed_tools=[
            "Agent", "Bash", "Edit", "Explore", "Glob", "Grep",
            "MultiEdit", "NotebookEdit", "NotebookRead", "Read",
            "Skill", "Task", "TodoWrite", "WebFetch", "WebSearch", "Write",
        ],
        # bypassPermissions: auto-approve everything without prompting.
        # Required for non-TTY subprocess use -- without this the CLI blocks
        # waiting for a permission grant that never arrives on piped stdin.
        permission_mode="bypassPermissions",
        # cwd: sets the working directory for the bundled CLI subprocess.
        cwd=PROJECT_ROOT,
        # stderr: pipe CLI stderr back to us so errors surface immediately
        # instead of being swallowed by the subprocess.
        stderr=cli_stderr,
        mcp_servers={
            "crm": {
                "type": "stdio",
                # Use the absolute path resolved by shutil.which so the
                # command is found even though the MCP subprocess env has
                # no PATH (Node.js env-replace behavior).
                "command": python_path,
                "args": MCP_ARGS,
                "env": mcp_env,
            }
        },
    )

    print(f"Prompt: {PROMPT!r}")
    print("-" * 60)

    exit_code = 0
    async for message in query(prompt=PROMPT, options=options):
        if isinstance(message, SystemMessage):
            # Print the raw init payload — shows MCP connection status and
            # the exact tool names the server exposed to the agent.
            print(f"[system:{message.subtype}]", file=sys.stderr)
            print(json.dumps(message.data, indent=2, default=str), file=sys.stderr)
            print(file=sys.stderr)
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print("-" * 60)
            print(f"\nCompleted  : {message.num_turns} turn(s)")
            if message.total_cost_usd is not None:
                print(f"Cost       : ${message.total_cost_usd:.6f}")
            if message.usage:
                print(f"Usage      : {message.usage}")
            if message.is_error:
                print(f"\nERROR: {message.result}", file=sys.stderr)
                # Don't sys.exit() inside async for — SystemExit raises
                # while the generator frame is still on the stack, causing
                # "aclose(): asynchronous generator is already running".
                exit_code = 1
                break

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
