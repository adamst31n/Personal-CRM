"""
Personal CRM agent harness.

Spawns the CRM MCP server as a stdio subprocess and runs a single prompt
against live Firestore data via the Claude Agent SDK.

Permission model
----------------
Read tools (find_contact, get_contact) are auto-approved — no prompt.
Write tools (log_interaction) require explicit user confirmation:
  - The agent proposes the entries to write.
  - The harness pauses and shows them to you.
  - You type "y" to approve or anything else to reject.
  - The tool only executes if you approve.

This is enforced by the SDK's `can_use_tool` callback, which replaces the
interactive permission prompt for the non-TTY CLI subprocess.

Usage:
    python3.11 crm_agent.py                          # default read prompt
    python3.11 crm_agent.py "your prompt here"       # any prompt
"""

from __future__ import annotations

import asyncio
import datetime
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
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)
from mcp_server.firestore_client import get_user_data

DEFAULT_PROMPT = "Who should I reach out to this week?"
PROMPT = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PROMPT
MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 12
MCP_COMMAND = "python3.11"
MCP_ARGS = ["-m", "mcp_server.server"]

# Absolute path to the project root so both the CLI subprocess and the MCP
# server subprocess can find mcp_server/ as a package regardless of CWD drift.
PROJECT_ROOT = pathlib.Path(__file__).parent.resolve()
CONTEXT_FILE = PROJECT_ROOT / "agent-context.md"


def _fmt_name(c: dict) -> str:
    """Build a display name from a contact dict."""
    first = (c.get("firstName") or "").strip()
    last = (c.get("lastName") or "").strip()
    return f"{first} {last}".strip() or c.get("name") or c.get("id", "?")


def load_system_prompt() -> str:
    """Load agent-context.md and inject today's date.

    Prompt caching note: this string is passed as the system prompt on every
    run. Haiku/Sonnet cache system prompts that exceed ~1 024 tokens — the
    context file easily clears that bar, so the second+ run in a session costs
    cache-read tokens (much cheaper) rather than cache-write or input tokens.
    The [SEE WATCHLIST REFERENCE] placeholder is intentionally left; the
    watchlist wiring is a future step.
    """
    if not CONTEXT_FILE.exists():
        sys.exit(f"ERROR: context file not found: {CONTEXT_FILE}")
    today = datetime.date.today().isoformat()
    text = CONTEXT_FILE.read_text(encoding="utf-8")
    # Resolve the date placeholder embedded in the file's "Placeholders" section.
    text = text.replace("[CURRENT DATE]", today)
    # Prepend a prominent date line so it anchors overdue calculations.
    return f"Today's date: {today}\n\n{text}"


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
    print(f"Auto-approved   : find_contact, get_contact, list_outreach_candidates (reads)")
    print(f"Requires prompt : log_interaction (write — pauses for your yes/no)")
    print(f"Built-ins       : all disallowed (agent restricted to CRM MCP tools)")
    print(f"Context file    : {CONTEXT_FILE}")
    print(f"MCP server      : {python_path} {' '.join(MCP_ARGS)}")
    print(f"Project root    : {PROJECT_ROOT}")
    print(f"Service acct    : {sa_path}")
    print(f"User UID        : {uid[:8]}...")
    print(f"Status          : all checks passed")
    print()
    return sa_path, python_path


async def main() -> None:
    sa_path, python_path = check_startup()
    system_prompt = load_system_prompt()

    # Pre-load contacts so the permission callback can show names, not UUIDs.
    loop = asyncio.get_running_loop()
    contacts, _ = await loop.run_in_executor(None, get_user_data)
    contact_map = {c["id"]: _fmt_name(c) for c in contacts if c.get("id")}

    # ------------------------------------------------------------------ #
    # Permission handler — called by the SDK instead of an interactive    #
    # prompt whenever a tool is NOT in allowed_tools and would normally   #
    # ask for approval.  Only log_interaction should ever reach here.     #
    # ------------------------------------------------------------------ #
    async def permission_handler(
        tool_name: str,
        tool_input: dict,
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        if tool_name != "mcp__crm__log_interaction":
            # Anything else reaching here is unexpected — deny and surface it.
            return PermissionResultDeny(
                message=f"Unexpected permission request for {tool_name!r}. Denied."
            )

        entries = tool_input.get("entries") or []

        print("\n" + "=" * 60, flush=True)
        print("  WRITE REQUEST — log_interaction", flush=True)
        print("=" * 60, flush=True)
        for idx, e in enumerate(entries, 1):
            cid = e.get("contactId", "")
            name = contact_map.get(cid, cid or "?")
            print(f"\n  [{idx}] {name}")
            print(f"       Date : {e.get('date', '?')}")
            print(f"       Type : {e.get('type', '?')}")
            notes = (e.get("notes") or "").strip()
            if notes:
                print(f"       Notes: {notes}")
            tags = e.get("taggedContacts") or []
            if tags:
                tag_names = ", ".join(contact_map.get(t, t) for t in tags)
                print(f"       Also : {tag_names}")
        print("\n" + "=" * 60, flush=True)

        # run_in_executor keeps the event loop unblocked while waiting for
        # the user to type — input() is a blocking call.
        raw = await loop.run_in_executor(
            None, lambda: input("Write to Firestore? [y/N] ")
        )
        if raw.strip().lower() == "y":
            print("Approved — writing.", flush=True)
            return PermissionResultAllow()

        print("Rejected — not writing.", flush=True)
        return PermissionResultDeny(
            message="User declined. Acknowledge that the interaction was NOT logged."
        )

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
        # System prompt loaded from agent-context.md with today's date injected.
        # This is where prompt caching attaches on the second run of a session —
        # the context file exceeds the ~1 024-token cache threshold.
        system_prompt=system_prompt,
        # Read tools are auto-approved — no prompt, no can_use_tool call.
        # log_interaction is intentionally absent so it triggers can_use_tool.
        allowed_tools=[
            "mcp__crm__find_contact",
            "mcp__crm__get_contact",
            "mcp__crm__list_outreach_candidates",
        ],
        # Remove all built-in tools from context so the agent can only call
        # CRM MCP tools.  disallowed_tools removes them from the model's view
        # entirely (tools=[] was observed to nuke MCP tools too).
        disallowed_tools=[
            "Agent", "Bash", "Edit", "Explore", "Glob", "Grep",
            "MultiEdit", "NotebookEdit", "NotebookRead", "Read",
            "Skill", "Task", "TodoWrite", "WebFetch", "WebSearch", "Write",
        ],
        # "default" permission mode: tools in allowed_tools are auto-approved;
        # everything else triggers can_use_tool instead of an interactive prompt.
        # Previously "bypassPermissions" (which bypasses can_use_tool entirely).
        permission_mode="default",
        # Intercept permission requests for log_interaction and route them to
        # the confirmation handler above.
        can_use_tool=permission_handler,
        cwd=PROJECT_ROOT,
        stderr=cli_stderr,
        mcp_servers={
            "crm": {
                "type": "stdio",
                "command": python_path,
                "args": MCP_ARGS,
                "env": mcp_env,
            }
        },
    )

    print(f"Prompt: {PROMPT!r}")
    print("-" * 60)

    # can_use_tool requires an AsyncIterable prompt (string is rejected by the SDK).
    # But a generator that exhausts immediately causes stream_input() to call
    # wait_for_result_and_end_input(), which closes stdin — breaking the control
    # protocol before any permission request can be routed back.
    #
    # Fix: keep the generator alive (blocking stream_input inside its `async for`)
    # until the ResultMessage arrives, then set result_event so the generator
    # exhausts cleanly.  stdin stays open for the entire conversation.
    result_event = asyncio.Event()

    async def prompt_stream():
        yield {
            "type": "user",
            "message": {"role": "user", "content": PROMPT},
            "parent_tool_use_id": None,
            "session_id": "default",
        }
        await result_event.wait()

    client = ClaudeSDKClient(options=options)
    await client.connect(prompt=prompt_stream())

    exit_code = 0
    try:
        async for message in client.receive_messages():
            if isinstance(message, SystemMessage):
                # Raw init payload — shows MCP connection status and tool names.
                print(f"[system:{message.subtype}]", file=sys.stderr)
                print(json.dumps(message.data, indent=2, default=str), file=sys.stderr)
                print(file=sys.stderr)
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        # Log tool calls to stderr so the write-pause is visible
                        # and so we can confirm log_interaction was attempted.
                        print(
                            f"[tool call: {block.name}]",
                            file=sys.stderr, flush=True,
                        )
            elif isinstance(message, ResultMessage):
                result_event.set()  # unblock prompt_stream → stream_input exits cleanly
                print("-" * 60)
                print(f"\nCompleted  : {message.num_turns} turn(s)")
                if message.total_cost_usd is not None:
                    print(f"Cost       : ${message.total_cost_usd:.6f}")
                if message.usage:
                    print(f"Usage      : {message.usage}")
                if message.is_error:
                    print(f"\nERROR: {message.result}", file=sys.stderr)
                    exit_code = 1
                break  # one-shot: stop after result regardless of error/success
    finally:
        await client.disconnect()

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
