"""Tree-building service for cocoon hierarchies."""

from __future__ import annotations

from app.models import Cocoon
from app.schemas.workspace.cocoons import CocoonTreeNode


class CocoonTreeService:
    """Builds nested cocoon trees from flat cocoon records."""

    def build_tree(
        self,
        nodes: list[Cocoon],
        parent_id: str | None = None,
    ) -> list[CocoonTreeNode]:
        """Return a recursive tree rooted at the provided parent id."""
        branch = []
        for cocoon in [item for item in nodes if item.parent_id == parent_id]:
            branch.append(
                CocoonTreeNode(
                    id=cocoon.id,
                    name=cocoon.name,
                    parent_id=cocoon.parent_id,
                    children=self.build_tree(nodes, cocoon.id),
                )
            )
        return branch
