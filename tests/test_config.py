"""Tests for the Celesto configuration module."""

import os
from unittest.mock import patch

import pytest

from agentor.config import CelestoConfig, celesto_config


class TestCelestoConfig:
    """Test suite for CelestoConfig class."""

    def test_default_values(self):
        """Test CelestoConfig default values."""
        config = CelestoConfig()

        assert config.base_url == "https://api.celesto.ai/v1"
        assert config.api_key is None
        assert config.disable_auto_tracing is False

    def test_custom_base_url(self):
        """Test CelestoConfig with custom base_url."""
        with patch.dict(
            os.environ, {"CELESTO_BASE_URL": "https://custom.api.com/v2"}, clear=False
        ):
            config = CelestoConfig()
            assert config.base_url == "https://custom.api.com/v2"

    def test_custom_api_key(self):
        """Test CelestoConfig with custom api_key."""
        with patch.dict(os.environ, {"CELESTO_API_KEY": "test-key-123"}, clear=False):
            config = CelestoConfig()
            assert config.api_key is not None
            assert config.api_key.get_secret_value() == "test-key-123"

    def test_disable_auto_tracing_true(self):
        """Test CelestoConfig with disable_auto_tracing set to True."""
        with patch.dict(
            os.environ, {"CELESTO_DISABLE_AUTO_TRACING": "true"}, clear=False
        ):
            config = CelestoConfig()
            assert config.disable_auto_tracing is True

    def test_disable_auto_tracing_false(self):
        """Test CelestoConfig with disable_auto_tracing set to False."""
        with patch.dict(
            os.environ, {"CELESTO_DISABLE_AUTO_TRACING": "false"}, clear=False
        ):
            config = CelestoConfig()
            assert config.disable_auto_tracing is False

    def test_all_custom_values(self):
        """Test CelestoConfig with all custom values."""
        env_vars = {
            "CELESTO_BASE_URL": "https://custom.api.com/v3",
            "CELESTO_API_KEY": "custom-key-456",
            "CELESTO_DISABLE_AUTO_TRACING": "True",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = CelestoConfig()
            assert config.base_url == "https://custom.api.com/v3"
            assert config.api_key.get_secret_value() == "custom-key-456"
            assert config.disable_auto_tracing is True

    def test_api_key_is_secret(self):
        """Test that api_key is properly stored as SecretStr."""
        with patch.dict(os.environ, {"CELESTO_API_KEY": "secret-key"}, clear=False):
            config = CelestoConfig()
            # Should not expose secret directly
            assert "secret-key" not in str(config.api_key)
            # But should be accessible via get_secret_value()
            assert config.api_key.get_secret_value() == "secret-key"

    def test_global_config_instance(self):
        """Test that celesto_config is a valid instance."""
        assert isinstance(celesto_config, CelestoConfig)
        assert celesto_config.base_url == "https://api.celesto.ai/v1"


class TestCelestoConfigFieldAliases:
    """Test suite for CelestoConfig field aliases."""

    def test_base_url_alias(self):
        """Test CELESTO_BASE_URL environment variable alias."""
        with patch.dict(
            os.environ, {"CELESTO_BASE_URL": "https://test.api.com"}, clear=False
        ):
            config = CelestoConfig()
            assert config.base_url == "https://test.api.com"

    def test_api_key_alias(self):
        """Test CELESTO_API_KEY environment variable alias."""
        with patch.dict(os.environ, {"CELESTO_API_KEY": "test-api-key"}, clear=False):
            config = CelestoConfig()
            assert config.api_key.get_secret_value() == "test-api-key"

    def test_disable_auto_tracing_alias(self):
        """Test CELESTO_DISABLE_AUTO_TRACING environment variable alias."""
        with patch.dict(
            os.environ, {"CELESTO_DISABLE_AUTO_TRACING": "1"}, clear=False
        ):
            config = CelestoConfig()
            assert config.disable_auto_tracing is True


class TestCelestoConfigBooleanParsing:
    """Test suite for CelestoConfig boolean value parsing."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
        ],
    )
    def test_disable_auto_tracing_boolean_values(self, env_value, expected):
        """Test various boolean representations for disable_auto_tracing."""
        with patch.dict(
            os.environ, {"CELESTO_DISABLE_AUTO_TRACING": env_value}, clear=False
        ):
            config = CelestoConfig()
            assert config.disable_auto_tracing is expected
