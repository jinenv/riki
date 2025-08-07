# src/services/tower_service.py
import random
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select

from src.services.base_service import BaseService, ServiceResult
from src.services.resource_service import ResourceService
from src.services.power_service import PowerService
from src.services.currency_service import CurrencyService, CurrencyType
from src.database.models.player import Player
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TowerService(BaseService):
    """Tower combat system with floor progression and idle raiding"""
    
    @classmethod
    async def climb_floor(cls, player_id: int, stamina_to_use: int = 1) -> ServiceResult[Dict[str, Any]]:
        """Attempt to climb to next floor using MW-style combat"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if stamina_to_use < 1:
                raise ValueError("Must use at least 1 stamina")
            
            # Validate stamina availability
            stamina_check = await ResourceService.validate_stamina_cost(player_id, stamina_to_use)
            if not stamina_check.data["can_afford"]:
                shortage = stamina_check.data["shortage"]
                raise ValueError(f"Insufficient stamina. Need {shortage} more stamina")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                current_floor = player.current_floor
                target_floor = current_floor + 1
                
                # Get combat efficiency for current floor boss
                efficiency_result = await PowerService.calculate_combat_efficiency(player_id, current_floor)
                efficiency_data = efficiency_result.data
                
                if not efficiency_data["can_clear"]:
                    raise ValueError(
                        f"Insufficient power to attempt floor {current_floor}. "
                        f"Need {efficiency_data['floor_requirement']:,} power, have {efficiency_data['player_power']:,}"
                    )
                
                # Consume stamina
                await ResourceService.consume_stamina(player_id, stamina_to_use, f"floor_{current_floor}_combat")
                
                # Calculate combat result
                combat_result = cls._simulate_combat(
                    efficiency_data, stamina_to_use, current_floor
                )
                
                # Apply combat results
                if combat_result["victory"]:
                    # Advance floor
                    old_floor = player.current_floor
                    player.current_floor = target_floor
                    player.highest_floor_reached = max(player.highest_floor_reached, target_floor)
                    player.total_floor_clears += 1
                    
                    # Reset raid progress for new floor
                    player.raid_progress = 0.0
                    player.last_climb_time = datetime.utcnow()
                    player.update_activity()
                    
                    await session.commit()
                    
                    # Log successful climb
                    transaction_logger.log_transaction(
                        player_id,
                        TransactionType.FLOOR_CLEARED,
                        {
                            "from_floor": old_floor,
                            "to_floor": target_floor,
                            "stamina_used": stamina_to_use,
                            "combat_efficiency": efficiency_data["efficiency"],
                            "damage_dealt": combat_result["damage_dealt"]
                        }
                    )
                    
                    climb_result = {
                        "success": True,
                        "victory": True,
                        "from_floor": old_floor,
                        "to_floor": target_floor,
                        "stamina_used": stamina_to_use,
                        "combat_result": combat_result,
                        "new_highest": player.highest_floor_reached
                    }
                else:
                    # Failed attempt
                    player.last_climb_time = datetime.utcnow()
                    player.update_activity()
                    
                    await session.commit()
                    
                    # Log failed attempt
                    transaction_logger.log_transaction(
                        player_id,
                        TransactionType.FLOOR_ATTEMPT_FAILED,
                        {
                            "floor": current_floor,
                            "stamina_used": stamina_to_use,
                            "damage_dealt": combat_result["damage_dealt"],
                            "boss_health_remaining": combat_result["boss_health_remaining"]
                        }
                    )
                    
                    climb_result = {
                        "success": True,
                        "victory": False,
                        "floor": current_floor,
                        "stamina_used": stamina_to_use,
                        "combat_result": combat_result,
                        "retry_available": True
                    }
                
                return climb_result
        
        return await cls._safe_execute(_operation, f"climb floor for player {player_id}")
    
    @classmethod
    async def raid_current_floor(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Collect idle loot from current floor based on time and progress"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Calculate idle time since last raid
                now = datetime.utcnow()
                last_raid = player.last_raid_time or player.last_climb_time or now
                idle_time = now - last_raid
                idle_hours = idle_time.total_seconds() / 3600
                
                # Cap idle time to prevent excessive rewards
                max_idle_hours = ConfigManager.get("tower.max_idle_hours", 24)
                capped_idle_hours = min(idle_hours, max_idle_hours)
                
                if capped_idle_hours < 0.1:  # Minimum 6 minutes
                    raise ValueError("Must wait at least 6 minutes between raids")
                
                # Calculate loot based on floor, time, and player power
                loot_result = cls._calculate_raid_loot(player, capped_idle_hours)
                
                # Apply loot rewards
                if loot_result["seios"] > 0:
                    await CurrencyService.add_currency(
                        player_id, CurrencyType.SEIOS, loot_result["seios"], "tower_raid"
                    )
                
                if loot_result["erythl"] > 0:
                    await CurrencyService.add_currency(
                        player_id, CurrencyType.ERYTHL, loot_result["erythl"], "tower_raid_premium"
                    )
                
                # Update raid progress toward next floor
                progress_gained = cls._calculate_progress_gain(player, capped_idle_hours)
                old_progress = player.raid_progress
                player.raid_progress = min(1.0, player.raid_progress + progress_gained)
                
                # Update timestamps
                player.last_raid_time = now
                player.update_activity()
                
                await session.commit()
                
                # Log raid transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.TOWER_RAID,
                    {
                        "floor": player.current_floor,
                        "idle_hours": capped_idle_hours,
                        "seios_gained": loot_result["seios"],
                        "erythl_gained": loot_result["erythl"],
                        "progress_gained": progress_gained,
                        "total_progress": player.raid_progress
                    }
                )
                
                return {
                    "floor": player.current_floor,
                    "idle_time_hours": capped_idle_hours,
                    "loot_gained": loot_result,
                    "progress_gained": progress_gained,
                    "total_progress": player.raid_progress,
                    "progress_to_next_floor": player.raid_progress,
                    "can_attempt_next_floor": player.raid_progress >= 1.0,
                    "special_encounters": loot_result.get("encounters", [])
                }
        
        return await cls._safe_execute(_operation, f"raid floor for player {player_id}")
    
    @classmethod
    async def get_floor_status(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get player's current tower status and progression info"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                # Get combat efficiency for current floor
                efficiency_result = await PowerService.calculate_combat_efficiency(
                    player_id, player.current_floor
                )
                
                # Calculate time since last raid
                now = datetime.utcnow()
                last_raid = player.last_raid_time or player.last_climb_time or now
                time_since_raid = now - last_raid
                
                # Get floor theme
                floor_theme = cls._get_floor_theme(player.current_floor)
                
                return {
                    "current_floor": player.current_floor,
                    "highest_floor": player.highest_floor_reached,
                    "total_clears": player.total_floor_clears,
                    "raid_progress": player.raid_progress,
                    "can_attempt_next": player.raid_progress >= 1.0,
                    "floor_theme": floor_theme,
                    "combat_efficiency": efficiency_result.data,
                    "time_since_last_raid": time_since_raid,
                    "estimated_raid_loot": cls._estimate_raid_loot(player, time_since_raid.total_seconds() / 3600)
                }
        
        return await cls._safe_execute(_operation, f"get floor status for player {player_id}")
    
    @classmethod
    def _simulate_combat(cls, efficiency_data: Dict[str, Any], stamina_used: int, floor: int) -> Dict[str, Any]:
        """Simulate MW-style combat against floor boss"""
        # Boss health scales with floor
        base_boss_health = ConfigManager.get("tower.base_boss_health", 100)
        boss_health = base_boss_health * floor
        
        # Player damage based on efficiency and stamina
        base_damage_per_stamina = efficiency_data["damage_multiplier"] * base_boss_health
        total_damage = base_damage_per_stamina * stamina_used
        
        # Add some randomness (±20%)
        damage_variance = ConfigManager.get("tower.damage_variance", 0.2)
        damage_multiplier = 1.0 + random.uniform(-damage_variance, damage_variance)
        actual_damage = int(total_damage * damage_multiplier)
        
        # Determine victory
        victory = actual_damage >= boss_health
        boss_health_remaining = max(0, boss_health - actual_damage)
        
        return {
            "boss_max_health": boss_health,
            "damage_dealt": actual_damage,
            "boss_health_remaining": boss_health_remaining,
            "victory": victory,
            "damage_per_stamina": base_damage_per_stamina,
            "stamina_used": stamina_used
        }
    
    @classmethod
    def _calculate_raid_loot(cls, player: Player, idle_hours: float) -> Dict[str, Any]:
        """Calculate loot rewards from tower raiding"""
        floor = player.current_floor
        
        # Base loot scales with floor
        base_seios_per_hour = ConfigManager.get("tower.base_seios_per_hour", 100)
        seios_per_hour = base_seios_per_hour * (1 + (floor - 1) * 0.1)  # 10% more per floor
        
        total_seios = int(seios_per_hour * idle_hours)
        
        # Premium currency chance (rare)
        erythl_chance = ConfigManager.get("tower.erythl_chance_per_hour", 0.05)  # 5% per hour
        total_erythl_chance = min(1.0, erythl_chance * idle_hours)
        
        erythl_gained = 0
        if random.random() < total_erythl_chance:
            erythl_gained = random.randint(1, max(1, int(floor / 10)))
        
        # Special encounters (future expansion)
        encounters = []
        encounter_chance = ConfigManager.get("tower.encounter_chance_per_hour", 0.1)
        if random.random() < (encounter_chance * idle_hours):
            encounters.append({
                "type": "treasure_chest",
                "bonus_seios": random.randint(50, 200)
            })
        
        return {
            "seios": total_seios,
            "erythl": erythl_gained,
            "encounters": encounters
        }
    
    @classmethod
    def _calculate_progress_gain(cls, player: Player, idle_hours: float) -> float:
        """Calculate raid progress gain toward next floor unlock"""
        # Progress rate scales with player power vs floor requirement
        floor_req_result = PowerService.calculate_floor_power_requirement(player.current_floor)
        floor_requirement = floor_req_result.data if hasattr(floor_req_result, 'data') else 1000
        
        player_power = player.attack_power + player.defense_power
        efficiency = min(player_power / floor_requirement, 2.0) if floor_requirement > 0 else 1.0
        
        # Base progress per hour (faster with higher power)
        base_progress_per_hour = ConfigManager.get("tower.base_progress_per_hour", 0.1)  # 10 hours for full progress
        actual_progress_per_hour = base_progress_per_hour * efficiency
        
        return min(1.0, actual_progress_per_hour * idle_hours)
    
    @classmethod
    def _get_floor_theme(cls, floor: int) -> str:
        """Get thematic description for floor range"""
        tower_themes = ConfigManager.get("tower.themes", [
            {"max_floor": 100, "name": "Lower Floors"},
            {"max_floor": 500, "name": "Mid Floors"},
            {"max_floor": 999999, "name": "Upper Floors"}
        ])
        
        for theme in tower_themes:
            if floor <= theme["max_floor"]:
                return theme["name"]
        
        return "Unknown Floors"
    
    @classmethod
    def _estimate_raid_loot(cls, player: Player, potential_hours: float) -> Dict[str, Any]:
        """Estimate what loot would be gained from raiding now"""
        max_idle_hours = ConfigManager.get("tower.max_idle_hours", 24)
        capped_hours = min(potential_hours, max_idle_hours)
        
        if capped_hours < 0.1:
            return {"seios": 0, "erythl": 0, "hours": 0}
        
        # Estimate without randomness
        floor = player.current_floor
        base_seios_per_hour = ConfigManager.get("tower.base_seios_per_hour", 100)
        seios_per_hour = base_seios_per_hour * (1 + (floor - 1) * 0.1)
        
        estimated_seios = int(seios_per_hour * capped_hours)
        
        # Estimate erythl chance
        erythl_chance = ConfigManager.get("tower.erythl_chance_per_hour", 0.05)
        estimated_erythl_chance = min(1.0, erythl_chance * capped_hours)
        
        return {
            "seios": estimated_seios,
            "erythl_chance": estimated_erythl_chance,
            "hours": capped_hours
        }