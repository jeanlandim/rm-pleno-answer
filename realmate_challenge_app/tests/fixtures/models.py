import pytest
from realmate_challenge_app.models import Conversation, Message


@pytest.fixture
def new_conversation(new_conversation_payload):
    return Conversation.objects.create(
        id=new_conversation_payload['data']['id'],
    )


@pytest.fixture
def new_message(new_conversation):
    return Message.objects.create(
        conversation=new_conversation,
        type=Message.MessageType.INBOUND,
        content="Olá",
        timestamp="2025-06-17T12:00:00Z"
    )
