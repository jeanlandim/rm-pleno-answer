import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock, call

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
    MSG_ERROR_PROCESSING_MESSAGE_CELERY,
    INTERVAL_MINIMAL_EXPECTED,
)

from realmate_challenge_app.models import Message, Conversation
from django.db.models.functions import Lag as LagOriginal


class TestCheckAndAssignConversationTaskUnit:

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_already_has_conversation(self, mock_message_objects, mock_logger, mock_atomic):
        mock_conversation_id_instance = MagicMock(spec=Conversation, id=uuid.uuid4())
        mock_message_instance = MagicMock(
            spec=Message,
            id=uuid.uuid4(),
            conversation_id=mock_conversation_id_instance,
            save=MagicMock(),
            delete=MagicMock(),
            expected_conversation_id=None,
            timestamp=None,
            processed=False,
            type=Message.MessageType.INBOUND
        )
        mock_message_objects.select_for_update.return_value.get.return_value = mock_message_instance

        check_and_assign_conversation(str(mock_message_instance.id))

        mock_atomic.assert_called_once()
        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_ALREADY_HAS_CONVERSATION.format(message_id=mock_message_instance.id)
        )
        mock_message_instance.save.assert_not_called()
        mock_message_instance.delete.assert_not_called()

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_no_expected_conversation_id(self, mock_message_objects, mock_logger, mock_atomic):
        mock_message_instance = MagicMock(
            spec=Message,
            id=uuid.uuid4(),
            conversation_id=None,
            expected_conversation_id=None,
            save=MagicMock(),
            delete=MagicMock(),
            timestamp=None,
            processed=False,
            type=Message.MessageType.INBOUND
        )
        mock_message_objects.select_for_update.return_value.get.return_value = mock_message_instance

        check_and_assign_conversation(str(mock_message_instance.id))

        mock_atomic.assert_called_once()
        mock_logger.warning.assert_called_once_with(
            MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED.format(message_id=mock_message_instance.id)
        )
        mock_message_instance.delete.assert_called_once()
        mock_message_instance.save.assert_not_called()

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_conversation_found_and_assigned(self, mock_message_objects, mock_conversation_objects, mock_logger, mock_atomic):
        mock_expected_conv_id = uuid.uuid4()
        mock_message_instance = MagicMock(
            spec=Message,
            id=uuid.uuid4(),
            conversation_id=None,
            expected_conversation_id=mock_expected_conv_id,
            save=MagicMock(),
            delete=MagicMock(),
            timestamp=None,
            processed=False,
            type=Message.MessageType.INBOUND
        )
        mock_conversation_instance = MagicMock(spec=Conversation, id=mock_expected_conv_id)

        mock_message_objects.select_for_update.return_value.get.return_value = mock_message_instance
        mock_conversation_objects.get.return_value = mock_conversation_instance

        check_and_assign_conversation(str(mock_message_instance.id))

        mock_atomic.assert_called_once()
        mock_conversation_objects.get.assert_called_once_with(id=mock_expected_conv_id)
        mock_message_instance.save.assert_called_once()

        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_SUCCESSFULLY_ASSIGNED.format(
                message_id=mock_message_instance.id,
                conversation_id=mock_expected_conv_id
            )
        )
        assert mock_message_instance.conversation_id == mock_conversation_instance
        mock_message_instance.delete.assert_not_called()

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_conversation_not_found_message_deleted(self, mock_message_objects, mock_conversation_objects, mock_logger, mock_atomic):
        non_existent_conversation_id = uuid.uuid4()
        mock_message_instance = MagicMock(
            spec=Message,
            id=uuid.uuid4(),
            conversation_id=None,
            expected_conversation_id=non_existent_conversation_id,
            save=MagicMock(),
            delete=MagicMock(),
            timestamp=None,
            processed=False,
            type=Message.MessageType.INBOUND
        )

        mock_message_objects.select_for_update.return_value.get.return_value = mock_message_instance
        mock_conversation_objects.get.side_effect = Conversation.DoesNotExist("Conversation not found")

        check_and_assign_conversation(str(mock_message_instance.id))

        mock_atomic.assert_called_once()
        mock_conversation_objects.get.assert_called_once_with(id=non_existent_conversation_id)
        mock_message_instance.delete.assert_called_once()
        mock_message_instance.save.assert_not_called()

        mock_logger.warning.assert_called_once_with(
            MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING.format(
                conversation_id=non_existent_conversation_id,
                message_id=mock_message_instance.id
            )
        )

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_message_does_not_exist(self, mock_message_objects, mock_logger, mock_atomic):
        non_existent_message_id = uuid.uuid4()
        mock_message_objects.select_for_update.return_value.get.side_effect = Message.DoesNotExist("Message not found")

        check_and_assign_conversation(str(non_existent_message_id))

        mock_atomic.assert_called_once()
        mock_logger.info.assert_called_once_with(
            MSG_MESSAGE_NOT_FOUND.format(message_id=non_existent_message_id)
        )

    @patch('django.db.transaction.atomic')
    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks.Message.objects.select_for_update')
    def test_unexpected_exception_handling(self, mock_select_for_update, mock_logger, mock_atomic):
        mock_message_id = uuid.uuid4()
        mock_select_for_update.side_effect = Exception("Simulated DB Error")

        check_and_assign_conversation(str(mock_message_id))

        mock_atomic.assert_called_once()
        mock_select_for_update.assert_called_once()
        mock_logger.error.assert_called_once_with(
            MSG_ERROR_PROCESSING_MESSAGE_CELERY.format(
                message_id=str(mock_message_id),
                exc="Simulated DB Error",
            )
        )


class TestHelperFunctionsUnit:

    @patch('realmate_challenge_app.tasks.timedelta')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Window')
    @patch('realmate_challenge_app.tasks.F')
    @patch('realmate_challenge_app.tasks.Lag', spec=LagOriginal)
    def test_get_messages_with_less_than_five_secs_filters_correctly(
        self, mock_Lag, mock_F, mock_Window, mock_message_objects, mock_timedelta
    ):
        mock_conversation_id = uuid.uuid4()
        mock_queryset = MagicMock()
        mock_message_objects.annotate.return_value.filter.return_value = mock_queryset

        mock_f_timestamp_asc = MagicMock()
        mock_F.return_value.asc.return_value = mock_f_timestamp_asc
        mock_Window.return_value = MagicMock()

        mock_f_timestamp_plus_interval = MagicMock()
        mock_F.return_value.__add__.return_value = mock_f_timestamp_plus_interval

        result = _get_messages_with_less_than_five_secs(str(mock_conversation_id))

        mock_message_objects.annotate.assert_called_once()
        mock_Lag.assert_called_once_with('timestamp')
        mock_Window.assert_called_once_with(
            expression=mock_Lag.return_value,
            order_by=mock_f_timestamp_asc
        )
        mock_F.assert_has_calls([
            call('timestamp'),
            call('previous_timestamp')
        ], any_order=True)

        mock_timedelta.assert_called_once_with(seconds=INTERVAL_MINIMAL_EXPECTED)
        mock_message_objects.annotate.return_value.filter.assert_called_once_with(
            conversation_id__id=str(mock_conversation_id),
            processed=False,
            type=Message.MessageType.INBOUND,
            previous_timestamp__isnull=False,
            timestamp__lte=mock_f_timestamp_plus_interval
        )
        assert result == mock_queryset

    def test_build_message_summary_formats_correctly(self):
        ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        expected_summary = "Mensagens recebidas:\n" + "\n".join(str(_id) for _id in ids)
        assert _build_message_summary(ids) == expected_summary

    @patch('realmate_challenge_app.tasks.Conversation.objects')
    @patch('realmate_challenge_app.tasks.Message.objects')
    def test_create_new_outbound_message_creates_and_returns(self, mock_message_objects, mock_conversation_objects):
        mock_conv_id = uuid.uuid4()
        mock_content = "Test outbound content"

        mock_conversation_instance = MagicMock(spec=Conversation, id=mock_conv_id)
        mock_conversation_objects.get.return_value = mock_conversation_instance

        mock_created_message = MagicMock(
            spec=Message,
            conversation_id=mock_conversation_instance,
            content=mock_content,
            processed=True,
            id=uuid.uuid4()
        )
        mock_message_objects.create.return_value = mock_created_message

        result = _create_new_outbound_message(str(mock_conv_id), mock_content)

        mock_conversation_objects.get.assert_called_once_with(id=str(mock_conv_id))
        mock_message_objects.create.assert_called_once_with(
            conversation_id=mock_conversation_instance,
            content=mock_content,
            processed=True,
            type=Message.MessageType.OUTBOUND
        )
        assert result == mock_created_message
        assert result.content == mock_content
        assert result.processed is True


class TestProcessInboundMessagesUnit:

    @patch('realmate_challenge_app.tasks.logger')
    @patch('realmate_challenge_app.tasks._create_new_outbound_message')
    @patch('realmate_challenge_app.tasks._build_message_summary')
    @patch('realmate_challenge_app.tasks._get_messages_with_less_than_five_secs')
    @patch('realmate_challenge_app.tasks.Message.objects')
    @patch('realmate_challenge_app.tasks.Conversation.objects')
    def test_process_inbound_messages_calls_helpers_correctly(
        self,
        mock_conversation_objects,
        mock_message_objects,
        mock_get_messages_less_than_five_secs,
        mock_build_message_summary,
        mock_create_new_outbound_message,
        mock_logger
    ):
        mock_conversation_ids = ["conv_id_1", "conv_id_2"]
        mock_conversation_objects.values_list.return_value = mock_conversation_ids

        mock_grouped_qs_1 = MagicMock()
        mock_grouped_qs_1.values_list.return_value = [uuid.uuid4(), uuid.uuid4()]
        mock_grouped_qs_1.update.return_value = 2

        mock_grouped_qs_2 = MagicMock()
        mock_grouped_qs_2.values_list.return_value = []
        mock_grouped_qs_2.update.return_value = 0

        mock_get_messages_less_than_five_secs.side_effect = [
            mock_grouped_qs_1,
            mock_grouped_qs_2
        ]

        mock_single_qs_1 = MagicMock()
        mock_single_qs_1.values_list.return_value = [uuid.uuid4()]
        mock_single_qs_1.update.return_value = 1

        mock_single_qs_2 = MagicMock()
        mock_single_qs_2.values_list.return_value = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        mock_single_qs_2.update.return_value = 3

        mock_message_objects.filter.side_effect = [
            mock_single_qs_1,
            mock_single_qs_2
        ]

        mock_build_message_summary.side_effect = [
            "Summary for Grouped 1",
            "Summary for Single 1",
            "Summary for Grouped 2 (empty)",
            "Summary for Single 2"
        ]

        mock_create_new_outbound_message.return_value = MagicMock()

        process_inbound_messages()

        mock_conversation_objects.values_list.assert_called_once_with("id", flat=True)

        mock_get_messages_less_than_five_secs.assert_has_calls([
            call("conv_id_1"),
            call("conv_id_2")
        ])
        mock_message_objects.filter.assert_has_calls([
            call(conversation_id__id="conv_id_1", processed=False, type=Message.MessageType.INBOUND),
            call(conversation_id__id="conv_id_2", processed=False, type=Message.MessageType.INBOUND)
        ])

        mock_build_message_summary.assert_has_calls([
            call(mock_single_qs_1.values_list.return_value),
            call(mock_grouped_qs_1.values_list.return_value),
            call(mock_single_qs_2.values_list.return_value),
            call(mock_grouped_qs_2.values_list.return_value)
        ], any_order=False)

        mock_create_new_outbound_message.assert_has_calls([
            call("conv_id_1", "Summary for Single 1"),
            call("conv_id_1", "Summary for Grouped 1"),
            call("conv_id_2", "Summary for Single 2"),
            call("conv_id_2", "Summary for Grouped 2 (empty)"),
        ], any_order=True)

        mock_logger.info.assert_has_calls([
            call("Summary for Single 1"),
            call("Summary for Grouped 1"),
            call("Summary for Single 2"),
            call("Summary for Grouped 2 (empty)"),
        ], any_order=True)

        mock_grouped_qs_1.update.assert_called_once_with(processed=True)
        mock_single_qs_1.update.assert_called_once_with(processed=True)
        mock_grouped_qs_2.update.assert_called_once_with(processed=True)
        mock_single_qs_2.update.assert_called_once_with(processed=True)
