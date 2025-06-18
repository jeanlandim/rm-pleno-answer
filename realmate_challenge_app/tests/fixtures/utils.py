import pytest
from datetime import datetime, timezone
from rest_framework.test import APIClient
from uuid import uuid4


@pytest.fixture
def current_time():
    return datetime.now(timezone.utc)


@pytest.fixture
def conversation_id():
    return uuid4()


@pytest.fixture
def message_id():
    return uuid4()

@pytest.fixture
def client():
    return APIClient()