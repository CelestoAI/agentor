from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    WebClient = None
    SlackApiError = Exception

import logging

logger = logging.getLogger(__name__)


class SlackTool(BaseTool):
    name = "slack"
    description = "Interact with Slack."

    def __init__(self, token: str, api_key: Optional[str] = None):
        if WebClient is None:
            raise ImportError(
                "Slack dependency is missing. Please install it with `pip install agentor[slack]`."
            )
        super().__init__(api_key)
        self.client = WebClient(token=token)

    @capability
    def send_message(self, channel: str, text: str) -> str:
        """Send a message to a Slack channel."""
        try:
            response = self.client.chat_postMessage(channel=channel, text=text)
            return f"Message sent: {response['ts']}"
        except SlackApiError as e:
            logger.exception("Slack API Error", e)
            return f"Slack API Error: {e.response['error']}"
        except Exception as e:
            return f"Error sending message: {str(e)}"

    @capability
    def list_channels(self) -> str:
        """List public channels."""
        try:
            response = self.client.conversations_list()
            channels = response["channels"]
            return "\n".join([f"#{c['name']} ({c['id']})" for c in channels])
        except SlackApiError as e:
            logger.exception("Slack API Error", e)
            return f"Slack API Error: {e.response['error']}"
        except Exception as e:
            logger.error(f"Error listing channels: {str(e)}")
            return f"Error listing channels: {str(e)}"
