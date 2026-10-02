import os,time,requests
from dotenv import load_dotenv
load_dotenv()
TALLY_URL=os.getenv("TALLY_URL","http://127.0.0.1:9000/")
CLOUD_URL=os.getenv("CLOUD_URL","")
SECRET=os.getenv("CONNECTOR_SHARED_SECRET","")
SYNC=int(os.getenv("SYNC_SECONDS","60"))
def tally(xml):
    r=requests.post(TALLY_URL,data=xml.encode("utf-8"),headers={"Content-Type":"text/xml"},timeout=30); r.raise_for_status(); return r.text
def sync():
    stock=tally("<ENVELOPE><HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>StockItem</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>")
    ledgers=tally("<ENVELOPE><HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>Ledger</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>")
    if not CLOUD_URL: raise RuntimeError("CLOUD_URL is not configured")
    requests.post(CLOUD_URL.rstrip("/")+"/connector/sync",json={"company":"default","stock":[{"raw":stock}],"ledgers":[{"raw":ledgers}]},headers={"X-Connector-Secret":SECRET},timeout=30).raise_for_status()
while True:
    try: sync(); print("SYNC OK",flush=True)
    except Exception as e: print("SYNC ERROR:",e,flush=True)
    time.sleep(SYNC)
