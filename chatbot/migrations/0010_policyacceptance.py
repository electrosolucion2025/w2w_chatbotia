# Generated by Django 5.1.7 on 2025-03-21 12:32

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0009_alter_policyversion_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolicyAcceptance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('accepted_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('policy_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='acceptances', to='chatbot.policyversion')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='policy_acceptances', to='chatbot.user')),
            ],
            options={
                'verbose_name': 'Policy Acceptance',
                'verbose_name_plural': 'Policy Acceptances',
                'ordering': ['-accepted_at'],
            },
        ),
    ]
