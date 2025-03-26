from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Company, CompanyAdmin, Ticket, TicketComment
from .forms import CompanyAdminForm 
from django.utils import timezone

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

@staff_member_required
def reply_to_ticket(request, ticket_id):
    """Vista para responder a un ticket desde el panel admin"""
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    
    # Verificar permiso para la empresa
    if not request.user.is_superuser and (not hasattr(request.user, 'company_admin') or 
                                         request.user.company_admin.company != ticket.company):
        messages.error(request, "No tienes permiso para responder a este ticket.")
        return redirect('admin:chatbot_ticket_change', ticket_id)
    
    if request.method == 'POST':
        if 'comment' in request.POST and request.POST['comment'].strip():
            # Guardar comentario
            comment = TicketComment.objects.create(
                ticket=ticket,
                author=request.user,
                is_staff=True,
                content=request.POST['comment'].strip()
            )
            
            # Enviar mensaje al cliente por WhatsApp
            if 'send_whatsapp' in request.POST:
                from chatbot.services.whatsapp_service import WhatsAppService
                whatsapp = WhatsAppService()
                
                message = f"*Actualización de tu reporte #{ticket.id}*\n\n"
                message += request.POST['comment'].strip()
                
                if 'new_status' in request.POST:
                    new_status = dict(Ticket.STATUS_CHOICES).get(request.POST['new_status'])
                    message += f"\n\n_Estado actualizado: {new_status}_"
                    
                    # Actualizar estado del ticket
                    ticket.status = request.POST['new_status']
                    if request.POST['new_status'] == 'resolved':
                        ticket.resolved_at = timezone.now()
                    ticket.save()
                
                # Enviar mensaje
                try:
                    whatsapp.send_message(ticket.user.whatsapp_number, message)
                    messages.success(request, f"Respuesta enviada por WhatsApp a {ticket.user.whatsapp_number}")
                except Exception as e:
                    messages.error(request, f"Error enviando WhatsApp: {e}")
            
            messages.success(request, "Respuesta registrada correctamente")
            return redirect('admin:chatbot_ticket_change', ticket_id)
    
    return render(request, 'admin/ticket_reply.html', {
        'ticket': ticket,
        'status_choices': Ticket.STATUS_CHOICES,
        'comments': ticket.comments.all().order_by('-created_at')[:10],
    })