import pytest

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
