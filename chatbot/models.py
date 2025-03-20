import uuid
from django.db import models

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
    whatsapp_number = models.CharField(max_length=20)
    name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name or 'Unnamed'} ({self.whatsapp_number})"
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    feedback_requested = models.BooleanField(default=False)
    
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
        return f"Feedback de {self.user.name or self.user.whatsapp_number} - {self.get_rating_display()}"
    
    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"