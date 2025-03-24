import uuid
from django.db import models
from django.utils import timezone
import json

class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    whatsapp_api_token = models.CharField(max_length=500, blank=True, null=True)
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

class CompanyInfo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='info_sections')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.company.name} - {self.title}"

class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    whatsapp_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Nuevos campos para aceptación de políticas
    policies_accepted = models.BooleanField(default=False)
    policies_accepted_date = models.DateTimeField(blank=True, null=True)
    policies_version = models.CharField(max_length=20, blank=True, null=True)
    waiting_policy_acceptance = models.BooleanField(default=False)
    pending_message_text = models.TextField(blank=True, null=True)
    
    # Nuevos campos para gestión de idiomas
    language = models.CharField(
        max_length=10,
        default=None,
        help_text="Código ISO del idioma preferido",
        blank=True,
        null=True,
    )
    waiting_for_language = models.BooleanField(
        default=False,
        help_text="Indica si el usuario está esperando seleccionar un idioma"
    )
    
    def __str__(self):
        return self.name or self.whatsapp_number
    
    def accept_policies(self, version="1.0"):
        """Marca las políticas como aceptadas"""
        self.policies_accepted = True
        self.policies_accepted_date = timezone.now()
        self.policies_version = version
        self.waiting_policy_acceptance = False
        self.save()

    def needs_policy_update(self, current_version=None):
        """
        Verifica si el usuario necesita aceptar una versión más reciente de las políticas
        
        Args:
            current_version: La versión actual activa de la política (opcional)
            
        Returns:
            bool: True si necesita actualizar aceptación, False en caso contrario
        """
        # Si nunca aceptó políticas, definitivamente necesita actualizar
        if not self.policies_accepted:
            return True
            
        # Si no se proporcionó una versión actual, buscarla
        if not current_version:
            from django.apps import apps
            PolicyVersion = apps.get_model('chatbot', 'PolicyVersion')
            active_policy = PolicyVersion.objects.filter(active=True).first()
            if not active_policy:
                return False  # No hay política activa para comparar
            current_version = active_policy.version
        
        # Si la versión que aceptó es la misma que la actual, no necesita actualizar
        if self.policies_version == current_version:
            return False
        
        # Procesar versiones semánticas (1.0, 2.1, etc.)
        try:
            # Convertir versiones a componentes numéricos (mayor.menor)
            user_parts = [int(p) for p in self.policies_version.split('.')]
            current_parts = [int(p) for p in current_version.split('.')]
            
            # Asegurarse de que ambas tengan al menos dos componentes
            while len(user_parts) < 2:
                user_parts.append(0)
            while len(current_parts) < 2:
                current_parts.append(0)
            
            # Comparar componente principal (1.x vs 2.x)
            # Solo pedir actualización si cambia el número principal
            if current_parts[0] > user_parts[0]:
                return True
                
            # Por defecto, no pedir actualización para cambios menores
            return False
            
        except (ValueError, IndexError):
            # Si hay error al procesar versiones, ser conservador y pedir actualización
            return True
            
    def reset_policy_acceptance(self):
        """
        Resetea el estado de aceptación de políticas para forzar una nueva aceptación
        """
        self.policies_accepted = False
        self.waiting_policy_acceptance = False
        # Guardar mensaje pendiente si existe
        self.save()
        
        return True

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    feedback_requested = models.BooleanField(default=False)
    analysis_results_json = models.TextField(
        blank=True, 
        null=True,
        help_text="Resultados del análisis de la conversación (JSON)"
    )
    
    @property
    def analysis_results(self):
        """Obtiene los resultados del análisis como diccionario"""
        if not self.analysis_results_json:
            return None
        try:
            return json.loads(self.analysis_results_json)
        except:
            return None
        
    @analysis_results.setter
    def analysis_results(self, value):
        """Guarda los resultados del análisis como JSON"""
        if value is None:
            self.analysis_results_json = None
        else:
            self.analysis_results_json = json.dumps(value)

    def end_session(self):
        """End the session"""
        from django.utils import timezone
        self.ended_at = timezone.now()
        self.save()
    
    def __str__(self):
        status = "Activa" if self.ended_at is None else "Finalizada"
        return f"Sesión {status} - {self.user.whatsapp_number} con {self.company.name}"
    
    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Sessions"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='messages')
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    message_text = models.TextField()
    is_from_user = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Añadir el campo message_type según la migración 0012
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Texto'),
            ('audio', 'Audio'),
            ('image', 'Imagen'),
            ('location', 'Ubicación'),
            ('interactive', 'Interactivo')
        ],
        default='text'
    )
    
    def get_direction(self):
        return "Usuario → Bot" if self.is_from_user else "Bot → Usuario"
    
    def short_text(self, length=30):
        if len(self.message_text) > length:
            return f"{self.message_text[:length]}..."
        return self.message_text
    
    def __str__(self):
        return f"{self.get_direction()}: {self.short_text()}"
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']
        
# Añadir la función audio_file_path según la migración 0011
def audio_file_path(instance, filename):
    """Genera la ruta para guardar el archivo de audio"""
    # Guardar en estructura: media/audios/[company_id]/[date]/[filename]
    company_id = instance.message.company.id if instance.message and instance.message.company else 'unknown'
    date_path = instance.created_at.strftime('%Y/%m/%d')
    return f'audios/{company_id}/{date_path}/{filename}'

class AudioMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey('Message', on_delete=models.CASCADE, related_name='audio_messages')
    audio_file = models.FileField(upload_to=audio_file_path, null=True, blank=True)
    audio_duration = models.FloatField(null=True, blank=True)
    transcription = models.TextField(blank=True, null=True)
    transcription_model = models.CharField(max_length=100, blank=True, null=True)
    confidence_score = models.FloatField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('processing', 'Procesando'),
            ('completed', 'Completado'),
            ('failed', 'Fallido'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Audio {self.id} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Audio Message"
        verbose_name_plural = "Audio Messages"

class UserCompanyInteraction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_interactions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='user_interactions')
    first_interaction = models.DateTimeField(auto_now_add=True)
    last_interaction = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'company')
        verbose_name = "User-Company Interaction"
        verbose_name_plural = "User-Company Interactions"
    
    def __str__(self):
        return f"{self.user.name or self.user.whatsapp_number} - {self.company.name}"

class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='feedback')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='feedbacks')
    rating = models.CharField(max_length=10, choices=[
        ('positive', 'Positivo'),
        ('negative', 'Negativo'),
        ('neutral', 'Neutral')
    ])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Feedback de {self.user.name or self.whatsapp_number} - {self.get_rating_display()}"
    
    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"

class PolicyVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    privacy_policy_text = models.TextField()
    terms_text = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Políticas v{self.version}" + (" [Activa]" if self.active else "")
    
    class Meta:
        verbose_name = "Policy Version"
        verbose_name_plural = "Policy Versions"

class PolicyAcceptance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='policy_acceptances')
    policy_version = models.ForeignKey(PolicyVersion, on_delete=models.PROTECT, related_name='acceptances')
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user} aceptó v{self.policy_version.version} el {self.accepted_at.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Policy Acceptance"
        verbose_name_plural = "Policy Acceptances"
        ordering = ['-accepted_at']

class LeadStatistics(Session):
    class Meta:
        proxy = True
        verbose_name = 'Lead Statistics'
        verbose_name_plural = 'Lead Statistics'