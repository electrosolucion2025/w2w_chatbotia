# Generated by Django 5.1.7 on 2025-03-25 12:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0018_alter_leadstatistics_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='feedback_requested_at',
            field=models.DateTimeField(blank=True, help_text='Fecha y hora en que se solicitó el feedback', null=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='feedback_requested',
            field=models.BooleanField(default=False, help_text='Indica si se ha solicitado feedback al usuario'),
        ),
    ]
