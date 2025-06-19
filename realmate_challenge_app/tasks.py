from celery import shared_task
from django.db import transaction

from realmate_challenge.logger import logger
from .models import Message, Conversation

from django.db.models import F, Window
from django.db.models.functions import Lag
from datetime import timedelta


INTERVAL_MINIMAL_EXPECTED = 5
MSG_MESSAGE_ALREADY_HAS_CONVERSATION = "Message {message_id} already has a conversation ID. Skipping."
MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED = "Message {message_id} has no conversation_id and no expected_conversation_id. Deleting."
MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING = "Conversation {conversation_id} not found for message {message_id}. Deleting message."
MSG_MESSAGE_SUCCESSFULLY_ASSIGNED = "Message {message_id} successfully assigned to conversation {conversation_id}."
MSG_MESSAGE_NOT_FOUND = "Message {message_id} not found (might have been deleted by another process)."
MSG_ERROR_PROCESSING_MESSAGE_CELERY = "Error processing message {message_id}. Error: {exc}"

@shared_task
def check_and_assign_conversation(message_id: str):
    try:
        with transaction.atomic():
            message = Message.objects.select_for_update().get(id=message_id)

            if message.conversation_id is not None:
                logger.info(MSG_MESSAGE_ALREADY_HAS_CONVERSATION.format(message_id=message.id))
                return

            if message.expected_conversation_id is None:
                logger.warning(MSG_MESSAGE_NO_CONVERSATION_OR_EXPECTED.format(message_id=message.id))
                message.delete()
                return

            try:
                conversation = Conversation.objects.get(id=message.expected_conversation_id)
                message.conversation_id = conversation
                message.save()
                logger.info(MSG_MESSAGE_SUCCESSFULLY_ASSIGNED.format(
                    message_id=message.id, 
                    conversation_id=conversation.id
                    )
                )
            except Conversation.DoesNotExist:
                logger.warning(
                    MSG_CONVERSATION_NOT_FOUND_FOR_MESSAGE_DELETING.format(
                        conversation_id=message.expected_conversation_id, 
                        message_id=message.id
                    )
                )
                message.delete()

    except Message.DoesNotExist:
        logger.info(MSG_MESSAGE_NOT_FOUND.format(message_id=message_id))
    except Exception as exc:
        logger.error(MSG_ERROR_PROCESSING_MESSAGE_CELERY.format(message_id=message_id, exc=exc))


def _get_messages_with_less_than_five_secs(conversation_id):
    messages = Message.objects.annotate(
        previous_timestamp=Window(
            expression=Lag('timestamp'),
            order_by=F('timestamp').asc()
        )
    ).filter(
        conversation_id__id=conversation_id,
        processed=False,
        type=Message.MessageType.INBOUND,
        previous_timestamp__isnull=False,
        timestamp__lte=F('previous_timestamp') + timedelta(seconds=INTERVAL_MINIMAL_EXPECTED)
    )

    return messages

def _build_message_summary(ids):
    return "Mensagens recebidas:\n" + "\n".join(str(_id) for _id in ids)

def _create_new_outbound_message(conversation_id: str, content: str):
    return Message.objects.create(
        conversation_id=Conversation.objects.get(id=conversation_id),
        content=content,
        processed=True,
    )

@shared_task
def process_inbound_messages():
    for conversation_id in Conversation.objects.values_list("id", flat=True):
        messages_to_group = _get_messages_with_less_than_five_secs(conversation_id)
        single_messages = Message.objects.filter(
            conversation_id__id=conversation_id
        )

        for messages in [single_messages, messages_to_group]:
            content = _build_message_summary(messages.values_list('id', flat=True))
            _create_new_outbound_message(conversation_id, content)
            
            logger.info(content)
            messages.update(
                processed=True
            )
        
    