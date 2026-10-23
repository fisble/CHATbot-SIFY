import requests
import os

# Try to get API key from config first, then fallback to env
from config import settings
SERPER_API_KEY = settings.serper_api_key or os.getenv("SERPER_API_KEY")

def web_search(query: str, top_k: int = 5):
    """
    Calls a web search provider and returns normalized results.
    Returns empty list on error (API key missing, unauthorized, etc.)
    """
    if not SERPER_API_KEY:
        print("[WEB_SEARCH] WARNING: SERPER_API_KEY not set. Skipping web search.")
        return []
    
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "q": query,
        "num": top_k
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Check for authentication errors
        if response.status_code == 403:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("message", "Unauthorized")
            print(f"[WEB_SEARCH] 403 Error: {error_msg}. Please check your SERPER_API_KEY or sign up at https://serper.dev")
            return []
        
        response.raise_for_status()

        data = response.json()

        results = []
        for i, item in enumerate(data.get("organic", [])):
            results.append({
                "id": i + 1,
                "title": item.get("title", "No title"),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })

        return results
    
    except requests.exceptions.Timeout:
        print(f"[WEB_SEARCH] Timeout error when searching for: {query}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[WEB_SEARCH] Request error: {str(e)}")
        return []
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"[WEB_SEARCH] {error_msg}")
        return []
