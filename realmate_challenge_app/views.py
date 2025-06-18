from typing import Any
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import RetrieveAPIView

from realmate_challenge.logger import logger
from .models import Conversation
from .serializers.payloads import (
    NewConversationPayloadSerializer,
    NewMessagePayloadSerializer,
    CloseConversationPayloadSerializer,
)
from .serializers.responses import ConversationDetailSerializer
from .tasks import (
    new_conversation_task,
    new_message_task,
    close_conversation_task,
)

INVALID_PAYLOAD_MESSAGE = "Invalid payload message."
INTERNAL_SERVER_ERROR_MESSAGE = "Internal server error: {}"

class WebhookView(APIView):
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload_type = request.data.get("type")

        serializer_class = None
        if payload_type == "NEW_CONVERSATION":
            serializer_class = NewConversationPayloadSerializer
        elif payload_type == "NEW_MESSAGE":
            serializer_class = NewMessagePayloadSerializer
        elif payload_type == "CLOSE_CONVERSATION":
            serializer_class = CloseConversationPayloadSerializer
        else:
            return Response(
                {"error": "Invalid or inexistent payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_payload = serializer.validated_data

            if payload_type == "NEW_CONVERSATION":
                result = new_conversation_task.delay(
                    validated_payload["data"]["id"],
                )
            elif payload_type == "NEW_MESSAGE":
                result = new_message_task.delay(
                    validated_payload["data"]["id"],
                    validated_payload["data"]["conversation_id"],
                    validated_payload["data"]["content"],
                    validated_payload["timestamp"],  
                )
            elif payload_type == "CLOSE_CONVERSATION":
                result = close_conversation_task.delay(
                    validated_payload["data"]["id"],
                )
                
            output, http_status = result.get()
            logger.info(output["message"] if "message" in output else output["error"])
            return Response(output, status=http_status)

        except DRFValidationError as exc:
            logger.exception(INVALID_PAYLOAD_MESSAGE)
            return Response(
                {"error": INVALID_PAYLOAD_MESSAGE, "details": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error(INTERNAL_SERVER_ERROR_MESSAGE.format(str(exc)))
            return Response(
                {"error": INTERNAL_SERVER_ERROR_MESSAGE.format(str(exc))},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConversationDetailView(RetrieveAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationDetailSerializer
    lookup_field = "id"
