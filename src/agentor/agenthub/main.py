import os
from typing import Optional, Tuple

from agents import Agent
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from agentor.integrations.google.google_agent import (
    create_google_agent,
    create_google_context,
)

from .web_search import web_search_agent

concept_research_agent = Agent(
    name="Concept research agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert concept researcher. For every request, think about the topic, language, and complexity of the request.
You must use the web_search tool to get latest information about the topic. Replan the implementation and write the code.
""",
    model="gpt-5",
    tools=[
        web_search_agent.as_tool(
            tool_name="web_search",
            tool_description="Search the web for information on coding related topics",
        )
    ],
)


coder_agent = Agent(
    name="Coder agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert coder. For every request, think about the topic, language, and complexity of the request.
You must use the web_search tool to get latest information about the topic. Replan the implementation and write the code.
""",
    model="gpt-5",
    handoffs=[concept_research_agent],
)

# Google agent initialization - lazy loaded to avoid import errors
_google_agent_cache: Optional[Tuple[Agent, any]] = None


def get_google_agent_and_context():
    """Get Google agent, building it on first access."""
    global _google_agent_cache
    if _google_agent_cache is None:
        try:
            agent = create_google_agent()
            context = create_google_context()
            _google_agent_cache = (agent, context)
        except FileNotFoundError as e:
            # Check what type of credentials are missing and provide specific guidance
            user_creds_file = "credentials.my_google_account.json"
            credentials_file = "credentials.json"

            if not os.path.exists(user_creds_file) and not os.path.exists(
                credentials_file
            ):
                # Missing OAuth app credentials (dev setup)
                error_msg = (
                    "❌ Google OAuth app credentials missing!\n\n"
                    "🔧 SETUP REQUIRED:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create/select project\n"
                    "3. Enable Gmail API and Calendar API\n"
                    "4. Create OAuth 2.0 Client ID (Desktop application)\n"
                    "5. Download JSON as 'credentials.json'\n"
                    "6. Run this again!\n\n"
                    f"📁 Place credentials.json in: {os.getcwd()}"
                )
            elif not os.path.exists(user_creds_file):
                # Has OAuth app credentials but missing user authentication
                if os.path.exists(credentials_file):
                    # Try automatic authentication
                    print(
                        "🔄 Found credentials.json - starting automatic authentication..."
                    )
                    try:
                        import json

                        from agentor.integrations.google.creds import (
                            DEFAULT_GOOGLE_OAUTH_SCOPES,
                            authenticate_user,
                        )

                        # Extract client credentials
                        with open(credentials_file) as f:
                            creds_data = json.load(f)
                            client_id = creds_data["installed"]["client_id"]
                            client_secret = creds_data["installed"]["client_secret"]

                        # Authenticate user automatically
                        scopes = DEFAULT_GOOGLE_OAUTH_SCOPES

                        print("🌐 Opening browser for authentication...")
                        creds = authenticate_user(
                            client_id=client_id,
                            client_secret=client_secret,
                            scopes=scopes,
                            user_storage_path=user_creds_file,
                            credentials_file=credentials_file,
                        )

                        print(f"✅ Authentication successful for: {creds.user_id}")
                        print("🔄 Retrying agent initialization...")

                        # Retry building the agent
                        agent = create_google_agent()
                        context = create_google_context()
                        _google_agent_cache = (agent, context)
                        return _google_agent_cache

                    except Exception as auth_error:
                        error_msg = (
                            f"❌ Automatic authentication failed: {auth_error}\n\n"
                            "🔧 MANUAL FIX:\n"
                            "Run: python examples/desktop_oauth_demo.py\n\n"
                            "📄 Missing file: credentials.my_google_account.json"
                        )
                else:
                    error_msg = (
                        "❌ User authentication required!\n\n"
                        "🔧 QUICK FIX:\n"
                        "Run: agentor setup-google\n"
                        "(This will open your browser to authenticate)\n\n"
                        "📄 Missing file: credentials.my_google_account.json"
                    )
            else:
                # Other error
                error_msg = f"❌ Google credential error: {e}"

            raise FileNotFoundError(error_msg)
    return _google_agent_cache


def get_main_agent():
    """Get main agent with available handoffs."""
    handoffs = [coder_agent]

    # Add Google agent (required)
    google_agent, _ = get_google_agent_and_context()
    if google_agent is None:
        raise FileNotFoundError(
            "Google credentials not found. Please run 'agentor setup-google' first to authenticate."
        )
    handoffs.append(google_agent)

    return Agent(
        name="Triage agent",
        instructions="Handoff to the appropriate agent whenever required. E.g. when the user asks for a code, handoff to the coder agent.",
        handoffs=handoffs,
        model="gpt-4o",
    )


# Create main agent with available handoffs
# Use lazy loading to avoid import-time Google credential requirements
_main_agent = None


def get_main_agent_instance():
    """Get the main agent instance, creating it if necessary."""
    global _main_agent
    if _main_agent is None:
        _main_agent = get_main_agent()
    return _main_agent


# For backward compatibility, provide main_agent as a lazy property
class LazyMainAgent:
    def __getattr__(self, name):
        agent = get_main_agent_instance()
        return getattr(agent, name)

    def __call__(self, *args, **kwargs):
        agent = get_main_agent_instance()
        return agent(*args, **kwargs)


main_agent = LazyMainAgent()
