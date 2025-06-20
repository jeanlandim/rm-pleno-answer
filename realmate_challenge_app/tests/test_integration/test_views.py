from datetime import datetime, timedelta, timezone

from unittest.mock import patch
from uuid import uuid4
import random

from rest_framework import status
from rest_framework.test import APITestCase

from realmate_challenge_app.models import Conversation, Message
from realmate_challenge_app.tasks import process_inbound_messages
from realmate_challenge_app.views import (
    INVALID_PAYLOAD_MESSAGE,
    INTERNAL_SERVER_ERROR_MESSAGE,
    ERROR_CONVERSATION_ALREADY_EXISTS,
    MESSAGE_WITHOUT_CONVERSATION_PROCESSED,
    ERROR_CONVERSATION_CLOSED,
    ERROR_CONVERSATION_ALREADY_CLOSED,
    ERROR_CONVERSATION_NOT_FOUND,
    MESSAGE_CONVERSATION_CREATED,
    MESSAGE_PROCESSED,
    MESSAGE_CONVERSATION_CLOSED,
)

UNEXPECTED_ERROR_EXCEPTION_MESSAGE = "Unexpected error message."

class BaseWebhookTest(APITestCase):
    webhook_url = "/webhook/"

    def _get_current_time_isoformat(self):
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _get_payload_base(self, payload_type, data=None, timestamp=None):
        timestamp = timestamp.isoformat()
        return {
            "type": payload_type,
            "timestamp": timestamp,
            "data": data if data is not None else {}
        }

class TestWebhookPostNewConversation(BaseWebhookTest):
    def get_new_conversation_payload(self, conversation_id=None):
        if conversation_id is None:
            conversation_id = str(uuid4())
        return self._get_payload_base(
            "NEW_CONVERSATION",
            {"id": conversation_id}
        )

    def test_new_conversation_created(self):
        new_conversation_payload_data = self.get_new_conversation_payload()
        conversation_identifier = new_conversation_payload_data['data']['id']

        response = self.client.post(self.webhook_url, data=new_conversation_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json(), {"message": MESSAGE_CONVERSATION_CREATED.format(conversation_identifier)})
        self.assertTrue(Conversation.objects.filter(id=conversation_identifier).exists())

    def test_new_conversation_already_exists(self):
        new_conversation_payload_data = self.get_new_conversation_payload()
        conversation_identifier = new_conversation_payload_data['data']['id']

        self.client.post(self.webhook_url, data=new_conversation_payload_data, format='json')

        response = self.client.post(self.webhook_url, data=new_conversation_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"error": ERROR_CONVERSATION_ALREADY_EXISTS.format(conversation_identifier)})
        self.assertEqual(Conversation.objects.filter(id=conversation_identifier).count(), 1)

class TestWebhookPostNewMessage(BaseWebhookTest):
    def setUp(self):
        super().setUp()
        self.open_conversation_object = Conversation.objects.create(id=uuid4(), status=Conversation.Status.OPEN)

    def get_new_message_payload(self, message_id=None, conversation_id=None, content="Olá", timestamp_dt=None):
        if message_id is None:
            message_id = str(uuid4())
        if conversation_id is None:
            conversation_id = str(uuid4())
        return self._get_payload_base(
            "NEW_MESSAGE",
            {
                "id": message_id,
                "content": content,
                "conversation_id": conversation_id,
            },
            timestamp=timestamp_dt
        )

    def get_new_message_conversation_not_found_payload(self):
        return self._get_payload_base(
            "NEW_MESSAGE",
            {
                "id": str(uuid4()),
                "conversation_id": str(uuid4()),
                "content": "Mensagem sem conversa"
            }
        )

    def test_new_message_accepted(self):
        new_message_payload_data = self.get_new_message_payload(conversation_id=str(self.open_conversation_object.id))
        message_identifier = new_message_payload_data['data']['id']
        conversation_identifier = new_message_payload_data['data']['conversation_id']

        response = self.client.post(self.webhook_url, data=new_message_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"message": MESSAGE_PROCESSED.format(message_id=message_identifier, conversation_id=conversation_identifier)})
        self.assertTrue(Message.objects.filter(id=message_identifier, conversation_id=conversation_identifier).exists())

    def test_new_message_conversation_closed(self):
        closed_conversation_object = Conversation.objects.create(id=uuid4(), status=Conversation.Status.CLOSED)
        new_message_payload_data = self.get_new_message_payload(conversation_id=str(closed_conversation_object.id))

        response = self.client.post(self.webhook_url, data=new_message_payload_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], ERROR_CONVERSATION_CLOSED.format(closed_conversation_object.id))

    def test_new_message_conversation_not_found(self):
        new_message_conversation_not_found_payload_data = self.get_new_message_conversation_not_found_payload()
        message_identifier = new_message_conversation_not_found_payload_data["data"]["id"]
        conversation_identifier = new_message_conversation_not_found_payload_data["data"]["conversation_id"]

        response = self.client.post(self.webhook_url, data=new_message_conversation_not_found_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["message"], MESSAGE_WITHOUT_CONVERSATION_PROCESSED.format(
                        message_id=message_identifier, conversation_id=conversation_identifier))
        self.assertTrue(Message.objects.filter(id=message_identifier, conversation_id=None, expected_conversation_id=conversation_identifier).exists())

    def test_many_messages_process(self):
        conversation_one_id = str(self.open_conversation_object.id)
        conversation_two_object = Conversation.objects.create(id=uuid4(), status=Conversation.Status.OPEN)
        conversation_two_id = str(conversation_two_object.id)

        base_timestamp = datetime.now() - timedelta(minutes=5)
        sent_message_identifiers = []
        contents = ["Olá?", "Tudo bom?", "Tenho interesse em imóvel"]

        current_timestamp_conv1 = base_timestamp
        for content in contents:
            interval_seconds = random.randint(1, 5)
            current_timestamp_conv1 += timedelta(seconds=interval_seconds)
            payload = self.get_new_message_payload(
                conversation_id=conversation_one_id,
                content=content,
                timestamp_dt=current_timestamp_conv1
            )
            response = self.client.post(self.webhook_url, data=payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            sent_message_identifiers.append(payload['data']['id'])

        current_timestamp_conv2 = base_timestamp
        for content in contents:
            interval_seconds = random.randint(1, 5)
            current_timestamp_conv2 += timedelta(seconds=interval_seconds)
            payload = self.get_new_message_payload(
                conversation_id=conversation_two_id,
                content=content,
                timestamp_dt=current_timestamp_conv2
            )
            response = self.client.post(self.webhook_url, data=payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            sent_message_identifiers.append(payload['data']['id'])

        large_gap_timestamp = current_timestamp_conv1 + timedelta(seconds=random.randint(15,20))
        payload = self.get_new_message_payload(
            conversation_id=conversation_one_id,
            content="Boa tarde!",
            timestamp_dt=large_gap_timestamp
        )
        response = self.client.post(self.webhook_url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        sent_message_identifiers.append(payload['data']['id'])
        
        self.assertEqual(len(sent_message_identifiers), 7)
        for message_identifier in sent_message_identifiers:
            self.assertTrue(Message.objects.filter(id=message_identifier).exists())
        
        self.assertEqual(len(process_inbound_messages()), 3)
        self.assertEqual(Message.objects.filter(type=Message.MessageType.OUTBOUND).count(), 3)

class TestWebhookPostCloseConversation(BaseWebhookTest):
    def get_close_conversation_payload(self, conversation_id=None):
        if conversation_id is None:
            conversation_id = str(uuid4())
        return self._get_payload_base(
            "CLOSE_CONVERSATION",
            {"id": conversation_id}
        )

    def test_close_conversation_success(self):
        conversation_to_close = Conversation.objects.create(id=uuid4(), status=Conversation.Status.OPEN)
        close_conversation_payload_data = self.get_close_conversation_payload(conversation_id=str(conversation_to_close.id))
        conversation_identifier = close_conversation_payload_data['data']['id']

        response = self.client.post(self.webhook_url, data=close_conversation_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"message": MESSAGE_CONVERSATION_CLOSED.format(conversation_identifier)})
        conversation = Conversation.objects.get(id=conversation_identifier)
        self.assertEqual(conversation.status, Conversation.Status.CLOSED)

    def test_close_conversation_already_closed(self):
        closed_conversation = Conversation.objects.create(id=uuid4(), status=Conversation.Status.CLOSED)
        close_conversation_payload_data = self.get_close_conversation_payload(conversation_id=str(closed_conversation.id))
        conversation_identifier = close_conversation_payload_data['data']['id']

        response = self.client.post(self.webhook_url, data=close_conversation_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], ERROR_CONVERSATION_ALREADY_CLOSED.format(conversation_identifier))
        self.assertEqual(Conversation.objects.get(id=conversation_identifier).status, Conversation.Status.CLOSED)

    def test_close_conversation_not_found(self):
        close_conversation_not_found_payload_data = self.get_close_conversation_payload(conversation_id=str(uuid4()))
        conversation_identifier = close_conversation_not_found_payload_data['data']['id']

        response = self.client.post(self.webhook_url, data=close_conversation_not_found_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], ERROR_CONVERSATION_NOT_FOUND.format(conversation_identifier))

class TestWebhookPostInvalidPayloads(BaseWebhookTest):
    def get_missing_type_payload(self):
        return self._get_payload_base(None, {"id": str(uuid4())})

    def get_invalid_type_payload(self):
        return self._get_payload_base("INVALID_TYPE", {"id": str(uuid4())})

    def get_invalid_new_conversation_payload(self):
        return self._get_payload_base("NEW_CONVERSATION", None)

    def test_missing_type_field_returns_400(self):
        missing_type_payload_data = self.get_missing_type_payload()
        response = self.client.post(self.webhook_url, data=missing_type_payload_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], INVALID_PAYLOAD_MESSAGE)

    def test_invalid_type_field_returns_400(self):
        invalid_type_payload_data = self.get_invalid_type_payload()
        response = self.client.post(self.webhook_url, data=invalid_type_payload_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], INVALID_PAYLOAD_MESSAGE)

    def test_new_conversation_payload_invalid_returns_400(self):
        invalid_new_conversation_payload_data = self.get_invalid_new_conversation_payload()
        response = self.client.post(self.webhook_url, data=invalid_new_conversation_payload_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], INVALID_PAYLOAD_MESSAGE)
        self.assertIn('details', response.data)

class TestWebhookPostErrorHandling(BaseWebhookTest):
    def test_unhandled_exception_returns_500(self):
        new_conversation_payload_data = TestWebhookPostNewConversation().get_new_conversation_payload()

        with patch(
            "realmate_challenge_app.models.Conversation.objects.get_or_create"
        ) as mocked_handler:
            mocked_handler.side_effect = Exception(UNEXPECTED_ERROR_EXCEPTION_MESSAGE)

            response = self.client.post(self.webhook_url, data=new_conversation_payload_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["error"], INTERNAL_SERVER_ERROR_MESSAGE.format(UNEXPECTED_ERROR_EXCEPTION_MESSAGE))

class TestConversationDetailView(APITestCase):
    conversation_base_url = "/conversations/"

    def setUp(self):
        self.new_conversation_object = Conversation.objects.create(id=uuid4(), status=Conversation.Status.OPEN)
        self.new_message_object = Message.objects.create(
            id=uuid4(),
            conversation_id=self.new_conversation_object,
            content="Mensagem de teste",
            type=Message.MessageType.INBOUND
        )
        self.conversation_url_specific = f"{self.conversation_base_url}{self.new_conversation_object.id}/"

    def test_get_conversation_detail_returns_data(self):
        response = self.client.get(self.conversation_url_specific)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_data = response.json()

        self.assertEqual(returned_data['id'], str(self.new_conversation_object.id))
        self.assertEqual(returned_data['status'], self.new_conversation_object.status)

        self.assertIn('messages', returned_data)
        self.assertEqual(len(returned_data['messages']), 1)

        message_data = returned_data['messages'][0]
        self.assertEqual(message_data['id'], str(self.new_message_object.id))
        self.assertEqual(message_data['type'], self.new_message_object.type)
        self.assertEqual(message_data['content'], self.new_message_object.content)
        self.assertEqual(message_data['timestamp'], self.new_message_object.timestamp.isoformat().replace('+00:00', 'Z'))

    def test_get_conversation_detail_not_found(self):
        conversation_url_non_existent = f"{self.conversation_base_url}{uuid4()}/"
        response = self.client.get(conversation_url_non_existent)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
