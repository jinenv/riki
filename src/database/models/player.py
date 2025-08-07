# src/models/player.py
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Index, JSON
from datetime import datetime

class Player(SQLModel, table=True):
    """Player model for Discord RPG with tower progression system."""
    
    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_discord_id", "discord_id"),
        Index("ix_players_attack_power", "attack_power"),
        Index("ix_players_current_floor", "current_floor"),
        Index("ix_players_last_active", "last_active"),
    )
    
    # Core Identity
    id: Optional[int] = Field(default=None, primary_key=True)
    discord_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: str = Field(default="Unknown Player", max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Progression Stats
    level: int = Field(default=1, ge=1)
    experience: int = Field(default=0, ge=0, sa_column=Column(BigInteger))
    
    # Resources
    energy: int = Field(default=50, ge=0)
    stamina: int = Field(default=25, ge=0)
    
    # Currencies
    seios: int = Field(default=1000, ge=0, sa_column=Column(BigInteger))
    ichor: int = Field(default=10, ge=0)
    erythl: int = Field(default=0, ge=0)
    
    # Combat Power - Pure MW Style
    attack_power: int = Field(default=0, ge=0, sa_column=Column(BigInteger))
    defense_power: int = Field(default=0, ge=0, sa_column=Column(BigInteger))
    
    # Collection Management
    leader_esprit_id: Optional[int] = Field(default=None, foreign_key="esprits.id")
    inventory: Optional[Dict[str, int]] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Tower Progression
    current_floor: int = Field(default=1, ge=1)
    highest_floor_reached: int = Field(default=1, ge=1)
    total_floor_clears: int = Field(default=0, ge=0)
    total_boss_kills: int = Field(default=0, ge=0)
    
    # Activity Tracking
    last_active: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_pray_time: Optional[datetime] = Field(default=None)
    last_clear_time: Optional[datetime] = Field(default=None)
    last_climb_time: Optional[datetime] = Field(default=None)
    last_energy_regen: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_stamina_regen: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Preferences
    pray_notifications: bool = Field(default=False)
    energy_notifications: bool = Field(default=False)
    
    # Simple Display Helpers Only
    def get_power_display(self) -> str:
        """Basic power formatting."""
        if self.attack_power >= 1_000_000:
            return f"{self.attack_power / 1_000_000:.1f}M"
        elif self.attack_power >= 1_000:
            return f"{self.attack_power / 1_000:.1f}K"
        else:
            return str(self.attack_power)
    
    def update_activity(self) -> None:
        """Update last active timestamp."""
        self.last_active = datetime.utcnow()
    
    def get_inventory_item_count(self, item_name: str) -> int:
        """Get count of specific inventory item."""
        if not self.inventory:
            return 0
        return self.inventory.get(item_name, 0)
    
    def __repr__(self) -> str:
        return f"<Player(id={self.id}, discord_id={self.discord_id}, level={self.level}, floor={self.current_floor}, atk={self.attack_power})>"