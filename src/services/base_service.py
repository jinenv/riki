# src/services/base_service.py
from typing import TypeVar, Generic, Any, Dict, Optional
from dataclasses import dataclass
from abc import ABC
import traceback

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class ServiceResult(Generic[T]):
    """Standardized service response wrapper"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    
    @classmethod
    def success_result(cls, data: T) -> 'ServiceResult[T]':
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str, error_code: str = None) -> 'ServiceResult[T]':
        return cls(success=False, error=error, error_code=error_code)

class BaseService(ABC):
    """Base class for all services with common patterns"""
    
    @classmethod
    async def _safe_execute(cls, operation, operation_name: str) -> ServiceResult[Any]:
        """Execute operation with standardized error handling"""
        try:
            result = await operation()
            return ServiceResult.success_result(result)
        
        except ValueError as e:
            # User input errors - don't log stack trace
            logger.warning(f"{operation_name} failed: {str(e)}")
            return ServiceResult.error_result(str(e), "VALIDATION_ERROR")
        
        except PermissionError as e:
            # Authorization errors
            logger.warning(f"{operation_name} permission denied: {str(e)}")
            return ServiceResult.error_result("Permission denied", "PERMISSION_ERROR")
        
        except Exception as e:
            # Unexpected errors - log full context
            logger.error(f"{operation_name} unexpected error: {str(e)}", exc_info=True)
            return ServiceResult.error_result(
                "An unexpected error occurred", 
                "INTERNAL_ERROR"
            )
    
    @classmethod
    def _validate_player_id(cls, player_id: int) -> None:
        """Validate player ID parameter"""
        if not isinstance(player_id, int) or player_id <= 0:
            raise ValueError("Invalid player ID")
    
    @classmethod
    def _validate_positive_amount(cls, amount: int, field_name: str = "amount") -> None:
        """Validate positive integer amounts"""
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
    
    @classmethod
    def _validate_non_negative_amount(cls, amount: int, field_name: str = "amount") -> None:
        """Validate non-negative integer amounts"""
        if not isinstance(amount, int) or amount < 0:
            raise ValueError(f"{field_name} must be non-negative")