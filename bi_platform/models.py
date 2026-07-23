import os
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")

    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}


class SavedView(Base):
    __tablename__ = "saved_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    view_type = Column(String(50), nullable=False, default="filter")
    filters_json = Column(Text, nullable=False, default="{}")
    sql_query = Column(Text, nullable=True)
    connection = Column(String(100), nullable=True, default="demo")
    section = Column(String(50), nullable=True, default="overview")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "view_type": self.view_type,
            "filters": json.loads(self.filters_json) if self.filters_json else {},
            "sql_query": self.sql_query,
            "connection": self.connection,
            "section": self.section,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    report_format = Column(String(20), nullable=False, default="pdf")
    frequency = Column(String(20), nullable=False, default="daily")
    email = Column(String(200), nullable=False)
    connection = Column(String(100), nullable=True, default="demo")
    filters_json = Column(Text, nullable=True, default="{}")
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "report_format": self.report_format,
            "frequency": self.frequency,
            "email": self.email,
            "connection": self.connection,
            "filters": json.loads(self.filters_json) if self.filters_json else {},
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def get_engine(db_url: str | None = None):
    url = db_url or os.environ.get("DATABASE_URL", "sqlite:///bi_platform_demo.db")
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        url,
        connect_args=connect_args,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def _make_engine():
    from dotenv import load_dotenv

    load_dotenv(override=True)
    return get_engine()


Engine = _make_engine()
SessionLocal = sessionmaker(bind=Engine)


def init_db():
    Base.metadata.create_all(Engine)
    _seed_default_user()


def _seed_default_user():
    from sqlalchemy import select

    session = SessionLocal()
    try:
        existing = session.execute(
            select(User).where(User.username == os.environ.get("ADMIN_USERNAME", "admin"))
        ).scalar_one_or_none()
        if existing:
            return
        user = User(
            username=os.environ.get("ADMIN_USERNAME", "admin"),
            password_hash=generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123")),
            role="admin",
        )
        session.add(user)
        session.commit()
    finally:
        session.close()
