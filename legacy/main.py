import asyncio
import schemas
import models
import hashlib
from passlib.context import CryptContext
from fastapi import FastAPI, Request, Depends
from seo_analyzer import AsyncSEOAnalyzer
from urllib.parse import urlparse
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException
from database import SessionLocal, engine
from sqlalchemy.orm import Session
from models import SEOReport
from datetime import datetime


app = FastAPI(title="SEO Analysis API", version="0.0.1", description="Analyze and generate SEO reports for web pages.")
# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Utils ---

# hash password
def hash_password(password: str) -> str:
    # Step 1: Pre-hash the password with SHA-256 (any length supported)
    sha256_digest = hashlib.sha256(password.encode("utf-8")).digest()
    # Step 2: Pass the digest to bcrypt
    return pwd_context.hash(sha256_digest)

# verify password with hash from database
def verify_password(password: str, hashed: str) -> bool:
    sha256_digest = hashlib.sha256(password.encode("utf-8")).digest()
    return pwd_context.verify(sha256_digest, hashed)






#core seo analysis endpoint
@app.get("/seoapi")
async def analyze(url: str, db: Session = Depends(get_db)):
    parsed = urlparse(url)

    dominant_keyword, json_output = await AsyncSEOAnalyzer(url).analyze()
    
    # 🔹 STORE IN DATABASE
    report = SEOReport(
        url=url,
        user_id=1,  # TEMP: replace later with authenticated user ID
        title=json_output.get("checks", {}).get("title_tag", {}).get("value", "") if isinstance(json_output, dict) else "",
        dominant_keyword=dominant_keyword,
        results=json_output,
        
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    # 🔹 RETURN API RESPONSE (unchanged)
    return {
        "url": url,
        "domain": parsed.netloc,
        "dominant_keyword": dominant_keyword,
        "results": json_output
    }


##############################################################################################

# user creation / signup
@app.post("/signup", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    exists = db.query(models.Users).filter(
        (models.Users.email == user.email) |
        (models.Users.username == user.username)
    ).first()

    if exists:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = models.Users(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # create quota automatically
    quota = models.Quotas(user_id=new_user.id)
    db.add(quota)
    db.commit()

    return new_user


# user login check
@app.post("/login", response_model=schemas.UserOut)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.Users).filter(models.Users.email == user.email).first()
    if not db_user :
        raise HTTPException(status_code=400, detail="No such user found")
    elif not verify_password(user.password, str(db_user.hashed_password)):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return db_user


