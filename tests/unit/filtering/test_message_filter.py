"""Tests for message filtering service."""

import pytest
from datetime import datetime, timedelta

from email_csv_extractor.filtering.message_filter import EmailMessageFilter
from email_csv_extractor.core.interfaces import EmailMessage, CsvAttachment, FilterCriteria


class TestEmailMessageFilter:
    """Test cases for email message filter."""
    
    def test_init(self, mock_logger):
        """Test filter initialization."""
        config = {
            "csv_file_extensions": [".csv", ".CSV"],
            "min_file_size_bytes": 100,
            "max_file_size_mb": 50
        }
        
        filter_service = EmailMessageFilter(config, mock_logger)
        
        assert filter_service._csv_extensions == [".csv", ".CSV"]
        assert filter_service._min_file_size == 100
        assert filter_service._max_file_size_bytes == 50 * 1024 * 1024
    
    def test_should_process_message_no_attachments(self, mock_logger, sample_filter_criteria):
        """Test rejecting messages without attachments."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        message = EmailMessage(
            id="test-id",
            sender="test@example.com",
            subject="Test Subject",
            received_datetime="2024-01-01T12:00:00Z",
            has_attachments=False,
            body_preview="Test body"
        )
        
        result = filter_service.should_process_message(message, sample_filter_criteria)
        assert result is False
    
    def test_should_process_message_sender_pattern_match(self, mock_logger):
        """Test sender pattern matching."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        message = EmailMessage(
            id="test-id",
            sender="report@company.com",
            subject="Test Subject",
            received_datetime="2024-01-01T12:00:00Z",
            has_attachments=True,
            body_preview="Test body"
        )
        
        criteria = FilterCriteria(
            sender_patterns=["report@company.com", "data@partner.com"],
            subject_patterns=[],
            max_age_days=7
        )
        
        result = filter_service.should_process_message(message, criteria)
        assert result is True
    
    def test_should_process_message_sender_pattern_no_match(self, mock_logger):
        """Test sender pattern not matching."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        message = EmailMessage(
            id="test-id",
            sender="spam@bad.com",
            subject="Test Subject", 
            received_datetime="2024-01-01T12:00:00Z",
            has_attachments=True,
            body_preview="Test body"
        )
        
        criteria = FilterCriteria(
            sender_patterns=["report@company.com"],
            subject_patterns=[],
            max_age_days=7
        )
        
        result = filter_service.should_process_message(message, criteria)
        assert result is False
    
    def test_should_process_message_subject_pattern_match(self, mock_logger):
        """Test subject pattern matching."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        message = EmailMessage(
            id="test-id",
            sender="test@example.com",
            subject="Daily CSV Report",
            received_datetime="2024-01-01T12:00:00Z",
            has_attachments=True,
            body_preview="Test body"
        )
        
        criteria = FilterCriteria(
            sender_patterns=[],
            subject_patterns=["csv report", "data export"],
            max_age_days=7
        )
        
        result = filter_service.should_process_message(message, criteria)
        assert result is True
    
    def test_should_process_message_age_limit(self, mock_logger):
        """Test message age filtering."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        # Old message
        old_date = (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z"
        old_message = EmailMessage(
            id="test-id",
            sender="test@example.com",
            subject="Test Subject",
            received_datetime=old_date,
            has_attachments=True,
            body_preview="Test body"
        )
        
        criteria = FilterCriteria(
            sender_patterns=[],
            subject_patterns=[],
            max_age_days=7
        )
        
        result = filter_service.should_process_message(old_message, criteria)
        assert result is False
        
        # Recent message
        recent_date = (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"
        recent_message = EmailMessage(
            id="test-id-2",
            sender="test@example.com",
            subject="Test Subject",
            received_datetime=recent_date,
            has_attachments=True,
            body_preview="Test body"
        )
        
        result = filter_service.should_process_message(recent_message, criteria)
        assert result is True
    
    def test_extract_csv_attachments_valid(self, mock_logger):
        """Test extracting valid CSV attachments."""
        config = {
            "csv_file_extensions": [".csv"],
            "min_file_size_bytes": 100,
            "max_file_size_mb": 10
        }
        filter_service = EmailMessageFilter(config, mock_logger)
        
        attachments = [
            CsvAttachment(
                id="csv-1",
                name="report.csv",
                size=1024,
                content_type="text/csv"
            ),
            CsvAttachment(
                id="doc-1", 
                name="document.pdf",
                size=2048,
                content_type="application/pdf"
            ),
            CsvAttachment(
                id="csv-2",
                name="data.CSV",
                size=512,
                content_type="text/plain"
            )
        ]
        
        csv_attachments = filter_service.extract_csv_attachments(attachments)
        
        assert len(csv_attachments) == 2
        assert csv_attachments[0].name == "report.csv"
        assert csv_attachments[1].name == "data.CSV"
    
    def test_extract_csv_attachments_size_limits(self, mock_logger):
        """Test CSV attachment size filtering."""
        config = {
            "csv_file_extensions": [".csv"],
            "min_file_size_bytes": 500,
            "max_file_size_mb": 1  # 1MB = 1024*1024 bytes
        }
        filter_service = EmailMessageFilter(config, mock_logger)
        
        attachments = [
            CsvAttachment(
                id="too-small",
                name="tiny.csv",
                size=100,  # Below minimum
                content_type="text/csv"
            ),
            CsvAttachment(
                id="just-right",
                name="good.csv", 
                size=1000,  # Within limits
                content_type="text/csv"
            ),
            CsvAttachment(
                id="too-big",
                name="huge.csv",
                size=2 * 1024 * 1024,  # Above maximum
                content_type="text/csv"
            )
        ]
        
        csv_attachments = filter_service.extract_csv_attachments(attachments)
        
        assert len(csv_attachments) == 1
        assert csv_attachments[0].name == "good.csv"
    
    def test_matches_sender_patterns_regex(self, mock_logger):
        """Test sender pattern matching with regex."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        # Test regex pattern
        patterns = [r".*@company\.com", "exact@email.org"]
        
        # Should match regex
        assert filter_service._matches_sender_patterns("user@company.com", patterns)
        assert filter_service._matches_sender_patterns("admin@company.com", patterns)
        
        # Should match exact
        assert filter_service._matches_sender_patterns("exact@email.org", patterns)
        
        # Should not match
        assert not filter_service._matches_sender_patterns("user@other.com", patterns)
    
    def test_matches_sender_patterns_fallback(self, mock_logger):
        """Test sender pattern matching with invalid regex fallback."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        # Invalid regex pattern should fall back to substring matching
        patterns = ["[invalid-regex", "company"]
        
        # Should match substring fallback
        assert filter_service._matches_sender_patterns("user@company.com", patterns)
        
        # Should not match
        assert not filter_service._matches_sender_patterns("user@other.org", patterns)
    
    def test_is_message_within_age_limit_invalid_date(self, mock_logger):
        """Test age limit check with invalid date format."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        # Invalid date should return True (assume within limit)
        result = filter_service._is_message_within_age_limit("invalid-date", 7)
        assert result is True
    
    def test_has_csv_extension(self, mock_logger):
        """Test CSV extension checking."""
        config = {"csv_file_extensions": [".csv", ".CSV"]}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        assert filter_service._has_csv_extension("report.csv")
        assert filter_service._has_csv_extension("DATA.CSV")
        assert filter_service._has_csv_extension("file.Csv")  # Case insensitive
        assert not filter_service._has_csv_extension("document.pdf")
        assert not filter_service._has_csv_extension("file.txt")
        assert not filter_service._has_csv_extension("")
    
    def test_has_csv_content_type(self, mock_logger):
        """Test CSV content type checking."""
        config = {}
        filter_service = EmailMessageFilter(config, mock_logger)
        
        assert filter_service._has_csv_content_type("text/csv")
        assert filter_service._has_csv_content_type("application/csv")
        assert filter_service._has_csv_content_type("text/comma-separated-values")
        assert filter_service._has_csv_content_type("text/plain")
        assert not filter_service._has_csv_content_type("application/pdf")
        assert not filter_service._has_csv_content_type("")
    
    def test_get_filter_statistics(self, mock_logger):
        """Test getting filter statistics."""
        config = {
            "csv_file_extensions": [".csv", ".CSV"],
            "min_file_size_bytes": 1000,
            "max_file_size_mb": 50
        }
        filter_service = EmailMessageFilter(config, mock_logger)
        
        stats = filter_service.get_filter_statistics()
        
        assert stats["csv_extensions"] == [".csv", ".CSV"]
        assert stats["min_file_size_bytes"] == 1000
        assert stats["max_file_size_bytes"] == 50 * 1024 * 1024
        assert stats["max_file_size_mb"] == 50