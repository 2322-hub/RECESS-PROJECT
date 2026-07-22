import os

from sqlalchemy import Column, Integer, String, create_engine
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
