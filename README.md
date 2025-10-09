<center>

<div align="center">

<h1>Agentor</h1>

<h2>Fastest way to build, prototype and deploy AI Agents.</h2>
Connect AI Agents with your everyday tools — Gmail, Calendar, CRMs, and more — in minutes.


<img src="/assets/Agentor.png" alt="banner" width="640" />



[![💻 Try Celesto AI](https://img.shields.io/badge/%F0%9F%92%BB%20Try%20CelestoAI-Click%20Here-blue?style=for-the-badge)](https://celesto.ai)

[![PyPI version](https://badge.fury.io/py/agentor.svg)](https://badge.fury.io/py/agentor)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

</div>
</center>

## ✨ What is Agentor?

Agentor is an open-source framework for building AI assistants that handle your personal and professional tasks.
Connect it with your everyday tools — Gmail, Calendar, CRMs, and more — in minutes.


## 🚀 Quick Start

<p align="center">
  🔧 <b>DIY with OSS</b> &nbsp; | &nbsp; 
  🖥️ <a href="https://celesto.ai" target="_blank"><b>Try the CelestoAI web interface</b></a>
</p>

### Installation

```bash
pip install agentor
```

## Examples

### Chat with email and calendar

1. **Start chatting with your data**:

   ```bash
   agentor chat
   ```

1. **Ask questions like**:

   - *"Show me emails from GitHub about security alerts"*
   - *"What meetings do I have this week?"*
   - *"Find invoices from Stripe in my Gmail"*


#### Setup Gmail and Calendar integration

The `agentor setup-google` command guides you through:

1. **Creating Google Cloud Project** (if needed)
1. **Enabling APIs** (Gmail, Calendar)
1. **OAuth credentials** (desktop app)
1. **Browser authentication** (automatic)
1. **Credential storage** (secure, local)

**1. First run:**

```bash
agentor setup-google
# ✅ Opens browser for one-time authentication
# ✅ Saves credentials locally
# ✅ Ready to use!
```

**2. Already set up:**

```bash
agentor setup-google
# ✅ Google credentials already exist
# Use --force to re-authenticate
```

# 🧑‍💻 Developer Experience

Use Agentor programmatically in your applications:

```python
from agentor import agents

# Simple agent usage
result = agents.run_sync(
    "Find emails from GitHub about security issues", tools=["search_gmail"], max_turns=3
)
print(result)

# Advanced usage with specific tools
result = agents.run_sync(
    "What's my schedule conflicts next week?",
    tools=["list_calendar_events", "search_gmail"],
    model="gpt-5-mini",  # Optional model override
)
```

## Use Tools & Services without LLMs

You can direcrly use the underlying tools and services without using LLMs such as search through emails and calendar events.

```python
from agentor.integrations.google import GmailService, load_user_credentials

# Load your saved credentials
creds = load_user_credentials("credentials.my_google_account.json")

# Direct tool usage
gmail = GmailService(creds)
messages = gmail.search_messages(query="from:github.com", limit=10)
```

## Building Public Applications with OAuth

If you are building an application which is used by multiple public users, it's recommended to authenticate them using OAuth to access their data. For example, you can build a public application which allows users to search through their emails and calendar events.


```python
from agentor.integrations.google import CredentialRecord, UserProviderMetadata, UserInfo

# Create from your database/API
user_creds = CredentialRecord(
    access_token="ya29.xxx",
    user_provider_metadata=UserProviderMetadata(
        refresh_token="1//xxx",
        scope=(
            "openid "
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/calendar "
            "https://www.googleapis.com/auth/calendar.readonly "
            "https://www.googleapis.com/auth/userinfo.email "
            "https://www.googleapis.com/auth/userinfo.profile"
        ),
        expires_at=1234567890,
    ),
    user_info=UserInfo(email="user@example.com", sub="google_user_id"),
    client_id="your_oauth_client_id",
    client_secret="your_oauth_secret",
)

# Use with any tool
gmail = GmailService(user_creds)
```


## 🔧 Configuration

### CLI Options

You can use the following CLI options to configure the Agentor CLI.

```bash
agentor chat --help
```

### Environment Variables

```bash
# Optional: Set default model
export OPENAI_MODEL=gpt-4o

# Optional: Custom credential paths
agentor setup-google --credentials-file /path/to/creds.json
agentor setup-google --user-storage /path/to/user-creds.json
```


## 🔐 Security & Privacy

**🛡️ Your data stays yours:**

- **Local credentials** - Stored securely on your machine
- **No data collection** - We don't see your emails or calendar
- **Open source** - Audit the code yourself
- **Standard OAuth** - Uses Google's official authentication

**🔒 Credential management:**

- Automatic token refresh
- Secure local storage
- Per-user isolation
- Configurable file paths


## 🛣️ Roadmap

| Feature | Status | Description |
|---------|--------|-------------|
| Gmail Integration | ✅ | Search, read, analyze emails |
| Google Calendar | ✅ | View events, check availability |
| Chat Interface | ✅ | Conversational AI with memory |
| Desktop OAuth | ✅ | One-command authentication |
| Backend API | ✅ | Programmatic access |
| Calendar Management | ✅ | Create, update events |
| **Email Actions** | 🔜 | Draft, reply, send emails |
| **Slack Integration** | 🔜 | Team communication |
| **Document AI** | 🔜 | Google Docs, Sheets analysis |
| **Multi-user Support** | 🔜 | Team deployments |
| **Plugin System** | 🔮 | Custom integrations |


## 🤝 Contributing

We'd love your help making Agentor even better! Please read our [Contributing Guidelines](.github/CONTRIBUTING.md) and [Code of Conduct](.github/CODE_OF_CONDUCT.md).

## 🙏 Acknowledgments

**Built with love using:**

- [OpenAI Agents](https://github.com/openai/agents) - The backbone of our AI system
- [Typer](https://typer.tiangolo.com/) - Beautiful CLI interfaces
- [Rich](https://rich.readthedocs.io/) - Rich text and formatting
- [Google APIs](https://developers.google.com/) - Gmail and Calendar integration

**Special thanks to:**

- The open-source community for inspiration and contributions
- Early beta testers for valuable feedback

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE) for details.
