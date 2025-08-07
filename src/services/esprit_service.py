# src/services/esprit_service.py
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from sqlalchemy import select, and_

from src.services.base_service import BaseService, ServiceResult
from src.services.currency_service import CurrencyService, CurrencyType
from src.database.models.player import Player
from src.database.models.esprit import Esprit
from src.database.models.esprit_base import EspritBase
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SummonResult:
    """Result of a single esprit summon"""
    esprit_base_id: int
    esprit_name: str
    tier: int
    element: str
    is_new: bool
    quantity_gained: int
    total_quantity: int

class EspritService(BaseService):
    """Gacha summoning and esprit collection management"""
    
    @classmethod
    async def summon_esprit(cls, player_id: int) -> ServiceResult[SummonResult]:
        """Summon a random esprit using 1 ichor"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            # Validate ichor cost
            ichor_cost = ConfigManager.get("summoning.ichor_cost", 1)
            validation_result = await CurrencyService.validate_currency_cost(
                player_id, CurrencyType.ICHOR, ichor_cost
            )
            
            if not validation_result.data["can_afford"]:
                raise ValueError(f"Insufficient ichor. Need {ichor_cost}, have {validation_result.data['current_amount']}")
            
            async with DatabaseService.get_transaction() as session:
                # Consume ichor
                await CurrencyService.subtract_currency(
                    player_id, CurrencyType.ICHOR, ichor_cost, "esprit_summon"
                )
                
                # Get summon rates
                summon_config = ConfigManager.get("summoning") or {}
                rates = summon_config.get("rates", {"1": 0.7, "2": 0.2, "3": 0.08, "4": 0.02})
                
                # Perform gacha roll
                selected_tier = cls._select_tier_by_probability(rates)
                
                # Get random esprit of selected tier
                esprit_base = await cls._get_random_esprit_by_tier(session, selected_tier)
                
                # Add to player collection
                summon_result = await cls._add_esprit_to_collection(
                    session, player_id, esprit_base.id, esprit_base.name, 
                    esprit_base.base_tier, esprit_base.element
                )
                
                await session.commit()
                
                # Log transaction
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.ESPRIT_SUMMONED,
                    {
                        "esprit_base_id": esprit_base.id,
                        "esprit_name": esprit_base.name,
                        "tier": esprit_base.base_tier,
                        "element": esprit_base.element,
                        "ichor_cost": ichor_cost,
                        "is_new": summon_result.is_new,
                        "quantity_gained": summon_result.quantity_gained
                    }
                )
                
                return summon_result
        
        return await cls._safe_execute(_operation, f"summon esprit for player {player_id}")
    
    @classmethod
    async def get_player_collection(cls, player_id: int, limit: int = 50, offset: int = 0) -> ServiceResult[Dict[str, Any]]:
        """Get player's esprit collection with pagination"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                # Get player's esprits with base data
                stmt = select(Esprit, EspritBase).where(
                    and_(
                        Esprit.owner_id == player_id,
                        Esprit.esprit_base_id == EspritBase.id
                    )
                ).order_by(
                    EspritBase.base_tier.desc(),
                    Esprit.tier.desc(),
                    Esprit.quantity.desc()
                ).limit(limit).offset(offset)
                
                results = await session.execute(stmt)
                esprit_data = []
                
                for esprit, base in results:
                    esprit_data.append({
                        "esprit_id": esprit.id,
                        "esprit_base_id": base.id,
                        "name": base.name,
                        "element": esprit.element,
                        "base_tier": base.base_tier,
                        "current_tier": esprit.tier,
                        "quantity": esprit.quantity,
                        "tier_display": esprit.get_tier_display(),
                        "stack_display": esprit.get_stack_display(),
                        "base_atk": base.base_atk,
                        "base_def": base.base_def,
                        "base_power": base.get_base_power()
                    })
                
                # Get collection statistics
                total_stmt = select(Esprit).where(Esprit.owner_id == player_id)
                total_results = await session.execute(total_stmt)
                total_esprits = len(list(total_results.scalars().all()))
                
                return {
                    "esprits": esprit_data,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total_count": total_esprits,
                        "has_more": (offset + limit) < total_esprits
                    }
                }
        
        return await cls._safe_execute(_operation, f"get collection for player {player_id}")
    
    @classmethod
    async def get_esprit_details(cls, esprit_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get detailed information about a specific esprit"""
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
                
                return {
                    "esprit_id": esprit.id,
                    "owner_id": esprit.owner_id,
                    "esprit_base_id": base.id,
                    "name": base.name,
                    "description": base.description,
                    "element": esprit.element,
                    "base_tier": base.base_tier,
                    "current_tier": esprit.tier,
                    "tier_cap": esprit.get_tier_cap(),
                    "quantity": esprit.quantity,
                    "base_atk": base.base_atk,
                    "base_def": base.base_def,
                    "base_power": base.get_base_power(),
                    "image_url": base.image_url,
                    "portrait_url": base.portrait_url,
                    "created_at": esprit.created_at,
                    "last_modified": esprit.last_modified
                }
        
        return await cls._safe_execute(_operation, f"get esprit details {esprit_id}")
    
    @classmethod
    async def validate_esprit_ownership(cls, player_id: int, esprit_id: int) -> ServiceResult[bool]:
        """Validate that player owns the specified esprit"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Esprit).where(
                    and_(
                        Esprit.id == esprit_id,
                        Esprit.owner_id == player_id
                    )
                )
                
                result = await session.execute(stmt)
                esprit = result.scalar_one_or_none()
                
                return esprit is not None
        
        return await cls._safe_execute(_operation, f"validate ownership for esprit {esprit_id}")
    
    @classmethod
    async def _add_esprit_to_collection(
        cls, 
        session, 
        player_id: int, 
        esprit_base_id: int, 
        name: str, 
        tier: int, 
        element: str
    ) -> SummonResult:
        """Add esprit to player collection or stack existing"""
        # Check if player already owns this esprit type
        existing_stmt = select(Esprit).where(
            and_(
                Esprit.owner_id == player_id,
                Esprit.esprit_base_id == esprit_base_id
            )
        ).with_for_update()
        
        existing_esprit = (await session.execute(existing_stmt)).scalar_one_or_none()
        
        if existing_esprit:
            # Stack with existing esprit
            old_quantity = existing_esprit.quantity
            existing_esprit.quantity += 1
            existing_esprit.update_modification_time()
            
            return SummonResult(
                esprit_base_id=esprit_base_id,
                esprit_name=name,
                tier=tier,
                element=element,
                is_new=False,
                quantity_gained=1,
                total_quantity=existing_esprit.quantity
            )
        else:
            # Create new esprit entry
            new_esprit = Esprit(
                esprit_base_id=esprit_base_id,
                owner_id=player_id,
                quantity=1,
                tier=1,  # All summoned esprits start at tier 1
                element=element
            )
            
            session.add(new_esprit)
            await session.flush()  # Get the ID
            
            return SummonResult(
                esprit_base_id=esprit_base_id,
                esprit_name=name,
                tier=tier,
                element=element,
                is_new=True,
                quantity_gained=1,
                total_quantity=1
            )
    
    @classmethod
    def _select_tier_by_probability(cls, rates: Dict[str, float]) -> int:
        """Select tier based on probability rates"""
        roll = random.random()
        cumulative = 0.0
        
        # Sort by tier (lowest first for proper cumulative distribution)
        sorted_tiers = sorted(rates.keys(), key=int)
        
        for tier_str in sorted_tiers:
            cumulative += rates[tier_str]
            if roll <= cumulative:
                return int(tier_str)
        
        # Fallback to highest tier
        return int(sorted_tiers[-1])
    
    @classmethod
    async def _get_random_esprit_by_tier(cls, session, tier: int) -> EspritBase:
        """Get random esprit base of specified tier"""
        stmt = select(EspritBase).where(EspritBase.base_tier == tier)
        available_esprits = list((await session.execute(stmt)).scalars().all())
        
        if not available_esprits:
            # Fallback to tier 1 if no esprits found
            stmt = select(EspritBase).where(EspritBase.base_tier == 1)
            available_esprits = list((await session.execute(stmt)).scalars().all())
        
        if not available_esprits:
            raise ValueError("No esprit bases found in database")
        
        return random.choice(available_esprits)