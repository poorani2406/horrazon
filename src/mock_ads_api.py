from fastapi import FastAPI, HTTPException
from pathlib import Path
from datetime import datetime
import json, random
app=FastAPI(title="Meridian Ads API")
rows=json.loads((Path(__file__).resolve().parents[1]/"sources/ads.json").read_text(encoding="utf-8"))
@app.get("/ads")
def ads(page:int=1,page_size:int=100,updated_after:str|None=None):
    if random.random()<0.05:
        raise HTTPException(429,"Temporary API rate limit")
    selected=rows
    if updated_after:
        cutoff=datetime.fromisoformat(updated_after.replace("Z","+00:00"))
        selected=[r for r in rows if datetime.fromisoformat(r["updated_at"].replace("Z","+00:00"))>cutoff]
    start=(page-1)*page_size
    return {"data":selected[start:start+page_size],"has_next":start+page_size<len(selected)}
