import pytest
from uuid import uuid4


@pytest.fixture
def new_conversation_payload(current_time, conversation_id):
    return {
        "type": "NEW_CONVERSATION",
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(conversation_id),
        }
    }


@pytest.fixture
def new_message_payload(current_time, message_id, conversation_id):
    return {
        "type": "NEW_MESSAGE",
        "timestamp": str(current_time.isoformat()),
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
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(conversation_id),
        }
    }


@pytest.fixture
def close_conversation_not_found_payload(current_time):
    return {
        "type": "CLOSE_CONVERSATION",
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(uuid4()),
        }
    }


@pytest.fixture
def missing_type_payload(current_time):
    return {
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(uuid4())
        }
    }


@pytest.fixture
def invalid_type_payload(current_time):
    return {
        "type": "INVALID_TYPE",
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(uuid4())
        }
    }


@pytest.fixture
def invalid_new_conversation_payload(current_time):
    return {
        "type": "NEW_CONVERSATION",
        "timestamp": str(current_time.isoformat()),
    }


@pytest.fixture
def new_message_conversation_not_found_payload(current_time):
    return {
        "type": "NEW_MESSAGE",
        "timestamp": str(current_time.isoformat()),
        "data": {
            "id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "content": "Mensagem sem conversa"
        }
    }
