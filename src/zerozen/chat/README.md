# ZeroZen Chat Module

This module contains the terminal-based chatbot interface built with Textual. The code has been refactored into a clean, modular structure for better maintainability and extensibility.

## 📁 Module Structure

```
src/zerozen/chat/
├── __init__.py          # Module exports and public API
├── app.py              # Main Textual application class
├── widgets.py          # Custom Textual widgets
├── commands.py         # Command handling and bot responses
├── cli.py              # CLI commands for chat interface
└── README.md           # This documentation
```

## 📚 Module Components

### `app.py` - Main Application

Contains the `ZeroZenChatApp` class - the main Textual application that:

- Defines the UI layout and styling
- Handles user interactions and message flow
- Manages application state and keyboard bindings
- Coordinates between widgets and command handlers

### `widgets.py` - UI Components

Custom Textual widgets that make up the chat interface:

- `ChatMessage` - Individual message display with rich formatting
- `ChatHistory` - Scrollable container for all messages
- `ChatInput` - Input area with send button
- `StatusBar` - Status information and help text
- `SidePanel` - Model selection and control buttons

### `commands.py` - Business Logic

The `ChatCommands` class handles:

- Chat command processing (`/help`, `/clear`, etc.)
- Bot response generation (currently demo mode)
- Message routing and state management
- Integration point for AI backends

### `cli.py` - Command Line Interface

Typer-based CLI commands:

- `zen chat` - Launch the chat interface
- `zen chat start` - Same as above (explicit command)
- Proper help text and command organization

## 🚀 Usage

### From Command Line

```bash
# Launch chat interface
zen chat

# Or explicitly use the start command
zen chat start
```

### Programmatic Usage

```python
from zerozen.chat import run_chat, ZeroZenChatApp

# Simple function call
run_chat()

# Or create app instance for customization
app = ZeroZenChatApp()
app.run()
```

### Import Individual Components

```python
from zerozen.chat import ChatMessage, ChatHistory, ChatCommands
from zerozen.chat.widgets import SidePanel, StatusBar
from zerozen.chat.commands import ChatCommands
```

## 🔧 Customization & Extension

### Adding New Widgets

Create new widgets in `widgets.py` and import them in `__init__.py`:

```python
class MyCustomWidget(Static):
    def compose(self):
        yield Label("My Custom Content")


# Add to __init__.py exports
__all__ = [..., "MyCustomWidget"]
```

### Extending Commands

Add new commands to the `ChatCommands` class:

```python
def handle_command(self, command: str) -> None:
    # ... existing commands ...
    elif cmd == "/mycmd":
        self.app.add_bot_message("My custom command response!")
```

### AI Backend Integration

Replace the `simulate_bot_response` method in `commands.py`:

```python
def simulate_bot_response(self, user_message: str) -> None:
    # Your AI integration here
    response = your_ai_model.generate(user_message)
    self.app.set_timer(0.1, lambda: self._delayed_response(response))
```

### Custom Styling

Modify the CSS in `app.py` or add new styles:

```python
CSS = """
/* Your custom styles here */
.my-custom-style {
    background: blue;
    color: white;
}
"""
```

## 🎯 Integration Points

1. **AI Backends**: Replace `ChatCommands.simulate_bot_response()`
1. **Model Selection**: Hook into the model dropdown in `SidePanel`
1. **Export Functionality**: Implement `export_chat()` method
1. **Settings Panel**: Create settings widgets and handlers
1. **Custom Commands**: Extend the command system
1. **Themes**: Add custom CSS themes and color schemes

## 🧪 Testing

```bash
# Test the interface
zen chat

# Test specific components in Python
python -c "from zerozen.chat import ZeroZenChatApp; ZeroZenChatApp().run()"
```

## 📝 Next Steps

1. **Real AI Integration**: Connect to OpenAI, Claude, or local models
1. **Persistence**: Save/load chat history
1. **Streaming**: Real-time response streaming
1. **File Support**: Document upload and analysis
1. **Themes**: Multiple color schemes
1. **Plugins**: Extensible plugin system

The modular structure makes it easy to extend any part of the system independently while maintaining clean separation of concerns.
