"""Duplicate data detection service for handling overlapping log files."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Set, List, Optional, Any
import csv
import io

from .interfaces import Logger
from .exceptions import EmailCsvExtractorError


class DuplicateDetector:
    """Service for detecting and handling duplicate data in overlapping log files."""
    
    def __init__(self, 
                 data_dir: Path, 
                 logger: Logger,
                 detection_window_minutes: int = 15,
                 enabled: bool = True) -> None:
        """Initialize the duplicate detector.
        
        Args:
            data_dir: Directory to store processed data hashes
            logger: Logger instance
            detection_window_minutes: Time window to check for duplicates
            enabled: Whether duplicate detection is enabled
        """
        self._data_dir = data_dir
        self._logger = logger
        self._detection_window = timedelta(minutes=detection_window_minutes)
        self._enabled = enabled
        
        # Create data directory
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # File to store processed data hashes
        self._hash_store_file = self._data_dir / "processed_data_hashes.json"
        
        # Load existing hashes
        self._processed_hashes = self._load_processed_hashes()
        
        self._logger.info(
            "Initialized duplicate detector",
            enabled=self._enabled,
            detection_window_minutes=detection_window_minutes,
            stored_hashes=len(self._processed_hashes),
            data_dir=str(self._data_dir)
        )
    
    def detect_duplicate_rows(self, csv_content: bytes, filename: str) -> Dict[str, Any]:
        """Detect duplicate rows in CSV content and return processing info.
        
        Args:
            csv_content: Raw CSV file content
            filename: Name of the CSV file for logging
            
        Returns:
            Dictionary with processing information:
            - has_duplicates: bool
            - total_rows: int
            - duplicate_rows: int
            - unique_rows: int
            - processed_content: bytes (deduplicated content)
            - row_hashes: Set[str] (hashes of processed rows)
        """
        if not self._enabled:
            return {
                "has_duplicates": False,
                "total_rows": 0,
                "duplicate_rows": 0,
                "unique_rows": 0,
                "processed_content": csv_content,
                "row_hashes": set()
            }
        
        try:
            # Parse CSV content
            csv_text = csv_content.decode('utf-8-sig')  # Handle BOM
            csv_reader = csv.reader(io.StringIO(csv_text))
            
            # Read all rows
            rows = list(csv_reader)
            
            if not rows:
                self._logger.warning(f"Empty CSV file: {filename}")
                return {
                    "has_duplicates": False,
                    "total_rows": 0,
                    "duplicate_rows": 0,
                    "unique_rows": 0,
                    "processed_content": csv_content,
                    "row_hashes": set()
                }
            
            # Extract header
            header = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            
            # Process rows for duplicates
            unique_rows = []
            row_hashes = set()
            duplicate_count = 0
            
            for row in data_rows:
                # Create hash for the row (excluding any timestamp columns that might vary)
                row_hash = self._create_row_hash(row, header)
                
                # Check if we've seen this row recently
                if self._is_duplicate_row(row_hash):
                    duplicate_count += 1
                    self._logger.debug(
                        f"Duplicate row detected in {filename}",
                        row_hash=row_hash[:8],
                        row_data=row[:3] if len(row) > 3 else row  # Log first few columns
                    )
                else:
                    unique_rows.append(row)
                    row_hashes.add(row_hash)
            
            # Create deduplicated CSV content
            if unique_rows or header:
                output = io.StringIO()
                csv_writer = csv.writer(output)
                
                # Write header
                if header:
                    csv_writer.writerow(header)
                
                # Write unique rows
                csv_writer.writerows(unique_rows)
                
                processed_content = output.getvalue().encode('utf-8')
            else:
                processed_content = b""
            
            # Store new hashes
            self._store_row_hashes(row_hashes)
            
            result = {
                "has_duplicates": duplicate_count > 0,
                "total_rows": len(data_rows),
                "duplicate_rows": duplicate_count,
                "unique_rows": len(unique_rows),
                "processed_content": processed_content,
                "row_hashes": row_hashes
            }
            
            self._logger.info(
                f"Duplicate detection completed for {filename}",
                **{k: v for k, v in result.items() if k not in ["processed_content", "row_hashes"]}
            )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Failed to detect duplicates in {filename}",
                error=str(e),
                error_type=type(e).__name__
            )
            # Return original content on error
            return {
                "has_duplicates": False,
                "total_rows": 0,
                "duplicate_rows": 0,
                "unique_rows": 0,
                "processed_content": csv_content,
                "row_hashes": set()
            }
    
    def _create_row_hash(self, row: List[str], header: List[str]) -> str:
        """Create a hash for a CSV row, excluding timestamp columns that might vary.
        
        Args:
            row: CSV row data
            header: CSV header row
            
        Returns:
            SHA-256 hash of the row
        """
        # Common timestamp column names to exclude from hashing
        timestamp_columns = {
            'timestamp', 'time', 'datetime', 'date', 'created_at', 'updated_at',
            'processed_at', 'logged_at', 'received_at', 'sent_at'
        }
        
        # Create filtered row excluding timestamp columns
        filtered_row = []
        for i, value in enumerate(row):
            if i < len(header):
                column_name = header[i].lower().strip()
                # Skip timestamp columns
                if column_name not in timestamp_columns:
                    filtered_row.append(value.strip())
            else:
                filtered_row.append(value.strip())
        
        # Create hash
        row_str = '|'.join(filtered_row)
        return hashlib.sha256(row_str.encode('utf-8')).hexdigest()
    
    def _is_duplicate_row(self, row_hash: str) -> bool:
        """Check if a row hash represents a duplicate within the detection window.
        
        Args:
            row_hash: Hash of the row
            
        Returns:
            True if the row is a duplicate
        """
        current_time = datetime.utcnow()
        
        # Check if hash exists and is within detection window
        if row_hash in self._processed_hashes:
            hash_time = datetime.fromisoformat(self._processed_hashes[row_hash])
            if current_time - hash_time <= self._detection_window:
                return True
        
        return False
    
    def _store_row_hashes(self, row_hashes: Set[str]) -> None:
        """Store new row hashes with timestamps.
        
        Args:
            row_hashes: Set of row hashes to store
        """
        current_time = datetime.utcnow()
        
        # Add new hashes
        for row_hash in row_hashes:
            self._processed_hashes[row_hash] = current_time.isoformat()
        
        # Clean up old hashes outside detection window
        self._cleanup_old_hashes()
        
        # Save to disk
        self._save_processed_hashes()
    
    def _cleanup_old_hashes(self) -> None:
        """Remove hashes that are outside the detection window."""
        current_time = datetime.utcnow()
        expired_hashes = []
        
        for row_hash, timestamp_str in self._processed_hashes.items():
            hash_time = datetime.fromisoformat(timestamp_str)
            if current_time - hash_time > self._detection_window:
                expired_hashes.append(row_hash)
        
        # Remove expired hashes
        for row_hash in expired_hashes:
            del self._processed_hashes[row_hash]
        
        if expired_hashes:
            self._logger.debug(
                f"Cleaned up {len(expired_hashes)} expired row hashes"
            )
    
    def _load_processed_hashes(self) -> Dict[str, str]:
        """Load processed hashes from disk.
        
        Returns:
            Dictionary of hash -> timestamp
        """
        if not self._hash_store_file.exists():
            return {}
        
        try:
            with open(self._hash_store_file, 'r') as f:
                data = json.load(f)
                self._logger.debug(f"Loaded {len(data)} processed hashes from disk")
                return data
        except Exception as e:
            self._logger.warning(
                f"Failed to load processed hashes: {e}. Starting fresh."
            )
            return {}
    
    def _save_processed_hashes(self) -> None:
        """Save processed hashes to disk."""
        try:
            with open(self._hash_store_file, 'w') as f:
                json.dump(self._processed_hashes, f, indent=2)
        except Exception as e:
            self._logger.error(f"Failed to save processed hashes: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get duplicate detection statistics.
        
        Returns:
            Dictionary with statistics
        """
        current_time = datetime.utcnow()
        active_hashes = 0
        
        for timestamp_str in self._processed_hashes.values():
            hash_time = datetime.fromisoformat(timestamp_str)
            if current_time - hash_time <= self._detection_window:
                active_hashes += 1
        
        return {
            "enabled": self._enabled,
            "detection_window_minutes": self._detection_window.total_seconds() / 60,
            "total_stored_hashes": len(self._processed_hashes),
            "active_hashes": active_hashes,
            "data_dir": str(self._data_dir)
        }
    
    def clear_cache(self) -> None:
        """Clear all processed hashes."""
        self._processed_hashes.clear()
        if self._hash_store_file.exists():
            self._hash_store_file.unlink()
        
        self._logger.info("Cleared duplicate detection cache")