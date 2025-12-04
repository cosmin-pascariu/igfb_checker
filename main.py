from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

app = FastAPI(title="IG-FB Privacy Check")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class URLIn(BaseModel):
    url: str

def build_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--window-size=1920,1080")
    # User agent pentru a evita detectarea bot-ului
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=opts)

driver = build_driver()

def check_instagram_privacy(url: str) -> bool:
    """
    Returnează True dacă profilul este PUBLIC, False dacă este PRIVAT
    """
    driver.get(url)
    time.sleep(4)  # Așteaptă încărcarea completă
    
    try:
        page_source = driver.page_source.lower()
        
        # Verificări pentru cont PRIVAT
        # Instagram afișează un SVG specific pentru conturile private
        private_indicators = [
            "this account is private",
            "this account is private.",
            "follow to see their photos and videos",
            "follow this account to see their photos and videos",
        ]
        
        if any(indicator in page_source for indicator in private_indicators):
            return False
        
        # Verifică dacă există iconița de lacăt (profil privat)
        try:
            driver.find_element(By.XPATH, "//*[contains(@aria-label, 'private') or contains(@aria-label, 'Private')]")
            return False
        except:
            pass
        
        # Verifică prezența grid-ului de postări (indiciu de cont PUBLIC)
        try:
            # Caută article care conține imagini sau link-uri către postări
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article a[href*='/p/']"))
            )
            return True
        except TimeoutException:
            pass
        
        # Verifică dacă există mesajul "No posts yet" (cont public fără postări)
        if "no posts yet" in page_source or "when they share photos" in page_source:
            # Dacă e cont public fără postări, nu va avea mesajul de "follow to see"
            if "follow to see" not in page_source and "follow this account" not in page_source:
                return True
        
        # Dacă nu găsim dovezi clare, verificăm numărul de postări
        # Conturile private afișează "0 posts" chiar dacă au postări
        try:
            # Caută meta tags sau structured data
            posts_meta = driver.find_element(By.XPATH, "//meta[@property='og:description']")
            description = posts_meta.get_attribute("content").lower()
            
            # Dacă în descriere apare "followers" dar nu "posts", e privat
            if "followers" in description and "posts" not in description:
                return False
        except:
            pass
        
        # Default: dacă nu găsim indicatori clari, presupunem că e privat
        # (pentru siguranță, mai bine false negative decât false positive)
        return False
        
    except Exception as e:
        print(f"Error checking Instagram: {e}")
        return False

def check_facebook_privacy(url: str) -> bool:
    """
    Returnează True dacă profilul/pagina este PUBLIC, False dacă este PRIVAT
    """
    driver.get(url)
    time.sleep(4)
    
    try:
        page_source = driver.page_source.lower()
        
        # Verificări pentru profil/pagină PRIVATĂ
        private_indicators = [
            "this content isn't available",
            "content not available",
            "log in to continue",
            "you must log in to continue",
            "this profile is private",
        ]
        
        if any(indicator in page_source for indicator in private_indicators):
            return False
        
        # Verifică dacă există postări vizibile (indiciu de cont public)
        try:
            # Caută feed-ul de postări
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='article'], [data-pagelet*='FeedUnit']"))
            )
            return True
        except TimeoutException:
            pass
        
        # Verifică dacă există butonul "Add Friend" sau "Follow" (indiciu de profil vizibil)
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), 'Add Friend') or contains(text(), 'Follow')]")
            return True
        except:
            pass
        
        # Default: privat
        return False
        
    except Exception as e:
        print(f"Error checking Facebook: {e}")
        return False

@app.post("/check/instagram")
def ig_check(data: URLIn):
    if "instagram.com" not in data.url:
        raise HTTPException(400, "URL invalid (Instagram)")
    
    is_public = check_instagram_privacy(data.url)
    return {
        "url": data.url,
        "platform": "instagram",
        "public": is_public,
        "private": not is_public
    }

@app.post("/check/facebook")
def fb_check(data: URLIn):
    if "facebook.com" not in data.url:
        raise HTTPException(400, "URL invalid (Facebook)")
    
    is_public = check_facebook_privacy(data.url)
    return {
        "url": data.url,
        "platform": "facebook",
        "public": is_public,
        "private": not is_public
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("shutdown")
def shutdown():
    driver.quit()