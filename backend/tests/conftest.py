"""
Pytest configuration and fixtures for Paperbase tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.main import app


# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_paperbase.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database for each test.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with the test database.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_schema():
    """
    Sample schema for testing.
    """
    return {
        "name": "Test Invoices",
        "fields": [
            {
                "name": "invoice_number",
                "type": "text",
                "required": True,
                "extraction_hints": ["Invoice #", "Invoice No"],
                "confidence_threshold": 0.75,
                "description": "Invoice number"
            },
            {
                "name": "invoice_date",
                "type": "date",
                "required": True,
                "extraction_hints": ["Date:", "Invoice Date:"],
                "confidence_threshold": 0.8,
                "description": "Invoice date"
            },
            {
                "name": "total_amount",
                "type": "number",
                "required": True,
                "extraction_hints": ["Total:", "Amount Due:"],
                "confidence_threshold": 0.85,
                "description": "Total amount"
            }
        ]
    }


@pytest.fixture
def sample_reducto_response():
    """
    Sample Reducto API response for testing.
    """
    return {
        "chunks": [
            {
                "id": "chunk_1",
                "text": "Invoice #12345\nDate: 2024-01-15\nTotal: $1,250.00",
                "page": 1,
                "logprobs_confidence": 0.92
            },
            {
                "id": "chunk_2",
                "text": "Customer: Acme Corp\nAddress: 123 Main St",
                "page": 1,
                "logprobs_confidence": 0.88
            }
        ],
        "metadata": {
            "pages": 1,
            "file_type": "pdf"
        }
    }


@pytest.fixture
def sample_extraction():
    """
    Sample extraction result for testing.
    """
    return {
        "invoice_number": {
            "value": "12345",
            "confidence": 0.92,
            "source_page": 1
        },
        "invoice_date": {
            "value": "2024-01-15",
            "confidence": 0.88,
            "source_page": 1
        },
        "total_amount": {
            "value": "1250.00",
            "confidence": 0.85,
            "source_page": 1
        }
    }
