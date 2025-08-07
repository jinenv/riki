# src/utils/transaction_logger.py
import json
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict

from src.utils.logger import get_logger

logger = get_logger(__name__)

class TransactionType(str, Enum):
    """Transaction types for audit trail"""
    # Currency Operations
    CURRENCY_GAIN = "currency_gain"
    CURRENCY_SPEND = "currency_spend"
    
    # Resource Operations  
    RESOURCE_CONSUME = "resource_consume"
    RESOURCE_REGEN = "resource_regen"
    
    # Esprit Operations
    ESPRIT_SUMMONED = "esprit_summoned"
    ESPRIT_FUSED = "esprit_fused"
    
    # Tower Operations
    FLOOR_CLEARED = "floor_cleared"
    FLOOR_ATTEMPT_FAILED = "floor_attempt_failed"
    TOWER_RAID = "tower_raid"
    
    # Player Operations
    PLAYER_CREATED = "player_created"
    LEVEL_GAINED = "level_gained"
    
    # System Operations
    SYSTEM_ACTION = "system_action"
    ERROR_OCCURRED = "error_occurred"

@dataclass
class Transaction:
    """Transaction record structure"""
    timestamp: datetime
    player_id: int
    transaction_type: TransactionType
    data: Dict[str, Any]
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['transaction_type'] = self.transaction_type.value
        return result

class TransactionLogger:
    """Centralized transaction logging system"""
    
    def __init__(self):
        self._log_to_file = True
        self._log_to_console = False
    
    def log_transaction(
        self, 
        player_id: int, 
        transaction_type: TransactionType, 
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """Log a transaction with full audit trail"""
        transaction = Transaction(
            timestamp=datetime.utcnow(),
            player_id=player_id,
            transaction_type=transaction_type,
            data=data,
            session_id=session_id
        )
        
        self._write_transaction(transaction)
    
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
    
    def _write_transaction(self, transaction: Transaction) -> None:
        """Write transaction to configured outputs"""
        transaction_dict = transaction.to_dict()
        
        # Log to structured logger
        logger.info(
            f"TRANSACTION: {transaction.transaction_type.value}",
            extra={
                "transaction": transaction_dict,
                "player_id": transaction.player_id,
                "transaction_type": transaction.transaction_type.value
            }
        )
        
        # Optional: Log to console for debugging
        if self._log_to_console:
            print(f"[TRANSACTION] {json.dumps(transaction_dict, indent=2)}")
    
    def create_audit_summary(
        self, 
        player_id: int, 
        transaction_types: Optional[list] = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """Create audit summary for player (placeholder for future DB implementation)"""
        # This would query a transaction database in a full implementation
        # For MVP, we rely on log analysis
        return {
            "player_id": player_id,
            "summary_period_hours": hours_back,
            "transaction_types": transaction_types,
            "note": "Full audit querying requires database transaction storage"
        }

# Global transaction logger instance
transaction_logger = TransactionLogger()