# src/services/ichor_service.py
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select

from src.services.base_service import BaseService, ServiceResult
from src.database.models.player import Player
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class IchorService(BaseService):
    """Prayer system for ichor generation with 5-minute cooldowns"""
    
    @classmethod
    async def pray_for_ichor(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Execute prayer command to gain 1 ichor (5-minute cooldown)"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_transaction() as session:
                # Get player with locking
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Check prayer cooldown
                prayer_info = cls._calculate_prayer_availability(player)
                
                if not prayer_info["can_pray"]:
                    time_remaining = prayer_info["time_until_prayer"]
                    minutes = int(time_remaining.total_seconds() // 60)
                    seconds = int(time_remaining.total_seconds() % 60)
                    raise ValueError(f"Prayer on cooldown. Next prayer available in {minutes}m {seconds}s")
                
                # Grant 1 ichor
                old_ichor = player.ichor
                player.ichor += 1
                player.last_pray_time = datetime.utcnow()
                player.update_activity()
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.CURRENCY_GAIN,
                    {
                        "action": "prayer",
                        "currency_type": "ichor",
                        "amount": 1,
                        "old_amount": old_ichor,
                        "new_amount": player.ichor
                    }
                )
                
                return {
                    "success": True,
                    "ichor_gained": 1,
                    "total_ichor": player.ichor,
                    "next_prayer_time": player.last_pray_time + timedelta(minutes=5)
                }
        
        return await cls._safe_execute(_operation, f"prayer for player {player_id}")
    
    @classmethod
    async def get_prayer_status(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get player's current prayer cooldown status"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                prayer_info = cls._calculate_prayer_availability(player)
                
                return {
                    "can_pray": prayer_info["can_pray"],
                    "current_ichor": player.ichor,
                    "time_until_prayer": prayer_info["time_until_prayer"],
                    "next_prayer_time": prayer_info["next_prayer_time"],
                    "has_notifications": player.pray_notifications
                }
        
        return await cls._safe_execute(_operation, f"prayer status for player {player_id}")
    
    @classmethod
    async def toggle_prayer_notifications(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Toggle prayer notification preferences"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Toggle notification preference
                old_setting = player.pray_notifications
                player.pray_notifications = not old_setting
                player.update_activity()
                
                await session.commit()
                
                return {
                    "notifications_enabled": player.pray_notifications,
                    "changed_from": old_setting,
                    "message": f"Prayer notifications {'enabled' if player.pray_notifications else 'disabled'}"
                }
        
        return await cls._safe_execute(_operation, f"toggle prayer notifications for player {player_id}")
    
    @classmethod
    def _calculate_prayer_availability(cls, player: Player) -> Dict[str, Any]:
        """Calculate prayer cooldown status for a player"""
        # Get prayer cooldown from config (default 5 minutes)
        prayer_cooldown_minutes = ConfigManager.get("prayer.cooldown_minutes", 5)
        
        now = datetime.utcnow()
        
        # First time praying
        if not player.last_pray_time:
            return {
                "can_pray": True,
                "time_until_prayer": timedelta(0),
                "next_prayer_time": now
            }
        
        # Calculate time since last prayer
        time_since_prayer = now - player.last_pray_time
        cooldown_duration = timedelta(minutes=prayer_cooldown_minutes)
        
        # Check if cooldown has elapsed
        if time_since_prayer >= cooldown_duration:
            return {
                "can_pray": True,
                "time_until_prayer": timedelta(0),
                "next_prayer_time": now
            }
        else:
            time_remaining = cooldown_duration - time_since_prayer
            next_prayer_time = player.last_pray_time + cooldown_duration
            
            return {
                "can_pray": False,
                "time_until_prayer": time_remaining,
                "next_prayer_time": next_prayer_time
            }
    
    @classmethod
    async def get_players_ready_for_notification(cls) -> ServiceResult[List[int]]:
        """Get list of player IDs who have prayer notifications enabled and can pray"""
        async def _operation():
            prayer_cooldown_minutes = ConfigManager.get("prayer.cooldown_minutes", 5)
            cutoff_time = datetime.utcnow() - timedelta(minutes=prayer_cooldown_minutes)
            
            async with DatabaseService.get_session() as session:
                # Find players with notifications enabled who can pray
                stmt = select(Player.id).where(
                    Player.pray_notifications == True,
                    Player.last_pray_time <= cutoff_time
                )
                
                result = await session.execute(stmt)
                ready_player_ids = [row[0] for row in result.fetchall()]
                
                return ready_player_ids
        
        return await cls._safe_execute(_operation, "get players ready for prayer notification")