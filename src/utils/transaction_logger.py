import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict

from src.utils.logger import get_logger

logger = get_logger(__name__)

class TransactionType(str, Enum):
    """Transaction types for RIKI audit trail"""
    
    # Player Operations
    PLAYER_CREATED = "player_created"
    PLAYER_DELETED = "player_deleted"
    LEVEL_GAINED = "level_gained"
    EXPERIENCE_GAINED = "experience_gained"
    
    # Currency Operations (Rikies, Grace, Shards)
    RIKIES_GAINED = "rikies_gained"
    RIKIES_SPENT = "rikies_spent"
    GRACE_GAINED = "grace_gained"
    GRACE_SPENT = "grace_spent"
    SHARDS_GAINED = "shards_gained"
    SHARDS_SPENT = "shards_spent"
    
    # Resource Operations (Energy, Stamina)
    ENERGY_CONSUMED = "energy_consumed"
    ENERGY_REGENERATED = "energy_regenerated"
    STAMINA_CONSUMED = "stamina_consumed"
    STAMINA_REGENERATED = "stamina_regenerated"
    RESOURCES_REFRESHED = "resources_refreshed"  # Level up refresh
    
    # Maiden Operations
    MAIDEN_SUMMONED = "maiden_summoned"
    MAIDEN_FUSED = "maiden_fused"
    MAIDEN_STACKED = "maiden_stacked"
    TUTORIAL_MAIDEN_GRANTED = "tutorial_maiden_granted"
    
    # Prayer Operations
    PRAYER_EXECUTED = "prayer_executed"
    PRAYER_COOLDOWN_RESET = "prayer_cooldown_reset"
    
    # Skill Point Operations
    SKILL_POINTS_ALLOCATED = "skill_points_allocated"
    SKILL_POINTS_RESET = "skill_points_reset"
    
    # Zone/Exploration Operations
    ZONE_EXPLORED = "zone_explored"
    ZONE_COMPLETED = "zone_completed"
    SUBZONE_UNLOCKED = "subzone_unlocked"
    ENCOUNTER_COMPLETED = "encounter_completed"
    
    # Combat Operations
    BOSS_CHALLENGED = "boss_challenged"
    BOSS_DEFEATED = "boss_defeated"
    COMBAT_VICTORY = "combat_victory"
    COMBAT_DEFEAT = "combat_defeat"
    
    # Tutorial Operations
    TUTORIAL_STARTED = "tutorial_started"
    TUTORIAL_STEP_COMPLETED = "tutorial_step_completed"
    TUTORIAL_COMPLETED = "tutorial_completed"
    TUTORIAL_SKIPPED = "tutorial_skipped"
    
    # System Operations
    SYSTEM_ACTION = "system_action"
    CACHE_INVALIDATED = "cache_invalidated"
    ERROR_OCCURRED = "error_occurred"
    ROLLBACK_EXECUTED = "rollback_executed"
    
    # Bulk Operations
    BULK_OPERATION = "bulk_operation"
    ADMIN_ACTION = "admin_action"

@dataclass
class Transaction:
    """Transaction record structure"""
    timestamp: datetime
    player_id: int
    transaction_type: TransactionType
    data: Dict[str, Any]
    session_id: Optional[str] = None
    context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['transaction_type'] = self.transaction_type.value
        return result

class TransactionLogger:
    """Centralized transaction logging system for RIKI"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._log_to_file = True
            self._log_to_console = False
            self._buffer: List[Transaction] = []
            self._buffer_size = 100
            self._initialized = True
    
    def log_transaction(
        self, 
        player_id: int, 
        transaction_type: TransactionType, 
        data: Dict[str, Any],
        context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """Log a transaction with full audit trail"""
        transaction = Transaction(
            timestamp=datetime.utcnow(),
            player_id=player_id,
            transaction_type=transaction_type,
            data=data,
            context=context,
            session_id=session_id
        )
        
        self._write_transaction(transaction)
        self._add_to_buffer(transaction)
    
    def log_currency_change(
        self,
        player_id: int,
        currency_type: str,
        old_value: int,
        new_value: int,
        change: int,
        context: str
    ) -> None:
        """Specialized logging for currency changes"""
        if change > 0:
            transaction_type = getattr(TransactionType, f"{currency_type.upper()}_GAINED")
        else:
            transaction_type = getattr(TransactionType, f"{currency_type.upper()}_SPENT")
        
        self.log_transaction(
            player_id=player_id,
            transaction_type=transaction_type,
            data={
                "old_value": old_value,
                "new_value": new_value,
                "change": abs(change),
                "context": context
            },
            context=context
        )
    
    def log_resource_change(
        self,
        player_id: int,
        resource_type: str,
        old_value: int,
        new_value: int,
        change: int,
        context: str
    ) -> None:
        """Specialized logging for resource changes"""
        if change < 0:
            transaction_type = getattr(TransactionType, f"{resource_type.upper()}_CONSUMED")
        else:
            transaction_type = getattr(TransactionType, f"{resource_type.upper()}_REGENERATED")
        
        self.log_transaction(
            player_id=player_id,
            transaction_type=transaction_type,
            data={
                "old_value": old_value,
                "new_value": new_value,
                "change": abs(change),
                "context": context
            },
            context=context
        )
    
    def log_maiden_operation(
        self,
        player_id: int,
        operation: str,
        maiden_data: Dict[str, Any],
        context: str = None
    ) -> None:
        """Specialized logging for maiden operations"""
        transaction_map = {
            "summon": TransactionType.MAIDEN_SUMMONED,
            "fusion": TransactionType.MAIDEN_FUSED,
            "stack": TransactionType.MAIDEN_STACKED
        }
        
        self.log_transaction(
            player_id=player_id,
            transaction_type=transaction_map.get(operation, TransactionType.SYSTEM_ACTION),
            data=maiden_data,
            context=context
        )
    
    def log_system_action(self, action: str, data: Dict[str, Any]) -> None:
        """Log system-level actions without player context"""
        transaction = Transaction(
            timestamp=datetime.utcnow(),
            player_id=0,  # System actions use player_id 0
            transaction_type=TransactionType.SYSTEM_ACTION,
            data={"action": action, **data}
        )
        
        self._write_transaction(transaction)
    
    def log_error(
        self, 
        player_id: int, 
        error_type: str, 
        error_message: str,
        context: Dict[str, Any] = None
    ) -> None:
        """Log error events for debugging"""
        transaction = Transaction(
            timestamp=datetime.utcnow(),
            player_id=player_id,
            transaction_type=TransactionType.ERROR_OCCURRED,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "context": context or {}
            }
        )
        
        self._write_transaction(transaction)
    
    def log_bulk_operation(
        self,
        admin_id: int,
        operation_type: str,
        affected_players: List[int],
        results: Dict[str, Any]
    ) -> None:
        """Log bulk administrative operations"""
        self.log_transaction(
            player_id=0,  # System level
            transaction_type=TransactionType.BULK_OPERATION,
            data={
                "admin_id": admin_id,
                "operation_type": operation_type,
                "affected_players": affected_players,
                "affected_count": len(affected_players),
                "results": results
            }
        )
    
    def _write_transaction(self, transaction: Transaction) -> None:
        """Write transaction to configured outputs"""
        transaction_dict = transaction.to_dict()
        
        # Log to structured logger
        logger.info(
            f"TRANSACTION: {transaction.transaction_type.value}",
            extra={
                "transaction": transaction_dict,
                "player_id": transaction.player_id,
                "transaction_type": transaction.transaction_type.value,
                "context": transaction.context
            }
        )
        
        # Optional: Log to console for debugging
        if self._log_to_console:
            print(f"[TRANSACTION] {json.dumps(transaction_dict, indent=2)}")
    
    def _add_to_buffer(self, transaction: Transaction) -> None:
        """Add transaction to buffer for batch processing"""
        self._buffer.append(transaction)
        
        if len(self._buffer) >= self._buffer_size:
            self.flush_buffer()
    
    def flush_buffer(self) -> None:
        """Flush transaction buffer (for future DB implementation)"""
        if self._buffer:
            logger.debug(f"Flushing {len(self._buffer)} transactions")
            self._buffer.clear()
    
    def create_audit_summary(
        self, 
        player_id: int, 
        transaction_types: Optional[List[TransactionType]] = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """Create audit summary for player (placeholder for future DB implementation)"""
        return {
            "player_id": player_id,
            "summary_period_hours": hours_back,
            "transaction_types": transaction_types,
            "note": "Full audit querying requires database transaction storage",
            "buffer_size": len(self._buffer)
        }

# Global transaction logger instance
transaction_logger = TransactionLogger()