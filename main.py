from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from pydantic import BaseModel

app = FastAPI(title="IG-FB Privacy Check")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class URLIn(BaseModel):
    url: str

def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)

def check_privacy(url: str) -> bool:
    """return True dacă e PUBLIC și False dacă e PRIVAT"""
    driver = get_driver()
    try:
        driver.get(url)
        time.sleep(3)
        private_msgs = [
            "This Account is Private",
            "Sorry, this page isn't available",
            "Content not available",
            "log in to continue" 
        ]
        return not any(msg in driver.page_source for msg in private_msgs)
    finally:
        driver.quit()

@app.post("/check/instagram")
def ig_check(data: URLIn):
    if "instagram.com" not in data.url:
        raise HTTPException(400, "URL invalid (Instagram)")
    return {"public": check_privacy(data.url)}

@app.post("/check/facebook")
def fb_check(data: URLIn):
    if "facebook.com" not in data.url:
        raise HTTPException(400, "URL invalid (Facebook)")
    return {"public": check_privacy(data.url)}