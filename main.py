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
    opts.add_argument("--window-size=1920,1080")
    # User agent real pentru a evita blocarea
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=opts)

def check_instagram_privacy(url: str) -> bool:
    """Returnează True dacă e PUBLIC, False dacă e PRIVAT"""
    driver = get_driver()
    try:
        driver.get(url)
        time.sleep(5)  # Așteaptă încărcarea completă
        
        source = driver.page_source
        source_lower = source.lower()
        
        # DEBUG - elimină după testare
        print(f"\n=== DEBUG Instagram: {url} ===")
        print(f"Title: {driver.title}")
        print(f"URL final: {driver.current_url}")
        print(f"Source length: {len(source)}")
        
        # Salvează pentru debugging (opțional)
        with open("/tmp/instagram_page.html", "w", encoding="utf-8") as f:
            f.write(source[:10000])
        
        # Verifică dacă pagina s-a încărcat corect
        if len(source) < 5000:
            print("⚠ Pagină prea scurtă - Instagram poate bloca")
            return True  # Default public dacă nu putem determina
        
        # Indicatori de cont PRIVAT
        private_indicators = [
            "this account is private",
            "follow to see their photos and videos",
            "follow this account to see their photos and videos",
        ]
        
        for indicator in private_indicators:
            if indicator in source_lower:
                print(f"✓ Găsit indicator PRIVAT: '{indicator}'")
                return False
        
        # Indicatori de cont PUBLIC - caută JSON embedded
        # Instagram pune datele în <script type="application/ld+json">
        if '"@type":"ProfilePage"' in source:
            print("✓ Găsit ProfilePage schema - verificăm JSON")
            # Caută în JSON după indicii
            import re
            json_match = re.search(r'window\._sharedData = ({.*?});</script>', source)
            if json_match:
                json_str = json_match.group(1).lower()
                if '"is_private":true' in json_str:
                    print("✓ JSON conține is_private:true - cont PRIVAT")
                    return False
                elif '"is_private":false' in json_str:
                    print("✓ JSON conține is_private:false - cont PUBLIC")
                    return True
        
        # Verifică dacă există postări vizibile (link-uri către /p/)
        if '/p/' in source and 'href' in source_lower:
            post_count = source.count('/p/')
            print(f"✓ Găsite {post_count} referințe către postări - probabil PUBLIC")
            if post_count > 5:  # Dacă sunt multe link-uri către postări
                return True
        
        # Verifică meta tag og:description
        import re
        meta_match = re.search(r'<meta property="og:description" content="([^"]*)"', source, re.IGNORECASE)
        if meta_match:
            description = meta_match.group(1).lower()
            print(f"Meta description: {description}")
            # Dacă descrie "X Followers, Y Posts" = public
            # Dacă descrie doar "X Followers" = privat
            if "posts" in description or "post" in description:
                print("✓ Meta conține 'posts' - probabil PUBLIC")
                return True
        
        print("⚠ Nu s-au găsit indicatori clari - DEFAULT: PUBLIC")
        return True
        
    except Exception as e:
        print(f"✗ Eroare: {e}")
        return True  # Default public în caz de eroare
    finally:
        driver.quit()

def check_facebook_privacy(url: str) -> bool:
    """Returnează True dacă e PUBLIC, False dacă e PRIVAT"""
    driver = get_driver()
    try:
        driver.get(url)
        time.sleep(5)
        
        source = driver.page_source
        source_lower = source.lower()
        
        # DEBUG
        print(f"\n=== DEBUG Facebook: {url} ===")
        print(f"Title: {driver.title}")
        print(f"Source length: {len(source)}")
        
        # Indicatori de cont/pagină PRIVATĂ
        private_indicators = [
            "this content isn't available",
            "content isn't available",
            "log in to continue",
            "you must log in",
            "create an account or log in",
        ]
        
        for indicator in private_indicators:
            if indicator in source_lower:
                print(f"✓ Găsit indicator PRIVAT: '{indicator}'")
                return False
        
        # Indicatori de cont PUBLIC
        # Verifică dacă există postări sau timeline
        public_indicators = [
            'role="article"',
            'data-pagelet="FeedUnit',
            '<article',
        ]
        
        for indicator in public_indicators:
            if indicator in source:
                print(f"✓ Găsit indicator PUBLIC: '{indicator}'")
                return True
        
        print("⚠ Nu s-au găsit indicatori clari - DEFAULT: PUBLIC")
        return True
        
    except Exception as e:
        print(f"✗ Eroare: {e}")
        return True
    finally:
        driver.quit()

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

@app.get("/")
def root():
    return {"message": "IG-FB Privacy Checker API", "endpoints": ["/check/instagram", "/check/facebook"]}