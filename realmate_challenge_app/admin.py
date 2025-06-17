from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'started_at', 'closed_at')
    list_filter = ('status', 'started_at')
    search_fields = ('id',)
    ordering = ('-started_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'type', 'timestamp', 'sender')
    list_filter = ('type', 'timestamp')
    search_fields = ('id', 'content', 'sender')
    ordering = ('-timestamp',)