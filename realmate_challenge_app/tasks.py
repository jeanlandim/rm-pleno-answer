from celery import shared_task
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from rest_framework import status

from .models import Conversation, Message

set_cache_key = lambda conversation_id: f"conversation:{conversation_id}:messages"

@shared_task
def new_conversation_task(
    conversation_id: str,
):
    _, created = Conversation.objects.get_or_create(
        id=conversation_id,
    )
    if created:
        return {"message": "Conversation created"}, status.HTTP_201_CREATED
    return {"error": "Conversation already exists"}, status.HTTP_400_BAD_REQUEST

@shared_task
def close_conversation_task(
    conversation_id: str,
):
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {"error": "Conversation not found"}, status.HTTP_400_BAD_REQUEST

    if conversation.status == Conversation.Status.CLOSED:
        return {"error": "Conversation is already closed"}, status.HTTP_400_BAD_REQUEST

    conversation.status = Conversation.Status.CLOSED
    conversation.save()
    return {"message": "Conversation closed"}, status.HTTP_200_OK


@shared_task
def new_message_task(
    message_id: str,
    conversation_id: str,
    content: str,
    timestamp: str
):
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        pass

    if conversation.status == Conversation.Status.CLOSED:
        return {"error": f"Conversation {conversation_id} is closed"}, status.HTTP_400_BAD_REQUEST

    cache_key = set_cache_key(conversation_id)
    cached = cache.get(cache_key, {"messages": [], "last_timestamp": None})

    cached["messages"].append({"id": message_id, "content": content, "timestamp": timestamp})
    cached["last_timestamp"] = timestamp
    cache.set(cache_key, cached, timeout=10)

    persist_cached_message.delay(kwargs={"conversation_id": conversation_id}, countdown=5)
    return {"message": f"Message {message_id} accepted for processing"}, status.HTTP_202_ACCEPTED

@shared_task
def persist_cached_message(conversation_id: str):
    cache_key = set_cache_key(conversation_id)
    cached_messages = cache.get(cache_key)

    conversation = Conversation.objects.get(id=conversation_id)

    last_message = cached_messages["messages"][-1]
    last_timestamp = parse_datetime(last_message["timestamp"])
    if (now() - last_timestamp).total_seconds() < 5:
        return {"message": "Waiting for more messages"}, status.HTTP_202_ACCEPTED

    combined_content = " ".join([msg["content"] for msg in cached["messages"]])
    Message.objects.create(
        conversation_id=conversation,
        type=Message.MessageType.OUTBOUND,
        content=combined_content,
        timestamp=now(),
    )

    cache.delete(cache_key)
    return {"message": "Combined message persisted"}, status.HTTP_201_CREATED
