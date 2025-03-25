# Generated by Django 5.1.7 on 2025-03-25 16:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0023_alter_feedback_rating'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='company',
            options={'ordering': ['name'], 'verbose_name': 'Company', 'verbose_name_plural': 'Companies'},
        ),
        migrations.AddField(
            model_name='company',
            name='address_line1',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Dirección'),
        ),
        migrations.AddField(
            model_name='company',
            name='address_line2',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Complemento dirección'),
        ),
        migrations.AddField(
            model_name='company',
            name='business_category',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Categoría de negocio'),
        ),
        migrations.AddField(
            model_name='company',
            name='business_description',
            field=models.TextField(blank=True, null=True, verbose_name='Descripción del negocio'),
        ),
        migrations.AddField(
            model_name='company',
            name='city',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Ciudad'),
        ),
        migrations.AddField(
            model_name='company',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email de contacto'),
        ),
        migrations.AddField(
            model_name='company',
            name='contact_name',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Persona de contacto'),
        ),
        migrations.AddField(
            model_name='company',
            name='contact_phone',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Teléfono de contacto'),
        ),
        migrations.AddField(
            model_name='company',
            name='country',
            field=models.CharField(blank=True, default='España', max_length=100, null=True, verbose_name='País'),
        ),
        migrations.AddField(
            model_name='company',
            name='employee_count',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Número de empleados'),
        ),
        migrations.AddField(
            model_name='company',
            name='facebook',
            field=models.URLField(blank=True, null=True, verbose_name='Facebook'),
        ),
        migrations.AddField(
            model_name='company',
            name='founding_year',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Año de fundación'),
        ),
        migrations.AddField(
            model_name='company',
            name='instagram',
            field=models.URLField(blank=True, null=True, verbose_name='Instagram'),
        ),
        migrations.AddField(
            model_name='company',
            name='legal_name',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Razón social'),
        ),
        migrations.AddField(
            model_name='company',
            name='linkedin',
            field=models.URLField(blank=True, null=True, verbose_name='LinkedIn'),
        ),
        migrations.AddField(
            model_name='company',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='company_logos/', verbose_name='Logo'),
        ),
        migrations.AddField(
            model_name='company',
            name='postal_code',
            field=models.CharField(blank=True, max_length=10, null=True, verbose_name='Código postal'),
        ),
        migrations.AddField(
            model_name='company',
            name='state',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Provincia'),
        ),
        migrations.AddField(
            model_name='company',
            name='subscription_end_date',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha fin suscripción'),
        ),
        migrations.AddField(
            model_name='company',
            name='subscription_plan',
            field=models.CharField(blank=True, default='standard', max_length=50, null=True, verbose_name='Plan de suscripción'),
        ),
        migrations.AddField(
            model_name='company',
            name='tax_id',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='NIF/CIF'),
        ),
        migrations.AddField(
            model_name='company',
            name='twitter',
            field=models.URLField(blank=True, null=True, verbose_name='Twitter'),
        ),
        migrations.AddField(
            model_name='company',
            name='website',
            field=models.URLField(blank=True, null=True, verbose_name='Sitio web'),
        ),
        migrations.AlterField(
            model_name='company',
            name='active',
            field=models.BooleanField(default=True, verbose_name='Activa'),
        ),
        migrations.AlterField(
            model_name='company',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación'),
        ),
        migrations.AlterField(
            model_name='company',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Nombre de la empresa'),
        ),
        migrations.AlterField(
            model_name='company',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Última actualización'),
        ),
    ]
