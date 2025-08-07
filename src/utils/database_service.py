# src/utils/database_service.py
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import StaticPool
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseService:
    """Async database service with connection pooling and transaction management"""
    
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker] = None
    _is_initialized = False
    
    @classmethod
    async def initialize(
        cls, 
        database_url: Optional[str] = None,
        echo: bool = False
    ) -> None:
        """Initialize database connection and session factory"""
        if cls._is_initialized:
            logger.warning("Database already initialized")
            return
        
        # Use environment variable or default to SQLite
        if not database_url:
            database_url = os.getenv(
                "DATABASE_URL", 
                "sqlite+aiosqlite:///seio_game.db"
            )
        
        logger.info(f"Initializing database: {database_url.split('://')[0]}://...")
        
        # Engine configuration
        engine_kwargs = {
            "echo": echo,
            "future": True,
        }
        
        # SQLite specific configuration
        if "sqlite" in database_url:
            engine_kwargs.update({
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30
                }
            })
        else:
            # PostgreSQL configuration
            engine_kwargs.update({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600
            })
        
        cls._engine = create_async_engine(database_url, **engine_kwargs)
        cls._session_factory = async_sessionmaker(
            cls._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        cls._is_initialized = True
        logger.info("Database service initialized successfully")
    
    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown database connections"""
        if cls._engine:
            await cls._engine.dispose()
            logger.info("Database connections closed")
        
        cls._engine = None
        cls._session_factory = None
        cls._is_initialized = False
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure database service is initialized"""
        if not cls._is_initialized:
            raise RuntimeError("Database service not initialized. Call DatabaseService.initialize() first.")
    
    @classmethod
    @asynccontextmanager
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        """Get database session for read operations"""
        cls._ensure_initialized()
        
        async with cls._session_factory() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @classmethod
    @asynccontextmanager
    async def get_transaction() -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic transaction management"""
        cls._ensure_initialized()
        
        async with cls._session_factory() as session:
            try:
                # Begin transaction
                await session.begin()
                yield session
                
                # Commit on success
                await session.commit()
                logger.debug("Transaction committed successfully")
                
            except Exception as e:
                # Rollback on error
                await session.rollback()
                logger.error(f"Transaction rolled back due to error: {e}")
                raise
            finally:
                await session.close()
    
    @classmethod
    async def create_tables(cls) -> None:
        """Create all database tables"""
        cls._ensure_initialized()
        
        # Import models to register them
        from src.database.models.player import Player
        from database.models.maiden import Esprit
        from database.models.maiden_base import EspritBase
        
        from sqlalchemy import MetaData
        metadata = MetaData()
        
        # Import all model metadata
        for model in [Player, Esprit, EspritBase]:
            for table in model.metadata.tables.values():
                table.tometadata(metadata)
        
        async with cls._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        
        logger.info("Database tables created successfully")
    
    @classmethod
    async def drop_tables(cls) -> None:
        """Drop all database tables (use with caution)"""
        cls._ensure_initialized()
        
        from src.database.models.player import Player
        from database.models.maiden import Esprit
        from database.models.maiden_base import EspritBase
        
        from sqlalchemy import MetaData
        metadata = MetaData()
        
        for model in [Player, Esprit, EspritBase]:
            for table in model.metadata.tables.values():
                table.tometadata(metadata)
        
        async with cls._engine.begin() as conn:
            await conn.run_sync(metadata.drop_all)
        
        logger.warning("All database tables dropped")
    
    @classmethod
    async def health_check(cls) -> Dict[str, Any]:
        """Check database connection health"""
        cls._ensure_initialized()
        
        try:
            async with cls.get_session() as session:
                result = await session.execute("SELECT 1")
                await result.fetchone()
            
            return {
                "status": "healthy",
                "database": "connected",
                "engine": str(cls._engine.url).split("://")[0]
            }
        
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "database": "disconnected"
            }
    
    @classmethod
    async def get_connection_info(cls) -> Dict[str, Any]:
        """Get database connection information"""
        cls._ensure_initialized()
        
        pool = cls._engine.pool
        return {
            "engine_url": str(cls._engine.url).replace(cls._engine.url.password or "", "***"),
            "pool_size": getattr(pool, 'size', lambda: 'N/A')(),
            "checked_out": getattr(pool, 'checkedout', lambda: 'N/A')(),
            "overflow": getattr(pool, 'overflow', lambda: 'N/A')(),
            "checked_in": getattr(pool, 'checkedin', lambda: 'N/A')()
        }