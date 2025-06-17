import pytest

from unittest.mock import patch
from rest_framework import status
from realmate_challenge_app.models import Conversation, Message


@pytest.mark.django_db
class TestWebhookView:

    def test_new_conversation_created(self, client, webhook_url, new_conversation_payload):
        response = client.post(webhook_url, data=new_conversation_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        conversation_id = new_conversation_payload['data']['id']
        assert Conversation.objects.filter(id=conversation_id).exists()

    def test_new_conversation_already_exists(self, client, webhook_url, new_conversation_payload, current_time):
        conversation_id = new_conversation_payload['data']['id']
        Conversation.objects.create(id=conversation_id, started_at=current_time)
        response = client.post(webhook_url, data=new_conversation_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Conversa já existe'

    def test_new_message_accepted(self, client, webhook_url, new_message_payload, current_time):
        conversation_id = new_message_payload['data']['conversation_id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.OPEN, started_at=current_time)
        response = client.post(webhook_url, data=new_message_payload, format='json')
        assert response.status_code == status.HTTP_202_ACCEPTED
        message_id = new_message_payload['data']['id']
        assert Message.objects.filter(id=message_id, conversation_id=conversation_id).exists()

    def test_new_message_conversation_closed(self, client, webhook_url, new_message_payload, current_time):
        conversation_id = new_message_payload['data']['conversation_id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.CLOSED, started_at=current_time)
        new_message_payload['data']['content'] = "Mensagem inválida"
        response = client.post(webhook_url, data=new_message_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Conversa fechada'

    def test_close_conversation_success(self, client, webhook_url, close_conversation_payload, current_time):
        conversation_id = close_conversation_payload['data']['id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.OPEN, started_at=current_time)
        response = client.post(webhook_url, data=close_conversation_payload, format='json')
        assert response.status_code == status.HTTP_200_OK
        conversation = Conversation.objects.get(id=conversation_id)
        assert conversation.status == Conversation.Status.CLOSED

    def test_close_conversation_already_closed(self, client, webhook_url, close_conversation_payload, current_time):
        conversation_id = close_conversation_payload['data']['id']
        Conversation.objects.create(id=conversation_id, status=Conversation.Status.CLOSED, started_at=current_time)
        response = client.post(webhook_url, data=close_conversation_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Conversa já está fechada'

    def test_close_conversation_not_found(self, client, webhook_url, close_conversation_not_found_payload):
        response = client.post(webhook_url, data=close_conversation_not_found_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Conversa não encontrada'


    def test_missing_type_field_returns_400(self, client, webhook_url, missing_type_payload):
        response = client.post(webhook_url, data=missing_type_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Tipo de payload inválido ou ausente'


    def test_invalid_type_field_returns_400(self, client, webhook_url, invalid_type_payload):
        response = client.post(webhook_url, data=invalid_type_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Tipo de payload inválido ou ausente'


    def test_new_conversation_payload_invalid_returns_400(self, client, webhook_url, invalid_new_conversation_payload):
        response = client.post(webhook_url, data=invalid_new_conversation_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Payload inválido'
        assert 'data' in response.data['details']


    def test_unhandled_exception_returns_500(self, client, webhook_url, new_conversation_payload):
        with patch(
            "realmate_challenge_app.views.WebhookView._handle_new_conversation"
        ) as mocked_handler:
            mocked_handler.side_effect = Exception("Erro inesperado")

            response = client.post(webhook_url, data=new_conversation_payload, format='json')

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['error'].startswith('Erro interno do servidor')
        assert 'Erro inesperado' in response.data['error']


    def test_new_message_conversation_not_found(self, client, webhook_url, new_message_conversation_not_found_payload):
        response = client.post(webhook_url, data=new_message_conversation_not_found_payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'Conversa não encontrada'

@pytest.mark.django_db
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
        assert 'started_at' in data
        assert 'closed_at' in data

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