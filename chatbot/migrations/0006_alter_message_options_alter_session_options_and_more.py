# Generated by Django 5.1.7 on 2025-03-20 21:47

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0005_alter_session_options_session_last_activity_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='message',
            options={'ordering': ['created_at'], 'verbose_name': 'Message', 'verbose_name_plural': 'Messages'},
        ),
        migrations.AlterModelOptions(
            name='session',
            options={'verbose_name': 'Session', 'verbose_name_plural': 'Sessions'},
        ),
        migrations.AddField(
            model_name='session',
            name='feedback_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='message',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='chatbot.company'),
        ),
        migrations.AlterField(
            model_name='message',
            name='session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='messages', to='chatbot.session'),
        ),
        migrations.AlterField(
            model_name='message',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='chatbot.user'),
        ),
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rating', models.CharField(choices=[('positive', 'Positivo'), ('negative', 'Negativo'), ('neutral', 'Neutral')], max_length=10)),
                ('comment', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedbacks', to='chatbot.company')),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='chatbot.session')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedbacks', to='chatbot.user')),
            ],
            options={
                'verbose_name': 'Feedback',
                'verbose_name_plural': 'Feedbacks',
            },
        ),
    ]
