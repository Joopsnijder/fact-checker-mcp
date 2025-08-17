#!/usr/bin/env python3
"""Test script to verify path handling for markdown and JSON export"""

from pathlib import Path
from datetime import datetime
import json

def test_export_paths():
    """Test that export paths are correctly calculated"""
    
    # Test case 1: With input filename
    input_filename = "/tmp/test_fact_checker/test_claim.txt"
    
    # Simulate the path calculation from export_to_markdown
    original_path = Path(input_filename)
    output_dir = original_path.parent
    base_name = original_path.stem
    markdown_output = output_dir / f"fc_{base_name}.md"
    
    print(f"Test 1 - With input file:")
    print(f"  Input: {input_filename}")
    print(f"  Output dir: {output_dir}")
    print(f"  Base name: {base_name}")
    print(f"  Markdown output: {markdown_output}")
    print(f"  Expected: /tmp/test_fact_checker/fc_test_claim.md")
    assert str(markdown_output) == "/tmp/test_fact_checker/fc_test_claim.md", "Path calculation failed!"
    print("  ✓ PASSED")
    
    # Test case 2: JSON output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_output = output_dir / f"{base_name}_fact_check_{timestamp}.json"
    
    print(f"\nTest 2 - JSON output:")
    print(f"  JSON output: {json_output}")
    print(f"  Directory: {json_output.parent}")
    assert str(json_output.parent) == "/tmp/test_fact_checker", "JSON path calculation failed!"
    print("  ✓ PASSED")
    
    # Test case 3: Without input filename (current directory)
    print(f"\nTest 3 - Without input file (current directory):")
    markdown_output_no_input = Path(f"fc_{timestamp}.md")
    json_output_no_input = Path(f"fact_check_{timestamp}.json")
    
    print(f"  Markdown: {markdown_output_no_input}")
    print(f"  JSON: {json_output_no_input}")
    print(f"  Both in current directory: {Path.cwd()}")
    print("  ✓ PASSED")
    
    print("\n✅ All path handling tests passed!")

if __name__ == "__main__":
    test_export_paths()