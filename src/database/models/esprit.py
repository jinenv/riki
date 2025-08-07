# src/models/esprit.py
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from datetime import datetime
from src.utils.config_manager import ConfigManager

if TYPE_CHECKING:
    from src.models.esprit_base import EspritBase

class Esprit(SQLModel, table=True):
    """Universal stacking system for player-owned Esprits with fusion progression."""
    
    __tablename__ = "esprits" 
    __table_args__ = (
        UniqueConstraint("owner_id", "esprit_base_id", name="uq_player_esprit"),
        Index("ix_esprits_owner_id", "owner_id"),
        Index("ix_esprits_base_id", "esprit_base_id"),
        Index("ix_esprits_tier", "tier"),
        Index("ix_esprits_element", "element"),
        Index("ix_esprits_owner_tier", "owner_id", "tier"),
        Index("ix_esprits_power_calc", "tier", "element"),
    )
    
    # Core Identity
    id: Optional[int] = Field(default=None, primary_key=True)
    esprit_base_id: int = Field(foreign_key="esprit_bases.id", nullable=False, index=True)
    owner_id: int = Field(foreign_key="players.id", nullable=False, index=True)
    
    # Universal Stacking System
    quantity: int = Field(default=1, ge=1, sa_column=Column(BigInteger))
    
    # Progression System
    tier: int = Field(default=1, ge=1, le=6)
    
    # Cached Attributes
    element: str = Field(sa_column=Column(String), nullable=False)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_modified: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    def get_tier_display(self) -> str:
        """Format tier for display."""
        return f"Tier {self.tier}"
    
    def get_stack_display(self) -> str:
        """Format stack quantity for display."""
        base_display = self.get_tier_display()
        
        if self.quantity == 1:
            return base_display
        return f"{base_display} (×{self.quantity:,})"
    
    def validate_tier(self) -> bool:
        """Validate tier against configuration limits."""
        max_tier = ConfigManager.get("fusion.max_tier", 6)
        return 1 <= self.tier <= max_tier
    
    def get_tier_cap(self) -> int:
        """Get maximum tier from configuration."""
        return ConfigManager.get("fusion.max_tier", 6)
    
    def update_modification_time(self) -> None:
        """Update last modified timestamp."""
        self.last_modified = datetime.utcnow()
    
    def __repr__(self) -> str:
        return (
            f"<Esprit(id={self.id}, base_id={self.esprit_base_id}, "
            f"owner={self.owner_id}, T{self.tier}, "
            f"qty={self.quantity}, element={self.element})>"
        )