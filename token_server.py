"""Issues short-lived LiveKit room tokens. Never expose LIVEKIT_API_SECRET to the browser."""
import os, re, uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

app = FastAPI(title="BoloPay LiveKit Token Service")
allowed = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed, allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"ok": True, "service": "bolopay-token"}

@app.get("/token")
async def create_token(language: str = Query("en-IN", max_length=10), room: str = Query("", max_length=120), identity: str = Query("", max_length=80)):
    api_key = os.getenv("LIVEKIT_API_KEY", "")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "")
    livekit_url = os.getenv("LIVEKIT_URL", "")
    if not all([api_key, api_secret, livekit_url]):
        raise HTTPException(503, "LiveKit server credentials are not configured")
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", language):
        raise HTTPException(400, "Unsupported language code format")
    if not room:
        room = f"bolopay_{language}_{uuid.uuid4().hex[:12]}"
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,120}", room):
        raise HTTPException(400, "Invalid room name")
    if not identity:
        identity = f"web-{uuid.uuid4().hex[:10]}"
    identity = re.sub(r"[^A-Za-z0-9_-]", "", identity)[:80] or f"web-{uuid.uuid4().hex[:10]}"
    token = api.AccessToken(api_key, api_secret).with_identity(identity).with_name("BoloPay Web User").with_grants(
        api.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True, can_publish_data=True)
    ).to_jwt()
    return {"token": token, "url": livekit_url, "room": room, "identity": identity}
