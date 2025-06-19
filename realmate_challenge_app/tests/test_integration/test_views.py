import pytest

from unittest.mock import patch
from rest_framework import status
from realmate_challenge_app.models import Conversation, Message

from realmate_challenge_app.views import (
    INVALID_PAYLOAD_MESSAGE,
    INTERNAL_SERVER_ERROR_MESSAGE,
    ERROR_CONVERSATION_ALREADY_EXISTS,
    ERROR_CONVERSATION_NOT_FOUND_FOR_MESSAGE,
    ERROR_CONVERSATION_CLOSED,
    ERROR_CONVERSATION_ALREADY_CLOSED,
    ERROR_CONVERSATION_NOT_FOUND,
    MESSAGE_CONVERSATION_CREATED,
    MESSAGE_MESSAGE_PROCESSED,
    MESSAGE_CONVERSATION_CLOSED,
)

pytestmark = [pytest.mark.django_db]

class TestWebhookView:

    def test_new_conversation_created(self, client, webhook_url, new_conversation_payload):
        response = client.post(webhook_url, data=new_conversation_payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": MESSAGE_CONVERSATION_CREATED.format(new_conversation_payload['data']['id'])}

    def test_new_conversation_already_exists(self, client, webhook_url, new_conversation_payload):
        for _ in range(2):
            response = client.post(webhook_url, data=new_conversation_payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"error": ERROR_CONVERSATION_ALREADY_EXISTS.format(new_conversation_payload['data']['id'])}

    def test_new_message_accepted(self, client, webhook_url, new_message_payload, new_conversation):
        response = client.post(webhook_url, data=new_message_payload, format='json')

        new_message_payload['data']['conversation_id'] = new_conversation.id
        message_id = new_message_payload['data']['id']

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json() == {"message": MESSAGE_MESSAGE_PROCESSED.format(message_id=message_id, conversation_id=new_conversation.id)}
        assert Message.objects.filter(id=message_id, conversation_id=new_conversation.id).exists()

    def test_new_message_conversation_closed(self, client, webhook_url, new_closed_conversation, new_message_payload):
        new_message_payload['data']['conversation_id'] = new_closed_conversation.id
        response = client.post(webhook_url, data=new_message_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == ERROR_CONVERSATION_CLOSED.format(new_closed_conversation.id)

    def test_close_conversation_success(self, client, webhook_url, close_conversation_payload):
        conversation_id = close_conversation_payload['data']['id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.OPEN)
        response = client.post(webhook_url, data=close_conversation_payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": MESSAGE_CONVERSATION_CLOSED.format(conversation_id)}
        conversation = Conversation.objects.get(id=conversation_id)
        assert conversation.status == Conversation.Status.CLOSED

    def test_close_conversation_already_closed(self, client, webhook_url, close_conversation_payload):
        conversation_id = close_conversation_payload['data']['id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.CLOSED)
        response = client.post(webhook_url, data=close_conversation_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == ERROR_CONVERSATION_ALREADY_CLOSED.format(conversation_id)

    def test_close_conversation_not_found(self, client, webhook_url, close_conversation_not_found_payload):
        response = client.post(webhook_url, data=close_conversation_not_found_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == ERROR_CONVERSATION_NOT_FOUND.format(close_conversation_not_found_payload['data']['id'])


    def test_missing_type_field_returns_400(self, client, webhook_url, missing_type_payload):
        response = client.post(webhook_url, data=missing_type_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_PAYLOAD_MESSAGE


    def test_invalid_type_field_returns_400(self, client, webhook_url, invalid_type_payload):
        response = client.post(webhook_url, data=invalid_type_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_PAYLOAD_MESSAGE


    def test_new_conversation_payload_invalid_returns_400(self, client, webhook_url, invalid_new_conversation_payload):
        response = client.post(webhook_url, data=invalid_new_conversation_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_PAYLOAD_MESSAGE
        assert 'details' in response.data


    def test_unhandled_exception_returns_500(self, client, webhook_url, new_conversation_payload):
        with patch(
            "realmate_challenge_app.views.WebhookView.post"
        ) as mocked_handler:
            mocked_handler.side_effect = Exception("Erro inesperado")

            response = client.post(webhook_url, data=new_conversation_payload, format='json')

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['error'].startswith(INTERNAL_SERVER_ERROR_MESSAGE.split(':')[0])
        assert 'Erro inesperado' in response.data['error']


    def test_new_message_conversation_not_found(self, client, webhook_url, new_message_conversation_not_found_payload):
        response = client.post(webhook_url, data=new_message_conversation_not_found_payload, format='json')
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['error'] == ERROR_CONVERSATION_NOT_FOUND_FOR_MESSAGE.format(new_message_conversation_not_found_payload['data']['conversation_id'])

class TestConversationDetailView:

    def test_get_conversation_detail_returns_data(self, 
            client, 
            new_conversation, 
            new_message, 
            conversation_url
    ):
        response = client.get(conversation_url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['id'] == str(new_conversation.id)
        assert data['status'] == new_conversation.status

        assert 'messages' in data
        assert len(data['messages']) == 1

        message_data = data['messages'][0]
        assert message_data['id'] == str(new_message.id)
        assert message_data['type'] == new_message.type
        assert message_data['content'] == new_message.content
        assert message_data['timestamp'] == new_message.timestamp

    def test_get_conversation_detail_not_found(self, client, conversation_url_without_id):
        response = client.get(conversation_url_without_id)
        assert response.status_code == status.HTTP_404_NOT_FOUND