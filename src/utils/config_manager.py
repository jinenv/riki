# src/utils/config_manager.py
import json
import yaml
from typing import Any, Dict, Optional
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

class ConfigManager:
    """Configuration management system with hot-reloading support"""
    
    _config_cache: Dict[str, Any] = {}
    _config_dir = Path("config")
    _loaded_files: Dict[str, float] = {}
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get configuration value with dot notation support"""
        cls._ensure_configs_loaded()
        
        # Split key by dots for nested access
        keys = key.split('.')
        value = cls._config_cache
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    @classmethod
    def reload_all(cls) -> None:
        """Force reload all configuration files"""
        cls._config_cache.clear()
        cls._loaded_files.clear()
        cls._ensure_configs_loaded()
        logger.info("Configuration reloaded")
    
    @classmethod
    def _ensure_configs_loaded(cls) -> None:
        """Load all configuration files if not already loaded"""
        if not cls._config_cache:
            cls._load_all_configs()
    
    @classmethod
    def _load_all_configs(cls) -> None:
        """Load all configuration files from config directory"""
        if not cls._config_dir.exists():
            logger.warning(f"Config directory {cls._config_dir} not found")
            cls._config_cache = cls._get_default_config()
            return
        
        merged_config = {}
        
        # Load all JSON and YAML files
        for config_file in cls._config_dir.glob("*.json"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                merged_config.update(file_config)
                cls._loaded_files[str(config_file)] = config_file.stat().st_mtime
                logger.debug(f"Loaded config: {config_file}")
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")
        
        for config_file in cls._config_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                merged_config.update(file_config or {})
                cls._loaded_files[str(config_file)] = config_file.stat().st_mtime
                logger.debug(f"Loaded config: {config_file}")
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")
        
        # Merge with defaults
        default_config = cls._get_default_config()
        cls._config_cache = cls._deep_merge(default_config, merged_config)
        
        logger.info(f"Loaded {len(cls._loaded_files)} configuration files")
    
    @classmethod
    def _deep_merge(cls, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """Default configuration values for MVP"""
        return {
            "prayer": {
                "cooldown_minutes": 5
            },
            "summoning": {
                "ichor_cost": 1,
                "rates": {
                    "1": 0.70,  # 70% Common
                    "2": 0.20,  # 20% Uncommon  
                    "3": 0.08,  # 8% Rare
                    "4": 0.015, # 1.5% Epic
                    "5": 0.004, # 0.4% Legendary
                    "6": 0.001  # 0.1% Mythic
                }
            },
            "fusion": {
                "max_tier": 6,
                "base_cost": 1000,
                "tier_cost_multiplier": 500
            },
            "power": {
                "tier_scaling_base": 1.0,
                "tier_scaling_multiplier": 0.15,
                "element_bonus_multiplier": 0.05
            },
            "tower": {
                "base_boss_health": 100,
                "difficulty_multiplier": 1000,
                "damage_variance": 0.2,
                "base_seios_per_hour": 100,
                "base_progress_per_hour": 0.1,
                "max_idle_hours": 24,
                "erythl_chance_per_hour": 0.05,
                "encounter_chance_per_hour": 0.1,
                "themes": [
                    {"max_floor": 100, "name": "Lower Floors"},
                    {"max_floor": 500, "name": "Mid Floors"},
                    {"max_floor": 999999, "name": "Upper Floors"}
                ]
            },
            "player": {
                "base_energy": 50,
                "energy_per_level": 10,
                "base_stamina": 25,
                "stamina_per_level": 5,
                "xp_base": 1000,
                "xp_multiplier": 1.15
            },
            "energy": {
                "regen_minutes": 5,
                "regen_amount": 1
            },
            "stamina": {
                "regen_minutes": 5,
                "regen_amount": 1
            },
            "element_system": {
                "valid_elements": [
                    "Inferno", "Aqua", "Tempest", "Earth", "Umbral", "Radiant"
                ],
                "emojis": {
                    "Inferno": "🔥",
                    "Aqua": "💧",
                    "Tempest": "⚡", 
                    "Earth": "🌿",
                    "Umbral": "🌑",
                    "Radiant": "✨"
                }
            },
            "tier_system": {
                "names": {
                    "1": "Common",
                    "2": "Uncommon", 
                    "3": "Rare",
                    "4": "Epic",
                    "5": "Legendary",
                    "6": "Mythic"
                }
            },
            "currency": {
                "exchange_rates": {
                    "seios_to_base": 1,
                    "ichor_to_base": 100,
                    "erythl_to_base": 1000
                },
                "transfers": {
                    "seios": {"enabled": False},
                    "ichor": {"enabled": False},
                    "erythl": {"enabled": False}
                }
            }
        }