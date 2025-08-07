from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import BigInteger, Index, JSON, String, Numeric, CheckConstraint
from datetime import datetime

class Player(SQLModel, table=True):
    """Player model for RIKI RPG with strategic progression system."""
    
    __tablename__ = "players" 
    __table_args__ = (
        Index("ix_players_discord_id", "discord_id"),
        Index("ix_players_total_attack", "total_attack"),
        Index("ix_players_total_power", "total_power"),
        Index("ix_players_current_zone", "current_zone"),
        Index("ix_players_last_active", "last_active"),
        Index("ix_players_onboarding_state", "onboarding_state"),
        Index("ix_players_tutorial_step", "current_tutorial_step"),
    )
    
    # Core Identity
    id: Optional[int] = Field(default=None, primary_key=True)
    discord_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: str = Field(default="Unknown Player", max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Progression Stats - Allow level 0 for new/skipped players
    level: int = Field(default=0, ge=0)  # Start at 0, gain levels through gameplay
    experience: int = Field(default=0, ge=0, sa_column=Column(BigInteger))
    
    # RIKI Point Allocation System - Strategic Build Choices
    energy_investment: int = Field(default=0, ge=0)      # Points allocated to energy capacity
    stamina_investment: int = Field(default=0, ge=0)     # Points allocated to stamina capacity  
    attack_investment: int = Field(default=0, ge=0)      # Points allocated to attack bonus
    defense_investment: int = Field(default=0, ge=0)     # Points allocated to defense bonus
    available_skill_points: int = Field(default=0, ge=0) # Unspent points from leveling
    
    # Resources - Current values with investment scaling
    energy: int = Field(default=50, ge=0)   # Current energy available
    stamina: int = Field(default=25, ge=0)  # Current stamina available
    
    # RIKI Currencies - Start at 0 for tutorial grants
    grace: int = Field(default=0, ge=0)                                    # Riki's Grace - summoning currency
    rikies: int = Field(default=0, ge=0, sa_column=Column(BigInteger))     # Rikies - primary currency
    rikishi_shards: int = Field(default=0, ge=0)                          # Rikishi Shards - premium currency
    
    # Combat Stats - Cached totals from maiden collection + investments
    total_attack: int = Field(default=0, ge=0, sa_column=Column(BigInteger))   # Total attack for damage calculations
    total_defense: int = Field(default=0, ge=0, sa_column=Column(BigInteger))  # Total defense for damage reduction
    total_power: int = Field(default=0, ge=0, sa_column=Column(BigInteger))    # Combined power for raid scaling
    
    # Collection Management - Fixed foreign key reference
    leader_maiden_id: Optional[int] = Field(default=None, foreign_key="maiden_collection.id")
    
    # Zone Progression (embedded for MVP)
    current_zone: int = Field(default=1, ge=1)
    current_subzone: int = Field(default=1, ge=1)
    zone_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    highest_zone_reached: int = Field(default=1, ge=1)
    total_zone_clears: int = Field(default=0, ge=0)
    total_boss_kills: int = Field(default=0, ge=0)
    
    # Artifact System (JSON field for MVP)
    artifacts: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    # Structure: {"artifact_id": {"fragments": 5, "total_needed": 10, "completed": False}}
    
    # Achievement System
    achievements: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, server_default="{}")
    )
    # Structure: {"achievement_id": {"earned_at": "2024-01-15T12:00:00", "progress": 100, "tier": "bronze"}}
    
    # Onboarding & Tutorial System
    onboarding_state: str = Field(
        default="not_started", 
        max_length=20,
        sa_column=Column(
            String(20), 
            CheckConstraint(
                "onboarding_state IN ('not_started', 'in_progress', 'completed', 'skipped')",
                name="valid_onboarding_state"
            ),
            nullable=False,
            server_default="not_started"
        )
    )
    current_tutorial_step: float = Field(
        default=0.0, 
        ge=0.0, 
        le=9.0,  # 9 total tutorial steps
        sa_column=Column(Numeric(3, 1), nullable=False, server_default="0.0")
    )
    tutorial_progress_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        sa_column=Column(JSON, server_default="{}")
    )
    tutorial_skipped_at: Optional[datetime] = Field(default=None)
    last_tutorial_interaction: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Class System
    player_class: Optional[str] = Field(
        default=None,
        max_length=20,
        sa_column=Column(
            String(20),
            CheckConstraint(
                "player_class IN ('destroyer', 'adapter', 'invoker') OR player_class IS NULL",
                name="valid_player_class"
            )
        )
    )
    class_selected_at: Optional[datetime] = Field(default=None)
    
    # Activity Tracking
    last_active: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_prayer_time: Optional[datetime] = Field(default=None)
    last_exploration_time: Optional[datetime] = Field(default=None)
    last_energy_regen: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    last_stamina_regen: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    # Preferences
    prayer_notifications: bool = Field(default=False)
    energy_notifications: bool = Field(default=False)
    
    # ========== RIKI-Specific Calculations ==========
    
    def get_energy_cap(self) -> int:
        """Calculate maximum energy from level + investment."""
        base = 50 + (max(0, self.level - 1) * 10)  # Base: 50 + 10 per level after 1st
        investment_bonus = self.energy_investment * 5  # Each point = +5 max energy
        return base + investment_bonus
    
    def get_stamina_cap(self) -> int:
        """Calculate maximum stamina from level + investment."""
        base = 25 + (max(0, self.level - 1) * 5)   # Base: 25 + 5 per level after 1st
        investment_bonus = self.stamina_investment * 5 # Each point = +5 max stamina
        return base + investment_bonus
    
    def get_attack_bonus(self) -> int:
        """Calculate attack bonus from skill point investment."""
        return self.attack_investment * 10  # Each point = +10 attack
    
    def get_defense_bonus(self) -> int:
        """Calculate defense bonus from skill point investment."""
        return self.defense_investment * 10  # Each point = +10 defense
    
    def get_total_invested_points(self) -> int:
        """Calculate total skill points allocated across all stats."""
        return (self.energy_investment + self.stamina_investment + 
                self.attack_investment + self.defense_investment)
    
    def get_total_power(self) -> int:
        """Calculate total power as attack + defense."""
        return self.total_attack + self.total_defense
    
    def get_power_display(self) -> str:
        """Format total power for display."""
        power = self.total_power or self.get_total_power()
        if power >= 1_000_000:
            return f"{power / 1_000_000:.1f}M"
        elif power >= 1_000:
            return f"{power / 1_000:.1f}K"
        else:
            return str(power)
    
    def get_combat_display(self) -> str:
        """Format attack/defense for display."""
        if self.total_attack >= 1_000_000:
            atk_str = f"{self.total_attack / 1_000_000:.1f}M"
        elif self.total_attack >= 1_000:
            atk_str = f"{self.total_attack / 1_000:.1f}K"
        else:
            atk_str = str(self.total_attack)
            
        if self.total_defense >= 1_000_000:
            def_str = f"{self.total_defense / 1_000_000:.1f}M"
        elif self.total_defense >= 1_000:
            def_str = f"{self.total_defense / 1_000:.1f}K"
        else:
            def_str = str(self.total_defense)
            
        return f"{atk_str} ATK / {def_str} DEF"
    
    def update_activity(self) -> None:
        """Update last active timestamp."""
        self.last_active = datetime.utcnow()
    
    # ========== Artifact System Methods ==========
    
    def get_artifact_progress(self, artifact_id: str) -> Dict[str, Any]:
        """Get progress for specific artifact."""
        if not self.artifacts:
            return {"fragments": 0, "total_needed": 10, "completed": False}
        
        return self.artifacts.get(artifact_id, {
            "fragments": 0, 
            "total_needed": 10, 
            "completed": False
        })
    
    def add_artifact_fragment(self, artifact_id: str, fragments: int = 1) -> bool:
        """Add artifact fragments and check completion."""
        if not self.artifacts:
            self.artifacts = {}
        
        if artifact_id not in self.artifacts:
            self.artifacts[artifact_id] = {
                "fragments": 0,
                "total_needed": 10,
                "completed": False
            }
        
        artifact = self.artifacts[artifact_id]
        if artifact["completed"]:
            return False  # Already completed
        
        artifact["fragments"] = min(
            artifact["fragments"] + fragments,
            artifact["total_needed"]
        )
        
        if artifact["fragments"] >= artifact["total_needed"]:
            artifact["completed"] = True
            return True  # Just completed
        
        return False  # Progress made but not completed
    
    # ========== Achievement System Methods ==========
    
    def has_achievement(self, achievement_id: str) -> bool:
        """Check if player has earned an achievement."""
        if not self.achievements:
            return False
        return achievement_id in self.achievements and self.achievements[achievement_id].get("earned_at") is not None
    
    def grant_achievement(self, achievement_id: str, tier: str = "bronze") -> bool:
        """Grant an achievement to the player."""
        if not self.achievements:
            self.achievements = {}
        
        if self.has_achievement(achievement_id):
            return False  # Already has achievement
        
        self.achievements[achievement_id] = {
            "earned_at": datetime.utcnow().isoformat(),
            "progress": 100,
            "tier": tier
        }
        return True
    
    def update_achievement_progress(self, achievement_id: str, progress: int) -> bool:
        """Update progress toward an achievement."""
        if not self.achievements:
            self.achievements = {}
        
        if achievement_id not in self.achievements:
            self.achievements[achievement_id] = {
                "earned_at": None,
                "progress": 0,
                "tier": None
            }
        
        achievement = self.achievements[achievement_id]
        if achievement.get("earned_at"):
            return False  # Already completed
        
        achievement["progress"] = min(progress, 100)
        
        if achievement["progress"] >= 100:
            achievement["earned_at"] = datetime.utcnow().isoformat()
            achievement["tier"] = "bronze"  # Default tier
            return True  # Just completed
        
        return False
    
    # ========== Tutorial System Methods ==========
    
    def is_tutorial_required(self) -> bool:
        """Check if player needs to complete or resume tutorial."""
        return self.onboarding_state in ["not_started", "in_progress"]
    
    def is_tutorial_completed(self) -> bool:
        """Check if player has completed the full tutorial."""
        return self.onboarding_state == "completed"
    
    def is_tutorial_skipped(self) -> bool:
        """Check if player skipped the tutorial."""
        return self.onboarding_state == "skipped"
    
    def can_re_enable_tutorial(self) -> bool:
        """Check if skipped player can restart tutorial."""
        return (self.onboarding_state == "skipped" and 
                self.current_tutorial_step < 9.0)
    
    def get_tutorial_progress_percentage(self) -> float:
        """Calculate tutorial completion percentage."""
        if self.onboarding_state == "completed":
            return 100.0
        elif self.onboarding_state == "skipped":
            return 0.0
        else:
            # Tutorial has 9 steps total
            return (self.current_tutorial_step / 9.0) * 100
    
    def update_tutorial_interaction(self) -> None:
        """Update last tutorial interaction timestamp."""
        self.last_tutorial_interaction = datetime.utcnow()
    
    def get_tutorial_step_name(self) -> str:
        """Get human-readable name for current tutorial step."""
        step_names = {
            0.0: "Not Started",
            1.0: "Terms & Agreement",
            1.5: "Tutorial Choice",
            2.0: "Game Introduction",
            3.0: "First Prayer",
            4.0: "Summon Guidance",
            5.0: "First Summon",
            6.0: "Class Selection",
            7.0: "Mini Boss Combat",
            8.0: "Fusion Demonstration",
            9.0: "Tutorial Complete"
        }
        return step_names.get(self.current_tutorial_step, f"Step {self.current_tutorial_step}")
    
    def needs_tutorial_resume(self, timeout_minutes: int = 30) -> bool:
        """Check if tutorial needs resuming due to timeout."""
        if self.onboarding_state != "in_progress":
            return False
        
        time_since_interaction = datetime.utcnow() - self.last_tutorial_interaction
        return time_since_interaction.total_seconds() > (timeout_minutes * 60)
    
    # ========== Class System Methods ==========
    
    def get_class_display(self) -> str:
        """Get formatted class name for display."""
        if not self.player_class:
            return "No Class"
        return self.player_class.capitalize()
    
    def has_class(self) -> bool:
        """Check if player has selected a class."""
        return self.player_class is not None
    
    def get_class_bonus_description(self) -> str:
        """Get description of class bonuses."""
        if self.player_class == "destroyer":
            return "25% increased stamina regeneration"
        elif self.player_class == "adapter":
            return "25% increased energy regeneration"
        elif self.player_class == "invoker":
            return "20% increased rikies from all sources"
        else:
            return "No class bonus active"
    
    def get_stamina_regen_multiplier(self) -> float:
        """Get stamina regeneration multiplier from class."""
        if self.player_class == "destroyer":
            return 1.25  # 25% increase
        return 1.0
    
    def get_energy_regen_multiplier(self) -> float:
        """Get energy regeneration multiplier from class."""
        if self.player_class == "adapter":
            return 1.25  # 25% increase
        return 1.0
    
    def get_rikies_multiplier(self) -> float:
        """Get rikies gain multiplier from class."""
        if self.player_class == "invoker":
            return 1.2  # 20% increase
        return 1.0
    
    def __repr__(self) -> str:
        return (
            f"<Player(id={self.id}, discord_id={self.discord_id}, "
            f"level={self.level}, zone={self.current_zone}, "
            f"power={self.total_power})>"
        )