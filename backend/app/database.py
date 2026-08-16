import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Đọc từ file .env (xem .env.example) hoặc biến môi trường DATABASE_URL.
# Nếu không có gì, dùng giá trị mặc định dưới đây cho dev — nhớ đổi mật khẩu
# thật, và KHÔNG commit file .env thật lên Git (đã có trong .gitignore).
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/warehouse_db"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency dùng trong FastAPI: cấp 1 session/request, tự đóng khi xong."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
