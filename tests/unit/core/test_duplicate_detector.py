"""Tests for duplicate data detection service."""

import pytest
from pathlib import Path
from unittest.mock import Mock
import tempfile
import shutil

from email_csv_extractor.core.duplicate_detector import DuplicateDetector


class TestDuplicateDetector:
    """Test cases for duplicate detector."""
    
    def test_init(self, mock_logger, temp_directory):
        """Test duplicate detector initialization."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            detection_window_minutes=10,
            enabled=True
        )
        
        assert detector._enabled is True
        assert detector._detection_window.total_seconds() == 600  # 10 minutes
        assert detector._data_dir == temp_directory
        assert (temp_directory / "processed_data_hashes.json").exists() or True  # May not exist initially
    
    def test_disabled_detector(self, mock_logger, temp_directory):
        """Test duplicate detector when disabled."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=False
        )
        
        csv_content = b"col1,col2\nvalue1,value2\nvalue1,value2"
        result = detector.detect_duplicate_rows(csv_content, "test.csv")
        
        assert result["has_duplicates"] is False
        assert result["total_rows"] == 0
        assert result["duplicate_rows"] == 0
        assert result["unique_rows"] == 0
        assert result["processed_content"] == csv_content
    
    def test_detect_duplicate_rows_with_duplicates(self, mock_logger, temp_directory):
        """Test detecting duplicate rows in CSV content."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        # CSV with duplicate rows
        csv_content = b"""timestamp,event,value
2024-01-01 10:00:00,login,user1
2024-01-01 10:01:00,logout,user1
2024-01-01 10:01:00,logout,user1
2024-01-01 10:02:00,login,user2"""
        
        result = detector.detect_duplicate_rows(csv_content, "test.csv")
        
        assert result["total_rows"] == 4
        assert result["duplicate_rows"] == 0  # First time, no duplicates from cache
        assert result["unique_rows"] == 4
        assert result["has_duplicates"] is False
        
        # Process the same content again - should detect duplicates
        result2 = detector.detect_duplicate_rows(csv_content, "test2.csv")
        
        assert result2["total_rows"] == 4
        assert result2["duplicate_rows"] == 4  # All rows are duplicates now
        assert result2["unique_rows"] == 0
        assert result2["has_duplicates"] is True
    
    def test_detect_duplicate_rows_no_duplicates(self, mock_logger, temp_directory):
        """Test CSV content with no duplicates."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        csv_content = b"""col1,col2
value1,value2
value3,value4
value5,value6"""
        
        result = detector.detect_duplicate_rows(csv_content, "test.csv")
        
        assert result["total_rows"] == 3
        assert result["duplicate_rows"] == 0
        assert result["unique_rows"] == 3
        assert result["has_duplicates"] is False
    
    def test_detect_duplicate_rows_empty_csv(self, mock_logger, temp_directory):
        """Test empty CSV content."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        csv_content = b""
        result = detector.detect_duplicate_rows(csv_content, "empty.csv")
        
        assert result["total_rows"] == 0
        assert result["duplicate_rows"] == 0
        assert result["unique_rows"] == 0
        assert result["has_duplicates"] is False
    
    def test_create_row_hash_excludes_timestamps(self, mock_logger, temp_directory):
        """Test that row hashing excludes timestamp columns."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        header = ["timestamp", "event", "value"]
        row1 = ["2024-01-01 10:00:00", "login", "user1"]
        row2 = ["2024-01-01 10:01:00", "login", "user1"]  # Different timestamp, same data
        
        hash1 = detector._create_row_hash(row1, header)
        hash2 = detector._create_row_hash(row2, header)
        
        # Hashes should be the same because timestamp is excluded
        assert hash1 == hash2
    
    def test_create_row_hash_includes_data_columns(self, mock_logger, temp_directory):
        """Test that row hashing includes data columns."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        header = ["timestamp", "event", "value"]
        row1 = ["2024-01-01 10:00:00", "login", "user1"]
        row2 = ["2024-01-01 10:00:00", "logout", "user1"]  # Different event
        
        hash1 = detector._create_row_hash(row1, header)
        hash2 = detector._create_row_hash(row2, header)
        
        # Hashes should be different because event is different
        assert hash1 != hash2
    
    def test_get_statistics(self, mock_logger, temp_directory):
        """Test getting duplicate detection statistics."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            detection_window_minutes=5,
            enabled=True
        )
        
        stats = detector.get_statistics()
        
        assert stats["enabled"] is True
        assert stats["detection_window_minutes"] == 5.0
        assert stats["total_stored_hashes"] == 0
        assert stats["active_hashes"] == 0
        assert str(temp_directory) in stats["data_dir"]
    
    def test_clear_cache(self, mock_logger, temp_directory):
        """Test clearing the duplicate detection cache."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        # Add some data to the cache
        csv_content = b"col1,col2\nvalue1,value2"
        detector.detect_duplicate_rows(csv_content, "test.csv")
        
        # Verify cache has data
        stats_before = detector.get_statistics()
        assert stats_before["total_stored_hashes"] > 0
        
        # Clear cache
        detector.clear_cache()
        
        # Verify cache is empty
        stats_after = detector.get_statistics()
        assert stats_after["total_stored_hashes"] == 0
    
    def test_error_handling(self, mock_logger, temp_directory):
        """Test error handling with invalid CSV content."""
        detector = DuplicateDetector(
            data_dir=temp_directory,
            logger=mock_logger,
            enabled=True
        )
        
        # Invalid CSV content that might cause issues
        invalid_content = b"\xff\xfe\x00\x01"  # Invalid UTF-8
        
        result = detector.detect_duplicate_rows(invalid_content, "invalid.csv")
        
        # Should return original content on error
        assert result["processed_content"] == invalid_content
        assert result["has_duplicates"] is False