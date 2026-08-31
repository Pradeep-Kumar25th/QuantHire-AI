"""Base service class with enterprise patterns."""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.core.exceptions import DatabaseException, ResourceNotFoundException

ModelType = TypeVar("ModelType", bound=SQLModel)

logger = logging.getLogger(__name__)


class BaseService(Generic[ModelType]):
    """
    Base service class implementing common CRUD operations.
    
    Provides:
    - Standard CRUD methods
    - Pagination support
    - Filtering and sorting
    - Transaction management
    - Error handling
    - Audit logging
    """
    
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize service.
        
        Args:
            model: SQLModel class
            db: Database session
        """
        self.model = model
        self.db = db
        self.logger = logging.getLogger(f"service.{model.__name__}")
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        Get entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity or None if not found
            
        Raises:
            DatabaseException: If database operation fails
        """
        try:
            result = await self.db.execute(
                select(self.model).where(self.model.id == id)
            )
            return result.scalar_one_or_none()
        
        except Exception as e:
            self.logger.error(f"Failed to get {self.model.__name__} by ID: {e}")
            raise DatabaseException(
                message=f"Failed to retrieve {self.model.__name__}",
                operation="get_by_id",
            )
    
    async def get_by_id_or_404(self, id: str) -> ModelType:
        """
        Get entity by ID or raise 404.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity
            
        Raises:
            ResourceNotFoundException: If entity not found
        """
        entity = await self.get_by_id(id)
        if entity is None:
            raise ResourceNotFoundException(
                resource_type=self.model.__name__,
                resource_id=id,
            )
        return entity
    
    async def list(
        self,
        offset: int = 0,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> List[ModelType]:
        """
        List entities with pagination and filtering.
        
        Args:
            offset: Offset for pagination
            limit: Number of items to return
            filters: Filter conditions
            order_by: Field to order by
            
        Returns:
            List of entities
        """
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.where(getattr(self.model, key) == value)
            
            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                query = query.order_by(getattr(self.model, order_by).desc())
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        
        except Exception as e:
            self.logger.error(f"Failed to list {self.model.__name__}: {e}")
            raise DatabaseException(
                message=f"Failed to list {self.model.__name__}",
                operation="list",
            )
    
    async def create(self, entity: ModelType) -> ModelType:
        """
        Create new entity.
        
        Args:
            entity: Entity to create
            
        Returns:
            Created entity with ID
        """
        try:
            self.db.add(entity)
            await self.db.flush()
            await self.db.refresh(entity)
            
            self.logger.info(
                f"Created {self.model.__name__}",
                extra={"entity_id": str(entity.id) if hasattr(entity, "id") else None}
            )
            
            return entity
        
        except Exception as e:
            self.logger.error(f"Failed to create {self.model.__name__}: {e}")
            raise DatabaseException(
                message=f"Failed to create {self.model.__name__}",
                operation="create",
            )
    
    async def update(self, id: str, updates: Dict[str, Any]) -> ModelType:
        """
        Update entity.
        
        Args:
            id: Entity ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated entity
        """
        entity = await self.get_by_id_or_404(id)
        
        try:
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            await self.db.flush()
            await self.db.refresh(entity)
            
            self.logger.info(
                f"Updated {self.model.__name__}",
                extra={"entity_id": id, "updated_fields": list(updates.keys())}
            )
            
            return entity
        
        except Exception as e:
            self.logger.error(f"Failed to update {self.model.__name__}: {e}")
            raise DatabaseException(
                message=f"Failed to update {self.model.__name__}",
                operation="update",
            )
    
    async def delete(self, id: str) -> bool:
        """
        Delete entity (soft delete if supported).
        
        Args:
            id: Entity ID
            
        Returns:
            True if deleted successfully
        """
        entity = await self.get_by_id_or_404(id)
        
        try:
            # Check if model supports soft delete
            if hasattr(entity, "deleted_at"):
                from datetime import datetime
                entity.deleted_at = datetime.utcnow()
                await self.db.flush()
                self.logger.info(f"Soft deleted {self.model.__name__}: {id}")
            else:
                await self.db.delete(entity)
                self.logger.info(f"Hard deleted {self.model.__name__}: {id}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to delete {self.model.__name__}: {e}")
            raise DatabaseException(
                message=f"Failed to delete {self.model.__name__}",
                operation="delete",
            )
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities matching filters.
        
        Args:
            filters: Filter conditions
            
        Returns:
            Count of matching entities
        """
        try:
            from sqlalchemy import func
            
            query = select(func.count(self.model.id))
            
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.where(getattr(self.model, key) == value)
            
            result = await self.db.execute(query)
            return result.scalar_one()
        
        except Exception as e:
            self.logger.error(f"Failed to count {self.model.__name__}: {e}")
            raise DatabaseException(
                message=f"Failed to count {self.model.__name__}",
                operation="count",
            )
    
    async def exists(self, id: str) -> bool:
        """
        Check if entity exists.
        
        Args:
            id: Entity ID
            
        Returns:
            True if exists, False otherwise
        """
        entity = await self.get_by_id(id)
        return entity is not None












