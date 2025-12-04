from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests, re, json, time

app = FastAPI(title="IG-FB Privacy Check")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class URLIn(BaseModel):
    url: str

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
}

def ig_is_public(shortcode: str) -> bool:
    """ shortcode = username sau post """
    api = f"https://www.instagram.com/{shortcode}/?__a=1&__d=dis"
    r = requests.get(api, headers=HEADERS, timeout=3)
    if r.status_code != 200:
        return False
    try:
        return not r.json()["user"]["is_private"]
    except:
        return False

def fb_is_public(url: str) -> bool:
    r = requests.get(url, headers=HEADERS, timeout=3)
    return "This content isn't available right now" not in r.text

@app.post("/check/instagram")
def ig_check(data: URLIn):
    if "instagram.com" not in data.url:
        raise HTTPException(400, "URL invalid (Instagram)")
    username = data.url.strip("/").split("/")[-1]
    return {"public": ig_is_public(username)}

@app.post("/check/facebook")
def fb_check(data: URLIn):
    if "facebook.com" not in data.url:
        raise HTTPException(400, "URL invalid (Facebook)")
    return {"public": fb_is_public(data.url)}