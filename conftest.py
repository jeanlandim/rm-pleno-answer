import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from uuid import uuid4
from datetime import datetime, timezone
from realmate_challenge_app.models import Conversation, Message

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def webhook_url():
    return reverse('webhook')

@pytest.fixture
def conversation_url(new_conversation):
    return reverse('conversations', args=[new_conversation.id])

@pytest.fixture
def conversation_url_without_id():
    return reverse('conversations', args=[uuid4()])


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
def new_conversation(new_conversation_payload):
    return Conversation.objects.create(
        id=new_conversation_payload['data']['id'],
        started_at=new_conversation_payload['timestamp'],
    )


@pytest.fixture
def new_message(new_conversation):
    return Message.objects.create(
        conversation=new_conversation,
        type=Message.MessageType.INBOUND,
        content="Olá",
        timestamp="2025-06-17T12:00:00Z"
    )


@pytest.fixture
def new_conversation_payload(current_time, conversation_id):
    return {
        "type": "NEW_CONVERSATION",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(conversation_id),
        }
    }


@pytest.fixture
def new_message_payload(current_time, message_id, conversation_id):
    return {
        "type": "NEW_MESSAGE",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(message_id),
            "content": "Olá",
            "conversation_id": str(conversation_id),
        }
    }


@pytest.fixture
def close_conversation_payload(current_time, conversation_id):
    return {
        "type": "CLOSE_CONVERSATION",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(conversation_id),
        }
    }


@pytest.fixture
def close_conversation_not_found_payload(current_time):
    return {
        "type": "CLOSE_CONVERSATION",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(uuid4()),
        }
    }


@pytest.fixture
def missing_type_payload(current_time):
    return {
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(uuid4())
        }
    }


@pytest.fixture
def invalid_type_payload(current_time):
    return {
        "type": "INVALID_TYPE",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(uuid4())
        }
    }


@pytest.fixture
def invalid_new_conversation_payload(current_time):
    return {
        "type": "NEW_CONVERSATION",
        "timestamp": current_time.isoformat(),
    }

@pytest.fixture
def new_message_conversation_not_found_payload(current_time):
    return {
        "type": "NEW_MESSAGE",
        "timestamp": current_time.isoformat(),
        "data": {
            "id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "content": "Mensagem sem conversa"
        }
    }