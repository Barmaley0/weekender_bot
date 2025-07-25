import logging

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.bot.db.connection import Base, engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=True)
    username: Mapped[str] = mapped_column(String(40), nullable=True)
    year: Mapped[int] = mapped_column(Integer(), nullable=True)
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_update: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    points: Mapped[int] = mapped_column(Integer(), default=100, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    profession: Mapped[str] = mapped_column(String(50), nullable=True)
    about: Mapped[str] = mapped_column(Text, nullable=True)
    total_likes: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)

    options: Mapped[list['UserOption']] = relationship(
        back_populates='user',
        cascade='save-update, merge',
        passive_deletes=True,
    )
    photo_profile: Mapped[list['PhotoProfile']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    sent_likes: Mapped[list['LikeProfile']] = relationship(
        back_populates='from_user',
        cascade='all, delete-orphan',
        foreign_keys='LikeProfile.from_user_id',
        passive_deletes=True,
    )
    received_likes: Mapped[list['LikeProfile']] = relationship(
        back_populates='to_user',
        cascade='all, delete-orphan',
        foreign_keys='LikeProfile.to_user_id',
        passive_deletes=True,
    )
    sent_friend_requests: Mapped[list['FriendRequest']] = relationship(
        back_populates='from_user',
        cascade='all, delete-orphan',
        foreign_keys='FriendRequest.from_user_id',
        passive_deletes=True,
    )
    received_friend_requests: Mapped[list['FriendRequest']] = relationship(
        back_populates='to_user',
        cascade='all, delete-orphan',
        foreign_keys='FriendRequest.to_user_id',
        passive_deletes=True,
    )
    support_tickets: Mapped[list['SupportTicket']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f'User id: {self.id}, tg_id: {self.tg_id}'


class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped['User'] = relationship(back_populates='support_tickets', lazy='joined')
    messages: Mapped[list['SupportMessage']] = relationship(
        back_populates='ticket',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='SupportMessage.date_create',
    )


class SupportMessage(Base):
    __tablename__ = 'support_messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey('support_tickets.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    is_from_user: Mapped[bool] = mapped_column(
        Boolean(),
        default=False,
        doc='True if message is from User, False if message is from Admin',
    )
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)

    ticket: Mapped['SupportTicket'] = relationship(back_populates='messages', lazy='joined')


class PhotoProfile(Base):
    __tablename__ = 'photo_profile'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    profile_photo_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=True)

    user: Mapped['User'] = relationship(back_populates='photo_profile', lazy='joined')


class LikeProfile(Base):
    __tablename__ = 'like_profile'

    id: Mapped[int] = mapped_column(primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_reciprocated: Mapped[bool] = mapped_column(Boolean(), default=False)

    from_user: Mapped['User'] = relationship(
        foreign_keys=[from_user_id],
        back_populates='sent_likes',
        lazy='selectin',
    )
    to_user: Mapped['User'] = relationship(
        foreign_keys=[to_user_id],
        back_populates='received_likes',
        lazy='selectin',
    )

    __table_args__ = (
        UniqueConstraint('from_user_id', 'to_user_id', name='unique_like'),
        Index('ix_like_profile_reciprocated', 'is_reciprocated'),
        Index('ix_like_profile_date_create', 'date_create'),
    )


class FriendRequest(Base):
    __tablename__ = 'friend_requests'

    id: Mapped[int] = mapped_column(primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_reciprocated: Mapped[bool] = mapped_column(Boolean(), default=False)

    from_user: Mapped['User'] = relationship(
        foreign_keys=[from_user_id],
        back_populates='sent_friend_requests',
        lazy='selectin',
    )
    to_user: Mapped['User'] = relationship(
        foreign_keys=[to_user_id],
        back_populates='received_friend_requests',
        lazy='selectin',
    )

    __table_args__ = (
        UniqueConstraint('from_user_id', 'to_user_id', name='unique_friend_request'),
        Index('ix_friend_request_reciprocated', 'is_reciprocated'),
        Index('ix_friend_request_date_create', 'date_create'),
    )


class OptionCategory(Base):
    __tablename__ = 'options_categories'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=True)


class Option(Base):
    __tablename__ = 'options'

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('options_categories.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(40), nullable=True)

    category: Mapped['OptionCategory'] = relationship()
    users: Mapped[list['UserOption']] = relationship(
        back_populates='option',
        passive_deletes=True,
    )
    events: Mapped[list['EventInterest']] = relationship(
        back_populates='interest',
        passive_deletes=True,
    )


class UserOption(Base):
    __tablename__ = 'user_options'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True, primary_key=True)
    option_id: Mapped[int] = mapped_column(ForeignKey('options.id', ondelete='CASCADE'), index=True, primary_key=True)
    selected: Mapped[bool] = mapped_column(Boolean(), nullable=True)

    user: Mapped['User'] = relationship(back_populates='options')
    option: Mapped['Option'] = relationship(back_populates='users')


class Event(Base):
    __tablename__ = 'events'

    id: Mapped[int] = mapped_column(primary_key=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=True)
    year: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=True)
    url: Mapped[str] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    interests: Mapped[list['EventInterest']] = relationship(
        back_populates='event',
        cascade='all, delete-orphan',
        lazy='selectin',
        passive_deletes=False,
    )


class EventInterest(Base):
    __tablename__ = 'events_interests'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True, primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey('options.id', ondelete='CASCADE'), index=True, primary_key=True)

    event: Mapped['Event'] = relationship(back_populates='interests', lazy='joined')
    interest: Mapped['Option'] = relationship(back_populates='events', lazy='joined')


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
