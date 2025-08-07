# src/services/player_service.py
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select

from src.services.base_service import BaseService, ServiceResult
from src.database.models.player import Player
from src.utils.database_service import DatabaseService
from src.utils.transaction_logger import transaction_logger, TransactionType
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PlayerService(BaseService):
    """Core player operations and progression management"""
    
    @classmethod
    async def create_player(cls, discord_id: int, username: str = "Unknown Player") -> ServiceResult[Dict[str, Any]]:
        """Create new player account"""
        async def _operation():
            if not isinstance(discord_id, int) or discord_id <= 0:
                raise ValueError("Invalid Discord ID")
            
            async with DatabaseService.get_transaction() as session:
                # Check if player already exists
                existing_stmt = select(Player).where(Player.discord_id == discord_id)
                existing_player = (await session.execute(existing_stmt)).scalar_one_or_none()
                
                if existing_player:
                    raise ValueError("Player already exists")
                
                # Create new player with default values
                new_player = Player(
                    discord_id=discord_id,
                    username=username[:100],  # Truncate username
                    level=1,
                    experience=0,
                    energy=ConfigManager.get("player.base_energy", 50),
                    stamina=ConfigManager.get("player.base_stamina", 25),
                    seios=1000,  # Starting currency
                    ichor=10,    # Starting ichor for first summons
                    erythl=0,    # Premium currency starts at 0
                    attack_power=0,
                    defense_power=0,
                    current_floor=1,
                    highest_floor_reached=1,
                    total_floor_clears=0,
                    total_boss_kills=0,
                    raid_progress=0.0,
                    building_slots=3,  # Starting building slots
                    pray_notifications=False,
                    energy_notifications=False
                )
                
                session.add(new_player)
                await session.flush()  # Get the player ID
                
                await session.commit()
                
                # Log player creation
                transaction_logger.log_transaction(
                    new_player.id,
                    TransactionType.PLAYER_CREATED,
                    {
                        "discord_id": discord_id,
                        "username": username,
                        "starting_seios": new_player.seios,
                        "starting_ichor": new_player.ichor
                    }
                )
                
                return {
                    "player_id": new_player.id,
                    "discord_id": discord_id,
                    "username": username,
                    "level": new_player.level,
                    "starting_resources": {
                        "seios": new_player.seios,
                        "ichor": new_player.ichor,
                        "energy": new_player.energy,
                        "stamina": new_player.stamina
                    }
                }
        
        return await cls._safe_execute(_operation, f"create player for discord_id {discord_id}")
    
    @classmethod
    async def get_player_by_discord_id(cls, discord_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get player by Discord ID"""
        async def _operation():
            if not isinstance(discord_id, int) or discord_id <= 0:
                raise ValueError("Invalid Discord ID")
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.discord_id == discord_id)
                player = (await session.execute(stmt)).scalar_one_or_none()
                
                if not player:
                    raise ValueError("Player not found")
                
                return {
                    "player_id": player.id,
                    "discord_id": player.discord_id,
                    "username": player.username,
                    "level": player.level,
                    "experience": player.experience,
                    "energy": player.energy,
                    "stamina": player.stamina,
                    "seios": player.seios,
                    "ichor": player.ichor,
                    "erythl": player.erythl,
                    "attack_power": player.attack_power,
                    "defense_power": player.defense_power,
                    "current_floor": player.current_floor,
                    "highest_floor_reached": player.highest_floor_reached,
                    "raid_progress": player.raid_progress,
                    "created_at": player.created_at,
                    "last_active": player.last_active
                }
        
        return await cls._safe_execute(_operation, f"get player by discord_id {discord_id}")
    
    @classmethod
    async def add_experience(cls, player_id: int, amount: int, source: str = "unknown") -> ServiceResult[Dict[str, Any]]:
        """Add experience and handle level ups"""
        async def _operation():
            cls._validate_player_id(player_id)
            cls._validate_positive_amount(amount, "experience")
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                old_level = player.level
                old_experience = player.experience
                
                # Add experience
                player.experience += amount
                
                # Check for level ups
                levels_gained = 0
                while True:
                    experience_needed = cls._get_experience_for_level(player.level + 1)
                    if player.experience >= experience_needed:
                        player.level += 1
                        levels_gained += 1
                    else:
                        break
                
                player.update_activity()
                await session.commit()
                
                # Log experience gain
                transaction_logger.log_transaction(
                    player_id,
                    TransactionType.CURRENCY_GAIN,
                    {
                        "currency_type": "experience",
                        "amount": amount,
                        "source": source,
                        "old_experience": old_experience,
                        "new_experience": player.experience,
                        "old_level": old_level,
                        "new_level": player.level,
                        "levels_gained": levels_gained
                    }
                )
                
                # Log level gains separately
                if levels_gained > 0:
                    transaction_logger.log_transaction(
                        player_id,
                        TransactionType.LEVEL_GAINED,
                        {
                            "from_level": old_level,
                            "to_level": player.level,
                            "levels_gained": levels_gained,
                            "trigger_source": source
                        }
                    )
                
                return {
                    "experience_gained": amount,
                    "old_experience": old_experience,
                    "new_experience": player.experience,
                    "old_level": old_level,
                    "new_level": player.level,
                    "levels_gained": levels_gained,
                    "source": source
                }
        
        return await cls._safe_execute(_operation, f"add experience to player {player_id}")
    
    @classmethod
    async def get_level_info(cls, player_id: int) -> ServiceResult[Dict[str, Any]]:
        """Get detailed level and experience information"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            async with DatabaseService.get_session() as session:
                stmt = select(Player).where(Player.id == player_id)
                player = (await session.execute(stmt)).scalar_one()
                
                current_level_xp = cls._get_experience_for_level(player.level)
                next_level_xp = cls._get_experience_for_level(player.level + 1)
                experience_to_next = max(0, next_level_xp - player.experience)
                
                # Calculate progress percentage
                if player.level == 1:
                    progress = min(1.0, player.experience / next_level_xp) if next_level_xp > 0 else 0.0
                else:
                    level_experience = player.experience - current_level_xp
                    level_requirement = next_level_xp - current_level_xp
                    progress = max(0.0, min(1.0, level_experience / level_requirement)) if level_requirement > 0 else 0.0
                
                return {
                    "current_level": player.level,
                    "current_experience": player.experience,
                    "experience_for_current_level": current_level_xp,
                    "experience_for_next_level": next_level_xp,
                    "experience_to_next_level": experience_to_next,
                    "progress_percentage": progress,
                    "energy_cap": cls._calculate_energy_cap(player),
                    "stamina_cap": cls._calculate_stamina_cap(player)
                }
        
        return await cls._safe_execute(_operation, f"get level info for player {player_id}")
    
    @classmethod
    async def update_username(cls, player_id: int, new_username: str) -> ServiceResult[Dict[str, Any]]:
        """Update player username"""
        async def _operation():
            cls._validate_player_id(player_id)
            
            if not new_username or len(new_username.strip()) == 0:
                raise ValueError("Username cannot be empty")
            
            cleaned_username = new_username.strip()[:100]
            
            async with DatabaseService.get_transaction() as session:
                stmt = select(Player).where(Player.id == player_id).with_for_update()
                player = (await session.execute(stmt)).scalar_one()
                
                old_username = player.username
                player.username = cleaned_username
                player.update_activity()
                
                await session.commit()
                
                return {
                    "old_username": old_username,
                    "new_username": cleaned_username,
                    "updated_at": player.last_active
                }
        
        return await cls._safe_execute(_operation, f"update username for player {player_id}")
    
    @classmethod
    async def get_or_create_player(cls, discord_id: int, username: str = "Unknown Player") -> ServiceResult[Dict[str, Any]]:
        """Get existing player or create new one"""
        async def _operation():
            # Try to get existing player first
            get_result = await cls.get_player_by_discord_id(discord_id)
            
            if get_result.success:
                return get_result.data
            
            # Create new player if not found
            create_result = await cls.create_player(discord_id, username)
            
            if create_result.success:
                # Return player data in same format as get_player
                player_data = create_result.data
                return {
                    "player_id": player_data["player_id"],
                    "discord_id": player_data["discord_id"],
                    "username": player_data["username"],
                    "level": player_data["level"],
                    "experience": 0,
                    "energy": player_data["starting_resources"]["energy"],
                    "stamina": player_data["starting_resources"]["stamina"],
                    "seios": player_data["starting_resources"]["seios"],
                    "ichor": player_data["starting_resources"]["ichor"],
                    "erythl": 0,
                    "attack_power": 0,
                    "defense_power": 0,
                    "current_floor": 1,
                    "highest_floor_reached": 1,
                    "raid_progress": 0.0,
                    "created_at": datetime.utcnow(),
                    "last_active": datetime.utcnow()
                }
            else:
                raise ValueError(f"Failed to create player: {create_result.error}")
        
        return await cls._safe_execute(_operation, f"get or create player for discord_id {discord_id}")
    
    @classmethod
    def _get_experience_for_level(cls, level: int) -> int:
        """Calculate total experience required to reach a specific level"""
        if level <= 1:
            return 0
        
        xp_base = ConfigManager.get("player.xp_base", 1000)
        xp_multiplier = ConfigManager.get("player.xp_multiplier", 1.15)
        
        num_terms = level - 1
        
        # Geometric series formula for O(1) efficiency
        if xp_multiplier == 1.0:
            total_xp = xp_base * num_terms
        else:
            total_xp = xp_base * (1 - xp_multiplier**num_terms) / (1 - xp_multiplier)
        
        return int(total_xp)
    
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