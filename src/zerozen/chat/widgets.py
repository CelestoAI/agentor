"""
Custom Textual widgets for the ZeroZen chat interface.
"""

from datetime import datetime
from typing import List
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Static, Input, Button, Label, Select
from textual.reactive import reactive
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel


class ChatMessage(Static):
    """A widget representing a single chat message."""

    def __init__(
        self, content: str, is_user: bool = True, timestamp: str = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.content = content
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now().strftime("%H:%M")
        self.update_display()

    def update_display(self):
        """Update the message display."""
        if self.is_user:
            # User message styling
            message = Text()
            message.append(f"[{self.timestamp}] ", style="dim")
            message.append("You: ", style="bold cyan")
            message.append(self.content, style="white")
            self.update(
                Panel(
                    message,
                    border_style="cyan",
                    padding=(0, 1),
                    title="User",
                    title_align="left",
                )
            )
        else:
            # Bot message styling
            message = Text()
            message.append(f"[{self.timestamp}] ", style="dim")
            message.append("ZeroZen: ", style="bold green")

            # Try to render as markdown if it looks like markdown
            if any(marker in self.content for marker in ["```", "**", "*", "#", ">"]):
                try:
                    md = Markdown(self.content)
                    self.update(
                        Panel(
                            md,
                            border_style="green",
                            padding=(0, 1),
                            title="ZeroZen",
                            title_align="left",
                        )
                    )
                    return
                except Exception:
                    pass

            message.append(self.content, style="white")
            self.update(
                Panel(
                    message,
                    border_style="green",
                    padding=(0, 1),
                    title="ZeroZen",
                    title_align="left",
                )
            )


class ChatHistory(ScrollableContainer):
    """Container for chat messages with auto-scroll."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages: List[ChatMessage] = []

    def add_message(self, content: str, is_user: bool = True):
        """Add a new message to the chat."""
        message = ChatMessage(content, is_user)
        self.messages.append(message)
        self.mount(message)
        # Auto-scroll to bottom
        self.call_after_refresh(self.scroll_end)

    def clear_messages(self):
        """Clear all messages from the chat."""
        for message in self.messages:
            message.remove()
        self.messages.clear()


class ChatInput(Container):
    """Chat input area with send button."""

    def compose(self):
        with Horizontal():
            yield Input(placeholder="Type your message here...", id="message_input")
            yield Button("Send", variant="primary", id="send_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send_button":
            self.send_message()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message_input":
            self.send_message()

    def send_message(self):
        """Send the current message."""
        input_widget = self.query_one("#message_input", Input)
        message = input_widget.value.strip()
        if message:
            self.app.send_user_message(message)
            input_widget.value = ""


class StatusBar(Static):
    """Status bar showing connection status and info."""

    status = reactive("Ready")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.update_display()

    def watch_status(self, status: str):
        """Update display when status changes."""
        self.update_display()

    def update_display(self):
        """Update the status bar display."""
        self.update(
            f"Status: {self.status} | Type /help for commands | Press Ctrl+C to exit"
        )


class SidePanel(Container):
    """Side panel with model selection and settings."""

    def compose(self):
        yield Label("🤖 ZeroZen Chat", classes="sidebar-title")
        yield Static("Model Selection:", classes="sidebar-section")
        yield Select(
            [
                ("GPT-4", "gpt-4"),
                ("GPT-3.5 Turbo", "gpt-3.5-turbo"),
                ("Claude-3", "claude-3"),
                ("Local Model", "local"),
            ],
            value="gpt-4",
            id="model_select",
        )

        yield Static("Quick Actions:", classes="sidebar-section")
        yield Button("Clear Chat", variant="warning", id="clear_chat")
        yield Button("Export Chat", variant="default", id="export_chat")
        yield Button("Settings", variant="default", id="settings")

        yield Static("Chat Stats:", classes="sidebar-section")
        yield Label("Messages: 0", id="message_count")
        yield Label("Active: ✅", id="connection_status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear_chat":
            self.app.clear_chat()
        elif event.button.id == "export_chat":
            self.app.export_chat()
        elif event.button.id == "settings":
            self.app.show_settings()
