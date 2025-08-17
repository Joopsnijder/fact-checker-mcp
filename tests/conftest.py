"""
Pytest configuration and shared fixtures for fact checker tests
"""

import asyncio
import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup global test environment"""
    # Ensure we're in the right directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Set test environment variables
    original_env = {}
    test_env_vars = {
        "OPENAI_API_KEY": "test-key-for-pytest",
        "SERPER_API_KEY": "test-serper-key",
        "BRAVE_API_KEY": "test-brave-key",
    }

    # Store original values and set test values
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original environment
    for key, original_value in original_env.items():
        if original_value is not None:
            os.environ[key] = original_value
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture
def sample_text():
    """Sample text for testing"""
    return """
    De Eiffeltoren is 324 meter hoog en werd gebouwd in 1889.
    GPT-4 heeft meer dan 100 miljard parameters.
    Nederland heeft ongeveer 17 miljoen inwoners.
    """


@pytest.fixture
def sample_claims():
    """Sample claims for testing"""
    return [
        "De Eiffeltoren is 324 meter hoog",
        "GPT-4 heeft meer dan 100 miljard parameters",
        "Nederland heeft ongeveer 17 miljoen inwoners",
    ]
