# main.py
import asyncio
import os
import sys
from pathlib import Path

import disnake
from disnake.ext import commands

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logger import setup_logging, get_logger
from src.utils.database_service import DatabaseService
from src.utils.config_manager import ConfigManager

# Setup logging first
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_to_file=True
)

logger = get_logger(__name__)

class SEIOBot(commands.Bot):
    """SEIO Discord Bot with Monster Warlord-inspired gameplay"""
    
    def __init__(self):
        # Bot configuration
        intents = disnake.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix='s',
            intents=intents,
            help_command=None,
            case_insensitive=True,
            test_guilds=None  # Add your test guild IDs here for faster slash command sync
        )
    
    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("🚀 SEIO Bot starting up...")
        
        # Initialize database
        await DatabaseService.initialize(
            database_url=os.getenv("DATABASE_URL"),
            echo=os.getenv("DB_ECHO", "False").lower() == "true"
        )
        
        # Create tables if they don't exist
        await DatabaseService.create_tables()
        
        # Load configuration
        ConfigManager.reload_all()
        
        logger.info("✅ Bot setup complete")
    
    async def on_ready(self):
        """Called when bot is ready and connected"""
        logger.info(f"🎮 {self.user} is ready!")
        logger.info(f"📊 Connected to {len(self.guilds)} guilds")
        
        # Set bot status
        activity = disnake.Game(name="SEIO | s help")
        await self.change_presence(activity=activity)
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {str(error)}")
            return
        
        # Log unexpected errors
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
        await ctx.send("❌ An unexpected error occurred. Please try again.")
    
    async def close(self):
        """Clean shutdown"""
        logger.info("🛑 Bot shutting down...")
        
        # Close database connections
        await DatabaseService.shutdown()
        
        await super().close()
        logger.info("👋 Bot shutdown complete")

async def main():
    """Main bot runner"""
    # Check for required environment variables
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN environment variable not set")
        sys.exit(1)
    
    # Create and run bot
    bot = SEIOBot()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested...")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    # Create necessary directories
    Path("logs").mkdir(exist_ok=True)
    Path("config").mkdir(exist_ok=True)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 SEIO bot shutdown complete")
    except Exception as e:
        logger.error(f"💥 Failed to start bot: {e}")
        sys.exit(1)