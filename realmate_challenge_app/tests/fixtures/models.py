import pytest
import uuid

from datetime import timedelta
from django.utils.timezone import now

from realmate_challenge_app.models import Conversation, Message
from faker import Faker

@pytest.fixture
def new_conversation(new_conversation_payload):
    return Conversation.objects.create(
        id=new_conversation_payload['data']['id'],
    )

@pytest.fixture
def new_closed_conversation(new_conversation_payload):
    return Conversation.objects.create(
        id=new_conversation_payload['data']['id'],
        status=Conversation.Status.CLOSED
    )

@pytest.fixture
def new_message(new_conversation):
    fake = Faker()
    return Message.objects.create(
        conversation_id=new_conversation,
        type=Message.MessageType.INBOUND,
        content=fake.sentence(nb_words=5),
        timestamp=fake.date_time_this_century(tzinfo=None)
    )


@pytest.fixture
def create_inbound_messages(new_conversation):
    def _create():
        base_time = now()
        
        base_kwargs = {
            "conversation_id": new_conversation,
            "type": Message.MessageType.INBOUND,
            "processed": False
        }

        message_data = [
            {"content": "Oi", "timestamp": base_time},
            {"content": "Tudo bem?", "timestamp": base_time + timedelta(seconds=3)},
            {"content": "Quero alugar um imóvel.", "timestamp": base_time + timedelta(seconds=5)},
            {"content": "Mensagem isolada", "timestamp": base_time + timedelta(seconds=20)},
        ]

        messages = [
            Message.objects.create(**{**base_kwargs, **data})
            for data in message_data
        ]

        return messages
    return (_create, new_conversation)
