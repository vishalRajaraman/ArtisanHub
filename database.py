# database.py
from sqlalchemy import create_engine, Column, String, Integer, Boolean, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from dotenv import load_dotenv

load_dotenv()

# 1. DATABASE CONNECTION
# Ensure DATABASE_URL is in your .env or Render Environment Variables
# If running locally without a real DB, you can use: "sqlite:///./test.db"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️ WARNING: DATABASE_URL not found. Using local SQLite for testing.")
    DATABASE_URL = "sqlite:///./artconnect.db"
    # Note: SQLite needs "check_same_thread": False, Postgres does not.
    connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    # Postgres connection
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. MODELS (Tables)

class UserTable(Base):
    __tablename__ = "users"
    
    phone = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    role = Column(String, default="Artisan") # "Artisan" or "Buyer"
    location = Column(String, nullable=True)
    is_new = Column(Boolean, default=True)
    joined_at = Column(String, nullable=True)
    
    # Relationship to Artworks
    artworks = relationship("ArtformTable", back_populates="owner")

class ArtformTable(Base):
    __tablename__ = "artforms"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    
    # The Image stored as BLOB (Binary Data)
    image_data = Column(LargeBinary, nullable=True)
    
    owner_phone = Column(String, ForeignKey("users.phone"))
    owner = relationship("UserTable", back_populates="artworks")

# 3. INITIALIZER
def init_db():
    Base.metadata.create_all(bind=engine)

# 4. DEPENDENCY
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()