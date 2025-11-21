"""
Canonical field mapping service for cross-template aggregations.

Provides methods to:
- Resolve canonical field names to actual field names
- Expand queries to work across multiple templates
- Manage canonical mappings (CRUD operations)
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.canonical_mapping import CanonicalAlias, CanonicalFieldMapping

logger = logging.getLogger(__name__)


class CanonicalFieldService:
    """Service for managing and resolving canonical field mappings."""

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, CanonicalFieldMapping] = {}
        self._alias_cache: Dict[str, str] = {}
        self._load_cache()

    def _load_cache(self):
        """Load canonical mappings and aliases into memory cache."""
        try:
            # Load active mappings
            mappings = self.db.query(CanonicalFieldMapping).filter(
                CanonicalFieldMapping.is_active == True
            ).all()

            for mapping in mappings:
                self._cache[mapping.canonical_name] = mapping

            # Load active aliases
            aliases = self.db.query(CanonicalAlias).join(
                CanonicalFieldMapping
            ).filter(
                CanonicalAlias.is_active == True,
                CanonicalFieldMapping.is_active == True
            ).all()

            for alias in aliases:
                self._alias_cache[alias.alias] = alias.canonical_field.canonical_name

            logger.info(f"Loaded {len(self._cache)} canonical mappings and {len(self._alias_cache)} aliases")

        except Exception as e:
            logger.warning(f"Failed to load canonical mappings cache: {e}")
            self._cache = {}
            self._alias_cache = {}

    def resolve_canonical_name(self, name_or_alias: str) -> Optional[str]:
        """
        Resolve a name or alias to its canonical name.

        Args:
            name_or_alias: Field name that might be canonical or an alias

        Returns:
            Canonical name if found, otherwise None
        """
        # Check if it's already a canonical name
        if name_or_alias in self._cache:
            return name_or_alias

        # Check if it's an alias
        if name_or_alias in self._alias_cache:
            return self._alias_cache[name_or_alias]

        return None

    def get_mapping(self, canonical_name: str) -> Optional[CanonicalFieldMapping]:
        """
        Get canonical field mapping by name.

        Args:
            canonical_name: Canonical field name

        Returns:
            CanonicalFieldMapping or None
        """
        return self._cache.get(canonical_name)

    def expand_field_for_template(self, canonical_name: str, template_name: str) -> Optional[str]:
        """
        Get the actual field name for a specific template.

        Args:
            canonical_name: Canonical field name (e.g., "revenue")
            template_name: Template name (e.g., "Invoice")

        Returns:
            Actual field name (e.g., "invoice_total") or None
        """
        mapping = self.get_mapping(canonical_name)
        if not mapping:
            return None

        return mapping.field_mappings.get(template_name)

    def expand_field_all_templates(self, canonical_name: str) -> Dict[str, str]:
        """
        Get all field mappings for a canonical name.

        Args:
            canonical_name: Canonical field name

        Returns:
            Dictionary of {template_name: field_name}
        """
        mapping = self.get_mapping(canonical_name)
        if not mapping:
            return {}

        return mapping.field_mappings

    def get_all_fields_for_canonical(self, canonical_name: str) -> List[str]:
        """
        Get list of all field names across all templates for a canonical name.

        Args:
            canonical_name: Canonical field name

        Returns:
            List of unique field names
        """
        mapping = self.get_mapping(canonical_name)
        if not mapping:
            return []

        return list(mapping.field_mappings.values())

    def get_aggregation_type(self, canonical_name: str) -> Optional[str]:
        """
        Get the default aggregation type for a canonical field.

        Args:
            canonical_name: Canonical field name

        Returns:
            Aggregation type (sum, avg, count, etc.) or None
        """
        mapping = self.get_mapping(canonical_name)
        if not mapping:
            return None

        return mapping.aggregation_type

    def is_canonical_field(self, name: str) -> bool:
        """
        Check if a name is a canonical field or alias.

        Args:
            name: Field name to check

        Returns:
            True if canonical or alias, False otherwise
        """
        return name in self._cache or name in self._alias_cache

    def create_mapping(
        self,
        canonical_name: str,
        field_mappings: Dict[str, str],
        aggregation_type: str,
        description: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> CanonicalFieldMapping:
        """
        Create a new canonical field mapping.

        Args:
            canonical_name: Canonical name (e.g., "revenue")
            field_mappings: {template_name: field_name}
            aggregation_type: sum, avg, count, etc.
            description: Human-readable description
            created_by: User ID who created this mapping

        Returns:
            Created CanonicalFieldMapping

        Raises:
            ValueError: If canonical_name already exists
        """
        # Check if already exists
        existing = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.canonical_name == canonical_name
        ).first()

        if existing:
            raise ValueError(f"Canonical field '{canonical_name}' already exists")

        # Create new mapping
        mapping = CanonicalFieldMapping(
            canonical_name=canonical_name,
            description=description,
            field_mappings=field_mappings,
            aggregation_type=aggregation_type,
            is_system=False,
            created_by=created_by
        )

        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)

        # Update cache
        self._cache[canonical_name] = mapping

        logger.info(f"Created canonical mapping: {canonical_name} → {len(field_mappings)} templates")

        return mapping

    def update_mapping(
        self,
        canonical_name: str,
        field_mappings: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        aggregation_type: Optional[str] = None
    ) -> CanonicalFieldMapping:
        """
        Update an existing canonical field mapping.

        Args:
            canonical_name: Canonical name to update
            field_mappings: New field mappings (optional)
            description: New description (optional)
            aggregation_type: New aggregation type (optional)

        Returns:
            Updated CanonicalFieldMapping

        Raises:
            ValueError: If mapping not found or is system-defined
        """
        mapping = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.canonical_name == canonical_name
        ).first()

        if not mapping:
            raise ValueError(f"Canonical field '{canonical_name}' not found")

        if mapping.is_system:
            raise ValueError(f"Cannot update system-defined mapping '{canonical_name}'")

        # Update fields
        if field_mappings is not None:
            mapping.field_mappings = field_mappings

        if description is not None:
            mapping.description = description

        if aggregation_type is not None:
            mapping.aggregation_type = aggregation_type

        self.db.commit()
        self.db.refresh(mapping)

        # Update cache
        self._cache[canonical_name] = mapping

        logger.info(f"Updated canonical mapping: {canonical_name}")

        return mapping

    def delete_mapping(self, canonical_name: str) -> None:
        """
        Delete (soft delete) a canonical field mapping.

        Args:
            canonical_name: Canonical name to delete

        Raises:
            ValueError: If mapping not found or is system-defined
        """
        mapping = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.canonical_name == canonical_name
        ).first()

        if not mapping:
            raise ValueError(f"Canonical field '{canonical_name}' not found")

        if mapping.is_system:
            raise ValueError(f"Cannot delete system-defined mapping '{canonical_name}'")

        # Soft delete
        mapping.is_active = False
        self.db.commit()

        # Remove from cache
        if canonical_name in self._cache:
            del self._cache[canonical_name]

        logger.info(f"Deleted canonical mapping: {canonical_name}")

    def add_alias(self, canonical_name: str, alias: str) -> CanonicalAlias:
        """
        Add an alias for a canonical field.

        Args:
            canonical_name: Canonical name
            alias: Alias to add

        Returns:
            Created CanonicalAlias

        Raises:
            ValueError: If canonical field not found or alias already exists
        """
        mapping = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.canonical_name == canonical_name
        ).first()

        if not mapping:
            raise ValueError(f"Canonical field '{canonical_name}' not found")

        # Check if alias already exists
        existing_alias = self.db.query(CanonicalAlias).filter(
            CanonicalAlias.alias == alias,
            CanonicalAlias.is_active == True
        ).first()

        if existing_alias:
            raise ValueError(f"Alias '{alias}' already exists for '{existing_alias.canonical_field.canonical_name}'")

        # Create alias
        alias_obj = CanonicalAlias(
            canonical_field_id=mapping.id,
            alias=alias
        )

        self.db.add(alias_obj)
        self.db.commit()
        self.db.refresh(alias_obj)

        # Update cache
        self._alias_cache[alias] = canonical_name

        logger.info(f"Added alias: {alias} → {canonical_name}")

        return alias_obj

    def remove_alias(self, alias: str) -> None:
        """
        Remove an alias.

        Args:
            alias: Alias to remove

        Raises:
            ValueError: If alias not found
        """
        alias_obj = self.db.query(CanonicalAlias).filter(
            CanonicalAlias.alias == alias
        ).first()

        if not alias_obj:
            raise ValueError(f"Alias '{alias}' not found")

        # Soft delete
        alias_obj.is_active = False
        self.db.commit()

        # Remove from cache
        if alias in self._alias_cache:
            del self._alias_cache[alias]

        logger.info(f"Removed alias: {alias}")

    def list_mappings(
        self,
        include_system: bool = True,
        include_user: bool = True
    ) -> List[CanonicalFieldMapping]:
        """
        List all canonical field mappings.

        Args:
            include_system: Include system-defined mappings
            include_user: Include user-defined mappings

        Returns:
            List of CanonicalFieldMapping objects
        """
        query = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.is_active == True
        )

        if not include_system:
            query = query.filter(CanonicalFieldMapping.is_system == False)

        if not include_user:
            query = query.filter(CanonicalFieldMapping.is_system == True)

        return query.order_by(CanonicalFieldMapping.canonical_name).all()

    def get_aliases_for_canonical(self, canonical_name: str) -> List[str]:
        """
        Get all aliases for a canonical field.

        Args:
            canonical_name: Canonical name

        Returns:
            List of alias strings
        """
        mapping = self.db.query(CanonicalFieldMapping).filter(
            CanonicalFieldMapping.canonical_name == canonical_name
        ).first()

        if not mapping:
            return []

        aliases = self.db.query(CanonicalAlias).filter(
            CanonicalAlias.canonical_field_id == mapping.id,
            CanonicalAlias.is_active == True
        ).all()

        return [a.alias for a in aliases]

    def refresh_cache(self):
        """Refresh the in-memory cache from database."""
        self._cache = {}
        self._alias_cache = {}
        self._load_cache()
