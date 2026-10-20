import pytest
from o2c.service import O2CService

@pytest.fixture(scope="session")
def service():
    # Use lexical mode in tests to avoid model downloads and keep CI deterministic.
    return O2CService(retrieval_mode="lexical")
