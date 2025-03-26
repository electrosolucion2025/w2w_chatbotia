from django import forms
from django.contrib.auth.models import User
from .models import Company

class CompanyAdminForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        label="Usuario"
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(active=True),
        label="Empresa"
    )
    is_primary = forms.BooleanField(
        required=False,
        label="Administrador Principal",
        help_text="El administrador principal puede gestionar otros administradores de la empresa"
    )