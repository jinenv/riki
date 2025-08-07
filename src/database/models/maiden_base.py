# src/database/models/maiden_base.py
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Index, String, Text

class MaidenBase(SQLModel, table=True):
    """Template definitions for all Maiden types in the game."""
    
    __tablename__ = "maiden_bases"
    __table_args__ = (
        Index("ix_maiden_bases_name", "name"),
        Index("ix_maiden_bases_element", "element"),
        Index("ix_maiden_bases_base_tier", "base_tier"),
        Index("ix_maiden_bases_power", "base_atk", "base_def"),
    )
    
    # Core Data Fields
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100)), nullable=False, index=True)
    element: str = Field(sa_column=Column(String(50)), nullable=False, index=True)
    base_tier: int = Field(default=1, ge=1, index=True)
    
    # Combat Stats
    base_atk: int = Field(default=10, ge=1)
    base_def: int = Field(default=10, ge=1)
    
    # Display Data
    description: str = Field(sa_column=Column(Text), nullable=False)
    image_url: str = Field(sa_column=Column(String(500)), nullable=False)
    portrait_url: str = Field(sa_column=Column(String(500)), nullable=False)
    
    # Simple Calculations Only
    def get_base_power(self) -> int:
        """Calculate total base power."""
        return self.base_atk + self.base_def
    
    def get_tier_display(self) -> str:
        """Format tier for display."""
        return f"Tier {self.base_tier}"
    
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
            f"<MaidenBase(id={self.id}, name='{self.name}', "
            f"element={self.element}, tier={self.base_tier}, "
            f"power={self.get_base_power()})>"
        )