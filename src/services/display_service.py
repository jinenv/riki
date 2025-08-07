# src/services/display_service.py
import discord
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.services.base_service import BaseService, ServiceResult
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DisplayService(BaseService):
    """Discord embed formatting and interactive display system"""
    
    # SEIO Theme Colors
    PRIMARY_COLOR = 0x2c2d31  # Dark theme as specified
    SUCCESS_COLOR = 0x2d5a2d  # Dark green for victories
    ERROR_COLOR = 0x5a2d2d    # Dark red for failures  
    WARNING_COLOR = 0x5a5a2d  # Dark yellow for warnings
    INFO_COLOR = 0x2d2d5a     # Dark blue for information
    
    @classmethod
    async def create_prayer_result_embed(cls, prayer_data: Dict[str, Any]) -> ServiceResult[discord.Embed]:
        """Create embed for prayer command result"""
        async def _operation():
            embed = disnake.Embed(
                title="🩸 Prayer Completed",
                color=cls.PRIMARY_COLOR,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Ichor Gained",
                value=f"+{prayer_data['ichor_gained']} 🩸",
                inline=True
            )
            
            embed.add_field(
                name="Total Ichor",
                value=f"{prayer_data['total_ichor']} 🩸",
                inline=True
            )
            
            # Next prayer time
            next_prayer = prayer_data['next_prayer_time']
            embed.add_field(
                name="Next Prayer",
                value=f"<t:{int(next_prayer.timestamp())}:R>",
                inline=True
            )
            
            embed.set_footer(text="Use 's summon' to use ichor for Esprit summoning")
            
            return embed
        
        return await cls._safe_execute(_operation, "create prayer result embed")
    
    @classmethod
    async def create_summon_result_embed(cls, summon_data: Dict[str, Any]) -> ServiceResult[disnake.Embed]:
        """Create embed for esprit summoning result"""
        async def _operation():
            result = summon_data
            
            # Color based on tier
            tier_colors = {
                1: 0x808080,  # Gray
                2: 0x90EE90,  # Light Green  
                3: 0x4169E1,  # Royal Blue
                4: 0x9932CC,  # Dark Orchid
                5: 0xFFD700,  # Gold
                6: 0xFF4500   # Orange Red
            }
            
            embed_color = tier_colors.get(result['tier'], cls.PRIMARY_COLOR)
            
            embed = disnake.Embed(
                title="✨ Esprit Summoned!",
                color=embed_color,
                timestamp=datetime.utcnow()
            )
            
            # Esprit details
            embed.add_field(
                name="Esprit",
                value=f"**{result['esprit_name']}**",
                inline=False
            )
            
            embed.add_field(
                name="Element",
                value=f"{cls._get_element_emoji(result['element'])} {result['element']}",
                inline=True
            )
            
            embed.add_field(
                name="Tier",
                value=f"⭐ Tier {result['tier']}",
                inline=True
            )
            
            # Collection status
            if result['is_new']:
                embed.add_field(
                    name="Status",
                    value="🆕 **NEW ESPRIT!**",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Status",
                    value=f"📚 Added to collection (×{result['total_quantity']})",
                    inline=True
                )
            
            embed.set_footer(text="Use 's collection' to view all your Esprits")
            
            return embed
        
        return await cls._safe_execute(_operation, "create summon result embed")
    
    @classmethod
    async def create_combat_result_embed(cls, combat_data: Dict[str, Any]) -> ServiceResult[disnake.Embed]:
        """Create embed for tower combat results"""
        async def _operation():
            result = combat_data
            
            if result['victory']:
                embed = disnake.Embed(
                    title="⚔️ Floor Cleared!",
                    color=cls.SUCCESS_COLOR,
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="Victory!",
                    value=f"Floor {result['from_floor']} → **Floor {result['to_floor']}**",
                    inline=False
                )
                
                embed.add_field(
                    name="Stamina Used",
                    value=f"⚡ {result['stamina_used']}",
                    inline=True
                )
                
                embed.add_field(
                    name="Damage Dealt",
                    value=f"💥 {result['combat_result']['damage_dealt']:,}",
                    inline=True
                )
                
                embed.add_field(
                    name="Highest Floor",
                    value=f"🏗️ {result['new_highest']}",
                    inline=True
                )
                
                embed.set_footer(text="Use 's raid' to collect idle loot from your new floor!")
                
            else:
                embed = disnake.Embed(
                    title="⚔️ Combat Failed",
                    color=cls.ERROR_COLOR,
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="Boss Survived",
                    value=f"Floor {result['floor']} boss withstood your attack",
                    inline=False
                )
                
                embed.add_field(
                    name="Damage Dealt",
                    value=f"💥 {result['combat_result']['damage_dealt']:,}",
                    inline=True
                )
                
                embed.add_field(
                    name="Boss Health",
                    value=f"❤️ {result['combat_result']['boss_health_remaining']:,} remaining",
                    inline=True
                )
                
                embed.add_field(
                    name="Stamina Used",
                    value=f"⚡ {result['stamina_used']}",
                    inline=True
                )
                
                embed.set_footer(text="Fuse Esprits or use more stamina for your next attempt!")
            
            return embed
        
        return await cls._safe_execute(_operation, "create combat result embed")
    
    @classmethod
    async def create_raid_result_embed(cls, raid_data: Dict[str, Any]) -> ServiceResult[Dict[str, Any]]:
        """Create interactive embed for raid results with buttons"""
        async def _operation():
            result = raid_data
            
            embed = disnake.Embed(
                title=f"🏗️ Floor {result['floor']} Raid Complete",
                color=cls.PRIMARY_COLOR,
                timestamp=datetime.utcnow()
            )
            
            # Time summary
            hours = result['idle_time_hours']
            if hours >= 1:
                time_str = f"{hours:.1f} hours"
            else:
                minutes = int(hours * 60)
                time_str = f"{minutes} minutes"
            
            embed.add_field(
                name="Idle Time",
                value=f"⏰ {time_str}",
                inline=True
            )
            
            # Loot gained
            loot = result['loot_gained']
            loot_text = []
            
            if loot['seios'] > 0:
                loot_text.append(f"🪙 {loot['seios']:,} Seios")
            
            if loot['erythl'] > 0:
                loot_text.append(f"💎 {loot['erythl']} Erythl")
            
            if loot.get('encounters'):
                for encounter in loot['encounters']:
                    if encounter['type'] == 'treasure_chest':
                        loot_text.append(f"📦 Treasure Chest (+{encounter['bonus_seios']} Seios)")
            
            embed.add_field(
                name="Loot Collected",
                value="\n".join(loot_text) if loot_text else "No loot this time",
                inline=True
            )
            
            # Progress bar
            progress = result['progress_to_next_floor']
            progress_bar = cls._create_progress_bar(progress)
            
            embed.add_field(
                name="Floor Progress",
                value=f"{progress_bar} {progress*100:.1f}%",
                inline=False
            )
            
            # Next floor availability
            if result['can_attempt_next_floor']:
                embed.add_field(
                    name="🆙 Ready!",
                    value="You can attempt the next floor with 's climb'!",
                    inline=False
                )
            
            # Create view with buttons for future interactions
            view = disnake.ui.View(timeout=300)
            
            # Collection button
            collection_button = disnake.ui.Button(
                label="View Collection",
                emoji="📚",
                style=disnake.ButtonStyle.secondary
            )
            view.add_item(collection_button)
            
            # Power button  
            power_button = disnake.ui.Button(
                label="Check Power",
                emoji="💪",
                style=disnake.ButtonStyle.secondary
            )
            view.add_item(power_button)
            
            # Fusion button (if applicable)
            if loot['seios'] > 1000:  # If gained significant seios
                fusion_button = disnake.ui.Button(
                    label="Fusion Shop",
                    emoji="⚗️",
                    style=disnake.ButtonStyle.primary
                )
                view.add_item(fusion_button)
            
            embed.set_footer(text="Buttons expire in 5 minutes • Use commands for full access")
            
            return {
                "embed": embed,
                "view": view
            }
        
        return await cls._safe_execute(_operation, "create raid result embed")
    
    @classmethod
    async def create_collection_embed(cls, collection_data: Dict[str, Any], page: int = 1) -> ServiceResult[disnake.Embed]:
        """Create embed showing player's esprit collection"""
        async def _operation():
            embed = disnake.Embed(
                title="📚 Your Esprit Collection",
                color=cls.PRIMARY_COLOR,
                timestamp=datetime.utcnow()
            )
            
            esprits = collection_data['esprits']
            pagination = collection_data['pagination']
            
            if not esprits:
                embed.description = "No Esprits found. Use 's summon' to get your first Esprit!"
                return embed
            
            # Add each esprit
            for esprit in esprits[:10]:  # Limit to 10 per page
                power_display = cls._format_power_display(esprit['base_power'])
                
                value_parts = [
                    f"{cls._get_element_emoji(esprit['element'])} {esprit['element']}",
                    f"⭐ {esprit['stack_display']}",
                    f"💪 {power_display} power"
                ]
                
                embed.add_field(
                    name=esprit['name'],
                    value=" • ".join(value_parts),
                    inline=False
                )
            
            # Pagination info
            total_pages = (pagination['total_count'] + 9) // 10  # Ceiling division
            embed.set_footer(
                text=f"Page {page}/{total_pages} • {pagination['total_count']} total Esprits"
            )
            
            return embed
        
        return await cls._safe_execute(_operation, "create collection embed")
    
    @classmethod
    async def create_status_embed(cls, player_data: Dict[str, Any]) -> ServiceResult[disnake.Embed]:
        """Create comprehensive status embed for player"""
        async def _operation():
            embed = disnake.Embed(
                title=f"📊 {player_data.get('username', 'Player')} Status",
                color=cls.PRIMARY_COLOR,
                timestamp=datetime.utcnow()
            )
            
            # Resources
            resources = player_data.get('resources', {})
            embed.add_field(
                name="🔋 Resources",
                value=(
                    f"⚡ Energy: {resources.get('energy', 0)}/{resources.get('energy_cap', 0)}\n"
                    f"💪 Stamina: {resources.get('stamina', 0)}/{resources.get('stamina_cap', 0)}"
                ),
                inline=True
            )
            
            # Currencies  
            embed.add_field(
                name="💰 Currencies",
                value=(
                    f"🪙 Seios: {player_data.get('seios', 0):,}\n"
                    f"🩸 Ichor: {player_data.get('ichor', 0)}\n"
                    f"💎 Erythl: {player_data.get('erythl', 0)}"
                ),
                inline=True
            )
            
            # Tower Progress
            tower = player_data.get('tower', {})
            embed.add_field(
                name="🏗️ Tower",
                value=(
                    f"Current Floor: {tower.get('current_floor', 1)}\n"
                    f"Highest: {tower.get('highest_floor', 1)}\n"
                    f"Progress: {tower.get('progress', 0)*100:.1f}%"
                ),
                inline=True
            )
            
            # Power
            power = player_data.get('total_power', 0)
            embed.add_field(
                name="💪 Combat Power",
                value=cls._format_power_display(power),
                inline=True
            )
            
            # Level & XP
            level_data = player_data.get('level', {})
            embed.add_field(
                name="📈 Level",
                value=(
                    f"Level {level_data.get('current', 1)}\n"
                    f"XP: {level_data.get('progress', 0)*100:.1f}%"
                ),
                inline=True
            )
            
            return embed
        
        return await cls._safe_execute(_operation, "create status embed")
    
    @classmethod
    def _create_progress_bar(cls, progress: float, length: int = 10) -> str:
        """Create ASCII progress bar"""
        filled = int(progress * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    @classmethod
    def _get_element_emoji(cls, element: str) -> str:
        """Get emoji for element type"""
        element_emojis = ConfigManager.get("element_system.emojis", {
            "Inferno": "🔥",
            "Aqua": "💧", 
            "Tempest": "⚡",
            "Earth": "🌿",
            "Umbral": "🌑",
            "Radiant": "✨"
        })
        
        return element_emojis.get(element, "❓")
    
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