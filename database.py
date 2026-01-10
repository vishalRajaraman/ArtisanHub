from sqlalchemy import create_engine, Column, String, Integer, Boolean, ForeignKey, LargeBinary, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from dotenv import load_dotenv

load_dotenv()

# 1. DATABASE CONNECTION
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️ WARNING: DATABASE_URL not found. Using local SQLite for testing.")
    DATABASE_URL = "sqlite:///./artconnect.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    # Postgres connection (Fix Render's postgres:// issue if present)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. MODELS (Tables)

class UserTable(Base):
    __tablename__ = "users"
    
    # We keep 'phone' as PK since your auth logic relies on it
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
    
    # Core Fields
    title = Column(String, nullable=True) # AI generates this now
    price = Column(Integer, nullable=True)
    description = Column(String, nullable=True) # Original User Voice
    image_data = Column(LargeBinary, nullable=True)
    
    # --- NEW AI FIELDS ---
    art_form_tag = Column(String, nullable=True)      # e.g., "Madhubani"
    app_title = Column(String, nullable=True)         # Emotional Title
    corrected_voice = Column(Text, nullable=True)     # Polished grammar
    min_price = Column(Integer, nullable=True)
    max_price = Column(Integer, nullable=True)
    is_published = Column(Boolean, default=False)     # Draft vs Live
    
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