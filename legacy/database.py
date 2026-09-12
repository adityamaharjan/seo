from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy.orm import Session
import os

load_dotenv()
DB = os.getenv('DB')
DBPort = os.getenv('DBPort')
DB_USER = os.getenv('DBUser')
DB_PASSWORD = os.getenv('DBPassword')
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@localhost:{DBPort}/{DB}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # set True for debugging
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
