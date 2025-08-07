# src/services/currency_service.py
from typing import Dict, Any, Optional
from sqlalchemy import select
from enum import Enum

from src.services.base_service import BaseService, ServiceResult
from src.database.models.player import Player
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class CurrencyType(str, Enum):
    """Supported currency types"""
    SEIOS = "seios"
    ICHOR = "ichor" 
    ERYTHL = "erythl"

class CurrencyService(BaseService):
    """Universal currency operations for seios, ichor, and erythl"""
    
    @classmethod
    async def add_currency(
        cls, 
        player_id: int, 
        currency_type: CurrencyType, 
        amount: int, 
        source: str = "unknown"
    ) -> ServiceResult[Dict[str, Any]]:
        """Add currency to player account"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Get current amount
                old_amount = getattr(player, currency_type.value)
                
                # Add currency
                new_amount = old_amount + amount
                setattr(player, currency_type.value, new_amount)
                player.update_activity()
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.CURRENCY_GAIN,
                    {
                        "currency_type": currency_type.value,
                        "amount": amount,
                        "old_amount": old_amount,
                        "new_amount": new_amount,
                        "source": source
                    }
                )
                
                return {
                    "currency_type": currency_type.value,
                    "amount_added": amount,
                    "old_amount": old_amount,
                    "new_amount": new_amount,
                    "source": source
                }
        
        return await cls._safe_execute(_operation, f"add {currency_type.value} to player {player_id}")
    
    @classmethod
    async def subtract_currency(
        cls, 
        player_id: int, 
        currency_type: CurrencyType, 
        amount: int, 
        purpose: str = "unknown"
    ) -> ServiceResult[Dict[str, Any]]:
        """Subtract currency from player account with validation"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Get current amount and validate
                current_amount = getattr(player, currency_type.value)
                
                if current_amount < amount:
                    raise ValueError(
                        f"Insufficient {currency_type.value}. "
                        f"Need {amount:,}, have {current_amount:,}"
                    )
                
                # Subtract currency
                new_amount = current_amount - amount
                setattr(player, currency_type.value, new_amount)
                player.update_activity()
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.CURRENCY_SPEND,
                    {
                        "currency_type": currency_type.value,
                        "amount": amount,
                        "old_amount": current_amount,
                        "new_amount": new_amount,
                        "purpose": purpose
                    }
                )
                
                return {
                    "currency_type": currency_type.value,
                    "amount_spent": amount,
                    "old_amount": current_amount,
                    "new_amount": new_amount,
                    "purpose": purpose
                }
        
        return await cls._safe_execute(_operation, f"subtract {currency_type.value} from player {player_id}")
    
    @classmethod
    async def validate_currency_cost(
        cls, 
        player_id: int, 
        currency_type: CurrencyType, 
        amount: int
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate if player can afford a currency cost without spending"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                current_amount = getattr(player, currency_type.value)
                can_afford = current_amount >= amount
                shortage = max(0, amount - current_amount)
                
                return {
                    "currency_type": currency_type.value,
                    "required_amount": amount,
                    "current_amount": current_amount,
                    "can_afford": can_afford,
                    "shortage": shortage
                }
        
        return await cls._safe_execute(_operation, f"validate {currency_type.value} cost for player {player_id}")
    
    @classmethod
    async def get_currency_summary(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get summary of all player currencies"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                return {
                    "seios": player.seios,
                    "ichor": player.ichor,
                    "erythl": player.erythl,
                    "total_value": cls._calculate_total_currency_value(player)
                }
        
        return await cls._safe_execute(_operation, f"get currency summary for player {player_id}")
    
    @classmethod
    async def transfer_currency(
        cls,
        from_player_id: int,
        to_player_id: int,
        currency_type: CurrencyType,
        amount: int,
        reason: str = "transfer"
    ) -> ServiceResult[Dict[str, Any]]:
        """Transfer currency between players (future trading system)"""
        async def _operation():
            cls._validate_player_id(from_player_id)
            cls._validate_player_id(to_player_id)
            
            if from_player_id == to_player_id:
                raise ValueError("Cannot transfer to self")
            
            if amount <= 0:
                raise ValueError("Transfer amount must be positive")
            
            # Check if transfers are enabled for this currency
            transfer_config = ConfigManager.get("currency.transfers", {})
            if not transfer_config.get(currency_type.value, {}).get("enabled", False):
                raise ValueError(f"{currency_type.value} transfers are not enabled")
            
            async with DatabaseService.get_transaction() as session:
                # Get both players with locking
                from_stmt = select(Player).where(Player.id == from_player_id).with_for_update()
                to_stmt = select(Player).where(Player.id == to_player_id).with_for_update()
                
                from_player = (await session.execute(from_stmt)).scalar_one()
                to_player = (await session.execute(to_stmt)).scalar_one()
                
                # Validate sender has enough currency
                from_current = getattr(from_player, currency_type.value)
                if from_current < amount:
                    raise ValueError(f"Insufficient {currency_type.value} for transfer")
                
                # Transfer currency
                setattr(from_player, currency_type.value, from_current - amount)
                
                to_current = getattr(to_player, currency_type.value)
                setattr(to_player, currency_type.value, to_current + amount)
                
                from_player.update_activity()
                to_player.update_activity()
                
                await session.commit()
                
                # Log transactions for both players
                transaction_logger.log_transaction(
                    from_player_id,
                    TransactionType.CURRENCY_SPEND,
                    {
                        "currency_type": currency_type.value,
                        "amount": amount,
                        "transfer_to": to_player_id,
                        "reason": reason
                    }
                )
                
                transaction_logger.log_transaction(
                    to_player_id,
                    TransactionType.CURRENCY_GAIN,
                    {
                        "currency_type": currency_type.value,
                        "amount": amount,
                        "transfer_from": from_player_id,
                        "reason": reason
                    }
                )
                
                return {
                    "currency_type": currency_type.value,
                    "amount": amount,
                    "from_player": from_player_id,
                    "to_player": to_player_id,
                    "from_new_balance": getattr(from_player, currency_type.value),
                    "to_new_balance": getattr(to_player, currency_type.value)
                }
        
        return await cls._safe_execute(_operation, f"transfer {currency_type.value} from {from_player_id} to {to_player_id}")
    
    @classmethod
    def _calculate_total_currency_value(cls, player: Player) -> int:
        """Calculate total currency value for display purposes"""
        # Get exchange rates from config
        rates = ConfigManager.get("currency.exchange_rates", {
            "seios_to_base": 1,
            "ichor_to_base": 100,  # Ichor is more valuable
            "erythl_to_base": 1000  # Premium currency most valuable
        })
        
        total = (
            player.seios * rates["seios_to_base"] +
            player.ichor * rates["ichor_to_base"] +
            player.erythl * rates["erythl_to_base"]
        )
        
        return total