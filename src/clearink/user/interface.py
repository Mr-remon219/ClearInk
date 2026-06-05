from rich.markdown import Markdown
from rich.prompt import Prompt

from clearink.message import extract_text_from_content
from clearink.user.console import console, render_lemon
from clearink.user.output_format import format_response_text
from clearink.user import mode


def _extract_response(messages: list) -> str | None:
    """Extract the final assistant text response from a message list.

    Walks messages in reverse to find the last assistant message that
    contains a plain string (not a list of tool-use blocks).
    """
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        text = extract_text_from_content(content).strip()
        if text:
            return text
    return None


def _make_user_message(text: str) -> dict:
    """Wrap user text with current mode instructions as a prefix."""
    mode_prompt = mode.get_mode_prompt()
    if mode_prompt:
        prefixed = (
            f"[Mode {mode.get_mode()} instructions begin]\n"
            f"{mode_prompt}\n"
            f"[Mode {mode.get_mode()} instructions end]\n\n"
            f"{text}"
        )
    else:
        prefixed = text
    return {"role": "user", "content": prefixed}


def run(agent_loop) -> None:
    # ── Welcome ──────────────────────────────────────────────
    console.print()
    render_lemon()
    console.print()

    # ── Mode status ──────────────────────────────────────────
    console.print(
        f"  [bold]Mode {mode.get_mode()}[/bold] · "
        f"{mode.get_mode_label()}  "
        f"[dim]({mode.get_switch_hint()})[/dim]"
    )
    console.print()

    # ── Input ────────────────────────────────────────────────
    title = Prompt.ask("[bold]Paper title[/bold]").strip()

    # Allow mode switch before entering paper title
    cmd = mode.detect_mode_command(title)
    if cmd is not None:
        mode.set_mode(cmd)
        console.print(
            f"[dim]Switched to Mode {mode.get_mode()} · "
            f"{mode.get_mode_label()}[/dim]"
        )
        console.print()
        title = Prompt.ask("[bold]Paper title[/bold]").strip()

    if not title:
        console.print("[dim]No paper title provided. Exiting.[/dim]")
        return

    console.print()
    second_prompt = f"[bold]{mode.get_second_input_prompt()}[/bold]"
    second_input = Prompt.ask(second_prompt).strip()
    console.print()

    # ── First query ──────────────────────────────────────────
    query = mode.build_query(title, second_input)
    messages = [{"role": "user", "content": query}]

    try:
        with console.status("[dim]Analyzing...[/dim]", spinner="dots"):
            messages = agent_loop(messages)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    response = _extract_response(messages)
    if response:
        console.print(Markdown(format_response_text(response)))
    else:
        console.print("[dim](No response received.)[/dim]")

    # ── Follow-up loop ───────────────────────────────────────
    if mode.is_step_mode():
        console.print(
            "[dim]Step mode active. /next to continue, /end to start new round, "
            "/nostep to disable, /exit to quit.[/dim]"
        )
    else:
        console.print(
            "[dim]Ask a follow-up, /step, /mode 1, /mode 2, or /exit to quit.[/dim]"
        )

    while True:
        console.print()
        try:
            followup = Prompt.ask("[dim]>[/dim]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break

        if followup.lower() in ("/exit", "/quit", "exit", "quit"):
            break

        # ── /step command ────────────────────────────────────
        if followup.lower() == "/step":
            mode.set_step_mode(True)
            console.print(
                "[dim]Step mode enabled. /next to continue, "
                "/end to start new round, /nostep to disable.[/dim]"
            )
            continue

        # ── /nostep command ──────────────────────────────────
        if followup.lower() == "/nostep":
            mode.set_step_mode(False)
            console.print("[dim]Step mode disabled.[/dim]")
            continue

        # ── Mode switch detection ────────────────────────────
        cmd = mode.detect_mode_command(followup)
        if cmd is not None:
            mode.set_mode(cmd)
            console.print(
                f"[dim]Switched to Mode {mode.get_mode()} · "
                f"{mode.get_mode_label()}[/dim]"
            )
            continue

        if not followup:
            continue

        # ── Build user message (with step instructions if active) ──
        msg = _make_user_message(followup)
        if mode.is_step_mode():
            msg["content"] = mode.build_step_instructions() + "\n\n" + msg["content"]

        messages.append(msg)

        # ── Step sub-loop ────────────────────────────────────
        if mode.is_step_mode():
            if _run_step_loop(agent_loop, messages):
                break  # /exit from within step loop
            continue

        # ── Normal (non-step) agent call ─────────────────────
        try:
            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                messages = agent_loop(messages)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            continue

        console.print()
        followup_response = _extract_response(messages)
        if followup_response:
            console.print(Markdown(format_response_text(followup_response)))

    console.print("[dim]Session ended.[/dim]")


# ── Step sub-loop ─────────────────────────────────────────────


def _run_step_loop(agent_loop, messages: list) -> bool:
    """Run a step-mode question through agent_loop, then enter
    a sub-loop waiting for /next, /end, or other commands.

    /next — continues the current step sequence.
    /end  — exits back to the main follow-up loop to start a new round.
    /exit — returns True to signal session exit.

    Returns:
        True if the main loop should exit (/exit was typed).
    """
    # First step
    try:
        with console.status("[dim]Step 1 — analyzing...[/dim]", spinner="dots"):
            messages = agent_loop(messages)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return False

    console.print()
    response = _extract_response(messages)
    if response:
        console.print(Markdown(format_response_text(response)))

    # Inner loop: /next, /end, or command
    while True:
        console.print()
        try:
            cmd = Prompt.ask("[dim]step >[/dim]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            return False

        # Commands that exit the step sub-loop
        if cmd.lower() == "/end":
            console.print(
                "[dim]本轮结束。请输入新问题，"
                "发送 /nostep 关闭分步模式，或 /exit 退出。[/dim]"
            )
            return False  # back to main follow-up loop

        if cmd.lower() == "/nostep":
            mode.set_step_mode(False)
            console.print("[dim]Step mode disabled.[/dim]")
            return False

        if cmd.lower() in ("/exit", "/quit", "exit", "quit"):
            return True  # signal main loop to exit

        mode_cmd = mode.detect_mode_command(cmd)
        if mode_cmd is not None:
            mode.set_mode(mode_cmd)
            console.print(
                f"[dim]Switched to Mode {mode.get_mode()} · "
                f"{mode.get_mode_label()}[/dim]"
            )
            continue

        # /next — next step
        if cmd.lower() == "/next":
            step_num = sum(
                1 for m in messages
                if m.get("role") == "user" and "[继续下一步]" in str(m.get("content", ""))
            ) + 2  # step 1 was first, so current is step N+1
            messages.append({"role": "user", "content": "[继续下一步]"})

            try:
                with console.status(
                    f"[dim]Step {step_num} — thinking...[/dim]", spinner="dots"
                ):
                    messages = agent_loop(messages)
            except Exception as exc:
                console.print(f"[red]Error:[/red] {exc}")
                continue

            console.print()
            response = _extract_response(messages)
            if response:
                console.print(Markdown(format_response_text(response)))
            continue

        # /step — already in step mode; no-op
        if cmd.lower() == "/step":
            console.print("[dim]Already in step mode.[/dim]")
            continue

        if not cmd:
            continue

        # Free text — treat as new query, exit step sub-loop
        msg = _make_user_message(cmd)
        msg["content"] = mode.build_step_instructions() + "\n\n" + msg["content"]
        messages.append(msg)

        try:
            with console.status("[dim]Step 1 — analyzing...[/dim]", spinner="dots"):
                messages = agent_loop(messages)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            continue

        console.print()
        response = _extract_response(messages)
        if response:
            console.print(Markdown(format_response_text(response)))
        # stay in step sub-loop for /next or /end
