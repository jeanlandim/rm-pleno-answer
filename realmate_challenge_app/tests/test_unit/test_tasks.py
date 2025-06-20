import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

from django.test import TestCase
from django.utils import timezone

from realmate_challenge_app.tasks import (
    check_and_assign_conversation,
    _get_single_and_grouped_messages,
    _build_message_summary,
    _create_new_outbound_message,
    process_inbound_messages,
    INTERVAL_MINIMAL_EXPECTED,
    MSG_MESSAGE_ALREADY_HAS_CONVERSATION,
    MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED,
    MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING,
    MSG_MESSAGE_SUCCESSFULLY_ASSIGNED,
    MSG_MESSAGE_NOT_FOUND,
    MSG_ERROR_PROCESSING_MESSAGE_CELERY,
)

from realmate_challenge_app.models import Message, Conversation


class MessageGroupingBaseTest(TestCase):
    def setUp(self):
        self.conversation_id = uuid.uuid4()
        self.now = timezone.now()

    def _create_mock_message(self, timestamp_offset_seconds=0, content="test", conversation_id=None,
                              message_id=None, processed=False, type="INBOUND", expected_conversation_id=None):
        mock_msg = MagicMock(spec=Message)
        mock_msg.id = message_id if message_id else uuid.uuid4()
        mock_msg.conversation_id = conversation_id
        mock_msg.timestamp = self.now + timedelta(seconds=timestamp_offset_seconds)
        mock_msg.content = content
        mock_msg.processed = processed
        mock_msg.type = type
        mock_msg.expected_conversation_id = expected_conversation_id
        mock_msg.save = MagicMock()
        mock_msg.delete = MagicMock()
        return mock_msg

    def _create_mock_conversation(self, conv_id=None, status="OPEN"):
        mock_conv = MagicMock(spec=Conversation)
        mock_conv.id = conv_id if conv_id else uuid.uuid4()
        mock_conv.status = status
        return mock_conv


class TestCheckAndAssignConversation(MessageGroupingBaseTest):

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_already_has_conversation(self, mock_message_objects, mock_logger, mock_atomic):
        mock_conv_instance = self._create_mock_conversation()
        mock_msg_instance = self._create_mock_message(conversation_id=mock_conv_instance.id)

        mock_message_objects.select_for_update.return_value.get.return_value = mock_msg_instance

        check_and_assign_conversation(str(mock_msg_instance.id))

        mock_atomic.assert_called_once()
        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_ALREADY_HAS_CONVERSATION.format(message_id=mock_msg_instance.id)
        )
        mock_msg_instance.save.assert_not_called()
        mock_msg_instance.delete.assert_not_called()

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_no_expected_conversation_id(self, mock_message_objects, mock_logger, mock_atomic):
        mock_msg_instance = self._create_mock_message(conversation_id=None, expected_conversation_id=None)
        mock_message_objects.select_for_update.return_value.get.return_value = mock_msg_instance

        check_and_assign_conversation(str(mock_msg_instance.id))

        mock_atomic.assert_called_once()
        mock_logger.warning.assert_called_once_with(
            MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED.format(message_id=mock_msg_instance.id)
        )
        mock_msg_instance.delete.assert_called_once()
        mock_msg_instance.save.assert_not_called()

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_conversation_found_and_assigned(self, mock_message_objects, mock_conversation_objects, mock_logger, mock_atomic):
        mock_expected_conv_id = uuid.uuid4()
        mock_msg_instance = self._create_mock_message(conversation_id=None, expected_conversation_id=mock_expected_conv_id)
        mock_conv_instance = self._create_mock_conversation(conv_id=mock_expected_conv_id)

        mock_message_objects.select_for_update.return_value.get.return_value = mock_msg_instance
        mock_conversation_objects.get.return_value = mock_conv_instance

        check_and_assign_conversation(str(mock_msg_instance.id))

        mock_atomic.assert_called_once()
        mock_conversation_objects.get.assert_called_once_with(id=mock_expected_conv_id)
        self.assertEqual(mock_msg_instance.conversation_id, mock_conv_instance)
        mock_msg_instance.save.assert_called_once()
        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_SUCCESSFULLY_ASSIGNED.format(
                message_id=mock_msg_instance.id,
                conversation_id=mock_expected_conv_id
            )
        )
        mock_msg_instance.delete.assert_not_called()

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_conversation_not_found_message_deleted(self, mock_message_objects, mock_conversation_objects, mock_logger, mock_atomic):
        non_existent_conversation_id = uuid.uuid4()
        mock_msg_instance = self._create_mock_message(conversation_id=None, expected_conversation_id=non_existent_conversation_id)

        mock_message_objects.select_for_update.return_value.get.return_value = mock_msg_instance
        mock_conversation_objects.get.side_effect = Conversation.DoesNotExist

        check_and_assign_conversation("")

        mock_atomic.assert_called_once()
        mock_conversation_objects.get.assert_called_once_with(id=non_existent_conversation_id)
        mock_msg_instance.delete.assert_called_once()
        mock_msg_instance.save.assert_not_called()
        mock_logger.warning.assert_called_once_with(
            MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING.format(
                conversation_id=non_existent_conversation_id,
                message_id=mock_msg_instance.id
            )
        )

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_does_not_exist(self, mock_message_objects, mock_logger, mock_atomic):
        non_existent_message_id = uuid.uuid4()
        mock_message_objects.select_for_update.return_value.get.side_effect = Message.DoesNotExist

        check_and_assign_conversation(str(non_existent_message_id))

        mock_atomic.assert_called_once()
        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_NOT_FOUND.format(message_id=non_existent_message_id)
        )

    @patch('realmate_challenge_app.tasks.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects.select_for_update')
    def test_unexpected_exception_handling(self, mock_select_for_update, mock_logger, mock_atomic):
        mock_message_id = uuid.uuid4()
        mock_select_for_update.side_effect = Exception("Simulated DB Error")

        check_and_assign_conversation(str(mock_message_id))

        mock_atomic.assert_called_once()
        mock_logger.error.assert_called_once_with(
            MSG_ERROR_PROCESSING_MESSAGE_CELERY.format(message_id=mock_message_id, exc="Simulated DB Error")
        )


class TestGetSingleAndGroupedMessages(MessageGroupingBaseTest):

    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_empty_messages(self, mock_message_objects):
        mock_message_objects.filter.return_value.order_by.return_value = []
        grouped, individual = _get_single_and_grouped_messages(self.conversation_id)
        self.assertEqual(len(grouped), 0)
        self.assertEqual(len(individual), 0)

    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_single_message_individual(self, mock_message_objects):
        msg = self._create_mock_message(0)
        mock_message_objects.filter.return_value.order_by.return_value = [msg]
        grouped, individual = _get_single_and_grouped_messages(self.conversation_id)
        self.assertEqual(len(grouped), 0)
        self.assertEqual(len(individual), 1)
        self.assertEqual(individual[0].id, msg.id)

    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_two_messages_grouped(self, mock_message_objects):
        msg1 = self._create_mock_message(0)
        msg2 = self._create_mock_message(INTERVAL_MINIMAL_EXPECTED - 1)
        mock_message_objects.filter.return_value.order_by.return_value = [msg1, msg2]
        grouped, individual = _get_single_and_grouped_messages(self.conversation_id)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(individual), 0)
        self.assertIn(msg1.id, [m.id for m in grouped])
        self.assertIn(msg2.id, [m.id for m in grouped])

    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_three_messages_grouped(self, mock_message_objects):
        msg1 = self._create_mock_message(0)
        msg2 = self._create_mock_message(2)
        msg3 = self._create_mock_message(4)
        mock_message_objects.filter.return_value.order_by.return_value = [msg1, msg2, msg3]
        grouped, individual = _get_single_and_grouped_messages(self.conversation_id)
        self.assertEqual(len(grouped), 3)
        self.assertEqual(len(individual), 0)
        self.assertIn(msg1.id, [m.id for m in grouped])
        self.assertIn(msg2.id, [m.id for m in grouped])
        self.assertIn(msg3.id, [m.id for m in grouped])

class TestBuildMessageSummary(TestCase):
    def test_empty_list(self):
        result = _build_message_summary([])
        self.assertEqual(result, "Mensagens recebidas:\n")

    def test_single_id(self):
        mock_id = uuid.uuid4()
        result = _build_message_summary([str(mock_id)])
        self.assertEqual(result, f"Mensagens recebidas:\n{mock_id}")

    def test_multiple_ids(self):
        mock_id1 = uuid.uuid4()
        mock_id2 = uuid.uuid4()
        mock_id3 = uuid.uuid4()
        result = _build_message_summary([str(mock_id1), str(mock_id2), str(mock_id3)])
        expected = f"Mensagens recebidas:\n{mock_id1}\n{mock_id2}\n{mock_id3}"
        self.assertEqual(result, expected)


class TestCreateNewOutboundMessage(MessageGroupingBaseTest):

    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.timezone.now')
    def test_create_outbound_message_success(self, mock_timezone_now, mock_conversation_objects, mock_message_objects):
        mock_conv = self._create_mock_conversation(conv_id=self.conversation_id)
        mock_conversation_objects.get.return_value = mock_conv
        mock_timezone_now.return_value = self.now
        
        mock_created_message = self._create_mock_message(
            conversation_id=mock_conv.id, content="Summary", processed=True, type="OUTBOUND"
        )
        mock_message_objects.create.return_value = mock_created_message

        content = "Test summary content"
        result = _create_new_outbound_message(str(self.conversation_id), content)

        mock_conversation_objects.get.assert_called_once_with(id=str(self.conversation_id))
        mock_message_objects.create.assert_called_once_with(
            conversation_id=mock_conv,
            content=content,
            processed=True,
            type=Message.MessageType.OUTBOUND,
            timestamp=self.now,
        )
        self.assertEqual(result, mock_created_message)

    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.timezone.now')
    def test_create_outbound_message_conversation_not_found(self, mock_timezone_now, mock_conversation_objects, mock_message_objects):
        mock_conversation_objects.get.side_effect = Conversation.DoesNotExist

        content = "Test summary content"
        
        with self.assertRaises(Conversation.DoesNotExist):
            _create_new_outbound_message(str(self.conversation_id), content)

        mock_conversation_objects.get.assert_called_once_with(id=str(self.conversation_id))
        mock_message_objects.create.assert_not_called()


class TestProcessInboundMessages(MessageGroupingBaseTest):

    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks._create_new_outbound_message')
    @patch('realmate_challenge_app.tasks._build_message_summary')
    @patch('realmate_challenge_app.tasks._get_single_and_grouped_messages')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    def test_no_conversations(self, mock_conversation_objects, mock_message_objects,
                               mock_get_messages, mock_build_summary, mock_create_outbound, mock_logger):
        mock_conversation_objects.values_list.return_value = []
        result = process_inbound_messages()
        self.assertEqual(result, [])
        mock_get_messages.assert_not_called()
        mock_build_summary.assert_not_called()
        mock_create_outbound.assert_not_called()
        mock_message_objects.filter.assert_not_called()

    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks._create_new_outbound_message')
    @patch('realmate_challenge_app.tasks._build_message_summary')
    @patch('realmate_challenge_app.tasks._get_single_and_grouped_messages')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    def test_only_single_messages_processed(self, mock_conversation_objects, mock_message_objects,
                                            mock_get_messages, mock_build_summary, mock_create_outbound, mock_logger):
        conv_id = self.conversation_id
        mock_conversation_objects.values_list.return_value = [conv_id]

        msg1 = self._create_mock_message(0, message_id=uuid.uuid4())
        msg2 = self._create_mock_message(INTERVAL_MINIMAL_EXPECTED + 10, message_id=uuid.uuid4())
        
        mock_get_messages.return_value = ([], [msg1, msg2])

        mock_build_summary.return_value = "Summary for individual messages"
        mock_create_outbound.return_value = self._create_mock_message(type="OUTBOUND", processed=True)
        
        mock_message_objects.filter.return_value.update.return_value = 2

        result = process_inbound_messages()

        mock_conversation_objects.values_list.assert_called_once_with("id", flat=True)
        mock_get_messages.assert_called_once_with(conv_id)
        
        mock_build_summary.assert_called_once_with([str(msg1.id), str(msg2.id)])
        mock_create_outbound.assert_called_once_with(conv_id, "Summary for individual messages")
        mock_logger.info.assert_called_once_with("Summary for individual messages")
        mock_message_objects.filter.assert_called_once_with(id__in=[str(msg1.id), str(msg2.id)])
        mock_message_objects.filter.return_value.update.assert_called_once_with(processed=True)
        self.assertEqual(result, ["Summary for individual messages"])

    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks._create_new_outbound_message')
    @patch('realmate_challenge_app.tasks._build_message_summary')
    @patch('realmate_challenge_app.tasks._get_single_and_grouped_messages')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    def test_only_grouped_messages_processed(self, mock_conversation_objects, mock_message_objects,
                                             mock_get_messages, mock_build_summary, mock_create_outbound, mock_logger):
        conv_id = self.conversation_id
        mock_conversation_objects.values_list.return_value = [conv_id]

        msg1 = self._create_mock_message(0, message_id=uuid.uuid4())
        msg2 = self._create_mock_message(INTERVAL_MINIMAL_EXPECTED - 1, message_id=uuid.uuid4())
        
        mock_get_messages.return_value = ([msg1, msg2], [])

        mock_build_summary.return_value = "Summary for grouped messages"
        mock_create_outbound.return_value = self._create_mock_message(type="OUTBOUND", processed=True)
        mock_message_objects.filter.return_value.update.return_value = 2

        result = process_inbound_messages()

        mock_get_messages.assert_called_once_with(conv_id)
        mock_build_summary.assert_called_once_with([str(msg1.id), str(msg2.id)])
        mock_create_outbound.assert_called_once_with(conv_id, "Summary for grouped messages")
        mock_logger.info.assert_called_once_with("Summary for grouped messages")
        mock_message_objects.filter.assert_called_once_with(id__in=[str(msg1.id), str(msg2.id)])
        mock_message_objects.filter.return_value.update.assert_called_once_with(processed=True)
        self.assertEqual(result, ["Summary for grouped messages"])

    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks._create_new_outbound_message')
    @patch('realmate_challenge_app.tasks._build_message_summary')
    @patch('realmate_challenge_app.tasks._get_single_and_grouped_messages')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    def test_both_single_and_grouped_messages_processed(self, mock_conversation_objects, mock_message_objects,
                                                        mock_get_messages, mock_build_summary, mock_create_outbound, mock_logger):
        conv_id = self.conversation_id
        mock_conversation_objects.values_list.return_value = [conv_id]

        msg_ind = self._create_mock_message(0, message_id=uuid.uuid4())
        msg_g1 = self._create_mock_message(INTERVAL_MINIMAL_EXPECTED + 10, message_id=uuid.uuid4())
        msg_g2 = self._create_mock_message(INTERVAL_MINIMAL_EXPECTED + 12, message_id=uuid.uuid4())
        
        mock_get_messages.return_value = ([msg_g1, msg_g2], [msg_ind])

        mock_build_summary.side_effect = [
            "Summary for individual",
            "Summary for grouped"
        ]
        mock_create_outbound.side_effect = [
            self._create_mock_message(type="OUTBOUND", processed=True, content="Summary for individual"),
            self._create_mock_message(type="OUTBOUND", processed=True, content="Summary for grouped")
        ]
        mock_message_objects.filter.return_value.update.side_effect = [1, 2]

        result = process_inbound_messages()

        mock_get_messages.assert_called_once_with(conv_id)

        mock_build_summary.assert_any_call([str(msg_ind.id)])
        mock_create_outbound.assert_any_call(conv_id, "Summary for individual")
        mock_logger.info.assert_any_call("Summary for individual")
        mock_message_objects.filter.assert_any_call(id__in=[str(msg_ind.id)])
        mock_message_objects.filter.return_value.update.assert_any_call(processed=True)

        mock_build_summary.assert_any_call([str(msg_g1.id), str(msg_g2.id)])
        mock_create_outbound.assert_any_call(conv_id, "Summary for grouped")
        mock_logger.info.assert_any_call("Summary for grouped")
        mock_message_objects.filter.assert_any_call(id__in=[str(msg_g1.id), str(msg_g2.id)])
        
        self.assertEqual(mock_build_summary.call_count, 2)
        self.assertEqual(mock_create_outbound.call_count, 2)
        self.assertEqual(mock_logger.info.call_count, 2)
        self.assertEqual(mock_message_objects.filter.call_count, 2)
        self.assertEqual(mock_message_objects.filter.return_value.update.call_count, 2)

        self.assertEqual(result, ["Summary for individual", "Summary for grouped"])
