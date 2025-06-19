import uuid
import pytest
from unittest.mock import patch

from realmate_challenge_app.models import Message
from realmate_challenge_app.tasks import (
    _get_messages_with_less_than_five_secs,
    _build_message_summary,
    _create_new_outbound_message,
    process_inbound_messages,
    check_and_assign_conversation,
    MSG_MESSAGE_ALREADY_HAS_CONVERSATION,
    MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED,
    MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING,
    MSG_MESSAGE_SUCCESSFULLY_ASSIGNED,
    MSG_MESSAGE_NOT_FOUND,
    MSG_ERROR_PROCESSING_MESSAGE_CELERY
)


pytestmark = [pytest.mark.django_db]


class TestCheckAndAssignConversationTask:

    @patch('realmate_challenge_app.tasks.logger')
    def test_message_already_has_conversation(self, mock_logger, new_message):
        message_id = new_message.id

        check_and_assign_conversation(str(message_id))

        mock_logger.info.assert_called_with(
            MSG_MESSAGE_ALREADY_HAS_CONVERSATION.format(message_id=message_id)
        )
        assert str(Message.objects.get(id=message_id).conversation_id.id) == new_message.conversation_id.id
        assert Message.objects.count() == 1

    @patch('realmate_challenge_app.tasks.logger')
    def test_message_no_expected_conversation_id(self, mock_logger, new_message):
        new_message.conversation_id = None
        new_message.expected_conversation_id = None
        new_message.save()

        check_and_assign_conversation(str(new_message.id))

        mock_logger.warning.assert_called_with(
            MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED.format(message_id=new_message.id)
        )
        assert not Message.objects.filter(id=new_message.id).exists()

    @patch('realmate_challenge_app.tasks.logger')
    def test_conversation_found_and_assigned(self, mock_logger, new_message):
        new_message.expected_conversation_id = new_message.conversation_id.id
        new_message.conversation_id = None
        new_message.save()

        check_and_assign_conversation(str(new_message.id))

        mock_logger.info.assert_called_with(
            MSG_MESSAGE_SUCCESSFULLY_ASSIGNED.format(
                message_id=new_message.id, 
                conversation_id=new_message.expected_conversation_id
            )
        )
        updated_message = Message.objects.get(id=new_message.id)
        assert str(updated_message.conversation_id_id) == new_message.expected_conversation_id

    @patch('realmate_challenge_app.tasks.logger')
    def test_conversation_not_found_message_deleted(self, mock_logger, new_message):
        non_existent_conversation_id = uuid.uuid4()
        new_message.conversation_id = None
        new_message.expected_conversation_id = non_existent_conversation_id
        new_message.save()

        check_and_assign_conversation(str(new_message.id))

        mock_logger.warning.assert_called_with(
            MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING.format(
                conversation_id=non_existent_conversation_id,
                message_id=new_message.id
            )
        )
        assert not Message.objects.filter(id=new_message.id).exists()

    @patch('realmate_challenge_app.tasks.logger')
    def test_message_does_not_exist(self, mock_logger):
        non_existent_message_id = uuid.uuid4()
        check_and_assign_conversation(str(non_existent_message_id))
        mock_logger.info.assert_called_with(
            MSG_MESSAGE_NOT_FOUND.format(message_id=non_existent_message_id)
        )

    @patch('realmate_challenge_app.tasks.Message.objects.select_for_update')
    @patch('realmate_challenge_app.tasks.logger')
    def test_unexpected_exception_handling(self, mock_logger, mock_select_for_update, new_message):
        mock_select_for_update.side_effect = Exception("Simulated DB Error")
        check_and_assign_conversation(str(new_message.id))

        mock_logger.error.assert_called_with(
            MSG_ERROR_PROCESSING_MESSAGE_CELERY.format(
                message_id=str(new_message.id),
                exc="Simulated DB Error",
            )
        )
        assert Message.objects.filter(id=new_message.id).exists()


class TestProcessInboundMessages:

    def test_get_messages_with_less_than_five_secs(self, create_inbound_messages):
        create_messages, conversation = create_inbound_messages
        create_messages()

        messages = _get_messages_with_less_than_five_secs(conversation.id)
        assert len(messages) == 3
    
    def test_build_message_summary(self, create_inbound_messages):
        create_messages, conversation = create_inbound_messages
        create_messages()

        messages = _get_messages_with_less_than_five_secs(conversation.id)

        ids = _get_messages_with_less_than_five_secs(
            conversation.id
        ).values_list("id", flat=True)

        expected = "Mensagens recebidas:\n" + "\n".join(str(_id) for _id in ids)

        assert _build_message_summary(ids) == expected
    
    def test_create_new_outbound_message(self, new_conversation):
        new_outbound_message = _create_new_outbound_message(
            new_conversation.id,
            "content"
        )

        assert new_outbound_message.content == "content"
    
    def test_process_inbound_messages(self):
        pass
