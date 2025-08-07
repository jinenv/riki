# src/services/fusion_service.py
from typing import Dict, Any
from sqlalchemy import select, and_

from src.services.base_service import BaseService, ServiceResult
from src.services.currency_service import CurrencyService, CurrencyType
from src.services.power_service import PowerService
from src.database.models.player import Player
from src.database.models.esprit import Esprit
from src.database.models.esprit_base import EspritBase
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class FusionService(BaseService):
    """Esprit fusion system for tier progression"""
    
    @classmethod
    async def get_fusion_options(cls, player_id: int, esprit_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get fusion information and requirements for an esprit"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                # Validate ownership and get esprit data
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.id == esprit_id,
                        Esprit.owner_id == player_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                )
                
                result = await session.execute(stmt)
                row = result.first()
                
                if not row:
                    raise ValueError(f"Esprit {esprit_id} not found or not owned by player")
                
                esprit, base = row
                
                # Calculate fusion requirements
                fusion_cost = cls._calculate_fusion_cost(esprit.tier)
                can_fuse = cls._can_perform_fusion(esprit)
                max_tier = esprit.get_tier_cap()
                
                # Get power calculations for current and next tier
                current_power = await PowerService.calculate_esprit_power(esprit_id)
                
                fusion_data = {
                    "esprit_id": esprit_id,
                    "esprit_name": base.name,
                    "current_tier": esprit.tier,
                    "max_tier": max_tier,
                    "current_quantity": esprit.quantity,
                    "can_fuse": can_fuse,
                    "fusion_requirements": {
                        "copies_needed": 2,
                        "copies_available": esprit.quantity,
                        "seios_cost": fusion_cost,
                        "meets_requirements": can_fuse
                    },
                    "current_power": current_power.data["individual_power"],
                    "fusion_preview": None
                }
                
                # Add fusion preview if possible
                if can_fuse:
                    preview_power = cls._calculate_fusion_preview_power(esprit, base)
                    fusion_data["fusion_preview"] = {
                        "result_tier": esprit.tier + 1,
                        "result_quantity": esprit.quantity - 1,  # 2 copies become 1
                        "new_power": preview_power,
                        "power_increase": preview_power["power"] - current_power.data["individual_power"]["power"]
                    }
                
                return fusion_data
        
        return await cls._safe_execute(_operation, f"get fusion options for esprit {esprit_id}")
    
    @classmethod
    async def execute_fusion(cls, player_id: int, esprit_id: int) -> ServiceResult[Dict[str, Any]]:
        """Execute fusion to upgrade esprit tier"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_transaction() as session:
                # Get esprit with locking
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.id == esprit_id,
                        Esprit.owner_id == player_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                ).with_for_update()
                
                result = await session.execute(stmt)
                row = result.first()
                
                if not row:
                    raise ValueError(f"Esprit {esprit_id} not found or not owned by player")
                
                esprit, base = row
                
                # Validate fusion requirements
                if not cls._can_perform_fusion(esprit):
                    if esprit.quantity < 2:
                        raise ValueError(f"Need 2 copies for fusion, have {esprit.quantity}")
                    elif esprit.tier >= esprit.get_tier_cap():
                        raise ValueError(f"Esprit already at maximum tier ({esprit.get_tier_cap()})")
                    else:
                        raise ValueError("Fusion requirements not met")
                
                # Calculate and validate seios cost
                fusion_cost = cls._calculate_fusion_cost(esprit.tier)
                cost_validation = await CurrencyService.validate_currency_cost(
                    player_id, CurrencyType.SEIOS, fusion_cost
                )
                
                if not cost_validation.data["can_afford"]:
                    raise ValueError(
                        f"Insufficient seios. Need {fusion_cost:,}, have {cost_validation.data['current_amount']:,}"
                    )
                
                # Consume seios
                await CurrencyService.subtract_currency(
                    player_id, CurrencyType.SEIOS, fusion_cost, f"fusion_tier_{esprit.tier}_to_{esprit.tier + 1}"
                )
                
                # Store pre-fusion state for logging
                old_tier = esprit.tier
                old_quantity = esprit.quantity
                
                # Perform fusion
                esprit.tier += 1
                esprit.quantity -= 1  # 2 copies become 1 higher tier copy
                esprit.update_modification_time()
                
                await session.commit()
                
                # Update player's cached power
                await PowerService.update_player_cached_power(player_id)
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.ESPRIT_FUSED,
                    {
                        "esprit_id": esprit_id,
                        "esprit_base_id": base.id,
                        "esprit_name": base.name,
                        "from_tier": old_tier,
                        "to_tier": esprit.tier,
                        "from_quantity": old_quantity,
                        "to_quantity": esprit.quantity,
                        "seios_cost": fusion_cost
                    }
                )
                
                return {
                    "esprit_id": esprit_id,
                    "esprit_name": base.name,
                    "fusion_success": True,
                    "from_tier": old_tier,
                    "to_tier": esprit.tier,
                    "from_quantity": old_quantity,
                    "to_quantity": esprit.quantity,
                    "seios_spent": fusion_cost,
                    "power_gained": "Recalculate with PowerService"
                }
        
        return await cls._safe_execute(_operation, f"execute fusion for esprit {esprit_id}")
    
    @classmethod
    async def calculate_fusion_cost(cls, current_tier: int) -> ServiceResult[int]:
        """Calculate seios cost for fusion from current tier"""
        async def _operation():
            if current_tier < 1:
                raise ValueError("Invalid tier for fusion calculation")
            
            cost = cls._calculate_fusion_cost(current_tier)
            return cost
        
        return await cls._safe_execute(_operation, f"calculate fusion cost for tier {current_tier}")
    
    @classmethod
    async def validate_fusion_eligibility(cls, player_id: int, esprit_id: int) -> ServiceResult[Dict[str, Any]]:
        """Validate if fusion can be performed without executing it"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                # Get esprit data
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.id == esprit_id,
                        Esprit.owner_id == player_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                )
                
                result = await session.execute(stmt)
                row = result.first()
                
                if not row:
                    raise ValueError(f"Esprit {esprit_id} not found or not owned by player")
                
                esprit, base = row
                
                # Check all fusion requirements
                can_fuse = cls._can_perform_fusion(esprit)
                fusion_cost = cls._calculate_fusion_cost(esprit.tier)
                
                # Check seios availability
                cost_validation = await CurrencyService.validate_currency_cost(
                    player_id, CurrencyType.SEIOS, fusion_cost
                )
                
                # Determine specific failure reasons
                failure_reasons = []
                if esprit.quantity < 2:
                    failure_reasons.append(f"Need 2 copies, have {esprit.quantity}")
                if esprit.tier >= esprit.get_tier_cap():
                    failure_reasons.append(f"Already at max tier ({esprit.get_tier_cap()})")
                if not cost_validation.data["can_afford"]:
                    shortage = cost_validation.data["shortage"]
                    failure_reasons.append(f"Need {shortage:,} more seios")
                
                return {
                    "can_fuse": can_fuse and cost_validation.data["can_afford"],
                    "copy_requirement_met": esprit.quantity >= 2,
                    "tier_requirement_met": esprit.tier < esprit.get_tier_cap(),
                    "seios_requirement_met": cost_validation.data["can_afford"],
                    "fusion_cost": fusion_cost,
                    "current_seios": cost_validation.data["current_amount"],
                    "failure_reasons": failure_reasons
                }
        
        return await cls._safe_execute(_operation, f"validate fusion eligibility for esprit {esprit_id}")
    
    @classmethod
    def _calculate_fusion_cost(cls, current_tier: int) -> int:
        """Calculate seios cost for fusion based on current tier"""
        fusion_base_cost = ConfigManager.get("fusion.base_cost", 1000)
        tier_cost_multiplier = ConfigManager.get("fusion.tier_cost_multiplier", 500)
        
        return fusion_base_cost + (current_tier * tier_cost_multiplier)
    
    @classmethod
    def _can_perform_fusion(cls, esprit: Esprit) -> bool:
        """Check if esprit meets basic fusion requirements"""
        return (
            esprit.quantity >= 2 and 
            esprit.tier < esprit.get_tier_cap() and
            esprit.validate_tier()
        )
    
    @classmethod
    def _calculate_fusion_preview_power(cls, esprit: Esprit, base: EspritBase) -> Dict[str, Any]:
        """Calculate what power would be after fusion"""
        # Get scaling config
        tier_power_base = ConfigManager.get("power.tier_scaling_base", 1.0)
        tier_power_multiplier = ConfigManager.get("power.tier_scaling_multiplier", 0.15)
        element_bonus_multiplier = ConfigManager.get("power.element_bonus_multiplier", 0.05)
        
        # Calculate for next tier
        next_tier = esprit.tier + 1
        tier_multiplier = tier_power_base + ((next_tier - 1) * tier_power_multiplier)
        element_multiplier = 1.0 + element_bonus_multiplier
        total_multiplier = tier_multiplier * element_multiplier
        
        final_atk = int(base.base_atk * total_multiplier)
        final_def = int(base.base_def * total_multiplier)
        
        return {
            "atk": final_atk,
            "def": final_def,
            "power": final_atk + final_def,
            "tier_multiplier": tier_multiplier,
            "total_multiplier": total_multiplier
        }