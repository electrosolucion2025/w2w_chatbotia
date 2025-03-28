import uuid
from django.db import models
from django.utils import timezone
import json
from django.contrib.auth.models import User as DjangoUser

class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Nombre de la empresa")
    
    # Configuración WhatsApp
    phone_number = models.CharField(max_length=20, unique=True)
    whatsapp_api_token = models.CharField(max_length=500, blank=True, null=True)
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Información fiscal y legal
    tax_id = models.CharField(max_length=20, blank=True, null=True, verbose_name="NIF/CIF")
    legal_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Razón social")
    
    # Contacto empresa
    contact_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Persona de contacto")
    contact_email = models.EmailField(blank=True, null=True, verbose_name="Email de contacto")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de contacto")
    
    # Dirección
    address_line1 = models.CharField(max_length=150, blank=True, null=True, verbose_name="Dirección")
    address_line2 = models.CharField(max_length=150, blank=True, null=True, verbose_name="Complemento dirección")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ciudad")
    postal_code = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código postal")
    state = models.CharField(max_length=100, blank=True, null=True, verbose_name="Provincia")
    country = models.CharField(max_length=100, blank=True, null=True, verbose_name="País", default="España")
    
    # Redes sociales y web
    website = models.URLField(blank=True, null=True, verbose_name="Sitio web")
    facebook = models.URLField(blank=True, null=True, verbose_name="Facebook")
    instagram = models.URLField(blank=True, null=True, verbose_name="Instagram")
    twitter = models.URLField(blank=True, null=True, verbose_name="Twitter")
    linkedin = models.URLField(blank=True, null=True, verbose_name="LinkedIn")
    
    # Información de negocio
    business_category = models.CharField(max_length=100, blank=True, null=True, verbose_name="Categoría de negocio")
    business_description = models.TextField(blank=True, null=True, verbose_name="Descripción del negocio")
    founding_year = models.PositiveIntegerField(blank=True, null=True, verbose_name="Año de fundación")
    employee_count = models.PositiveIntegerField(blank=True, null=True, verbose_name="Número de empleados")
    
    # Campos administrativos
    active = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    subscription_plan = models.CharField(max_length=50, blank=True, null=True, verbose_name="Plan de suscripción", default="standard")
    subscription_end_date = models.DateField(blank=True, null=True, verbose_name="Fecha fin suscripción")
    
    # Logo e imágenes
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True, verbose_name="Logo")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['name']
        
    def save(self, *args, **kwargs):
        # Si es una nueva compañía sin fecha de suscripción, establecer por defecto a 1 mes
        if not self.pk and not self.subscription_end_date:
            from datetime import date, timedelta
            self.subscription_end_date = date.today() + timedelta(days=30)
        super().save(*args, **kwargs)

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
    feedback_requested = models.BooleanField(default=False, help_text="Indica si se ha solicitado feedback al usuario")
    feedback_requested_at = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora en que se solicitó el feedback")
    feedback_response = models.CharField(max_length=20, null=True, blank=True, help_text="Tipo de feedback: positive, negative, comment, etc.")
    feedback_received_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo se recibió el feedback")
    feedback_comment_requested = models.BooleanField(default=False, help_text="Indica si se solicitó un comentario adicional")
    feedback_comment = models.TextField(null=True, blank=True, help_text="Comentario adicional proporcionado como feedback")
    farewell_message_sent = models.BooleanField(default=False, help_text="Indica si ya se envió un mensaje de despedida")
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
    rating = models.CharField(max_length=20, choices=[
        ('positive', 'Positivo'),
        ('negative', 'Negativo'),
        ('neutral', 'Neutral'),
        ('comment', 'Comentario'),
        ('comment_requested', 'Comentario Solicitado')
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

class OpenAIUsageRecord(models.Model):
    """
    Modelo para registrar detalladamente el uso de la API de OpenAI por empresa
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='openai_usage_records')
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='openai_usages')
    
    # Detalles de la solicitud
    model = models.CharField(max_length=50, default='gpt-4o-mini')
    
    # Métricas de uso
    tokens_input = models.IntegerField(default=0, verbose_name="Tokens de entrada")
    tokens_output = models.IntegerField(default=0, verbose_name="Tokens de salida")
    tokens_total = models.IntegerField(default=0, verbose_name="Total de tokens")
    cached_request = models.BooleanField(default=False, verbose_name="Solicitud cacheada")
    
    # Costes según especificaciones GPT-4o-mini
    # Input: $0.15/M tokens, Cached Input: $0.075/M tokens, Output: $0.60/M tokens
    cost_input = models.DecimalField(max_digits=10, decimal_places=6, default=0, verbose_name="Coste de entrada ($)")
    cost_output = models.DecimalField(max_digits=10, decimal_places=6, default=0, verbose_name="Coste de salida ($)")
    cost_total = models.DecimalField(max_digits=10, decimal_places=6, default=0, verbose_name="Coste total ($)")
    
    # Metadatos
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Registro de uso de OpenAI"
        verbose_name_plural = "Registros de uso de OpenAI"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.timestamp.strftime('%d/%m/%Y %H:%M')} - {self.tokens_total} tokens"
    
    def save(self, *args, **kwargs):
        """Calcular costos antes de guardar"""
        from decimal import Decimal
        
        # Seleccionar tasas según el modelo
        if self.model == 'gpt-4o-mini':
            # GPT-4o-mini prices (March 2025)
            input_rate = Decimal('0.15') / Decimal('1000000')  # $0.15 per 1M tokens
            output_rate = Decimal('0.60') / Decimal('1000000') # $0.60 per 1M tokens
        elif self.model == 'gpt-4':
            # GPT-4 prices
            input_rate = Decimal('10.0') / Decimal('1000000')  
            output_rate = Decimal('30.0') / Decimal('1000000') 
        elif self.model == 'gpt-4o':
            # GPT-4o prices
            input_rate = Decimal('5.0') / Decimal('1000000')   
            output_rate = Decimal('15.0') / Decimal('1000000') 
        else:
            # Default/fallback prices
            input_rate = Decimal('0.15') / Decimal('1000000')  
            output_rate = Decimal('0.60') / Decimal('1000000') 
        
        # Si es una solicitud cacheada, descuento del 50%
        if self.cached_request:
            input_rate = input_rate * Decimal('0.5')
            output_rate = output_rate * Decimal('0.5')
            
        # Calcular costos
        self.cost_input = (Decimal(self.tokens_input) * input_rate).quantize(Decimal('0.000001'))
        self.cost_output = (Decimal(self.tokens_output) * output_rate).quantize(Decimal('0.000001'))
        self.cost_total = self.cost_input + self.cost_output
        
        super().save(*args, **kwargs)

class OpenAIMonthlySummary(models.Model):
    """
    Resumen mensual del uso de OpenAI por empresa
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='openai_monthly_summaries')
    
    # Periodo
    year = models.IntegerField(verbose_name="Año")
    month = models.IntegerField(verbose_name="Mes")  # 1-12
    
    # Totales
    total_requests = models.IntegerField(default=0, verbose_name="Total de solicitudes")
    total_tokens_input = models.IntegerField(default=0, verbose_name="Total tokens de entrada")
    total_tokens_output = models.IntegerField(default=0, verbose_name="Total tokens de salida")
    total_tokens = models.IntegerField(default=0, verbose_name="Total de tokens")
    
    # Costes
    total_cost_input = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Coste total entrada ($)")
    total_cost_output = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Coste total salida ($)")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Coste total ($)")
    
    # Metadatos
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Resumen mensual de OpenAI"
        verbose_name_plural = "Resúmenes mensuales de OpenAI"
        ordering = ['-year', '-month']
        unique_together = ['company', 'year', 'month']
    
    def __str__(self):
        return f"{self.company.name} - {self.month}/{self.year} - ${self.total_cost}"

class LeadStatistics(Session):
    class Meta:
        proxy = True
        verbose_name = 'Lead Statistics'
        verbose_name_plural = 'Lead Statistics'
        
class CompanyAdmin(models.Model):
    """
    Modelo para asociar usuarios administrativos a empresas específicas
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE, related_name='company_admin')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='administrators')
    is_primary = models.BooleanField(default=False, help_text="Indica si es el administrador principal de la empresa")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - Admin de {self.company.name}"
    
    class Meta:
        verbose_name = "Administrador de Empresa"
        verbose_name_plural = "Administradores de Empresas"
        unique_together = ('user', 'company')
        
class TicketCategory(models.Model):
    """Categorías para clasificar tickets (desperfectos, consultas técnicas, etc.)"""
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='ticket_categories')
    prompt_instructions = models.TextField(help_text="Instrucciones que se añaden al prompt cuando se detecta esta categoría")
    ask_for_photos = models.BooleanField(default=False, help_text="Si debe solicitar fotos automáticamente")
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Ticket(models.Model):
    """Modelo para almacenar tickets/incidencias reportadas"""
    STATUS_CHOICES = [
        ('new', 'Nuevo'),
        ('reviewing', 'En revisión'),
        ('in_progress', 'En proceso'),
        ('waiting_info', 'Esperando información'),
        ('resolved', 'Resuelto'),
        ('closed', 'Cerrado'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tickets')
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, related_name='tickets')
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, related_name='tickets')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tickets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.title

class TicketImage(models.Model):
    """Imágenes asociadas a un ticket"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ticket_images/%Y/%m/%d/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    ai_description = models.TextField(blank=True, null=True, help_text="Descripción generada por IA de lo que muestra la imagen")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    whatsapp_media_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        db_index=True
    )
    
    class Meta:
        unique_together = [['ticket', 'whatsapp_media_id']]
    
    def __str__(self):
        return f"Imagen para {self.ticket.title}"

class TicketComment(models.Model):
    """Comentarios y actualizaciones sobre un ticket"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, related_name='ticket_comments')
    is_staff = models.BooleanField(default=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comentario en {self.ticket.title} por {self.author}"
    
class ImageAnalysisPrompt(models.Model):
    """Plantilla de prompt para análisis de imágenes"""
    
    company = models.ForeignKey(
        'Company', 
        on_delete=models.CASCADE,
        related_name='image_prompts',
        help_text="Empresa a la que pertenece este prompt"
    )
    
    category = models.ForeignKey(
        'TicketCategory', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='image_prompts',
        help_text="Categoría específica (opcional)"
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo de este prompt"
    )
    
    prompt_text = models.TextField(
        help_text="Texto del prompt para analizar imágenes"
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text="Indica si es el prompt predeterminado para la empresa"
    )
    
    model = models.CharField(
        max_length=50,
        default="gpt-4o",
        help_text="Modelo de IA a utilizar"
    )
    
    max_tokens = models.IntegerField(
        default=500,
        help_text="Tokens máximos para la respuesta"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['company', 'category', 'is_default']]
        verbose_name = "Prompt de Análisis de Imagen"
        verbose_name_plural = "Prompts de Análisis de Imagen"
        
    def __str__(self):
        if self.category:
            return f"{self.company.name} - {self.category.name}: {self.name}"
        return f"{self.company.name} - Default: {self.name}"
        
    def save(self, *args, **kwargs):
        # Si se marca como default, desmarcar otros defaults para esta combinación
        if self.is_default:
            ImageAnalysisPrompt.objects.filter(
                company=self.company,
                category=self.category,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)