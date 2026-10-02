import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

JWT_SECRET=os.getenv("JWT_SECRET","CHANGE_ME")
CONNECTOR_SECRET=os.getenv("CONNECTOR_SHARED_SECRET","CHANGE_ME")
TOKEN_MINUTES=int(os.getenv("ACCESS_TOKEN_MINUTES","30"))
origins=[x.strip() for x in os.getenv("CORS_ORIGINS","*").split(",") if x.strip()]
app=FastAPI(title="Tally Inventory Portal API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
USERS={"admin":{"password":os.getenv("ADMIN_PASSWORD","CHANGE_ME"),"role":"admin","approved":True}}
STOCK_CACHE=[]; LEDGER_CACHE=[]; CONNECTOR_STATUS={"online":False,"last_seen":None}

class Login(BaseModel):
    username:str
    password:str
class ConnectorPayload(BaseModel):
    company:str="default"
    stock:list=[]
    ledgers:list=[]

def token(user,role):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":user,"role":role,"iat":now,"exp":now+timedelta(minutes=TOKEN_MINUTES)},JWT_SECRET,algorithm="HS256")
def auth(value:Optional[str]):
    if not value or not value.startswith("Bearer "): raise HTTPException(401,"Missing bearer token")
    try:return jwt.decode(value[7:],JWT_SECRET,algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401,"Invalid or expired token")

@app.get("/health")
def health(): return {"status":"OK","service":"tally-portal-cloud"}
@app.post("/auth/login")
def login(body:Login):
    u=USERS.get(body.username)
    if not u or u["password"]!=body.password: raise HTTPException(401,"Invalid credentials")
    if not u["approved"]: raise HTTPException(403,"User is awaiting approval")
    return {"access_token":token(body.username,u["role"]),"token_type":"bearer"}
@app.get("/api/stock")
def stock(authorization:Optional[str]=Header(None)):
    auth(authorization); return {"status":"LIVE_OR_CACHED","items":STOCK_CACHE}
@app.get("/api/ledgers")
def ledgers(authorization:Optional[str]=Header(None)):
    auth(authorization); return {"status":"LIVE_OR_CACHED","items":LEDGER_CACHE}
@app.post("/connector/sync")
def sync(payload:ConnectorPayload,x_connector_secret:Optional[str]=Header(None)):
    if x_connector_secret!=CONNECTOR_SECRET: raise HTTPException(401,"Invalid connector secret")
    global STOCK_CACHE,LEDGER_CACHE
    STOCK_CACHE=payload.stock; LEDGER_CACHE=payload.ledgers
    CONNECTOR_STATUS["online"]=True; CONNECTOR_STATUS["last_seen"]=datetime.now(timezone.utc).isoformat()
    return {"status":"OK","stock":len(STOCK_CACHE),"ledgers":len(LEDGER_CACHE)}
@app.get("/admin/connector-status")
def connector_status(authorization:Optional[str]=Header(None)):
    u=auth(authorization)
    if u.get("role")!="admin": raise HTTPException(403,"Admin only")
    return CONNECTOR_STATUS
