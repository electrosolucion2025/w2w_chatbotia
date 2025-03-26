# Generated by Django 5.1.7 on 2025-03-26 11:40

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0025_openaimonthlysummary_openaiusagerecord'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyAdmin',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_primary', models.BooleanField(default=False, help_text='Indica si es el administrador principal de la empresa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='administrators', to='chatbot.company')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='company_admin', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Administrador de Empresa',
                'verbose_name_plural': 'Administradores de Empresas',
                'unique_together': {('user', 'company')},
            },
        ),
    ]
