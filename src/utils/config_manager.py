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
        
        keys = key.split('.')
        value = cls._config_cache
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            logger.debug(f"Config key '{key}' not found, using default: {default}")
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
            logger.warning(f"Config directory {cls._config_dir} not found, using defaults")
            cls._config_cache = cls._get_default_config()
            return
        
        merged_config = {}
        
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
        """Default configuration values for RIKI MVP"""
        return {
            # Grace System
            "prayer": {
                "cooldown_minutes": 6,
                "base_grace_reward": 1
            },
            
            # Summoning
            "summoning": {
                "grace_cost": 1,
                "rates": {
                    "1": 0.70,   # 70%
                    "2": 0.20,   # 20%
                    "3": 0.08,   # 8%
                    "4": 0.015,  # 1.5%
                    "5": 0.004,  # 0.4%
                    "6": 0.001   # 0.1%
                }
            },
            
            # Fusion
            "fusion": {
                "max_tier": 12,
                "base_cost": 1000,
                "cost_multiplier": 2.5,
                "costs": {  # Pre-calculated for clarity
                    "1": 1000,       # Tier 1→2
                    "2": 2500,       # Tier 2→3
                    "3": 6250,       # Tier 3→4
                    "4": 15625,      # Tier 4→5
                    "5": 39062,      # Tier 5→6
                    "6": 97656,      # Tier 6→7
                    "7": 244140,     # Tier 7→8
                    "8": 610351,     # Tier 8→9
                    "9": 1525878,    # Tier 9→10
                    "10": 3814697,   # Tier 10→11
                    "11": 9536743    # Tier 11→12
                },
                "success_rates": {
                    "1": 0.80,
                    "2": 0.75,
                    "3": 0.70,
                    "4": 0.65,
                    "5": 0.60,
                    "6": 0.55,
                    "7": 0.50,
                    "8": 0.45,
                    "9": 0.40,
                    "10": 0.35,
                    "11": 0.30
                }
            },
            
            # Player
            "player": {
                "starting": {
                    "energy": 50,
                    "stamina": 25,
                    "level": 0
                },
                "per_level": {
                    "skill_points": 3,
                    "energy_base": 10,
                    "stamina_base": 5
                },
                "per_point": {
                    "energy": 5,
                    "stamina": 5,
                    "attack": 10,
                    "defense": 10
                }
            },
            
            # Resources
            "resources": {
                "energy": {
                    "regen_minutes": 3,
                    "regen_amount": 2
                },
                "stamina": {
                    "regen_minutes": 2,
                    "regen_amount": 1
                }
            },
            
            # Classes
            "classes": {
                "destroyer": {"stamina_regen_mult": 1.25},
                "adapter": {"energy_regen_mult": 1.25},
                "invoker": {"rikies_mult": 1.2}
            },
            
            # Combat
            "combat": {
                "power_per_tier": 0.5  # 50% increase per tier
            },
            
            # Elements
            "elements": [
                "infernal", "umbral", "earth", 
                "tempest", "radiant", "abyssal"
            ],
            
            # Tutorial
            "tutorial": {
                "rewards": {
                    "grace": 3,
                    "rikies": 500
                },
                "guaranteed_tier": 2,
                "total_steps": 9
            },
            
            # Zones
            "zones": {
                "count": 3,
                "subzones": 10
            },
            
            # Artifacts
            "artifacts": {
                "fragments_per": 10
            },
            
            # Rate Limits
            "rate_limits": {
                "uses": 5,
                "seconds": 60
            }
        }