from celery import shared_task
from django.utils.dateparse import parse_datetime
from .models import Conversation, Message

@shared_task
def new_conversation_task(conversation_id: str, timestamp: str) -> dict:
    obj, created = Conversation.objects.get_or_create(
        id=conversation_id,
        defaults={'started_at': parse_datetime(timestamp)}
    )
    if created:
        return {'message': 'Conversa criada', 'status': 201}
    return {'error': 'Conversa já existe', 'status': 400}

@shared_task
def new_message_task(message_id: str, conversation_id: str, content: str, timestamp: str) -> dict:
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {'error': 'Conversa não encontrada', 'status': 400}

    if conversation.status == Conversation.Status.CLOSED:
        return {'error': 'Conversa fechada', 'status': 400}

    Message.objects.create(
        id=message_id,
        conversation=conversation,
        type=Message.MessageType.INBOUND,
        content=content,
        timestamp=parse_datetime(timestamp),
    )
    return {'message': 'Mensagem aceita para processamento', 'status': 202}

@shared_task
def close_conversation_task(conversation_id: str, timestamp: str) -> dict:
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {'error': 'Conversa não encontrada', 'status': 400}

    if conversation.status == Conversation.Status.CLOSED:
        return {'error': 'Conversa já está fechada', 'status': 400}

    conversation.status = Conversation.Status.CLOSED
    conversation.closed_at = parse_datetime(timestamp)
    conversation.save()
    return {'message': 'Conversa fechada', 'status': 200}
