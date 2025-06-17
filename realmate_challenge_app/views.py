from typing import Any
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import RetrieveAPIView

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

class WebhookView(APIView):

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload_type = request.data.get('type')

        serializer_class = None
        if payload_type == 'NEW_CONVERSATION':
            serializer_class = NewConversationPayloadSerializer
        elif payload_type == 'NEW_MESSAGE':
            serializer_class = NewMessagePayloadSerializer
        elif payload_type == 'CLOSE_CONVERSATION':
            serializer_class = CloseConversationPayloadSerializer
        else:
            return Response(
                {'error': 'Tipo de payload inválido ou ausente'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)

            validated_payload = serializer.validated_data

            if payload_type == 'NEW_CONVERSATION':
                return new_conversation_task.delay(**validated_payload)
            elif payload_type == 'NEW_MESSAGE':
                return new_message_task.delay(**validated_payload)
            elif payload_type == 'CLOSE_CONVERSATION':
                return close_conversation_task.delay(**validated_payload)

        except DRFValidationError as exc:
            return Response(
                {'error': 'Payload inválido', 'details': exc.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            return Response(
                {'error': f'Erro interno do servidor: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

 
class ConversationDetailView(RetrieveAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationDetailSerializer
    lookup_field = 'id'
