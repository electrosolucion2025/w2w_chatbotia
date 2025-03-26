from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Company, CompanyAdmin
from .forms import CompanyAdminForm  # Crear este formulario

@user_passes_test(lambda u: u.is_superuser)
def create_company_admin(request):
    """Vista para crear un administrador de empresa"""
    if request.method == 'POST':
        form = CompanyAdminForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            company = form.cleaned_data['company']
            is_primary = form.cleaned_data['is_primary']
            
            # Verificar si ya existe
            if CompanyAdmin.objects.filter(user=user, company=company).exists():
                messages.error(request, f"El usuario {user.username} ya es administrador de {company.name}")
                return redirect('admin:index')
                
            # Crear el administrador
            admin = CompanyAdmin(
                user=user,
                company=company,
                is_primary=is_primary
            )
            admin.save()
            
            # Asegurar que el usuario tenga permisos de staff
            if not user.is_staff:
                user.is_staff = True
                user.save()
                
            messages.success(request, f"{user.username} ha sido asignado como administrador de {company.name}")
            return redirect('admin:index')
    else:
        form = CompanyAdminForm()
        
    return render(request, 'admin/create_company_admin.html', {'form': form})