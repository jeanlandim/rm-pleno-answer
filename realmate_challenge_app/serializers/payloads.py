from rest_framework import serializers


class ConversationDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class NewMessageDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    content = serializers.CharField(max_length=500)
    conversation_id = serializers.UUIDField()


class NewConversationPayloadSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[("NEW_CONVERSATION", "NEW_CONVERSATION")])
    timestamp = serializers.DateTimeField()
    data = ConversationDataSerializer()


class NewMessagePayloadSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[("NEW_MESSAGE", "NEW_MESSAGE")])
    timestamp = serializers.DateTimeField()
    data = NewMessageDataSerializer()


class CloseConversationPayloadSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[("CLOSE_CONVERSATION", "CLOSE_CONVERSATION")])
    timestamp = serializers.DateTimeField()
    data = ConversationDataSerializer()