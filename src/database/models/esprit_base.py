# src/models/esprit_base.py
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Index, String, Text

class EspritBase(SQLModel, table=True):
    """Template definitions for all Esprit types in the game."""
    
    __tablename__ = "esprit_bases"
    __table_args__ = (
        Index("ix_esprit_bases_name", "name"),
        Index("ix_esprit_bases_element", "element"),
        Index("ix_esprit_bases_base_tier", "base_tier"),
        Index("ix_esprit_bases_power", "base_atk", "base_def"),
    )
    
    # Core Data Fields
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(100)), nullable=False, index=True)
    element: str = Field(sa_column=Column(String(50)), nullable=False, index=True)
    base_tier: int = Field(default=1, ge=1, le=6, index=True)
    
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
    
    def __repr__(self) -> str:
        return (
            f"<EspritBase(id={self.id}, name='{self.name}', "
            f"element={self.element}, tier={self.base_tier}, "
            f"power={self.get_base_power()})>"
        )