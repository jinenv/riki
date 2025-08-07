# src/services/power_service.py
from typing import Dict, Any, List
from sqlalchemy import select, and_

from src.services.base_service import BaseService, ServiceResult
from src.database.models.player import Player
from src.database.models.esprit import Esprit
from src.database.models.esprit_base import EspritBase
from src.utils.database_service import DatabaseService
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PowerService(BaseService):
    """Combat power calculations for esprits and players"""
    
    @classmethod
    async def calculate_esprit_power(cls, esprit_id: int) -> ServiceResult[Dict[str, Any]]:
        """Calculate individual and stack power for a specific esprit"""
        async def _operation():
            async with DatabaseService.get_session() as session:
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.id == esprit_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                )
                
                result = await session.execute(stmt)
                row = result.first()
                
                if not row:
                    raise ValueError(f"Esprit {esprit_id} not found")
                
                esprit, base = row
                
                # Calculate individual power (one copy)
                individual_power = cls._calculate_individual_power(esprit, base)
                
                # Calculate stack power (all copies)
                stack_power = {
                    "atk": individual_power["atk"] * esprit.quantity,
                    "def": individual_power["def"] * esprit.quantity,
                    "power": individual_power["power"] * esprit.quantity,
                    "average_individual_power": individual_power["power"]
                }
                
                return {
                    "esprit_id": esprit_id,
                    "quantity": esprit.quantity,
                    "tier": esprit.tier,
                    "individual_power": individual_power,
                    "stack_power": stack_power
                }
        
        return await cls._safe_execute(_operation, f"calculate power for esprit {esprit_id}")
    
    @classmethod
    async def calculate_player_total_power(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Calculate player's total combat power from all esprits"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                # Get all player's esprits with base data
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.owner_id == player_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                )
                
                results = await session.execute(stmt)
                
                total_atk = 0
                total_def = 0
                esprit_count = 0
                power_breakdown = []
                
                for esprit, base in results:
                    # Calculate power for this esprit stack
                    individual_power = cls._calculate_individual_power(esprit, base)
                    stack_atk = individual_power["atk"] * esprit.quantity
                    stack_def = individual_power["def"] * esprit.quantity
                    stack_power = individual_power["power"] * esprit.quantity
                    
                    total_atk += stack_atk
                    total_def += stack_def
                    esprit_count += esprit.quantity
                    
                    power_breakdown.append({
                        "esprit_id": esprit.id,
                        "name": base.name,
                        "tier": esprit.tier,
                        "quantity": esprit.quantity,
                        "stack_power": stack_power,
                        "contribution_percent": 0  # Will be calculated after total
                    })
                
                total_power = total_atk + total_def
                
                # Calculate contribution percentages
                if total_power > 0:
                    for breakdown in power_breakdown:
                        breakdown["contribution_percent"] = (breakdown["stack_power"] / total_power) * 100
                
                # Sort by contribution
                power_breakdown.sort(key=lambda x: x["stack_power"], reverse=True)
                
                return {
                    "player_id": player_id,
                    "total_attack": total_atk,
                    "total_defense": total_def,
                    "total_power": total_power,
                    "esprit_count": esprit_count,
                    "power_breakdown": power_breakdown[:10],  # Top 10 contributors
                    "power_display": cls._format_power_display(total_power)
                }
        
        return await cls._safe_execute(_operation, f"calculate total power for player {player_id}")
    
    @classmethod
    async def update_player_cached_power(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Update player's cached attack/defense power in database"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            # Calculate current total power
            power_result = await cls.calculate_player_total_power(player_id)
            power_data = power_result.data
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                # Update cached power values
                old_attack = player.attack_power
                old_defense = player.defense_power
                
                player.attack_power = power_data["total_attack"]
                player.defense_power = power_data["total_defense"]
                player.update_activity()
                
                await session.commit()
                
                return {
                    "player_id": player_id,
                    "old_attack": old_attack,
                    "new_attack": player.attack_power,
                    "old_defense": old_defense,
                    "new_defense": player.defense_power,
                    "total_power": power_data["total_power"],
                    "power_change": power_data["total_power"] - (old_attack + old_defense)
                }
        
        return await cls._safe_execute(_operation, f"update cached power for player {player_id}")
    
    @classmethod
    async def calculate_floor_power_requirement(cls, floor: int) -> ServiceResult[int]:
        """Calculate minimum power required to efficiently clear a floor"""
        async def _operation():
            # Get tower difficulty scaling from config
            difficulty_multiplier = ConfigManager.get("tower.difficulty_multiplier", 1000)
            
            # Linear scaling for now - can be made more complex later
            required_power = floor * difficulty_multiplier
            
            return required_power
        
        return await cls._safe_execute(_operation, f"calculate power requirement for floor {floor}")
    
    @classmethod
    async def calculate_combat_efficiency(cls, player_id: int, floor: int) -> ServiceResult[Dict[str, Any]]:
        """Calculate player's combat efficiency against a specific floor"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            # Get player's current power
            power_result = await cls.calculate_player_total_power(player_id)
            player_power = power_result.data["total_power"]
            
            # Get floor requirement
            floor_requirement_result = await cls.calculate_floor_power_requirement(floor)
            floor_requirement = floor_requirement_result.data
            
            # Calculate efficiency (capped at 10x for balance)
            if floor_requirement <= 0:
                efficiency = 10.0
            else:
                efficiency = min(player_power / floor_requirement, 10.0)
            
            # Determine success chance and damage multiplier
            if efficiency >= 1.0:
                success_chance = min(0.95, 0.5 + (efficiency - 1.0) * 0.1)  # 50% base, up to 95%
                damage_multiplier = efficiency
            else:
                success_chance = max(0.05, efficiency * 0.5)  # Down to 5% minimum
                damage_multiplier = efficiency
            
            return {
                "player_power": player_power,
                "floor_requirement": floor_requirement,
                "efficiency": efficiency,
                "success_chance": success_chance,
                "damage_multiplier": damage_multiplier,
                "can_clear": efficiency >= 0.3,  # Minimum 30% efficiency to attempt
                "recommended": efficiency >= 1.0
            }
        
        return await cls._safe_execute(_operation, f"calculate combat efficiency for player {player_id} on floor {floor}")
    
    @classmethod
    def _calculate_individual_power(cls, esprit: Esprit, base: EspritBase) -> Dict[str, Any]:
        """Calculate power of one copy using Monster Warlord-style scaling"""
        # Get scaling config
        tier_power_base = ConfigManager.get("power.tier_scaling_base", 1.0)
        tier_power_multiplier = ConfigManager.get("power.tier_scaling_multiplier", 0.15)
        element_bonus_multiplier = ConfigManager.get("power.element_bonus_multiplier", 0.05)
        
        # MW-style tier scaling: exponential growth
        tier_multiplier = tier_power_base + ((esprit.tier - 1) * tier_power_multiplier)
        
        # Element bonus consideration (for future element synergy)
        element_multiplier = 1.0 + element_bonus_multiplier
        
        # Apply all multipliers
        total_multiplier = tier_multiplier * element_multiplier
        
        final_atk = int(base.base_atk * total_multiplier)
        final_def = int(base.base_def * total_multiplier)
        
        return {
            "atk": final_atk,
            "def": final_def,
            "power": final_atk + final_def,
            "tier_multiplier": tier_multiplier,
            "element_multiplier": element_multiplier,
            "total_multiplier": total_multiplier
        }
    
    @classmethod
    def _format_power_display(cls, power: int) -> str:
        """Format power number for display"""
        if power >= 1_000_000_000:
            return f"{power / 1_000_000_000:.1f}B"
        elif power >= 1_000_000:
            return f"{power / 1_000_000:.1f}M"
        elif power >= 1_000:
            return f"{power / 1_000:.1f}K"
        else:
            return str(power)