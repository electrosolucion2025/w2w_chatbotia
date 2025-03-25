import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from ..models import OpenAIUsageRecord, OpenAIMonthlySummary, Company

logger = logging.getLogger(__name__)

class OpenAIMetricsService:
    """Servicio para gestionar métricas de uso de OpenAI"""
    
    def record_api_usage(self, company, session, response_data):
        """
        Registra el uso de la API de OpenAI a partir de la respuesta directa de la API
        
        Args:
            company: Objeto Company
            session: Objeto Session opcional
            response_data: La respuesta completa de la API de OpenAI
        """
        try:
            # Agregar más logs para depuración
            logger.info(f"Intentando registrar uso de API para: {company.name}")
            logger.info(f"Datos de respuesta: {response_data}")
            
            # Validar que tenemos datos de uso
            if not response_data or not isinstance(response_data, dict) or 'usage' not in response_data:
                logger.warning(f"No se encontraron datos de uso en la respuesta de OpenAI: {response_data}")
                return False
            
            usage = response_data['usage']
            model = response_data.get('model', 'gpt-4o-mini')
            
            # Mostrar información detallada de lo que vamos a registrar
            logger.info(f"Registrando uso: Modelo={model}, Tokens={usage.get('total_tokens', 0)}")
            
            # Import at function level to avoid circular imports
            from ..models import OpenAIUsageRecord
            
            # Crear registro de uso
            record = OpenAIUsageRecord(
                company=company,
                session=session,
                model=model,
                tokens_input=usage.get('prompt_tokens', 0),
                tokens_output=usage.get('completion_tokens', 0),
                tokens_total=usage.get('total_tokens', 0),
                cached_request=False,  # Por defecto asumimos que no es cacheado
                timestamp=timezone.now()
            )
            
            # Calcular costos antes de guardar
            self._calculate_costs(record)
            
            # Guardar explícitamente
            record.save()
            
            logger.info(f"✅ Registro de uso guardado exitosamente: {company.name}, {record.tokens_total} tokens, ${record.cost_total}")
            return record
            
        except Exception as e:
            logger.error(f"❌ Error al registrar uso de OpenAI: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _calculate_costs(self, record):
        """Calcula los costos para un registro de uso"""
        try:
            # GPT-4o-mini precios: $0.50/1M tokens (input), $1.50/1M tokens (output)
            # Todos los precios en dólares americanos (USD)
            
            # Calcular costo en dólares
            if record.model == 'gpt-4o-mini':
                # GPT-4o-mini precios
                input_rate = Decimal('0.5') / Decimal('1000000')  # $0.5 por millón de tokens
                output_rate = Decimal('1.5') / Decimal('1000000') # $1.5 por millón de tokens
            elif record.model == 'gpt-4':
                # GPT-4 precios
                input_rate = Decimal('10.0') / Decimal('1000000')  # $10 por millón de tokens
                output_rate = Decimal('30.0') / Decimal('1000000') # $30 por millón de tokens
            elif record.model == 'gpt-4o':
                # GPT-4o precios
                input_rate = Decimal('5.0') / Decimal('1000000')   # $5 por millón de tokens
                output_rate = Decimal('15.0') / Decimal('1000000') # $15 por millón de tokens
            else:
                # Default para modelos no especificados
                input_rate = Decimal('0.5') / Decimal('1000000')   # $0.5 por millón de tokens
                output_rate = Decimal('1.5') / Decimal('1000000')  # $1.5 por millón de tokens
                
            # Si es una solicitud cacheada, aplicamos una tarifa reducida (ej: 10% del costo normal)
            if record.cached_request:
                input_rate *= Decimal('0.1')
                output_rate *= Decimal('0.1')
                
            # Calcular costos individuales
            record.cost_input = Decimal(record.tokens_input) * input_rate
            record.cost_output = Decimal(record.tokens_output) * output_rate
            record.cost_total = record.cost_input + record.cost_output
            
            return True
        except Exception as e:
            logger.error(f"Error al calcular costos: {e}")
            return False
    
    def record_cached_usage(self, company, session, tokens_input, tokens_output, tokens_total):
        """
        Registra uso de caché (sin llamada a API real)
        
        Args:
            company: Objeto Company
            session: Objeto Session opcional
            tokens_*: Contadores de tokens
        """
        try:
            # Import at function level to avoid circular imports
            from ..models import OpenAIUsageRecord
            
            # Crear registro de uso para caché
            record = OpenAIUsageRecord(
                company=company,
                session=session,
                model='gpt-4o-mini',  # O el modelo que uses por defecto
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                tokens_total=tokens_total,
                cached_request=True,
                timestamp=timezone.now()
            )
            
            # Calcular costos
            self._calculate_costs(record)
            
            # Guardar
            record.save()
            
            logger.info(f"Registro de uso cacheado: {company.name}, {tokens_total} tokens")
            return record
            
        except Exception as e:
            logger.error(f"Error al registrar uso cacheado: {e}")
            return None
    
    @transaction.atomic
    def generate_monthly_summary(self, year=None, month=None, company=None):
        """
        Genera o actualiza resúmenes mensuales para una o todas las empresas
        """
        try:
            # Import at function level to avoid circular imports
            from ..models import OpenAIUsageRecord, OpenAIMonthlySummary
            
            # Definir período
            current_date = timezone.now().date()
            year = year or current_date.year
            month = month or current_date.month
            
            # Definir compañías a procesar
            companies = [company] if company else Company.objects.filter(active=True)
            
            # Para cada compañía, generar o actualizar su resumen mensual
            for company in companies:
                logger.info(f"Generando resumen mensual para {company.name}, {month}/{year}")
                
                # Obtener todos los registros de uso del mes para esta empresa
                usage_records = OpenAIUsageRecord.objects.filter(
                    company=company,
                    timestamp__year=year,
                    timestamp__month=month
                )
                
                # Contar registros para depuración
                record_count = usage_records.count()
                logger.info(f"Encontrados {record_count} registros para {company.name} en {month}/{year}")
                
                # Agregar métricas
                aggregated = usage_records.aggregate(
                    total_requests=Count('id'),
                    total_tokens_input=Sum('tokens_input'),
                    total_tokens_output=Sum('tokens_output'),
                    total_tokens=Sum('tokens_total'),
                    total_cost_input=Sum('cost_input'),
                    total_cost_output=Sum('cost_output'),
                    total_cost=Sum('cost_total')
                )
                
                # Manejar caso de no haber registros
                if not aggregated['total_requests']:
                    logger.info(f"No hay registros para {company.name} en {month}/{year}")
                    continue
                
                # Crear o actualizar resumen mensual
                summary, created = OpenAIMonthlySummary.objects.update_or_create(
                    company=company,
                    year=year,
                    month=month,
                    defaults={
                        'total_requests': aggregated['total_requests'] or 0,
                        'total_tokens_input': aggregated['total_tokens_input'] or 0,
                        'total_tokens_output': aggregated['total_tokens_output'] or 0,
                        'total_tokens': aggregated['total_tokens'] or 0,
                        'total_cost_input': aggregated['total_cost_input'] or 0,
                        'total_cost_output': aggregated['total_cost_output'] or 0,
                        'total_cost': aggregated['total_cost'] or 0,
                    }
                )
                
                action = "Creado" if created else "Actualizado"
                logger.info(f"{action} resumen mensual para {company.name}, {month}/{year}: {summary.total_tokens} tokens, ${summary.total_cost}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error al generar resumen mensual: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
    def get_company_usage(self, company, start_date=None, end_date=None):
        """
        Obtiene estadísticas de uso para una empresa en un período
        """
        try:
            # Import at function level to avoid circular imports
            from ..models import OpenAIUsageRecord
            
            # Definir período
            today = timezone.now().date()
            
            if not start_date:
                # Por defecto, primer día del mes actual
                start_date = today.replace(day=1)
                
            if not end_date:
                end_date = today
                
            # Generamos una clave de caché única para estos parámetros
            cache_key = f"company_usage_{company.id}_{start_date}_{end_date}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
                
            # Obtener registros en el período
            usage_records = OpenAIUsageRecord.objects.filter(
                company=company,
                timestamp__date__range=(start_date, end_date)
            )
            
            # Agregar métricas
            stats = usage_records.aggregate(
                total_requests=Count('id'),
                total_tokens_input=Sum('tokens_input'),
                total_tokens_output=Sum('tokens_output'),
                total_tokens=Sum('tokens_total'),
                cached_requests=Count('id', filter=Q(cached_request=True)),
                total_cost=Sum('cost_total')
            )
            
            # Manejar caso de no haber registros
            if not stats['total_requests']:
                return {
                    'total_requests': 0,
                    'total_tokens_input': 0,
                    'total_tokens_output': 0,
                    'total_tokens': 0,
                    'cached_requests': 0,
                    'cached_percent': 0,
                    'total_cost': 0,
                    'start_date': start_date,
                    'end_date': end_date,
                    'days': (end_date - start_date).days + 1,
                    'daily_avg_tokens': 0,
                    'daily_avg_cost': 0
                }
            
            # Calcular porcentajes y promedios
            days_count = (end_date - start_date).days + 1
            cached_percent = (stats['cached_requests'] / stats['total_requests']) * 100 if stats['total_requests'] > 0 else 0
            daily_avg_tokens = stats['total_tokens'] / days_count if stats['total_tokens'] else 0
            daily_avg_cost = stats['total_cost'] / days_count if stats['total_cost'] else 0
            
            # Preparar resultado
            result = {
                'total_requests': stats['total_requests'] or 0,
                'total_tokens_input': stats['total_tokens_input'] or 0,
                'total_tokens_output': stats['total_tokens_output'] or 0,
                'total_tokens': stats['total_tokens'] or 0,
                'cached_requests': stats['cached_requests'] or 0,
                'cached_percent': round(cached_percent, 2),
                'total_cost': stats['total_cost'] or 0,
                'start_date': start_date,
                'end_date': end_date,
                'days': days_count,
                'daily_avg_tokens': int(daily_avg_tokens),
                'daily_avg_cost': daily_avg_cost
            }
            
            # Guardar en caché por 15 minutos
            cache.set(cache_key, result, 60*15)
            
            return result
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de uso: {e}")
            return {'error': str(e)}
            
    def get_daily_usage_data(self, company, days=30):
        """
        Obtiene datos de uso diario para visualizaciones
        """
        try:
            # Import at function level to avoid circular imports
            from ..models import OpenAIUsageRecord
            from django.db.models.functions import TruncDate
            
            # Definir período
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days-1)
            
            # Generar clave de caché
            cache_key = f"daily_usage_{company.id}_{days}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
                
            # Preparar array de días para el período
            date_range = []
            current_date = start_date
            while current_date <= end_date:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            # Consulta para agrupar por día
            daily_data = OpenAIUsageRecord.objects.filter(
                company=company,
                timestamp__date__range=(start_date, end_date)
            ).annotate(
                day=TruncDate('timestamp')
            ).values('day').annotate(
                tokens=Sum('tokens_total'),
                cost=Sum('cost_total'),
                requests=Count('id')
            ).order_by('day')
            
            # Convertir a diccionario para acceso rápido
            daily_dict = {item['day']: item for item in daily_data}
            
            # Construir resultado con todos los días del período
            result = []
            for day in date_range:
                data = daily_dict.get(day, {})
                result.append({
                    'date': day,
                    'tokens': data.get('tokens', 0),
                    'cost': float(data.get('cost', 0)),
                    'requests': data.get('requests', 0),
                })
            
            # Guardar en caché por 15 minutos
            cache.set(cache_key, result, 60*15)
                
            return result
            
        except Exception as e:
            logger.error(f"Error al obtener datos de uso diario: {e}")
            return []