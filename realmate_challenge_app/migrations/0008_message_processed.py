# Generated by Django 5.2.3 on 2025-06-19 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('realmate_challenge_app', '0007_message_expected_conversation_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='processed',
            field=models.BooleanField(default=False),
        ),
    ]
