import os,time,re,requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
load_dotenv()
TALLY_URL=os.getenv("TALLY_URL","http://127.0.0.1:9000/")
CLOUD_URL=os.getenv("CLOUD_URL","")
SECRET=os.getenv("CONNECTOR_SHARED_SECRET","")
SYNC=int(os.getenv("SYNC_SECONDS","60"))

def tally(xml):
    r=requests.post(TALLY_URL,data=xml.encode("utf-8"),headers={"Content-Type":"text/xml"},timeout=30);r.raise_for_status();return r.text
def clean(s):return re.sub(r"<(/?)[A-Za-z_][\w.-]*:",r"<\1",s)
def tag(e):return e.tag.split("}")[-1].upper()
def txt(e,names):
    for x in e.iter():
        if tag(x) in names and (x.text or "").strip():return x.text.strip()
    return ""
def stock_items(raw):
    try:root=ET.fromstring(clean(raw))
    except Exception:return []
    out=[]
    for e in root.iter():
        if tag(e) in {"STOCKITEM","STOCKITEMNAME"}:
            name=txt(e,{"NAME","STOCKITEMNAME"})
            if name:
                out.append({"name":name,"code":txt(e,{"STOCKITEMNAME","ALTERID"}),"quantity":txt(e,{"CLOSINGBALANCE","CLOSINGQTY","ACTUALQTY"}),"unit":txt(e,{"BASEUNITS","UNIT"})})
    return out
def ledger_items(raw):
    try:root=ET.fromstring(clean(raw))
    except Exception:return []
    out=[]
    for e in root.iter():
        if tag(e)=="LEDGER":
            name=txt(e,{"NAME","LEDGERNAME"})
            if name:out.append({"name":name,"parent":txt(e,{"PARENT"}),"closing":txt(e,{"CLOSINGBALANCE"})})
    return out
def sync():
    if not CLOUD_URL:raise RuntimeError("CLOUD_URL is not configured")
    stock_raw=tally("<ENVELOPE><HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>StockItem</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>")
    ledger_raw=tally("<ENVELOPE><HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>Ledger</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>")
    payload={"company":"default","stock":stock_items(stock_raw),"ledgers":ledger_items(ledger_raw),"documents":[]}
    r=requests.post(CLOUD_URL.rstrip("/")+"/connector/sync",json=payload,headers={"X-Connector-Secret":SECRET},timeout=30);r.raise_for_status()
    print("SYNC",r.text,flush=True)
while True:
    try:sync()
    except Exception as e:print("SYNC ERROR:",e,flush=True)
    time.sleep(SYNC)
