from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id',)
    ordering = ('-created_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation_id', 'type', 'timestamp')
    list_filter = ('type', 'timestamp')
    search_fields = ('id', 'content', 'sender')
    ordering = ('-timestamp',)