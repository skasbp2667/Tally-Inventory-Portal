from fastapi import FastAPI,Header,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse,Response
import os,jwt
from datetime import datetime,timedelta,timezone
from pydantic import BaseModel

JWT_SECRET=os.getenv("JWT_SECRET","CHANGE_ME")
CONNECTOR_SECRET=os.getenv("CONNECTOR_SHARED_SECRET","CHANGE_ME")
app=FastAPI(title="Tally Inventory Portal API",version="2.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS","*").split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
USERS={"admin":{"password":os.getenv("ADMIN_PASSWORD","CHANGE_ME"),"role":"admin","approved":True,"permissions":["stock","ledgers","multi_ledger","documents","users"]}}
STOCK_CACHE=[];LEDGER_CACHE=[];DOCUMENT_CACHE=[];STATUS={"online":False,"last_seen":None,"stock_count":0,"ledger_count":0}

class Login(BaseModel): username:str;password:str
class Register(BaseModel): username:str;password:str
class Sync(BaseModel): company:str="default";stock:list=[];ledgers:list=[];documents:list=[]

def auth(h):
    if not h or not h.startswith("Bearer "): raise HTTPException(401,"Missing bearer token")
    try:return jwt.decode(h[7:],JWT_SECRET,algorithms=["HS256"])
    except Exception:raise HTTPException(401,"Invalid or expired token")
def need(h,p):
    u=auth(h)
    if p not in u.get("permissions",[]):raise HTTPException(403,"Permission denied")
    return u
def make_token(name,u):
    n=datetime.now(timezone.utc)
    return jwt.encode({"sub":name,"role":u["role"],"permissions":u["permissions"],"iat":n,"exp":n+timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES","30")))},JWT_SECRET,algorithm="HS256")

@app.get("/health")
def health():return {"status":"OK","service":"tally-portal-cloud","version":"2.0","connector":STATUS}

@app.post("/auth/login")
def login(b:Login):
    u=USERS.get(b.username)
    if not u or u["password"]!=b.password:raise HTTPException(401,"Invalid credentials")
    if not u["approved"]:raise HTTPException(403,"User is awaiting approval")
    return {"access_token":make_token(b.username,u),"token_type":"bearer","permissions":u["permissions"]}

@app.post("/auth/register")
def register(b:Register):
    if b.username in USERS:raise HTTPException(409,"Username already exists")
    if len(b.password)<6:raise HTTPException(400,"Password must be at least 6 characters")
    USERS[b.username]={"password":b.password,"role":"user","approved":False,"permissions":["stock","ledgers"]}
    return {"status":"PENDING_APPROVAL"}

@app.get("/api/stock")
def stock(h:str=Header(None,alias="Authorization")):
    need(h,"stock");return {"status":"LIVE" if STATUS["online"] else "CACHED","items":STOCK_CACHE,"last_sync":STATUS["last_seen"]}

@app.get("/api/ledgers")
def ledgers(h:str=Header(None,alias="Authorization")):
    need(h,"ledgers");return {"status":"LIVE" if STATUS["online"] else "CACHED","items":LEDGER_CACHE,"last_sync":STATUS["last_seen"]}

@app.get("/api/documents")
def documents(h:str=Header(None,alias="Authorization")):
    need(h,"documents");return {"items":DOCUMENT_CACHE}

@app.get("/admin/users")
def users(h:str=Header(None,alias="Authorization")):
    need(h,"users");return [{"username":k,"approved":v["approved"],"permissions":v["permissions"]} for k,v in USERS.items()]

@app.post("/admin/users/{name}/approve")
def approve(name:str,h:str=Header(None,alias="Authorization")):
    need(h,"users")
    if name not in USERS:raise HTTPException(404,"User not found")
    USERS[name]["approved"]=True;return {"status":"APPROVED","username":name}

@app.post("/admin/users/{name}/permissions")
def perms(name:str,b:dict,h:str=Header(None,alias="Authorization")):
    need(h,"users")
    if name not in USERS:raise HTTPException(404,"User not found")
    allowed={"stock","ledgers","multi_ledger","documents"}
    USERS[name]["permissions"]=[x for x in b.get("permissions",[]) if x in allowed]
    return {"username":name,"permissions":USERS[name]["permissions"]}

@app.post("/connector/sync")
def sync(b:Sync,x_connector_secret:str=Header(None,alias="X-Connector-Secret")):
    if CONNECTOR_SECRET=="CHANGE_ME" or x_connector_secret!=CONNECTOR_SECRET:raise HTTPException(401,"Invalid connector secret")
    global STOCK_CACHE,LEDGER_CACHE,DOCUMENT_CACHE
    STOCK_CACHE=[{"name":x.get("name",""),"code":x.get("code",""),"quantity":x.get("quantity",x.get("qty",0)),"unit":x.get("unit","")} for x in b.stock if isinstance(x,dict) and x.get("name")]
    LEDGER_CACHE=b.ledgers;DOCUMENT_CACHE=b.documents
    STATUS.update({"online":True,"last_seen":datetime.now(timezone.utc).isoformat(),"stock_count":len(STOCK_CACHE),"ledger_count":len(LEDGER_CACHE)})
    return {"status":"OK","stock":len(STOCK_CACHE),"ledgers":len(LEDGER_CACHE)}

@app.get("/admin/connector-status")
def connector(h:str=Header(None,alias="Authorization")):need(h,"users");return STATUS

@app.get("/app",response_class=HTMLResponse)
def app_ui():
    return HTMLResponse("""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>Tally Inventory Portal</title><style>body{font-family:Arial;max-width:520px;margin:auto;padding:20px}input,button{width:100%;padding:12px;margin:6px 0;box-sizing:border-box}button{cursor:pointer}pre{white-space:pre-wrap}</style><h2>Tally Inventory Portal</h2><input id=u placeholder=Username><input id=p type=password placeholder=Password><button onclick=login()>Sign in</button><div id=x></div><script>let t=localStorage.tallyToken||"",d=[];async function login(){let r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u.value,password:p.value})});let j=await r.json();if(!r.ok)return alert(j.detail||'Login failed');t=j.access_token;localStorage.tallyToken=t;show()}async function get(z){return (await fetch(z,{headers:{Authorization:'Bearer '+t}})).json()}function show(){x.innerHTML='<button onclick=s()>Stock</button><button onclick=l()>Ledgers</button><input id=q placeholder="Search after 3 letters" oninput=f()><pre id=o></pre>';s()}async function s(){let j=await get('/api/stock');d=j.items||[];o.textContent=JSON.stringify(j,null,2)}async function l(){o.textContent=JSON.stringify(await get('/api/ledgers'),null,2)}function f(){let z=q.value.toLowerCase();if(z.length<3)return;let a=d.filter(v=>(v.name+' '+v.code).toLowerCase().includes(z));o.textContent=JSON.stringify(a,null,2)}if(t)show()</script>""")
@app.get("/app/manifest.webmanifest")
def manifest():return Response('{"name":"Tally Inventory Portal","short_name":"Tally Portal","start_url":"/app","display":"standalone","icons":[]}',media_type="application/manifest+json")
