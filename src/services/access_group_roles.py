"""
Access-group role helpers.

Authorization model for managing an access group:
  - The OWNER (access_groups.owner_account_id) or an ADMIN member
    (access_group_members.role == 'admin') is a "manager": may add/remove regular
    members, rename the group, and manage agent grants. Use is_group_manager.
  - Owner-only actions (delete the group, promote/demote a member, remove an admin)
    use is_group_owner.

The owner is never stored as an access_group_members row, so admins are members and
the owner is tracked separately on AccessGroup.
"""
from sqlalchemy.orm import Session

from src.db.models import AccessGroup, AccessGroupMember

ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"


def is_group_owner(group: AccessGroup, account_id: int) -> bool:
    return group.owner_account_id == account_id


def is_group_admin(db: Session, group_id: int, account_id: int) -> bool:
    """True if the account is an admin-role member of the group."""
    return (
        db.query(AccessGroupMember.id)
        .filter(
            AccessGroupMember.access_group_id == group_id,
            AccessGroupMember.account_id == account_id,
            AccessGroupMember.role == ADMIN_ROLE,
        )
        .first()
    ) is not None


def is_group_manager(db: Session, group: AccessGroup, account_id: int) -> bool:
    """True if the account may manage the group (owner or admin member)."""
    if is_group_owner(group, account_id):
        return True
    return is_group_admin(db, group.id, account_id)
