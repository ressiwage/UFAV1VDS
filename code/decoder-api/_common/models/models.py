from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, select, DateTime, Integer, Boolean, Text, ForeignKey
from datetime import datetime
import random, string
from typing import List

class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str

def generate_random_string(length=36):
    # Определяем возможные символы: цифры и буквы (верхний + нижний регистр)
    characters = string.ascii_letters + string.digits
    # Генерируем случайную строку заданной длины
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

class Base(DeclarativeBase):
    pass

# class User(Base):
#     __tablename__ = "users"

#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
#     password: Mapped[str] = mapped_column(String(64), nullable=False)
#     access_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
#     refresh_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default = generate_random_string)
    name: Mapped[str] = mapped_column(String(255))
    mail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at:  Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, default=datetime.now())
    auth_type : Mapped[str | None] = mapped_column(String(255), nullable=True)
    pwd_hash: Mapped[str] = mapped_column(String(255))
    head_id:  Mapped[int] = mapped_column(Integer(), nullable=True)
    TG:   Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True, )
    n_mail:  Mapped[bool] = mapped_column(Boolean())
    n_phone:  Mapped[bool] = mapped_column(Boolean())
    n_TG: Mapped[bool] = mapped_column(Boolean())
    use_card: Mapped[str | None]  = mapped_column(String(255), nullable=True)
    cn_mail:  Mapped[bool] = mapped_column(Boolean())
    cn_phone: Mapped[bool] = mapped_column(Boolean())
    cn_TG: Mapped[bool] = mapped_column(Boolean())
    current_hours: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    current_reqs: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    tariffs:  Mapped[str | None] = mapped_column(String(255), nullable=True)
    historical_hours: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    public_key:   Mapped[str] = mapped_column(String(255), nullable=True)
    available_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscription_status:  Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_expires_at:  Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    subscription_plan: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trial_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trial_end_date:   Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    pre_trial_tariff: Mapped[str | None] = mapped_column(String(255), nullable=True)


    access_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


    # Relationships
    users_roles: Mapped[List["RUsersRoles"]] = relationship(back_populates="user")
    archives: Mapped[List["Archives"]] = relationship(back_populates="user")
    api_keys: Mapped[List["ApiKey"]] = relationship(back_populates="user")

class RUsersRoles(Base):
    __tablename__ = "r_users_roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_users: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    id_roles: Mapped[int] = mapped_column(Integer(), ForeignKey("roles.id"))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="users_roles")
    role: Mapped["Roles"] = relationship(back_populates="users_roles")

class Roles(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Relationship
    users_roles: Mapped[List["RUsersRoles"]] = relationship(back_populates="role")

class Archives(Base):
    __tablename__ = "archives"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    deleted: Mapped[bool] = mapped_column(Boolean(), default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="archives")
    videos: Mapped[List["Videos"]] = relationship(back_populates="archive")

class Videos(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    md5_sum: Mapped[str | None] = mapped_column(String(32), nullable=True)
    archive_id: Mapped[int | None] = mapped_column(Integer(), ForeignKey("archives.id"), nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean(), default=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dur: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    deleted: Mapped[bool] = mapped_column(Boolean(), default=False)
    from_youtube: Mapped[bool] = mapped_column(Boolean(), default=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationship
    archive: Mapped["Archives"] = relationship(back_populates="videos")

class ApiKey(Base):
    __tablename__ = "api_keys"

    key_hash: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, default=datetime.now())
    last_used: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, default=datetime.now())
    is_active: Mapped[bool] = mapped_column(Boolean(), default=False)
    role: Mapped[str] = mapped_column(String(255))
    og_key: Mapped[str] = mapped_column(String(512))

    # Relationship
    user: Mapped["User"] = relationship(back_populates="api_keys")