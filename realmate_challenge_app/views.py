from typing import Any
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import RetrieveAPIView

from realmate_challenge.logger import logger
from .models import Conversation, Message
from .serializers.payloads import (
    NewConversationPayloadSerializer,
    NewMessagePayloadSerializer,
    CloseConversationPayloadSerializer,
)
from .serializers.responses import ConversationDetailSerializer

INVALID_PAYLOAD_MESSAGE = "Invalid or inexistent payload."
INTERNAL_SERVER_ERROR_MESSAGE = "Internal server error: {}"
ERROR_CONVERSATION_ALREADY_EXISTS = "Conversation {} already exists"
ERROR_CONVERSATION_NOT_FOUND_FOR_MESSAGE = "Conversation {} not found for message"
ERROR_CONVERSATION_CLOSED = "Conversation {} is closed"
ERROR_CONVERSATION_ALREADY_CLOSED = "Conversation {} is already closed"
ERROR_CONVERSATION_NOT_FOUND = "Conversation {} not found"

MESSAGE_CONVERSATION_CREATED = "Conversation {} created"
MESSAGE_MESSAGE_PROCESSED = "Message {message_id} processed with conversation {conversation_id}"
MESSAGE_MESSAGE_WITHOUT_CONVERSATION_PROCESSED = "Message {message_id} processed without conversation {conversation_id}"
MESSAGE_CONVERSATION_CLOSED = "Conversation {} closed"
MESSAGE_UNKNOWN_OPERATION_RESULT = "Unknown operation result"


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
                {"error": INVALID_PAYLOAD_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_payload = serializer.validated_data

            output = {"error": INVALID_PAYLOAD_MESSAGE}
            http_status = status.HTTP_400_BAD_REQUEST

            if payload_type == "NEW_CONVERSATION":
                conversation_id = validated_payload["data"]["id"]
                
                conversation, created = Conversation.objects.get_or_create(
                    id=conversation_id,
                )
                if created:
                    output = {"message": MESSAGE_CONVERSATION_CREATED.format(conversation_id)}
                    http_status = status.HTTP_201_CREATED
                else:
                    output = {"error": ERROR_CONVERSATION_ALREADY_EXISTS.format(conversation_id)}           
            elif payload_type == "NEW_MESSAGE":
                message_id = validated_payload["data"]["id"]
                conversation_id = validated_payload["data"]["conversation_id"]
                content = validated_payload["data"]["content"]
                timestamp = validated_payload["timestamp"]

                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                except Conversation.DoesNotExist:
                    conversation = None


                if conversation and conversation.status == Conversation.Status.CLOSED:
                    output = {"error": ERROR_CONVERSATION_CLOSED.format(conversation_id)}
                    logger.warning(ERROR_CONVERSATION_CLOSED.format(conversation_id))
                    return Response(output, status=http_status)

                Message.objects.create(
                    id=message_id,
                    conversation_id=conversation,
                    type=Message.MessageType.INBOUND,
                    content=content,
                    timestamp=timestamp
                )


                if not conversation:
                    output = {
                        "message": MESSAGE_MESSAGE_WITHOUT_CONVERSATION_PROCESSED.format(
                        message_id=message_id, conversation_id=conversation_id)
                    }
                else:
                    output = {
                        "message": MESSAGE_MESSAGE_PROCESSED.format(
                        message_id=message_id, conversation_id=conversation.id)
                    }

                http_status = status.HTTP_202_ACCEPTED
            elif payload_type == "CLOSE_CONVERSATION":
                conversation_id = validated_payload["data"]["id"]
                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                    if conversation.status == Conversation.Status.CLOSED:
                        output = {"error": ERROR_CONVERSATION_ALREADY_CLOSED.format(conversation_id)}
                    else:
                        conversation.status = Conversation.Status.CLOSED
                        conversation.save()
                        output = {"message": MESSAGE_CONVERSATION_CLOSED.format(conversation_id)}
                        http_status = status.HTTP_200_OK
                except Conversation.DoesNotExist:
                    output = {"error": ERROR_CONVERSATION_NOT_FOUND.format(conversation_id)}

            logger.info(output.get("message", output.get("error", MESSAGE_UNKNOWN_OPERATION_RESULT)))
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