from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import re
import json

app = FastAPI(title="IG-FB Privacy Check")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class URLIn(BaseModel):
    url: str

# Headers pentru a simula un browser real
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

def check_instagram_privacy(url: str) -> bool:
    """Returnează True dacă e PUBLIC, False dacă e PRIVAT"""
    try:
        # Instagram returnează JSON embedded în HTML
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        print(f"\n=== DEBUG Instagram: {url} ===")
        print(f"Status code: {response.status_code}")
        print(f"Response length: {len(response.text)}")
        
        if response.status_code != 200:
            print(f"⚠ Status code {response.status_code}")
            return True  # Default public
        
        html = response.text
        
        # Metoda 1: Caută JSON embedded în window._sharedData
        shared_data_match = re.search(r'window\._sharedData\s*=\s*({.*?});</script>', html)
        if shared_data_match:
            try:
                data = json.loads(shared_data_match.group(1))
                print("✓ Găsit window._sharedData JSON")
                
                # Navighează prin structura JSON
                entry_data = data.get('entry_data', {})
                profile_page = entry_data.get('ProfilePage', [{}])[0]
                graphql = profile_page.get('graphql', {})
                user = graphql.get('user', {})
                
                if 'is_private' in user:
                    is_private = user['is_private']
                    print(f"✓ is_private = {is_private}")
                    return not is_private  # Returnăm invers (True = public)
            except Exception as e:
                print(f"⚠ Eroare parsare JSON: {e}")
        
        # Metoda 2: Caută în structura JSON alternativă (Instagram nou)
        script_matches = re.findall(r'<script type="application/ld\+json">({.*?})</script>', html)
        for script in script_matches:
            try:
                data = json.loads(script)
                if data.get('@type') == 'ProfilePage':
                    print("✓ Găsit ProfilePage schema")
                    # Acest format nu conține is_private direct
            except:
                pass
        
        # Metoda 3: Caută textul "This account is private"
        if "this account is private" in html.lower():
            print("✓ Găsit text 'This account is private'")
            return False
        
        # Metoda 4: Verifică meta description
        meta_match = re.search(r'<meta property="og:description" content="([^"]*)"', html, re.IGNORECASE)
        if meta_match:
            description = meta_match.group(1)
            print(f"Meta description: {description}")
            
            # Format: "X Followers, Y Following, Z Posts"
            # Conturile private nu arată numărul de posts
            if "Posts" in description or "posts" in description:
                print("✓ Meta conține 'Posts' - probabil PUBLIC")
                return True
            elif "Followers" in description and "Posts" not in description:
                print("✓ Meta conține doar 'Followers' - probabil PRIVAT")
                return False
        
        # Metoda 5: Caută link-uri către postări (/p/)
        post_links = re.findall(r'"/p/[a-zA-Z0-9_-]+/"', html)
        if len(post_links) > 3:
            print(f"✓ Găsite {len(post_links)} link-uri către postări - PUBLIC")
            return True
        
        print("⚠ Nu s-au găsit indicatori clari - DEFAULT: PUBLIC")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Eroare request: {e}")
        return True
    except Exception as e:
        print(f"✗ Eroare generală: {e}")
        return True

def check_facebook_privacy(url: str) -> bool:
    """Returnează True dacă e PUBLIC, False dacă e PRIVAT"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        
        print(f"\n=== DEBUG Facebook: {url} ===")
        print(f"Status code: {response.status_code}")
        print(f"Final URL: {response.url}")
        
        if response.status_code != 200:
            print(f"⚠ Status code {response.status_code}")
            return False  # Probabil privat sau șters
        
        html = response.text.lower()
        
        # Indicatori de cont PRIVAT / blocat
        private_indicators = [
            "this content isn't available",
            "content isn't available",
            "log in to continue",
            "you must log in",
            "create an account or log in to see",
        ]
        
        for indicator in private_indicators:
            if indicator in html:
                print(f"✓ Găsit indicator PRIVAT: '{indicator}'")
                return False
        
        # Indicatori de cont PUBLIC
        public_indicators = [
            'role="article"',
            'data-pagelet="feedunit',
            '"@type":"profilepage"',
        ]
        
        for indicator in public_indicators:
            if indicator in html:
                print(f"✓ Găsit indicator PUBLIC: '{indicator}'")
                return True
        
        # Verifică dacă există link-uri către postări
        if "/posts/" in html or "/photos/" in html:
            print("✓ Găsite link-uri către posts/photos - probabil PUBLIC")
            return True
        
        print("⚠ Nu s-au găsit indicatori clari - DEFAULT: PUBLIC")
        return True
        
    except Exception as e:
        print(f"✗ Eroare: {e}")
        return True

@app.post("/check/instagram")
def ig_check(data: URLIn):
    if "instagram.com" not in data.url:
        raise HTTPException(400, "URL invalid (Instagram)")
    
    # Normalizează URL-ul (elimină trailing slash)
    url = data.url.rstrip('/')
    
    is_public = check_instagram_privacy(url)
    return {
        "url": url,
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