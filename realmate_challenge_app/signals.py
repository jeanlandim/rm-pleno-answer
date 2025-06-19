from django.db.models.signals import post_save
from django.dispatch import receiver
from realmate_challenge.logger import logger

from .models import Message
from .tasks import check_and_assign_conversation


MSG_SCHEDULED_CONVERSATION_CHECK = "Scheduled conversation check for message %s with expected conversation %s in %s seconds."
COUNTDOWN_SECONDS = 6

@receiver(post_save, sender=Message)
def schedule_conversation_check(sender, instance, created, **kwargs):
    if created and instance.conversation_id is None and instance.expected_conversation_id is not None:
        check_and_assign_conversation.apply_async(
            args=[str(instance.id)],
            countdown=COUNTDOWN_SECONDS
        )
        logger.info(
            MSG_SCHEDULED_CONVERSATION_CHECK,
            instance.id,
            instance.expected_conversation_id,
            COUNTDOWN_SECONDS
        )