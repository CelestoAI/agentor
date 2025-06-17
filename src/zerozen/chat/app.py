"""
Main Textual application for ZeroZen chat interface.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Label
from textual.binding import Binding
from .widgets import ChatHistory, ChatInput, StatusBar, SidePanel
from .commands import ChatCommands


class ZeroZenChatApp(App):
    """Main Textual application for ZeroZen chatbot interface."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 4 4;
        grid-columns: 1fr 3fr;
        grid-rows: auto 1fr auto auto;
    }
    
    Header {
        column-span: 2;
        background: $primary;
        color: $text;
    }
    
    SidePanel {
        row-span: 2;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }
    
    ChatHistory {
        background: $background;
        border: solid $primary;
        padding: 1;
    }
    
    ChatInput {
        column-span: 1;
        background: $surface;
        height: 3;
        padding: 1;
    }
    
    StatusBar {
        column-span: 2;
        background: $surface;
        color: $text;
        height: 1;
        padding: 0 1;
    }
    
    .sidebar-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    .sidebar-section {
        margin: 1 0;
        text-style: bold;
        color: $accent;
    }
    
    Input {
        margin-right: 1;
    }
    
    Button {
        min-width: 8;
    }
    
    ChatMessage {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+e", "export_chat", "Export"),
        Binding("f1", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.title = "ZeroZen - AI Chat Interface"
        self.sub_title = "LLMs in Zen mode"
        self.message_count = 0
        self.commands = ChatCommands(self)

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield SidePanel()
        yield ChatHistory(id="chat_history")
        yield ChatInput()
        yield StatusBar(id="status_bar")

    def on_mount(self) -> None:
        """Handle app mounting."""
        self.query_one(StatusBar).status = "Connected - Ready to chat!"
        # Add welcome message
        self.add_bot_message(
            "Welcome to ZeroZen! 🧘‍♂️\n\n"
            "I'm your AI assistant running in zen mode. How can I help you today?\n\n"
            "**Quick tips:**\n"
            "- Type `/help` for available commands\n"
            "- Use `Ctrl+L` to clear chat\n"
            "- Press `F1` for help\n"
            "- Press `Ctrl+C` to exit"
        )

    def send_user_message(self, message: str) -> None:
        """Handle sending a user message."""
        # Handle special commands
        if message.startswith("/"):
            self.commands.handle_command(message)
            return

        # Add user message to chat
        chat_history = self.query_one("#chat_history", ChatHistory)
        chat_history.add_message(message, is_user=True)
        self.message_count += 1
        self.update_message_count()

        # Update status
        status_bar = self.query_one("#status_bar", StatusBar)
        status_bar.status = "Processing..."

        # Generate bot response
        self.commands.simulate_bot_response(message)

    def add_bot_message(self, message: str) -> None:
        """Add a bot message to the chat."""
        chat_history = self.query_one("#chat_history", ChatHistory)
        chat_history.add_message(message, is_user=False)
        self.message_count += 1
        self.update_message_count()

    def clear_chat(self) -> None:
        """Clear the chat history."""
        chat_history = self.query_one("#chat_history", ChatHistory)
        chat_history.clear_messages()
        self.message_count = 0
        self.update_message_count()
        self.add_bot_message("Chat cleared! How can I help you?")

    def export_chat(self) -> None:
        """Export chat to file (placeholder)."""
        self.add_bot_message("💾 Chat export feature coming soon!")

    def show_settings(self) -> None:
        """Show settings (placeholder)."""
        self.add_bot_message("⚙️ Settings panel coming soon!")

    def update_message_count(self) -> None:
        """Update the message count display."""
        try:
            count_label = self.query_one("#message_count", Label)
            count_label.update(f"Messages: {self.message_count}")
        except Exception:
            pass

    def action_help(self) -> None:
        """Show help."""
        self.commands.handle_command("/help")

    def action_clear_chat(self) -> None:
        """Clear chat via keybinding."""
        self.clear_chat()

    def action_export_chat(self) -> None:
        """Export chat via keybinding."""
        self.export_chat()


def run_chat():
    """Run the ZeroZen chat application."""
    app = ZeroZenChatApp()
    app.run()
