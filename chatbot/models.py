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
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    whatsapp_number = models.CharField(max_length=20)
    name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name or 'Unnamed'} ({self.whatsapp_number})"

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Session {self.id} - {self.company.name} with {self.user}"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message_text = models.TextField()
    is_from_user = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        direction = "User → Bot" if self.is_from_user else "Bot → User"
        return f"{direction}: {self.message_text[:30]}{'...' if len(self.message_text) > 30 else ''}"
