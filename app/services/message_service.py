from datetime import datetime
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User


class MessageService:
    def ensure_user_and_group(self, event):
        with SessionLocal() as db:
            user = db.execute(select(User).where(User.platform_user_id == event.user_id)).scalar_one_or_none()
            if user is None:
                user = User(platform_user_id=event.user_id)
                db.add(user)
                db.flush()
            if event.group_id:
                group = db.execute(select(Group).where(Group.platform_group_id == event.group_id)).scalar_one_or_none()
                if group is None:
                    group = Group(platform_group_id=event.group_id)
                    db.add(group)
                    db.flush()
                member = db.execute(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)).scalar_one_or_none()
                if member is None:
                    member = GroupMember(group_id=group.id, user_id=user.id, role=event.sender_role)
                    db.add(member)
                else:
                    member.role = event.sender_role
                    member.updated_at = datetime.utcnow()
            db.commit()
