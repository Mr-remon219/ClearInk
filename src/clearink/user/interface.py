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
    console.print("[dim]Ask a follow-up, /mode 1, /mode 2, or /exit to quit.[/dim]")
    while True:
        console.print()
        try:
            followup = Prompt.ask("[dim]>[/dim]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break

        if followup.lower() in ("/exit", "/quit", "exit", "quit"):
            break

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

        messages.append(_make_user_message(followup))

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
