"""
Pytest tests voor Markdown Export Functionaliteit
Auteur: Joop Snijder

Tests om te controleren of markdown export correct werkt voor fact check rapporten.
"""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


# Import fact checker module (handle hyphenated filename)
@pytest.fixture(scope="session")
def fact_checker_module():
    """Load fact-checker.py module for testing"""
    project_root = Path(__file__).parent.parent
    spec = importlib.util.spec_from_file_location(
        "fact_checker", project_root / "fact-checker.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["fact_checker"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def export_to_markdown(fact_checker_module):
    """Get markdown export function"""
    return fact_checker_module.export_to_markdown


@pytest.fixture
def export_report_to_markdown_by_id(fact_checker_module):
    """Get markdown export by ID function"""
    return fact_checker_module.export_report_to_markdown_by_id


@pytest.fixture
def fact_check_history(fact_checker_module):
    """Get fact check history list"""
    return fact_checker_module.fact_check_history


@pytest.fixture
def sample_report_data():
    """Sample fact check report data for testing"""
    return {
        "original_text": "Tesla was founded in 2003 and has 100,000 employees.",
        "total_claims": 2,
        "verified_claims": 2,
        "false_claims": 0,
        "unverifiable_claims": 0,
        "overall_reliability": "High",
        "verifications": [
            {
                "original_claim": "Tesla has 100,000 employees",
                "claim_type": "Statistical",
                "verification_status": "Verified",
                "confidence_score": 0.95,
                "correct_information": "Tesla has approximately 127,855 employees as of 2024",
                "sources": [
                    "https://www.tesla.com/about",
                    "https://finance.yahoo.com/quote/TSLA/profile/",
                    "https://companiesmarketcap.com/tesla/number-of-employees/"
                ],
                "explanation": "According to Tesla's official reports and financial filings, the company has grown significantly and now employs over 127,000 people worldwide as of late 2023/early 2024."
            },
            {
                "original_claim": "Tesla was founded in 2003",
                "claim_type": "Historical",
                "verification_status": "Verified", 
                "confidence_score": 0.99,
                "correct_information": "Tesla was founded in July 2003",
                "sources": [
                    "https://en.wikipedia.org/wiki/Tesla,_Inc.",
                    "https://www.tesla.com/about",
                    "https://www.sec.gov/Archives/edgar/data/1318605/000119312510017054/d10k.htm"
                ],
                "explanation": "Tesla Motors was incorporated in July 2003 by Martin Eberhard and Marc Tarpenning. This is well-documented in official company filings and historical records."
            }
        ],
        "summary": "Both claims about Tesla are verified as accurate. The company was indeed founded in 2003, though the employee count has grown significantly beyond 100,000 to over 127,000 as of 2024.",
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def minimal_report_data():
    """Minimal fact check report data for edge case testing"""
    return {
        "original_text": "Simple test claim.",
        "total_claims": 1,
        "verified_claims": 0,
        "false_claims": 0,
        "unverifiable_claims": 1,
        "overall_reliability": "Low",
        "verifications": [],
        "summary": "No verifiable information found.",
        "timestamp": datetime.now().isoformat()
    }


class TestMarkdownExport:
    """Test class voor markdown export functionaliteit"""

    def test_export_to_markdown_with_filename(self, export_to_markdown, sample_report_data, tmp_path):
        """Test markdown export met een specifieke bestandsnaam"""
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Test export with original filename
            filename = export_to_markdown(sample_report_data, "test_document.txt")
            
            assert filename == "fc_test_document.md"
            assert Path(filename).exists()
            
            # Read and verify content
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check essential sections
            assert "# Fact Check Report" in content
            assert "## Summary" in content
            assert "Overall Reliability:** High" in content
            assert "Tesla has 100,000 employees" in content
            assert "Tesla was founded in 2003" in content
            assert "## Detailed Verification Results" in content
            assert "### Claim 1: Statistical" in content
            assert "### Claim 2: Historical" in content
            assert "## Original Text" in content
            assert "## About This Report" in content
            
        finally:
            os.chdir(original_cwd)

    def test_export_to_markdown_without_filename(self, export_to_markdown, sample_report_data, tmp_path):
        """Test markdown export zonder specifieke bestandsnaam"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Test export without original filename
            filename = export_to_markdown(sample_report_data)
            
            assert filename.startswith("fc_")
            assert filename.endswith(".md")
            assert Path(filename).exists()
            
            # Verify content structure
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert "# Fact Check Report" in content
            assert "Overall Reliability:** High" in content
            
        finally:
            os.chdir(original_cwd)

    def test_export_minimal_report(self, export_to_markdown, minimal_report_data, tmp_path):
        """Test markdown export met minimale report data"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            filename = export_to_markdown(minimal_report_data, "minimal_test.txt")
            
            assert filename == "fc_minimal_test.md"
            assert Path(filename).exists()
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check that it handles empty verifications gracefully
            assert "# Fact Check Report" in content
            assert "Overall Reliability:** Low" in content
            assert "No detailed verifications available" in content
            assert "Simple test claim" in content
            
        finally:
            os.chdir(original_cwd)

    def test_markdown_content_structure(self, export_to_markdown, sample_report_data, tmp_path):
        """Test de structuur van de gegenereerde markdown"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            filename = export_to_markdown(sample_report_data, "structure_test.txt")
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # Check specific markdown formatting
            assert lines[0] == "# Fact Check Report"
            
            # Check that sources are formatted as bullet points
            source_lines = [line for line in lines if line.startswith("- https://")]
            assert len(source_lines) >= 3  # At least 3 sources in our sample data
            
            # Check that claims are properly numbered
            assert "### Claim 1:" in content
            assert "### Claim 2:" in content
            
            # Check confidence scores are included
            assert "**Confidence Score:** 0.95" in content
            assert "**Confidence Score:** 0.99" in content
            
        finally:
            os.chdir(original_cwd)

    def test_markdown_handles_missing_fields(self, export_to_markdown, tmp_path):
        """Test hoe markdown export omgaat met ontbrekende velden"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Create report data with missing fields
            incomplete_data = {
                "total_claims": 1,
                "verified_claims": 1,
                "false_claims": 0,
                "verifications": [
                    {
                        "original_claim": "Test claim",
                        "verification_status": "Verified"
                        # Missing other fields intentionally
                    }
                ]
            }
            
            filename = export_to_markdown(incomplete_data, "incomplete_test.txt")
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should handle missing fields gracefully
            assert "# Fact Check Report" in content
            assert "Overall Reliability:** Unknown" in content
            assert "No summary available" in content
            assert "**Confidence Score:** N/A" in content
            
        finally:
            os.chdir(original_cwd)

    def test_export_by_id_success(self, fact_check_history, sample_report_data, tmp_path):
        """Test export by report ID functionality"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Add a report to history
            from fact_checker import FactCheckReport, export_report_to_markdown_by_id
            report = FactCheckReport.model_validate(sample_report_data)
            fact_check_history.clear()  # Start fresh
            fact_check_history.append(report)
            
            # Test the export function
            result = export_report_to_markdown_by_id(0, "id_test")
            
            assert result["status"] == "success"
            assert "fc_id_test.md" in result["filename"]
            assert Path(result["filename"]).exists()
            
        finally:
            os.chdir(original_cwd)
            fact_check_history.clear()  # Clean up

    def test_export_by_id_invalid_id(self, fact_check_history):
        """Test export function with invalid report ID"""
        fact_check_history.clear()  # Ensure empty history
        
        from fact_checker import export_report_to_markdown_by_id
        result = export_report_to_markdown_by_id(999, "test")
        
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_special_characters_in_content(self, export_to_markdown, tmp_path):
        """Test markdown export met speciale karakters"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            special_data = {
                "original_text": "Tesla heeft €50 miljard omzet & 100% groei!",
                "total_claims": 1,
                "verified_claims": 1,
                "false_claims": 0,
                "unverifiable_claims": 0,
                "overall_reliability": "High",
                "verifications": [
                    {
                        "original_claim": "Tesla heeft €50 miljard omzet & 100% groei",
                        "claim_type": "Financial",
                        "verification_status": "Verified",
                        "confidence_score": 0.85,
                        "explanation": "Financiële data met speciale tekens: €, &, %",
                        "sources": ["https://example.com/finance"]
                    }
                ],
                "summary": "Test met speciale karakters: €, &, %, <, >",
                "timestamp": datetime.now().isoformat()
            }
            
            filename = export_to_markdown(special_data, "special_chars.txt")
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Special characters should be preserved
            assert "€50 miljard" in content
            assert "100% groei" in content
            assert "&" in content
            
        finally:
            os.chdir(original_cwd)

    def test_large_report_export(self, export_to_markdown, tmp_path):
        """Test export van groot rapport met veel claims"""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Create large report with many claims
            large_data = {
                "original_text": "Large test document with many claims.",
                "total_claims": 5,
                "verified_claims": 3,
                "false_claims": 1,
                "unverifiable_claims": 1,
                "overall_reliability": "Medium",
                "verifications": [
                    {
                        "original_claim": f"Claim number {i+1}",
                        "claim_type": "Test",
                        "verification_status": "Verified" if i < 3 else "False" if i == 3 else "Unverifiable",
                        "confidence_score": 0.8 - (i * 0.1),
                        "explanation": f"Explanation for claim {i+1}",
                        "sources": [f"https://source{i+1}.com"]
                    }
                    for i in range(5)
                ],
                "summary": "Large report with multiple claims for testing purposes.",
                "timestamp": datetime.now().isoformat()
            }
            
            filename = export_to_markdown(large_data, "large_report.txt")
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check all claims are included
            for i in range(1, 6):
                assert f"### Claim {i}:" in content
                assert f"Claim number {i}" in content
            
            # Check statistics
            assert "**Total Claims:** 5" in content
            assert "**Verified Claims:** 3" in content
            assert "**False Claims:** 1" in content
            
        finally:
            os.chdir(original_cwd)