from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
from instagrapi import Client as InstaClient
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Annotated, List
from sqlalchemy.orm import Session
import os
import random
import json
import base64
import io
import time
import requests 
from fastapi.staticfiles import StaticFiles 
from fastapi.responses import FileResponse

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageEnhance
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec 

# Import database logic
from database import init_db, get_db, UserTable, ArtformTable

# --- 1. CONFIGURATION ---
load_dotenv()
init_db()

app = FastAPI()
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INSTAGRAM SETUP ---
IG_USER = os.getenv("IG_USERNAME")
IG_PASS = os.getenv("IG_PASSWORD")
cl = InstaClient()
SESSION_FILE = "instagram_session.json"

# --- SECRETS & KEYS ---
SECRET_KEY = os.getenv("SECRET_KEY", "hackathon_secret")
ALGORITHM = "HS256"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY") 
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)

# In-Memory OTP Storage
otp_storage = {} 

# --- AI CLIENTS SETUP ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.2})

pc = Pinecone(api_key=PINECONE_API_KEY)
INDEX_NAME = "art-recommendations"

if INDEX_NAME not in [i.name for i in pc.list_indexes()]:
    pc.create_index(
        name=INDEX_NAME,
        dimension=768, 
        metric="cosine", 
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
pinecone_index = pc.Index(INDEX_NAME)


# --- HELPER FUNCTIONS ---

def login_to_instagram():
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USER, IG_PASS)
            return
        except: pass
    try:
        time.sleep(2) 
        cl.login(IG_USER, IG_PASS)
        cl.dump_settings(SESSION_FILE)
    except Exception as e:
        print(f"IG Login Fail: {e}")

def upload_to_instagram_task(image_bytes, caption):
    temp_filename = f"temp_upload_{int(time.time())}.jpg"
    try:
        with open(temp_filename, "wb") as f: f.write(image_bytes)
        login_to_instagram()
        cl.photo_upload(path=temp_filename, caption=caption)
    except Exception as e: print(f"IG Upload Error: {e}")
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)

def process_sarvam_audio(audio_bytes, filename="audio.wav"):
    url = "https://api.sarvam.ai/speech-to-text-translate"
    payload = { "model": "saaras:v2.5" } 
    headers = { "api-subscription-key": SARVAM_API_KEY }
    try:
        files = [('file', (filename, audio_bytes, 'audio/wav'))]
        response = requests.post(url, headers=headers, data=payload, files=files)
        if response.status_code == 200: return response.json().get("transcript", "")
        else: return ""
    except: return ""

def get_embedding(text: str):
    return genai.embed_content(
        model="models/text-embedding-004", content=text,
        task_type="retrieval_document", output_dimensionality=768
    )['embedding']

def enhance_image_quality(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        enhancer = ImageEnhance.Sharpness(img)
        img_sharpened = enhancer.enhance(1.5)
        contrast = ImageEnhance.Contrast(img_sharpened)
        img_final = contrast.enhance(1.1)
        output = io.BytesIO()
        img_final.save(output, format=img.format or "JPEG", quality=95)
        return output.getvalue()
    except: return image_bytes

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token_obj: Annotated[HTTPAuthorizationCredentials, Depends(security)], db: Session = Depends(get_db)):
    token = token_obj.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone: str = payload.get("sub")
    except: raise HTTPException(401, "Invalid Token")
    user = db.query(UserTable).filter(UserTable.phone == phone).first()
    if not user: raise HTTPException(401)
    return user

# --- MODELS ---
class ArtworkProfileResponse(BaseModel):
    id: int
    title: str | None
    price: int | None
    description: str | None
    art_form_tag: str | None
    app_title: str | None
    corrected_voice: str | None
    min_price: int | None  # <--- Added
    max_price: int | None  # <--- Added
    is_published: bool
    image_base64: str | None

class LoginRequest(BaseModel):
    phone_number: str

class VerifyRequest(BaseModel):
    phone_number: str
    otp: str

class ProfileUpdate(BaseModel):
    full_name: str
    location: str
    role: str = "Artisan"

class PublishRequest(BaseModel):
    art_id: int
    final_price: int

# --- ENDPOINTS ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')
@app.post("/utils/transcribe")
async def transcribe_audio(voice_file: UploadFile = File(...)):
    audio_bytes = await voice_file.read()
    if not audio_bytes: raise HTTPException(400, "Empty audio")
    transcript = process_sarvam_audio(audio_bytes, voice_file.filename)
    if not transcript: raise HTTPException(500, "Transcription failed")
    return {"transcript": transcript}

# --- AUTH ---
@app.post("/auth/send-otp")
def send_otp(request: LoginRequest):
    otp = str(random.randint(1000, 9999))
    otp_storage[request.phone_number] = otp
    
    print(f"🔐 DEBUG OTP: {otp}")  # <--- Always works (Check terminal!)

    try:
        # Attempt to send SMS
        twilio_client.messages.create(
            body=f"Your ArtConnect Login Code: {otp}",
            from_=TWILIO_PHONE,
            to=request.phone_number
        )
        print("✅ Twilio SMS sent successfully")
    except Exception as e:
        # PRINT THE ERROR so you can see it
        print(f"❌ Twilio Failed: {str(e)}")
    
    return {"message": "OTP Sent (Check Terminal if SMS failed)"}

@app.post("/auth/verify-otp")
def verify_otp(request: VerifyRequest, db: Session = Depends(get_db)):
    if otp_storage.get(request.phone_number) != request.otp:
        raise HTTPException(400, "Invalid OTP")
    del otp_storage[request.phone_number]
    
    user = db.query(UserTable).filter(UserTable.phone == request.phone_number).first()
    is_new = False
    if not user:
        is_new = True
        user = UserTable(phone=request.phone_number, full_name="", is_new=True)
        db.add(user)
        db.commit()
    elif user.is_new: is_new = True
    
    return {
        "access_token": create_access_token({"sub": user.phone}), 
        "is_new_user": is_new,
        "full_name": user.full_name
    }

@app.post("/user/profile")
async def update_profile(data: ProfileUpdate, user: UserTable = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name
    user.location = data.location
    user.role = data.role
    user.is_new = False
    db.commit()
    return {"message": "Saved"}

# --- ART OPERATIONS ---

@app.post("/art/analyze-draft")
async def analyze_art_draft(
    user_voice: str = Form(...),
    file: UploadFile = File(...),     
    current_user: UserTable = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    original_bytes = await file.read()
    processed_bytes = enhance_image_quality(original_bytes)
    base64_img = base64.b64encode(processed_bytes).decode('utf-8')

    # 2. Gemini Analysis (USING THE FULL PROMPT)
    prompt = f"""
Role: You are a strict, conservative Art Appraiser and a Professional Social Media Editor. 
Task: Analyze the uploaded image and the user's description: '{user_voice}'.

--- PART 1: VALUATION RULES ---
1. CLASSIFY: Determine the 'Artist Level' based strictly on visual technical skill:
   - Beginner/Hobbyist: Simple techniques, standard materials. (Price Tier: Low)
   - Emerging Artist: Consistent style, good composition. (Price Tier: Medium)
   - Professional: Gallery-quality, exceptional technique. (Price Tier: High)

2. PRICE: Estimate a realistic sellable price in INDIAN RUPEES (₹).
   - Compare with unverified artwork on Etsy/ArtStation.
   - DO NOT assume the artist is famous. Be conservative.
   - The gap between Min and Max price must NOT exceed 30% of the Min price.

--- PART 2: CONTENT GENERATION RULES ---
1. ART TAG: Be precise and descriptive (e.g., "Oil on Canvas", "Digital Vector Art"). Avoid abstract terms.
2. APP TITLE: Write one emotional, captivating sentence about the art.
3. INSTAGRAM CAPTION: Create a catchy, trendy caption with hashtags.

--- PART 3: VOICE CORRECTION RULES ---
Refine the user's description ('{user_voice}') for the 'corrected_voice' field:
   - Preserve Core Meaning: Do not change the artist's intent.
   - Fix Grammar: Correct errors and awkward phrasing.
   - Polish Tone: Make it professional but authentic.
   - Maintain Voice: If they sound humble, keep it humble. If excited, keep it excited. DO NOT use corporate marketing speak.

--- OUTPUT FORMAT ---
Return ONLY a valid JSON object with this exact structure:
{{
  "price_min": 1000,
  "price_max": 1300,
  "currency": "INR",
  "reasoning": "Brief explanation of valuation based on skill level.",
  "instagram_caption": "Your caption here...",
  "art_tag": "Precise Art Form",
  "app_title": "Emotional sentence about the art...",
  "corrected_voice": "The refined version of the user's text..."
}}
"""
    try:
        res = model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': original_bytes}])
        analysis = json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e: raise HTTPException(500, f"AI Error: {e}")

    new_art = ArtformTable(
        title=analysis['app_title'], 
        price=0, 
        description=user_voice,
        image_data=processed_bytes, 
        owner_phone=current_user.phone,
        art_form_tag=analysis['art_tag'], 
        app_title=analysis['app_title'],
        corrected_voice=analysis['corrected_voice'], 
        min_price=analysis['price_min'], # <--- SAVING MIN PRICE
        max_price=analysis['price_max'], # <--- SAVING MAX PRICE
        is_published=False 
    )
    db.add(new_art)
    db.commit()
    
    return {
        "status": "draft_created", "art_id": new_art.id,
        "ai_suggestions": {
            "recommended_min": analysis['price_min'], 
            "recommended_max": analysis['price_max'],
            "title": analysis['app_title'],
            "voice": analysis['corrected_voice']
        },
        "image_preview": base64_img
    }

@app.post("/art/publish")
async def publish_art(
    request: PublishRequest, background_tasks: BackgroundTasks, 
    current_user: UserTable = Depends(get_current_user), db: Session = Depends(get_db)
):
    art = db.query(ArtformTable).filter(ArtformTable.id == request.art_id).first()
    if not art: raise HTTPException(404)
    art.price = request.final_price
    art.is_published = True
    db.commit()

    vector_text = f"{art.art_form_tag} {art.app_title} {art.corrected_voice}"
    pinecone_index.upsert(vectors=[{
        "id": str(art.id),
        "values": get_embedding(vector_text),
        "metadata": {"tag": art.art_form_tag, "price": request.final_price, "artist": current_user.full_name}
    }])

    caption = f"{art.app_title}\n\n🎨 {current_user.full_name}\n💰 ₹{art.price}\n\n{art.corrected_voice}\n#ArtConnect"
    background_tasks.add_task(upload_to_instagram_task, art.image_data, caption)

    return {"status": "published"}

# --- DELETE ENDPOINT ---
@app.delete("/art/{art_id}")
def delete_art(art_id: int, current_user: UserTable = Depends(get_current_user), db: Session = Depends(get_db)):
    art = db.query(ArtformTable).filter(ArtformTable.id == art_id).first()
    if not art: raise HTTPException(404, "Artwork not found")
    if art.owner_phone != current_user.phone: raise HTTPException(403, "Not authorized to delete this art")

    try:
        pinecone_index.delete(ids=[str(art_id)])
    except Exception as e:
        print(f"Pinecone delete error: {e}")

    db.delete(art)
    db.commit()
    return {"status": "deleted", "message": "Artwork removed from database and search index"}

# --- VIEWING ---
@app.get("/user/profile/artworks", response_model=List[ArtworkProfileResponse])
def get_my_artworks(current_user: UserTable = Depends(get_current_user), db: Session = Depends(get_db)):
    artworks = db.query(ArtformTable).filter(ArtformTable.owner_phone == current_user.phone).all()
    res = []
    for art in artworks:
        img = base64.b64encode(art.image_data).decode('utf-8') if art.image_data else None
        res.append(ArtworkProfileResponse(
            id=art.id, title=art.title, price=art.price, description=art.description,
            art_form_tag=art.art_form_tag, app_title=art.app_title, corrected_voice=art.corrected_voice,
            min_price=art.min_price, # <--- RETURNING MIN PRICE
            max_price=art.max_price, # <--- RETURNING MAX PRICE
            is_published=art.is_published, image_base64=img
        ))
    return res

@app.get("/buyer/recommendations")
def get_recommendations(query: str, db: Session = Depends(get_db)):
    res = pinecone_index.query(vector=get_embedding(query), top_k=5, include_metadata=True)
    out = []
    for m in res['matches']:
        art = db.query(ArtformTable).filter(ArtformTable.id == int(m['id']), ArtformTable.is_published == True).first()
        if art:
            img = base64.b64encode(art.image_data).decode('utf-8') if art.image_data else None
            out.append({
                "id": art.id, "title": art.app_title, "artist": m['metadata'].get('artist'),
                "price": art.price, "tag": art.art_form_tag, "image_base64": img
            })
    return out