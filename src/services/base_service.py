from typing import TypeVar, Generic, Any, Dict, Optional, List
from dataclasses import dataclass
from abc import ABC
import traceback
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class ServiceResult(Generic[T]):
    """Standardized service response wrapper"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    
    @classmethod
    def success_result(cls, data: T, message: str = None) -> 'ServiceResult[T]':
        return cls(success=True, data=data, message=message)
    
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
            logger.warning(f"{operation_name} failed: {str(e)}")
            return ServiceResult.error_result(str(e), "VALIDATION_ERROR")
        
        except PermissionError as e:
            logger.warning(f"{operation_name} permission denied: {str(e)}")
            return ServiceResult.error_result("Permission denied", "PERMISSION_ERROR")
        
        except ResourceError as e:
            logger.info(f"{operation_name} resource error: {str(e)}")
            return ServiceResult.error_result(str(e), "INSUFFICIENT_RESOURCES")
        
        except Exception as e:
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
    
    @classmethod
    def _validate_string_choice(cls, value: str, choices: List[str], field_name: str) -> None:
        """Validate string is in allowed choices"""
        if value not in choices:
            raise ValueError(f"{field_name} must be one of: {', '.join(choices)}")
    
    @classmethod
    def _validate_tier(cls, tier: int) -> None:
        """Validate maiden tier is within allowed range"""
        max_tier = ConfigManager.get("fusion.max_tier", 12)
        if not isinstance(tier, int) or tier < 1 or tier > max_tier:
            raise ValueError(f"Tier must be between 1 and {max_tier}")
    
    @classmethod
    def _validate_cost(cls, cost: Dict[str, int]) -> None:
        """Validate resource cost dictionary"""
        valid_resources = ["rikies", "grace", "shards", "energy", "stamina"]
        for resource, amount in cost.items():
            if resource not in valid_resources:
                raise ValueError(f"Invalid resource type: {resource}")
            cls._validate_non_negative_amount(amount, resource)

# Custom Exceptions
class ResourceError(Exception):
    """Raised when player has insufficient resources"""
    pass

class PlayerNotFoundError(Exception):
    """Raised when player doesn't exist"""
    pass

class InvalidStateError(Exception):
    """Raised when operation is invalid for current state"""
    pass