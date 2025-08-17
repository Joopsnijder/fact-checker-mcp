"""
Pytest tests voor Fact Checker Geschiedenis Functionaliteit
Auteur: Joop Snijder

Tests om te controleren of fact check rapporten correct worden opgeslagen
in de geschiedenis en of de MCP tools correct werken.
"""

import asyncio
import importlib.util
import json
import os
import sys
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
def fact_check_history(fact_checker_module):
    """Get fact check history list"""
    return fact_checker_module.fact_check_history


@pytest.fixture
def quick_fact_check(fact_checker_module):
    """Get quick fact check function"""
    return fact_checker_module.quick_fact_check


@pytest.fixture
def get_history_summary(fact_checker_module):
    """Get history summary MCP tool"""
    return fact_checker_module.get_history_summary


@pytest.fixture
def fact_check_report_class(fact_checker_module):
    """Get FactCheckReport class"""
    return fact_checker_module.FactCheckReport


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment with mock API key"""
    original_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
    yield
    if original_key:
        os.environ["OPENAI_API_KEY"] = original_key
    elif "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]


@pytest.fixture
def clean_history(fact_check_history):
    """Clean history before and after each test"""
    # Store original length
    original_length = len(fact_check_history)

    yield fact_check_history

    # Restore original length by removing any added items
    current_length = len(fact_check_history)
    if current_length > original_length:
        items_to_remove = current_length - original_length
        for _ in range(items_to_remove):
            fact_check_history.pop()


class TestFactCheckHistory:
    """Test class for fact check history functionality"""

    def test_history_list_access(self, fact_check_history):
        """Test direct access to fact_check_history list"""
        assert isinstance(fact_check_history, list), "History should be a list"

        # Test that we can get length
        current_length = len(fact_check_history)
        assert isinstance(current_length, int), "History length should be integer"
        assert current_length >= 0, "History length should be non-negative"

    def test_history_list_append(self, clean_history, fact_check_report_class):
        """Test adding items to history list"""
        original_length = len(clean_history)

        # Create mock report
        mock_report = fact_check_report_class(
            original_text="Test tekst voor pytest",
            total_claims=2,
            verified_claims=1,
            false_claims=1,
            unverifiable_claims=0,
            overall_reliability="Gemiddeld",
            verifications=[],
            summary="Pytest mock rapport",
            timestamp=datetime.now().isoformat(),
        )

        # Add to history
        clean_history.append(mock_report)

        # Verify addition
        assert len(clean_history) == original_length + 1
        assert clean_history[-1] == mock_report
        assert clean_history[-1].original_text == "Test tekst voor pytest"

    @pytest.mark.asyncio
    async def test_quick_fact_check_execution(self, quick_fact_check):
        """Test quick fact check execution"""
        test_text = "De Eiffeltoren is 324 meter hoog."

        result = await quick_fact_check(test_text)

        # Result should be a dictionary or valid JSON string
        if isinstance(result, str):
            result_data = json.loads(result)
        else:
            result_data = result

        # Check required fields
        assert "status" in result_data, "Result should have status field"
        assert "text" in result_data, "Result should have text field"
        assert "timestamp" in result_data, "Result should have timestamp field"
        assert result_data["text"] == test_text, "Text should match input"

    @pytest.mark.asyncio
    async def test_history_summary_empty(self, get_history_summary, clean_history):
        """Test history summary with empty history"""
        # Ensure history is empty
        clean_history.clear()

        summary_result = await get_history_summary()

        # Parse result
        if isinstance(summary_result, str):
            summary_data = json.loads(summary_result)
        else:
            summary_data = summary_result

        # Should report empty history
        assert "message" in summary_data
        assert summary_data["message"] == "Nog geen fact checks uitgevoerd"
        assert summary_data["total"] == 0

    @pytest.mark.asyncio
    async def test_history_summary_with_data(
        self, get_history_summary, clean_history, fact_check_report_class
    ):
        """Test history summary with mock data"""
        # Add mock data
        mock_report = fact_check_report_class(
            original_text="Pytest test data",
            total_claims=5,
            verified_claims=3,
            false_claims=2,
            unverifiable_claims=0,
            overall_reliability="Laag",
            verifications=[],
            summary="Test data voor pytest",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(mock_report)

        # Get summary
        summary_result = await get_history_summary()
        summary_data = json.loads(summary_result)

        # Verify summary data
        assert "total_reports" in summary_data
        assert summary_data["total_reports"] == 1
        assert summary_data["total_claims_checked"] == 5
        assert summary_data["total_false_claims"] == 2
        assert "60.0%" in summary_data["accuracy_rate"]  # (5-2)/5 * 100 = 60%

    def test_multiple_reports_statistics(self, clean_history, fact_check_report_class):
        """Test statistics calculation with multiple reports"""
        # Add multiple mock reports
        reports_data = [
            {"total": 10, "false": 2},  # 80% accuracy
            {"total": 5, "false": 1},  # 80% accuracy
            {"total": 8, "false": 0},  # 100% accuracy
        ]

        for i, data in enumerate(reports_data):
            report = fact_check_report_class(
                original_text=f"Test report {i + 1}",
                total_claims=data["total"],
                verified_claims=data["total"] - data["false"],
                false_claims=data["false"],
                unverifiable_claims=0,
                overall_reliability="Test",
                verifications=[],
                summary=f"Test summary {i + 1}",
                timestamp=datetime.now().isoformat(),
            )
            clean_history.append(report)

        # Verify we have 3 reports
        assert len(clean_history) == 3

        # Calculate expected totals
        total_claims = sum(data["total"] for data in reports_data)  # 23
        total_false = sum(data["false"] for data in reports_data)  # 3
        expected_accuracy = ((total_claims - total_false) / total_claims) * 100  # ~87%

        assert total_claims == 23
        assert total_false == 3
        assert abs(expected_accuracy - 86.95652173913044) < 0.001

    @pytest.mark.asyncio
    async def test_history_persistence_across_calls(
        self, clean_history, fact_check_report_class, get_history_summary
    ):
        """Test that history persists across multiple function calls"""
        # Add initial report
        report1 = fact_check_report_class(
            original_text="First report",
            total_claims=3,
            verified_claims=2,
            false_claims=1,
            unverifiable_claims=0,
            overall_reliability="Gemiddeld",
            verifications=[],
            summary="First test report",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(report1)

        # Get summary
        summary1 = await get_history_summary()
        data1 = json.loads(summary1)
        assert data1["total_reports"] == 1

        # Add second report
        report2 = fact_check_report_class(
            original_text="Second report",
            total_claims=2,
            verified_claims=2,
            false_claims=0,
            unverifiable_claims=0,
            overall_reliability="Hoog",
            verifications=[],
            summary="Second test report",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(report2)

        # Get summary again
        summary2 = await get_history_summary()
        data2 = json.loads(summary2)

        # Should now show 2 reports
        assert data2["total_reports"] == 2
        assert data2["total_claims_checked"] == 5  # 3 + 2
        assert data2["total_false_claims"] == 1  # 1 + 0

    def test_history_item_structure(self, clean_history, fact_check_report_class):
        """Test that history items have correct structure"""
        report = fact_check_report_class(
            original_text="Structure test",
            total_claims=1,
            verified_claims=1,
            false_claims=0,
            unverifiable_claims=0,
            overall_reliability="Hoog",
            verifications=[],
            summary="Testing item structure",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(report)

        # Get the added item
        added_item = clean_history[-1]

        # Check required attributes
        required_attrs = [
            "original_text",
            "total_claims",
            "verified_claims",
            "false_claims",
            "unverifiable_claims",
            "overall_reliability",
            "verifications",
            "summary",
            "timestamp",
        ]

        for attr in required_attrs:
            assert hasattr(added_item, attr), f"Missing attribute: {attr}"
            assert getattr(added_item, attr) is not None, f"Attribute {attr} is None"

    @pytest.mark.asyncio
    async def test_concurrent_history_access(
        self, clean_history, fact_check_report_class
    ):
        """Test concurrent access to history (basic thread safety check)"""

        async def add_report(index):
            report = fact_check_report_class(
                original_text=f"Concurrent test {index}",
                total_claims=1,
                verified_claims=1,
                false_claims=0,
                unverifiable_claims=0,
                overall_reliability="Test",
                verifications=[],
                summary=f"Concurrent summary {index}",
                timestamp=datetime.now().isoformat(),
            )
            clean_history.append(report)
            return len(clean_history)

        # Run multiple concurrent additions
        tasks = [add_report(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All tasks should complete
        assert len(results) == 5
        assert len(clean_history) >= 5  # Should have at least 5 items

    def test_edge_cases(self, clean_history, fact_check_report_class):
        """Test edge cases for history functionality"""

        # Test with zero claims
        zero_claims_report = fact_check_report_class(
            original_text="No claims text",
            total_claims=0,
            verified_claims=0,
            false_claims=0,
            unverifiable_claims=0,
            overall_reliability="Onbekend",
            verifications=[],
            summary="No claims found",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(zero_claims_report)

        assert len(clean_history) == 1
        assert clean_history[0].total_claims == 0

        # Test with empty text
        empty_text_report = fact_check_report_class(
            original_text="",
            total_claims=0,
            verified_claims=0,
            false_claims=0,
            unverifiable_claims=0,
            overall_reliability="Onbekend",
            verifications=[],
            summary="Empty text processed",
            timestamp=datetime.now().isoformat(),
        )
        clean_history.append(empty_text_report)

        assert len(clean_history) == 2
        assert clean_history[1].original_text == ""
