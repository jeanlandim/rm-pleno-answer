
import pytest
import uuid
from unittest.mock import patch

from realmate_challenge_app.models import Message
from realmate_challenge_app.signals import MSG_SCHEDULED_CONVERSATION_CHECK, COUNTDOWN_SECONDS

pytestmark = [pytest.mark.django_db]


@patch('realmate_challenge_app.signals.check_and_assign_conversation.apply_async')
@patch('realmate_challenge_app.signals.logger')
def test_schedule_conversation_check_signal(mock_logger, mock_apply_async):
    message = Message.objects.create(
        id=uuid.uuid4(),
        content="Teste",
        type=Message.MessageType.INBOUND,
        conversation_id=None,
        expected_conversation_id=uuid.uuid4()
   )

    mock_apply_async.assert_called_once_with(
        args=[str(message.id)],
        countdown=COUNTDOWN_SECONDS
    )

    mock_logger.info.assert_called_once_with(
        MSG_SCHEDULED_CONVERSATION_CHECK,
        message.id,
        message.expected_conversation_id,
        COUNTDOWN_SECONDS
    )
