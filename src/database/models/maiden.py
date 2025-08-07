# src/database/models/maiden.py
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from datetime import datetime
from src.utils.config_manager import ConfigManager

class Maiden(SQLModel, table=True):
    """Universal stacking system for player-owned maidens with fusion progression."""
    
    __tablename__ = "maidens"
    __table_args__ = (
        UniqueConstraint("player_id", "maiden_base_id", "tier", name="uq_player_maiden_tier"),
        Index("ix_maidens_player_id", "player_id"),
        Index("ix_maidens_base_id", "maiden_base_id"),
        Index("ix_maidens_tier", "tier"),
        Index("ix_maidens_element", "element"),
        Index("ix_maidens_player_tier", "player_id", "tier"),
        Index("ix_maidens_fusable", "player_id", "tier", "quantity"),
    )
    
    # Core Identity
    id: Optional[int] = Field(default=None, primary_key=True)
    maiden_base_id: int = Field(foreign_key="maiden_bases.id", nullable=False, index=True)
    player_id: int = Field(
        sa_column=Column(BigInteger, nullable=False),
        foreign_key="players.discord_id"
    )
    
    # Universal Stacking System
    quantity: int = Field(default=1, ge=0, sa_column=Column(BigInteger))
    
    # Progression System
    tier: int = Field(default=1, ge=1)
    
    # Cached Attributes
    element: str = Field(sa_column=Column(String(20)), nullable=False)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_modified: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Acquisition tracking
    acquired_from: str = Field(default="summon", max_length=50)
    fusion_count: int = Field(default=0, ge=0)
    
    def get_tier_display(self) -> str:
        """Format tier for display."""
        return f"Tier {self.tier}"
    
    def get_stack_display(self) -> str:
        """Format stack quantity for display."""
        base_display = self.get_tier_display()
        
        if self.quantity == 0:
            return f"{base_display} (Fused)"
        elif self.quantity == 1:
            return base_display
        else:
            return f"{base_display} (×{self.quantity:,})"
    
    def can_fuse(self) -> bool:
        """Check if this maiden stack can be used for fusion."""
        max_tier = self.get_tier_cap()
        return self.quantity >= 2 and self.tier < max_tier
    
    def get_fusion_cost(self) -> int:
        """Calculate rikies cost for fusion to next tier."""
        base_cost = ConfigManager.get("fusion.base_cost", 1000)
        multiplier = ConfigManager.get("fusion.cost_multiplier", 2.5)
        return int(base_cost * (multiplier ** (self.tier - 1)))
    
    def validate_tier(self) -> bool:
        """Validate tier against configuration limits."""
        max_tier = self.get_tier_cap()
        return 1 <= self.tier <= max_tier
    
    def get_tier_cap(self) -> int:
        """Get maximum tier from configuration."""
        return ConfigManager.get("fusion.current_max_tier", 6)
    
    def update_modification_time(self) -> None:
        """Update last modified timestamp."""
        self.last_modified = datetime.utcnow()
    
    def get_element_emoji(self) -> str:
        """Get emoji representation of element."""
        element_emojis = {
            "infernal": "🔥",
            "umbral": "🌑",
            "earth": "🌍",
            "tempest": "⚡",
            "radiant": "✨",
            "abyssal": "🌊"
        }
        return element_emojis.get(self.element, "❓")
    
    def __repr__(self) -> str:
        return (
            f"<Maiden(id={self.id}, base_id={self.maiden_base_id}, "
            f"player={self.player_id}, T{self.tier}, "
            f"qty={self.quantity}, element={self.element})>"
        )