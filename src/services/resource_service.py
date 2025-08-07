# src/services/resource_service.py
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select

from src.services.base_service import BaseService, ServiceResult
from src.database.models.player import Player
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ResourceService(BaseService):
    """Energy and stamina management system"""
    
    @classmethod
    async def get_resource_status(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get player's current energy and stamina status with regeneration"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Regenerate resources before returning status
                energy_regen = cls._regenerate_energy(player)
                stamina_regen = cls._regenerate_stamina(player)
                
                # Save if any regeneration occurred
                if energy_regen > 0 or stamina_regen > 0:
                    await session.commit()
                
                # Calculate caps
                energy_cap = cls._calculate_energy_cap(player)
                stamina_cap = cls._calculate_stamina_cap(player)
                
                return {
                    "energy": {
                        "current": player.energy,
                        "cap": energy_cap,
                        "regenerated": energy_regen,
                        "is_full": player.energy >= energy_cap
                    },
                    "stamina": {
                        "current": player.stamina,
                        "cap": stamina_cap,
                        "regenerated": stamina_regen,
                        "is_full": player.stamina >= stamina_cap
                    }
                }
        
        return await cls._safe_execute(_operation, f"get resource status for player {player_id}")
    
    @classmethod
    async def consume_stamina(
        cls, 
        player_id: int, 
        amount: int, 
        purpose: str = "combat"
    ) -> ServiceResult[Dict[str, Any]]:
        """Consume stamina for combat or other activities"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if amount <= 0:
                raise ValueError("Stamina amount must be positive")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Regenerate stamina first
                stamina_regen = cls._regenerate_stamina(player)
                
                # Validate sufficient stamina
                if player.stamina < amount:
                    stamina_cap = cls._calculate_stamina_cap(player)
                    raise ValueError(
                        f"Insufficient stamina. Need {amount}, have {player.stamina}/{stamina_cap}"
                    )
                
                # Consume stamina
                old_stamina = player.stamina
                player.stamina -= amount
                player.update_activity()
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.RESOURCE_CONSUME,
                    {
                        "resource_type": "stamina",
                        "amount": amount,
                        "old_amount": old_stamina,
                        "new_amount": player.stamina,
                        "purpose": purpose,
                        "regenerated_before": stamina_regen
                    }
                )
                
                return {
                    "stamina_consumed": amount,
                    "stamina_remaining": player.stamina,
                    "stamina_cap": cls._calculate_stamina_cap(player),
                    "stamina_regenerated": stamina_regen,
                    "purpose": purpose
                }
        
        return await cls._safe_execute(_operation, f"consume stamina for player {player_id}")
    
    @classmethod
    async def consume_energy(
        cls, 
        player_id: int, 
        amount: int, 
        purpose: str = "activity"
    ) -> ServiceResult[Dict[str, Any]]:
        """Consume energy for activities"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if amount <= 0:
                raise ValueError("Energy amount must be positive")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Regenerate energy first
                energy_regen = cls._regenerate_energy(player)
                
                # Validate sufficient energy
                if player.energy < amount:
                    energy_cap = cls._calculate_energy_cap(player)
                    raise ValueError(
                        f"Insufficient energy. Need {amount}, have {player.energy}/{energy_cap}"
                    )
                
                # Consume energy
                old_energy = player.energy
                player.energy -= amount
                player.update_activity()
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.RESOURCE_CONSUME,
                    {
                        "resource_type": "energy",
                        "amount": amount,
                        "old_amount": old_energy,
                        "new_amount": player.energy,
                        "purpose": purpose,
                        "regenerated_before": energy_regen
                    }
                )
                
                return {
                    "energy_consumed": amount,
                    "energy_remaining": player.energy,
                    "energy_cap": cls._calculate_energy_cap(player),
                    "energy_regenerated": energy_regen,
                    "purpose": purpose
                }
        
        return await cls._safe_execute(_operation, f"consume energy for player {player_id}")
    
    @classmethod
    async def validate_stamina_cost(cls, player_id: int, amount: int) -> ServiceResult[Dict[str, Any]]:
        """Validate if player has enough stamina without consuming"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                # Calculate current stamina with potential regeneration
                current_stamina = player.stamina
                stamina_cap = cls._calculate_stamina_cap(player)
                
                # Simulate regeneration without updating database
                potential_regen = cls._calculate_potential_stamina_regen(player)
                effective_stamina = min(current_stamina + potential_regen, stamina_cap)
                
                can_afford = effective_stamina >= amount
                shortage = max(0, amount - effective_stamina)
                
                return {
                    "required_stamina": amount,
                    "current_stamina": current_stamina,
                    "effective_stamina": effective_stamina,
                    "stamina_cap": stamina_cap,
                    "can_afford": can_afford,
                    "shortage": shortage,
                    "potential_regen": potential_regen
                }
        
        return await cls._safe_execute(_operation, f"validate stamina cost for player {player_id}")
    
    @classmethod
    def _regenerate_energy(cls, player: Player) -> int:
        """Regenerate player energy based on time elapsed"""
        energy_cap = cls._calculate_energy_cap(player)
        
        if player.energy >= energy_cap:
            return 0
        
        amount_added, new_regen_time = cls._regenerate_resource(
            current_value=player.energy,
            cap_value=energy_cap,
            last_regen_time=player.last_energy_regen,
            regen_minutes_key="energy.regen_minutes",
            regen_amount_key="energy.regen_amount"
        )
        
        if amount_added > 0:
            player.energy += amount_added
            player.last_energy_regen = new_regen_time
        
        return amount_added
    
    @classmethod
    def _regenerate_stamina(cls, player: Player) -> int:
        """Regenerate player stamina based on time elapsed"""
        stamina_cap = cls._calculate_stamina_cap(player)
        
        if player.stamina >= stamina_cap:
            return 0
        
        amount_added, new_regen_time = cls._regenerate_resource(
            current_value=player.stamina,
            cap_value=stamina_cap,
            last_regen_time=player.last_stamina_regen,
            regen_minutes_key="stamina.regen_minutes", 
            regen_amount_key="stamina.regen_amount"
        )
        
        if amount_added > 0:
            player.stamina += amount_added
            player.last_stamina_regen = new_regen_time
        
        return amount_added
    
    @classmethod
    def _regenerate_resource(
        cls,
        current_value: int,
        cap_value: int,
        last_regen_time: datetime,
        regen_minutes_key: str,
        regen_amount_key: str
    ) -> Tuple[int, datetime]:
        """Generic resource regeneration calculation"""
        if current_value >= cap_value:
            return 0, last_regen_time
        
        regen_minutes = ConfigManager.get(regen_minutes_key, 5)
        regen_amount = ConfigManager.get(regen_amount_key, 1)
        
        time_diff = datetime.utcnow() - last_regen_time
        intervals_passed = int(time_diff.total_seconds() // (regen_minutes * 60))
        
        if intervals_passed > 0:
            amount_to_add = min(intervals_passed * regen_amount, cap_value - current_value)
            if amount_to_add > 0:
                new_last_regen = last_regen_time + timedelta(minutes=regen_minutes * intervals_passed)
                return amount_to_add, new_last_regen
        
        return 0, last_regen_time
    
    @classmethod
    def _calculate_energy_cap(cls, player: Player) -> int:
        """Calculate player's energy capacity"""
        base_energy = ConfigManager.get("player.base_energy", 50)
        energy_per_level = ConfigManager.get("player.energy_per_level", 10)
        return base_energy + ((player.level - 1) * energy_per_level)
    
    @classmethod
    def _calculate_stamina_cap(cls, player: Player) -> int:
        """Calculate player's stamina capacity"""
        base_stamina = ConfigManager.get("player.base_stamina", 25)
        stamina_per_level = ConfigManager.get("player.stamina_per_level", 5)
        return base_stamina + ((player.level - 1) * stamina_per_level)
    
    @classmethod
    def _calculate_potential_stamina_regen(cls, player: Player) -> int:
        """Calculate how much stamina would regenerate if checked now"""
        stamina_cap = cls._calculate_stamina_cap(player)
        
        if player.stamina >= stamina_cap:
            return 0
        
        regen_minutes = ConfigManager.get("stamina.regen_minutes", 5)
        regen_amount = ConfigManager.get("stamina.regen_amount", 1)
        
        time_diff = datetime.utcnow() - player.last_stamina_regen
        intervals_passed = int(time_diff.total_seconds() // (regen_minutes * 60))
        
        return min(intervals_passed * regen_amount, stamina_cap - player.stamina)