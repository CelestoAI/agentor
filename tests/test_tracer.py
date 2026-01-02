"""Tests for the Celesto tracing module."""

import os
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest
from agents.tracing import Span, Trace

from agentor.tracer import (
    CelestoExporter,
    get_run_config,
    setup_celesto_tracing,
)


class TestCelestoExporter:
    """Test suite for CelestoExporter class."""

    def test_init(self):
        """Test CelestoExporter initialization."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
            timeout=15.0,
        )

        assert exporter.endpoint == "https://api.celesto.ai/v1/traces/ingest"
        assert exporter.token == "test-token"
        assert exporter.timeout == 15.0
        assert isinstance(exporter._client, httpx.Client)

    def test_init_default_timeout(self):
        """Test CelestoExporter initialization with default timeout."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        assert exporter.timeout == 10.0

    @patch("httpx.Client.post")
    def test_export_empty_items(self, mock_post):
        """Test export with empty items list."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        exporter.export([])

        # Should not make any HTTP request
        mock_post.assert_not_called()

    @patch("httpx.Client.post")
    def test_export_trace(self, mock_post):
        """Test exporting a trace."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        # Create a mock trace
        mock_trace = Mock(spec=Trace)
        mock_trace.trace_id = "trace-123"
        mock_trace.name = "test_workflow"
        mock_trace.export.return_value = {
            "id": "trace-123",
            "workflow_name": "test_workflow",
            "group_id": "group-456",
            "metadata": {"key": "value"},
        }

        exporter.export([mock_trace])

        # Verify HTTP request
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.celesto.ai/v1/traces/ingest"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

        # Verify payload
        payload = call_args[1]["json"]
        assert "data" in payload
        assert len(payload["data"]) == 1
        assert payload["data"][0]["object"] == "trace"
        assert payload["data"][0]["id"] == "trace-123"
        assert payload["data"][0]["workflow_name"] == "test_workflow"

    @patch("httpx.Client.post")
    def test_export_span(self, mock_post):
        """Test exporting a span."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        # Create a mock span
        mock_span = Mock(spec=Span)
        mock_span.span_id = "span-123"
        mock_span.trace_id = "trace-456"
        mock_span.span_data = None
        mock_span.export.return_value = {
            "span_id": "span-123",
            "trace_id": "trace-456",
            "parent_id": "parent-789",
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:01:00Z",
            "span_data": {"type": "llm"},
        }

        exporter.export([mock_span])

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify payload
        payload = call_args[1]["json"]
        assert "data" in payload
        assert len(payload["data"]) == 1
        assert payload["data"][0]["object"] == "trace.span"
        assert payload["data"][0]["span_id"] == "span-123"
        assert payload["data"][0]["trace_id"] == "trace-456"

    @patch("httpx.Client.post")
    def test_export_http_error(self, mock_post, capsys):
        """Test export handles HTTP errors gracefully."""
        mock_post.side_effect = httpx.HTTPError("Connection failed")

        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        # Create a mock trace
        mock_trace = Mock(spec=Trace)
        mock_trace.trace_id = "trace-123"
        mock_trace.export.return_value = {
            "id": "trace-123",
            "workflow_name": "test",
        }

        # Should not raise exception
        exporter.export([mock_trace])

        # Verify error was printed
        captured = capsys.readouterr()
        assert "Failed to export traces" in captured.out

    def test_convert_trace(self):
        """Test _convert_trace method."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        mock_trace = Mock(spec=Trace)
        mock_trace.trace_id = "trace-123"
        mock_trace.name = "workflow_name"

        exported = {
            "id": "trace-123",
            "workflow_name": "test_workflow",
            "group_id": "group-456",
            "metadata": {"key": "value"},
        }

        result = exporter._convert_trace(mock_trace, exported)

        assert result["object"] == "trace"
        assert result["id"] == "trace-123"
        assert result["workflow_name"] == "test_workflow"
        assert result["group_id"] == "group-456"
        assert result["metadata"] == {"key": "value"}

    def test_convert_span_basic(self):
        """Test _convert_span method with basic span."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        mock_span = Mock(spec=Span)
        mock_span.span_id = "span-123"
        mock_span.trace_id = "trace-456"
        mock_span.span_data = None

        exported = {
            "span_id": "span-123",
            "trace_id": "trace-456",
            "parent_id": "parent-789",
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:01:00Z",
            "span_data": {},
        }

        result = exporter._convert_span(mock_span, exported)

        assert result["object"] == "trace.span"
        assert result["span_id"] == "span-123"
        assert result["trace_id"] == "trace-456"
        assert result["parent_id"] == "parent-789"
        assert "span_data" in result

    def test_convert_span_with_response(self):
        """Test _convert_span with response data."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        # Create a mock span with response data
        mock_response = Mock()
        mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "Hello"}}]
        }

        mock_span_data = Mock()
        mock_span_data.type = "llm"
        mock_span_data.response = mock_response
        mock_span_data.input = [{"role": "user", "content": "Hi"}]
        mock_span_data.model = "gpt-4"
        mock_span_data.usage = {"total_tokens": 100}

        mock_span = Mock(spec=Span)
        mock_span.span_id = "span-123"
        mock_span.trace_id = "trace-456"
        mock_span.span_data = mock_span_data

        exported = {
            "span_id": "span-123",
            "trace_id": "trace-456",
            "span_data": {},
        }

        result = exporter._convert_span(mock_span, exported)

        assert result["span_data"]["type"] == "llm"
        assert result["span_data"]["model"] == "gpt-4"
        assert "response" in result["span_data"]
        assert "input" in result["span_data"]

    def test_serialize_primitives(self):
        """Test _serialize with primitive types."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        assert exporter._serialize(None) is None
        assert exporter._serialize("test") == "test"
        assert exporter._serialize(42) == 42
        assert exporter._serialize(3.14) == 3.14
        assert exporter._serialize(True) is True

    def test_serialize_collections(self):
        """Test _serialize with collections."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        assert exporter._serialize([1, 2, 3]) == [1, 2, 3]
        assert exporter._serialize((1, 2, 3)) == [1, 2, 3]
        assert exporter._serialize({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_serialize_nested(self):
        """Test _serialize with nested structures."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        data = {"list": [1, 2, {"nested": "value"}], "string": "test"}
        result = exporter._serialize(data)

        assert result == {"list": [1, 2, {"nested": "value"}], "string": "test"}

    def test_serialize_object_with_model_dump(self):
        """Test _serialize with object having model_dump method."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        mock_obj = Mock()
        mock_obj.model_dump.return_value = {"field": "value"}

        result = exporter._serialize(mock_obj)
        assert result == {"field": "value"}

    def test_serialize_object_with_dict(self):
        """Test _serialize with object having dict method."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        mock_obj = Mock()
        del mock_obj.model_dump  # Remove model_dump
        mock_obj.dict.return_value = {"field": "value"}

        result = exporter._serialize(mock_obj)
        assert result == {"field": "value"}

    def test_serialize_object_with_dict_attr(self):
        """Test _serialize with object having __dict__."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        class TestObj:
            def __init__(self):
                self.public = "value"
                self._private = "hidden"

        result = exporter._serialize(TestObj())
        assert result == {"public": "value"}
        assert "_private" not in result

    def test_shutdown(self):
        """Test shutdown method."""
        exporter = CelestoExporter(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        with patch.object(exporter._client, "close") as mock_close:
            exporter.shutdown()
            mock_close.assert_called_once()


class TestSetupCelestoTracing:
    """Test suite for setup_celesto_tracing function."""

    @patch("agentor.tracer.BatchTraceProcessor")
    @patch("agentor.tracer.set_trace_processors")
    @patch("agentor.tracer.atexit.register")
    def test_setup_celesto_tracing_default(
        self, mock_atexit, mock_set_processors, mock_batch_processor
    ):
        """Test setup_celesto_tracing with default parameters."""
        mock_processor = Mock()
        mock_batch_processor.return_value = mock_processor

        result = setup_celesto_tracing(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
        )

        # Verify processor was created
        mock_batch_processor.assert_called_once()
        call_kwargs = mock_batch_processor.call_args[1]
        assert isinstance(call_kwargs["exporter"], CelestoExporter)
        assert call_kwargs["schedule_delay"] == 1.0
        assert call_kwargs["max_batch_size"] == 256

        # Verify processor was set as default
        mock_set_processors.assert_called_once_with([mock_processor])

        # Verify atexit was registered
        mock_atexit.assert_called_once()

        # Verify return value
        assert result == mock_processor

    @patch("agentor.tracer.BatchTraceProcessor")
    @patch("agentor.tracer.add_trace_processor")
    @patch("agentor.tracer.set_trace_processors")
    def test_setup_celesto_tracing_add_processor(
        self, mock_set_processors, mock_add_processor, mock_batch_processor
    ):
        """Test setup_celesto_tracing with replace_default=False."""
        mock_processor = Mock()
        mock_batch_processor.return_value = mock_processor

        setup_celesto_tracing(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
            replace_default=False,
        )

        # Should add processor instead of replacing
        mock_add_processor.assert_called_once_with(mock_processor)
        mock_set_processors.assert_not_called()

    @patch("agentor.tracer.BatchTraceProcessor")
    @patch("agentor.tracer.set_trace_processors")
    def test_setup_celesto_tracing_custom_params(
        self, mock_set_processors, mock_batch_processor
    ):
        """Test setup_celesto_tracing with custom parameters."""
        mock_processor = Mock()
        mock_batch_processor.return_value = mock_processor

        setup_celesto_tracing(
            endpoint="https://api.celesto.ai/v1/traces/ingest",
            token="test-token",
            batch_delay=2.0,
            max_batch_size=512,
        )

        # Verify custom parameters were used
        call_kwargs = mock_batch_processor.call_args[1]
        assert call_kwargs["schedule_delay"] == 2.0
        assert call_kwargs["max_batch_size"] == 512


class TestGetRunConfig:
    """Test suite for get_run_config function."""

    def test_get_run_config_default(self):
        """Test get_run_config with default parameters."""
        config = get_run_config()

        assert config.trace_include_sensitive_data is True
        assert config.group_id is None
        assert config.trace_metadata is None

    def test_get_run_config_with_group_id(self):
        """Test get_run_config with group_id."""
        config = get_run_config(group_id="session-123")

        assert config.trace_include_sensitive_data is True
        assert config.group_id == "session-123"
        assert config.trace_metadata is None

    def test_get_run_config_with_metadata(self):
        """Test get_run_config with metadata."""
        metadata = {"user_id": "user-456", "source": "api"}
        config = get_run_config(metadata=metadata)

        assert config.trace_include_sensitive_data is True
        assert config.group_id is None
        assert config.trace_metadata == metadata

    def test_get_run_config_with_all_params(self):
        """Test get_run_config with all parameters."""
        metadata = {"user_id": "user-456"}
        config = get_run_config(group_id="session-123", metadata=metadata)

        assert config.trace_include_sensitive_data is True
        assert config.group_id == "session-123"
        assert config.trace_metadata == metadata


class TestShutdownHandler:
    """Test suite for shutdown handler."""

    @patch("agentor.tracer._processor")
    def test_shutdown_handler_success(self, mock_processor_global):
        """Test shutdown handler with successful flush."""
        from agentor.tracer import _shutdown_handler

        mock_processor = Mock()
        with patch("agentor.tracer._processor", mock_processor):
            _shutdown_handler()

            mock_processor.force_flush.assert_called_once()
            mock_processor.shutdown.assert_called_once()

    @patch("logging.getLogger")
    def test_shutdown_handler_error(self, mock_get_logger):
        """Test shutdown handler handles errors gracefully."""
        from agentor.tracer import _shutdown_handler

        mock_processor = Mock()
        mock_processor.force_flush.side_effect = Exception("Flush failed")

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        with patch("agentor.tracer._processor", mock_processor):
            # Should not raise exception
            _shutdown_handler()

            # Should log warning
            mock_logger.warning.assert_called_once()

    def test_shutdown_handler_no_processor(self):
        """Test shutdown handler when no processor is set."""
        from agentor.tracer import _shutdown_handler

        with patch("agentor.tracer._processor", None):
            # Should not raise exception
            _shutdown_handler()
