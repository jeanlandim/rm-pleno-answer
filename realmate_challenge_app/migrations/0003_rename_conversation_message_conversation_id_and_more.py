# Generated by Django 5.2.3 on 2025-06-18 22:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('realmate_challenge_app', '0002_rename_started_at_conversation_created_at_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='message',
            old_name='conversation',
            new_name='conversation_id',
        ),
        migrations.RemoveField(
            model_name='message',
            name='metadata',
        ),
        migrations.RemoveField(
            model_name='message',
            name='sender',
        ),
    ]
