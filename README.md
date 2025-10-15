<p align="center">
  <img src="https://raw.githubusercontent.com/CelestoAI/agentor/main/assets/celesto.png" alt="banner" />
  <br>
  <strong>Fastest way to build, prototype and deploy AI Agents with tools <mark><i>securely</i></mark></strong>
</p>
<p align="center">
  <a href="https://developers.celesto.ai">Docs</a> |
  <a href="https://github.com/celestoai/agentor/tree/main/examples">Examples</a>
</p>

--- 

[![💻 Try Celesto AI](https://img.shields.io/badge/%F0%9F%92%BB_Try_CelestoAI-Click_Here-ff6b2c?style=flat)](https://celesto.ai)
[![PyPI version](https://img.shields.io/pypi/v/agentor.svg?color=brightgreen&label=PyPI&style=flat)](https://pypi.org/project/agentor/)
[![Tests](https://github.com/CelestoAI/agentor/actions/workflows/test.yml/badge.svg)](https://github.com/CelestoAI/agentor/actions/workflows/test.yml)
[![Downloads](https://img.shields.io/pypi/dm/agentor.svg?label=Downloads&color=ff6b2c&style=flat)](https://pypi.org/project/agentor/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-yellow?style=flat)](https://opensource.org/licenses/Apache-2.0)
[![Discord](https://img.shields.io/badge/Join%20Us%20on%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KNb5UkrAmm)


## What is Agentor?

Agentor is an open-source framework that makes it easy to build multi-agent pipelines with secure integrations across email, calendars, CRMs, and more.

It lets you connect LLMs to tools — like Gmail, Google Calendar, and your CRM — securely, in just minutes.

## 🚅 Quick Start

### Installation

**Recommended:**

The recommended method of installing `agentor` is with pip from PyPI.

```bash
pip install agentor
```

**Latest (unstable):**

You can also install the latest bleeding edge version (could be unstable) of `agentor`, should you feel motivated enough, as follows:

```bash
pip install git+https://github.com/celestoai/agentor@main
```

## Examples

### Agents API

Use Agentor using the API in your applications:

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

## 🚀 Features

<p align="center">
  🔧 <b>Build with OSS</b> &nbsp; | &nbsp; 
  🧡 <a href="https://celesto.ai" target="_blank"><b>Managed Multi-Agent Platform</b></a>
</p>

✅ Pre-built agents with ready-to-use tools\
🔐 Secure integrations with email, calendar, CRMs, and more\
☁️ Easy agent deployment\
🦾 AgentMCP - Tool routing\
🧩 OpenAI App SDK for rapid development

### Managed Tool Hub (ready-to-use collection of tools)

Use Celesto [Tool Hub](https://celesto.ai/toolhub) for a realtime access to weather data and 100+ tools.

```python
from agentor import CelestoSDK

client = CelestoSDK(CELESTOAI_API_KEY)

# List all available tools
client.toolhub.list_tools()

# Run the weather tool for a specific location
client.toolhub.run_weather_tool("London")

# Run the Google email tool
client.toolhub.run_list_google_emails(limit=5)
```

### Tool Routing with AgentMCP

Adding multiple tools directly to a single Agent can bloat the LLM’s context and degrade performance. Agentor solves this with `AgentMCP` — a unified interface that aggregates all your tools under one connection to the LLM.

From the model’s perspective, there’s just one tool; `AgentMCP` automatically routes each request to the appropriate underlying tool based on context.

### Secure Tool use with LLMs

You can direcrly use the underlying tools and services without using LLMs such as search through emails and calendar events.

```python
from agentor.integrations.google import GmailService, load_user_credentials

# Load your saved credentials
creds = load_user_credentials("credentials.my_google_account.json")

# Direct tool usage
gmail = GmailService(creds)
messages = gmail.search_messages(query="from:github.com", limit=10)
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

### Tool-use and Security

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

## 🤝 Contributing

We'd love your help making Agentor even better! Please read our [Contributing Guidelines](.github/CONTRIBUTING.md) and [Code of Conduct](.github/CODE_OF_CONDUCT.md).

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE) for details.
