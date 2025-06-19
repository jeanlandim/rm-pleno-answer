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

        serializer_class = self._get_serializer_class(payload_type)
        if not serializer_class:
            return Response(
                {"error": INVALID_PAYLOAD_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_payload = serializer.validated_data

            output, http_status = self._process_payload(payload_type, validated_payload)

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

    def _get_serializer_class(self, payload_type: str):
        if payload_type == "NEW_CONVERSATION":
            return NewConversationPayloadSerializer
        if payload_type == "NEW_MESSAGE":
            return NewMessagePayloadSerializer
        if payload_type == "CLOSE_CONVERSATION":
            return CloseConversationPayloadSerializer
        return None

    def _process_payload(self, payload_type: str, validated_payload: dict) -> tuple[dict, int]:
        if payload_type == "NEW_CONVERSATION":
            return self._handle_new_conversation(validated_payload)
        if payload_type == "NEW_MESSAGE":
            return self._handle_new_message(validated_payload)
        if payload_type == "CLOSE_CONVERSATION":
            return self._handle_close_conversation(validated_payload)       

    def _handle_new_conversation(self, validated_payload: dict) -> tuple[dict, int]:
        conversation_id = validated_payload["data"]["id"]
        
        _, created = Conversation.objects.get_or_create(
            id=conversation_id,
        )
        if created:
            return {"message": MESSAGE_CONVERSATION_CREATED.format(conversation_id)}, status.HTTP_201_CREATED
        return {"error": ERROR_CONVERSATION_ALREADY_EXISTS.format(conversation_id)}, status.HTTP_400_BAD_REQUEST
    
    def _handle_new_message(self, validated_payload: dict) -> tuple[dict, int]:
        message_id = validated_payload["data"]["id"]
        conversation_id = validated_payload["data"]["conversation_id"]
        content = validated_payload["data"]["content"]
        timestamp = validated_payload["timestamp"]

        try:
            conversation = Conversation.objects.get(id=conversation_id)
            if conversation.status == Conversation.Status.CLOSED:
                logger.warning(ERROR_CONVERSATION_CLOSED.format(conversation_id))
                return {"error": ERROR_CONVERSATION_CLOSED.format(conversation_id)}, status.HTTP_400_BAD_REQUEST
        except Conversation.DoesNotExist:
            conversation = None
        

        if not conversation:
            output_message = MESSAGE_MESSAGE_WITHOUT_CONVERSATION_PROCESSED.format(
                message_id=message_id, conversation_id=conversation_id
            )
            expected_conversation_id = conversation_id
        else:
            output_message = MESSAGE_MESSAGE_PROCESSED.format(
                message_id=message_id, conversation_id=conversation.id
            )
            expected_conversation_id = None

        Message.objects.create(
            id=message_id,
            conversation_id=conversation,
            type=Message.MessageType.INBOUND,
            content=content,
            timestamp=timestamp,
            expected_conversation_id=expected_conversation_id
        )

        return {"message": output_message}, status.HTTP_202_ACCEPTED

    def _handle_close_conversation(self, validated_payload: dict) -> tuple[dict, int]:
        conversation_id = validated_payload["data"]["id"]
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            if conversation.status == Conversation.Status.CLOSED:
                return {"error": ERROR_CONVERSATION_ALREADY_CLOSED.format(conversation_id)}, status.HTTP_400_BAD_REQUEST
            else:
                conversation.status = Conversation.Status.CLOSED
                conversation.save()
                return {"message": MESSAGE_CONVERSATION_CLOSED.format(conversation_id)}, status.HTTP_200_OK
        except Conversation.DoesNotExist:
            return {"error": ERROR_CONVERSATION_NOT_FOUND.format(conversation_id)}, status.HTTP_400_BAD_REQUEST

class ConversationDetailView(RetrieveAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationDetailSerializer
    lookup_field = "id"