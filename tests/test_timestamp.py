"""Test to ensure timestamps are generated correctly"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import importlib.util

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module directly from the file
spec = importlib.util.spec_from_file_location("fact_checker", 
                                               Path(__file__).parent.parent / "fact-checker.py")
fact_checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fact_checker)

export_to_markdown = fact_checker.export_to_markdown


class TestTimestamp:
    """Test timestamp generation in fact check reports"""

    def test_export_markdown_uses_current_timestamp(self):
        """Test that export_to_markdown uses current timestamp when not provided"""
        # Create a test report without timestamp
        report_data = {
            'original_text': 'Test claim',
            'total_claims': 1,
            'verified_claims': 1,
            'false_claims': 0,
            'unverifiable_claims': 0,
            'overall_reliability': 'High',
            'summary': 'Test summary',
            'verifications': []
        }
        
        # Export to markdown
        before_time = datetime.now()
        output_file = export_to_markdown(report_data)
        after_time = datetime.now()
        
        # Read the generated file
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Extract the timestamp from the markdown
        import re
        match = re.search(r'\*\*Generated on:\*\* (.+)', content)
        assert match, "Could not find timestamp in markdown"
        
        timestamp_str = match.group(1)
        
        # Parse the timestamp
        # Try multiple formats as isoformat can vary
        for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S']:
            try:
                timestamp = datetime.strptime(timestamp_str.split('+')[0].split('Z')[0], fmt)
                break
            except ValueError:
                continue
        else:
            pytest.fail(f"Could not parse timestamp: {timestamp_str}")
        
        # Check that timestamp is within reasonable range (should be very recent)
        assert before_time <= timestamp <= after_time + timedelta(seconds=1), \
            f"Timestamp {timestamp} not in expected range {before_time} to {after_time}"
        
        # Clean up
        Path(output_file).unlink()
    
    def test_export_markdown_respects_provided_timestamp(self):
        """Test that export_to_markdown uses provided timestamp when available"""
        # Create a test report with specific timestamp
        test_timestamp = "2025-01-15T10:30:00Z"
        report_data = {
            'original_text': 'Test claim',
            'total_claims': 1,
            'verified_claims': 1,
            'false_claims': 0,
            'unverifiable_claims': 0,
            'overall_reliability': 'High',
            'summary': 'Test summary',
            'timestamp': test_timestamp,
            'verifications': []
        }
        
        # Export to markdown
        output_file = export_to_markdown(report_data)
        
        # Read the generated file
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Check that the provided timestamp is used
        assert f"**Generated on:** {test_timestamp}" in content, \
            f"Expected timestamp {test_timestamp} not found in markdown"
        
        # Clean up
        Path(output_file).unlink()
    
    def test_no_placeholder_timestamps(self):
        """Test that we never get placeholder timestamps like 2022-04-01"""
        # Create a test report without timestamp
        report_data = {
            'original_text': 'Test claim',
            'total_claims': 1,
            'verified_claims': 1,
            'false_claims': 0,
            'unverifiable_claims': 0,
            'overall_reliability': 'High',
            'summary': 'Test summary',
            'verifications': []
        }
        
        # Export to markdown
        output_file = export_to_markdown(report_data)
        
        # Read the generated file
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Check for known placeholder dates
        placeholder_dates = [
            "2022-04-01",
            "2023-12-31",
            "2024-12-31",
            "2022-01-01",
            "2023-01-01",
            "2024-01-01",
            "T00:00:00Z"
        ]
        
        for placeholder in placeholder_dates:
            assert placeholder not in content, \
                f"Found placeholder timestamp {placeholder} in output"
        
        # Clean up
        Path(output_file).unlink()
    
    def test_timestamp_in_same_directory_as_input(self):
        """Test that timestamp is correct when saving to different directory"""
        import tempfile
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test input file
            test_file = Path(tmpdir) / "test_input.txt"
            test_file.write_text("Test content")
            
            # Create report data
            report_data = {
                'original_text': 'Test claim',
                'total_claims': 1,
                'verified_claims': 1,
                'false_claims': 0,
                'unverifiable_claims': 0,
                'overall_reliability': 'High',
                'summary': 'Test summary',
                'verifications': []
            }
            
            # Export to markdown with input file path
            before_time = datetime.now()
            output_file = export_to_markdown(report_data, str(test_file))
            after_time = datetime.now()
            
            # Check that file is in correct directory
            assert Path(output_file).parent == Path(tmpdir), \
                f"Output file {output_file} not in expected directory {tmpdir}"
            
            # Read and check timestamp
            with open(output_file, 'r') as f:
                content = f.read()
            
            # Extract and verify timestamp
            import re
            match = re.search(r'\*\*Generated on:\*\* (.+)', content)
            assert match, "Could not find timestamp in markdown"
            
            timestamp_str = match.group(1)
            
            # Should not be a placeholder
            assert "2022-04-01" not in timestamp_str, "Found placeholder timestamp"
            assert "T00:00:00Z" not in timestamp_str, "Found placeholder timestamp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])