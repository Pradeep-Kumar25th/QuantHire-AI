"""Enterprise-grade database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from fastapi import HTTPException

from app.config import settings
from app.core.exceptions import DatabaseException, QuantHireException

logger = logging.getLogger(__name__)


def _asyncpg_url_and_ssl(raw_url: str):
    """
    Normalize a Postgres URL for asyncpg.

    asyncpg does not accept the libpq ``sslmode`` query parameter (Azure
    connection strings use ``?sslmode=require``), so translate it into the
    asyncpg ``ssl`` connect argument and force the asyncpg driver.
    Returns (sqlalchemy URL object, ssl_connect_arg_or_None).
    """
    url = make_url(raw_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    url = url.set(query=query)

    ssl_arg = None
    if sslmode in ("require", "verify-ca", "verify-full"):
        ssl_arg = True
    elif sslmode == "disable":
        ssl_arg = False
    return url, ssl_arg


# Database engine with enterprise configuration
def create_engine():
    """Create database engine with proper configuration."""
    # Check if database URL is configured
    if not settings.database_url or "postgresql" not in settings.database_url.lower():
        # Silently skip - database is optional for AI features
        return None
    
    try:
        db_url, ssl_arg = _asyncpg_url_and_ssl(settings.database_url)

        # Connection arguments
        connect_args = {
            "server_settings": {"application_name": "quanthire-api"},
            "command_timeout": 60,
            "timeout": 30,
        }
        if ssl_arg is not None:
            connect_args["ssl"] = ssl_arg
        
        # Pool configuration — async engine must not use sync QueuePool
        if settings.is_development and settings.debug:
            engine = create_async_engine(
                db_url,
                echo=settings.db_echo,
                poolclass=NullPool,
                connect_args=connect_args,
            )
        else:
            engine = create_async_engine(
                db_url,
                echo=settings.db_echo,
                connect_args=connect_args,
                pool_size=settings.db_pool_size,
                max_overflow=max(settings.db_max_overflow, 0),
                pool_pre_ping=True,
                pool_recycle=3600,
            )

        try:
            @event.listens_for(engine.sync_engine, "connect")
            def receive_connect(dbapi_conn, connection_record):
                logger.debug("Database connection established")

            @event.listens_for(engine.sync_engine, "checkout")
            def receive_checkout(dbapi_conn, connection_record, connection_proxy):
                logger.debug("Database connection checked out from pool")
        except Exception as monitor_error:
            logger.warning("Could not set up connection pool monitoring: %s", monitor_error)

        return engine
    except Exception as exc:
        logger.error("Failed to create database engine: %s", exc, exc_info=True)
        return None


# Create global engine (may be None if database not configured)
engine = create_engine()

# Create async session factory with proper configuration (only if engine exists)
if engine:
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    async_session_maker = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with proper error handling and transaction management.
    
    Yields:
        AsyncSession: Database session
        
    Raises:
        DatabaseException: If session creation or transaction fails
    """
    if not async_session_maker:
        raise DatabaseException(
            message="Database not configured. Please set DATABASE_URL environment variable.",
            operation="get_session",
        )
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
            logger.debug("Database transaction committed")
        except Exception as e:
            await session.rollback()
            # Route/business errors must not be relabeled as database failures.
            if isinstance(e, HTTPException):
                raise
            if isinstance(e, QuantHireException):
                raise
            logger.error(f"Database transaction rolled back: {e}", exc_info=True)
            raise DatabaseException(
                message=f"Database operation failed: {str(e)}",
                operation="transaction",
            )
        finally:
            await session.close()


# Alias for FastAPI dependency
get_db = get_session


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as context manager for manual transaction control.
    
    Usage:
        async with get_session_context() as session:
            # Your database operations
            await session.commit()
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables and extensions.
    
    Creates all tables and enables required PostgreSQL extensions.
    """
    if not engine:
        # Silently skip - database is optional
        return
    
    logger.info("Initializing database...")
    
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models import (  # noqa: F401
                applications,
                assessments,
                audit_logs,
                candidates,
                document_chunks,
                interviews,
                jobs,
                offers,
                organizations,
                users,
            )
            
            # Enable PostgreSQL extensions (Azure allow-lists extensions — skip optional ones)
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            if settings.is_azure_nonprod:
                # App UUIDs use Python uuid4; uuid-ossp is not allow-listed on Azure Postgres
                logger.info(
                    "Azure Non-Prod: vector enabled; skipping uuid-ossp/pg_trgm "
                    "(not allow-listed / not required)"
                )
            else:
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

            logger.info("PostgreSQL extensions enabled")

            if settings.is_azure_nonprod:
                logger.info(
                    "Azure Non-Prod: schema managed by Alembic (run `alembic upgrade head`)"
                )
            else:
                await conn.run_sync(SQLModel.metadata.create_all)
                logger.info("Database tables created")
        
        logger.info("✓ Database initialized successfully")
        
    except Exception as e:
        # Check if it's a connection error (common in local dev without Postgres)
        error_str = str(e).lower()
        if "connect call failed" in error_str or "connection refused" in error_str:
            logger.warning(f"Database connection failed (PostgreSQL not running?): {e}")
            logger.info("Server will continue without database features (JD Generation, Resume Parsing, QuantChat will still work)")
            # Do not raise exception, allow server to start
            return
            
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise DatabaseException(
            message=f"Database initialization failed: {str(e)}",
            operation="init_db",
        )


async def close_db() -> None:
    """Close database connections and dispose of connection pool."""
    if not engine:
        return
    
    logger.info("Closing database connections...")
    
    try:
        await engine.dispose()
        logger.info("✓ Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}", exc_info=True)


async def check_db_health() -> Dict[str, Any]:
    """
    Check database health and connection pool status.
    
    Returns:
        Dict with health status and metrics
    """
    if not engine:
        return {
            "status": "not_configured",
            "connected": False,
            "message": "Database URL not configured",
        }
    
    try:
        async with engine.connect() as conn:
            value = await conn.scalar(text("SELECT 1"))
            if value != 1:
                raise DatabaseException("Database health check returned unexpected result")
        
        # Get pool statistics when the pool supports them
        pool = engine.pool
        if hasattr(pool, "size"):
            pool_status = {
                "type": type(pool).__name__,
                "size": pool.size(),
                "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else 0,
                "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
            }
        else:
            pool_status = {
                "type": type(pool).__name__,
                "note": "Pool does not expose connection statistics",
            }
        
        return {
            "status": "healthy",
            "connected": True,
            "pool": pool_status,
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }

