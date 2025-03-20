# Generated by Django 5.1.7 on 2025-03-20 18:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0002_companyinfo'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='company',
            options={'verbose_name': 'Company', 'verbose_name_plural': 'Companies'},
        ),
        migrations.AddField(
            model_name='company',
            name='active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='company',
            name='whatsapp_api_token',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='whatsapp_phone_number_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
