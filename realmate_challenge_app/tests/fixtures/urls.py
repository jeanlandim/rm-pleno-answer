import pytest
from django.urls import reverse


@pytest.fixture
def webhook_url():
    return reverse('webhook')


@pytest.fixture
def conversation_url(new_conversation):
    return reverse('conversations', args=[new_conversation.id])


@pytest.fixture
def conversation_url_without_id():
    from uuid import uuid4
    return reverse('conversations', args=[uuid4()])
