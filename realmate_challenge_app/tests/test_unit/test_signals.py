import uuid
from unittest.mock import patch, MagicMock

from realmate_challenge_app.signals import schedule_conversation_check, MSG_SCHEDULED_CONVERSATION_CHECK, COUNTDOWN_SECONDS
from realmate_challenge_app.models import Message

@patch('realmate_challenge_app.signals.check_and_assign_conversation.apply_async')
@patch('realmate_challenge_app.signals.logger')
def test_schedule_conversation_check_signal_unit(mock_logger, mock_apply_async):
    mock_message = MagicMock(spec=Message)
    mock_message.conversation_id = None
    mock_message.id = uuid.uuid4()
    mock_message.expected_conversation_id = uuid.uuid4()

    schedule_conversation_check("Message", mock_message, True)

    mock_apply_async.assert_called_once_with(
        args=[str(mock_message.id)],
        countdown=COUNTDOWN_SECONDS
    )

    mock_logger.info.assert_called_once_with(
        MSG_SCHEDULED_CONVERSATION_CHECK,
        mock_message.id,
        mock_message.expected_conversation_id,
        COUNTDOWN_SECONDS
    )
