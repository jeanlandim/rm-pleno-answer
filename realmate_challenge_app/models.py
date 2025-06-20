import uuid

from django.db import models


class Conversation(models.Model):

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        CLOSED = 'CLOSED', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=6,
        choices=Status.choices,
        default=Status.OPEN
    )
    timestamp = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    
    class MessageType(models.TextChoices):
        INBOUND = 'INBOUND', 'Inbound'
        OUTBOUND = 'OUTBOUND', 'Outbound'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_id = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        null=True, 
        related_name='messages'
    )
    type = models.CharField(max_length=8, choices=MessageType.choices, default=MessageType.INBOUND)
    content = models.TextField()
    timestamp = models.DateTimeField()
    expected_conversation_id = models.UUIDField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    