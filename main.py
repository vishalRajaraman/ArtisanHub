from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from twilio.rest import Client
from jose import JWTError, jwt
from datetime import datetime, timedelta  # <--- FIXED: Added missing import
from typing import Dict, Optional, Annotated
import os
import random
from dotenv import load_dotenv

# 1. Load Keys
load_dotenv()

app = FastAPI()

# --- CONFIGURATION ---
SECRET_KEY = "hackathon_secret_key" # In real app, use os.getenv
ALGORITHM = "HS256"
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

# Initialize Twilio
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- IN-MEMORY DATABASES (Global) ---
otp_storage: Dict[str, str] = {} 
users_db: Dict[str, dict] = {}  # <--- FIXED: Defined global DB

# --- HELPER FUNCTIONS (You were missing these!) ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- MODELS ---
class LoginRequest(BaseModel):
    phone_number: str

class VerifyRequest(BaseModel):
    phone_number: str
    otp: str
    full_name: str = "Artisan"

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "ArtConnect API is LIVE!"}

@app.post("/auth/send-otp")
def send_otp(request: LoginRequest):
    phone = request.phone_number
    otp_code = str(random.randint(1000, 9999))
    otp_storage[phone] = otp_code
    
    print(f"🔐 GENERATED OTP for {phone}: {otp_code}") 

    try:
        twilio_client.messages.create(
            body=f"Your ArtConnect Login Code is: {otp_code}",
            from_=TWILIO_PHONE,
            to=phone
        )
    except Exception as e:
        print(f"⚠️ SMS Failed (Trial Account): {e}")

    return {"message": "OTP generated"}

@app.post("/auth/verify-otp")
def verify_otp(request: VerifyRequest):
    phone = request.phone_number
    user_otp = request.otp
    
    # 1. Check OTP
    if phone not in otp_storage or otp_storage[phone] != user_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # 2. Clear OTP
    del otp_storage[phone]
    
    # 3. Register User if new
    if phone not in users_db:
        users_db[phone] = {
            "phone": phone,
            "full_name": request.full_name,
            "joined_at": str(datetime.utcnow())
        }
    
    # 4. Generate Token
    access_token = create_access_token(data={"sub": phone})
    
    return {
        "message": "Login Successful",
        "access_token": access_token, 
        "token_type": "bearer",
        "user": users_db[phone]
    }