from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Annotated
from sqlalchemy.orm import Session
import os
import random
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
# Import database logic
from database import init_db, get_db, UserTable, ArtformTable

# 1. CONFIGURATION
load_dotenv()
init_db() # Creates tables

app = FastAPI()
security = HTTPBearer()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (perfect for local testing)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "hackathon_secret_key")
ALGORITHM = "HS256"
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# In-Memory OTP Storage
otp_storage = {} 

# --- HELPER FUNCTIONS ---

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7) # Token lasts 7 days
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token_obj: Annotated[HTTPAuthorizationCredentials, Depends(security)], 
    db: Session = Depends(get_db)
):
    token = token_obj.credentials 
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone: str = payload.get("sub")
        if phone is None:
            raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    
    user = db.query(UserTable).filter(UserTable.phone == phone).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- MODELS ---
class LoginRequest(BaseModel):
    phone_number: str

class VerifyRequest(BaseModel):
    phone_number: str
    otp: str

class ProfileUpdate(BaseModel):
    full_name: str
    location: str
    role: str = "Artisan" # Default

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "ArtConnect Auth & DB is LIVE 🚀"}

@app.post("/auth/send-otp")
def send_otp(request: LoginRequest):
    phone = request.phone_number
    otp_code = str(random.randint(1000, 9999))
    otp_storage[phone] = otp_code
    print(f"🔐 OTP for {phone}: {otp_code}") 

    try:
        twilio_client.messages.create(
            body=f"Your Login Code is: {otp_code}",
            from_=TWILIO_PHONE,
            to=phone
        )
    except Exception as e:
        print(f"⚠️ SMS Failed: {e}")

    return {"message": "OTP generated"}

@app.post("/auth/verify-otp")
def verify_otp(request: VerifyRequest, db: Session = Depends(get_db)):
    phone = request.phone_number
    
    # 1. Verify OTP
    if otp_storage.get(phone) != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    del otp_storage[phone]
    
    # 2. Check Database
    user = db.query(UserTable).filter(UserTable.phone == phone).first()
    is_new_user = False
    
    if not user:
        is_new_user = True
        # Create "Skeleton" User
        new_user = UserTable(phone=phone, full_name="", is_new=True)
        db.add(new_user)
        db.commit()
    elif user.is_new:
        is_new_user = True # They exist but haven't finished profile setup
    
    # 3. Create Token
    access_token = create_access_token(data={"sub": phone})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "is_new_user": is_new_user # True = Go to Profile Screen
    }

@app.post("/user/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: UserTable = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Saves the user's name/location and marks them as 'Active'.
    """
    # 1. Update Info
    current_user.full_name = profile_data.full_name
    current_user.location = profile_data.location
    current_user.role = profile_data.role
    
    # 2. FLIP THE SWITCH (Critical Step)
    current_user.is_new = False 
    
    db.commit()
    db.refresh(current_user)
    
    return {"message": "Profile Saved!", "user": current_user}

# --- MANUAL UPLOAD (No AI) ---
@app.post("/art/upload")
async def create_artwork(
    title: str = Form(...),
    price: int = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...), 
    current_user: UserTable = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Read image as bytes
    file_bytes = await file.read()
    
    new_art = ArtformTable(
        title=title,
        price=price,
        description=description,
        image_data=file_bytes, 
        owner_phone=current_user.phone
    )
    
    db.add(new_art)
    db.commit()
    db.refresh(new_art)
    
    return {"message": "Art saved!", "art_id": new_art.id}

@app.get("/art/image/{art_id}")
def get_art_image(art_id: int, db: Session = Depends(get_db)):
    art = db.query(ArtformTable).filter(ArtformTable.id == art_id).first()
    if not art or not art.image_data:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return Response(content=art.image_data, media_type="image/jpeg")
@app.get("/debug/db-check")
def check_database(db: Session = Depends(get_db)):
    """A quick way to see all users in your browser"""
    users = db.query(UserTable).all()
    return [{"phone": u.phone, "name": u.full_name, "is_new": u.is_new} for u in users]