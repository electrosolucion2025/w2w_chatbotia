import logging
from ..models import PolicyVersion, User

logger = logging.getLogger(__name__)

class PolicyService:
    def get_active_policy(self):
        """
        Obtiene la política activa actual
        
        Returns:
            PolicyVersion: La política activa o None si no existe
        """
        return PolicyVersion.objects.filter(active=True).first()
    
    def check_policy_acceptance(self, user, current_policy=None):
        """
        Verifica si el usuario tiene aceptada la política actual
        
        Args:
            user: El usuario a verificar
            current_policy: La política actual (opcional, se buscará si no se proporciona)
            
        Returns:
            dict: Estado de aceptación y acción requerida
        """
        if current_policy is None:
            current_policy = self.get_active_policy()
            
        if not current_policy:
            # No hay políticas definidas, ignorar verificación
            return {
                "accepted": True,  # Consideramos aceptado si no hay política
                "action_required": False,
                "reason": "no_policy_defined"
            }
        
        # Si nunca ha aceptado políticas
        if not user.policies_accepted:
            return {
                "accepted": False,
                "action_required": True,
                "reason": "never_accepted",
                "policy": current_policy
            }
        
        # Verificar si necesita actualizar
        if user.needs_policy_update(current_policy.version):
            return {
                "accepted": False,
                "action_required": True,
                "reason": "version_outdated",
                "policy": current_policy,
                "user_version": user.policies_version,
                "current_version": current_policy.version
            }
            
        # Todo está en orden
        return {
            "accepted": True,
            "action_required": False,
            "reason": "up_to_date",
            "policy": current_policy
        }
    
    def record_policy_acceptance(self, user, policy_version, ip_address=None, user_agent=None):
        """
        Registra la aceptación de una política por parte de un usuario
        
        Args:
            user: Usuario que acepta
            policy_version: Versión de la política aceptada
            ip_address: Dirección IP (opcional)
            user_agent: User agent (opcional)
            
        Returns:
            bool: True si se registró correctamente
        """
        from django.utils import timezone
        
        try:
            # Actualizar usuario
            user.policies_accepted = True
            user.policies_accepted_date = timezone.now()
            user.policies_version = policy_version.version if hasattr(policy_version, 'version') else policy_version
            user.waiting_policy_acceptance = False
            user.save()
            
            # Intenta crear registro histórico si existe el modelo PolicyAcceptance
            try:
                from ..models import PolicyAcceptance
                
                # Buscar la política si solo se proporcionó la versión
                policy_obj = policy_version
                if isinstance(policy_version, str):
                    policy_obj = PolicyVersion.objects.filter(version=policy_version).first()
                    
                if policy_obj and hasattr(policy_obj, 'id'):
                    PolicyAcceptance.objects.create(
                        user=user,
                        policy_version=policy_obj,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
            except (ImportError, AttributeError):
                logger.warning("No se pudo guardar el historial de aceptación: el modelo PolicyAcceptance no está disponible")
                
            return True
            
        except Exception as e:
            logger.error(f"Error al registrar aceptación de políticas: {e}")
            return False