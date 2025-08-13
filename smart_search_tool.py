"""
Smart Search Tool with Automatic Fallback
Auteur: Joop Snijder
Versie: 1.0

Dit systeem schakelt automatisch tussen search providers:
1. Serper (tot 2,500 gratis searches)
2. SearXNG (gratis, self-hosted of public instances)
3. Brave Search (gratis tier beschikbaar)
4. Web scraping als laatste redmiddel
"""

import os
import json
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from abc import ABC, abstractmethod

# CrewAI tools with fallback handling
try:
    from crewai_tools import SerperDevTool, BraveSearchTool
except ImportError:
    # Fallback for older crewai_tools versions
    SerperDevTool = None
    BraveSearchTool = None
from crewai.tools.base_tool import BaseTool
from langchain.tools import Tool

# Voor web scraping fallback
from bs4 import BeautifulSoup
import httpx

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# USAGE TRACKING
# ============================================

class UsageTracker:
    """Track API usage voor verschillende services"""
    
    def __init__(self, cache_file: str = ".search_usage_cache.json"):
        self.cache_file = Path(cache_file)
        self.usage_data = self.load_usage()
    
    def load_usage(self) -> Dict:
        """Laad usage data uit cache"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {
            "serper": {"count": 0, "month": datetime.now().strftime("%Y-%m")},
            "brave": {"count": 0, "day": datetime.now().strftime("%Y-%m-%d")},
            "searxng": {"count": 0, "day": datetime.now().strftime("%Y-%m-%d")}
        }
    
    def save_usage(self):
        """Sla usage data op"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.usage_data, f)
    
    def check_and_update(self, service: str) -> bool:
        """
        Check of service beschikbaar is en update usage
        Returns: True als service gebruikt kan worden
        """
        current_month = datetime.now().strftime("%Y-%m")
        current_day = datetime.now().strftime("%Y-%m-%d")
        
        if service == "serper":
            # Reset maandelijks
            if self.usage_data["serper"]["month"] != current_month:
                self.usage_data["serper"] = {"count": 0, "month": current_month}
            
            # Check limiet (2,500 gratis)
            if self.usage_data["serper"]["count"] >= 2500:
                logger.warning("Serper maandlimiet bereikt (2,500 searches)")
                return False
            
            self.usage_data["serper"]["count"] += 1
            
        elif service == "brave":
            # Reset dagelijks
            if self.usage_data["brave"]["day"] != current_day:
                self.usage_data["brave"] = {"count": 0, "day": current_day}
            
            # Brave gratis tier: ~2000 per maand, dus ~66 per dag
            if self.usage_data["brave"]["count"] >= 66:
                logger.warning("Brave daglimiet bereikt")
                return False
            
            self.usage_data["brave"]["count"] += 1
        
        elif service == "searxng":
            # Reset dagelijks
            if self.usage_data["searxng"]["day"] != current_day:
                self.usage_data["searxng"] = {"count": 0, "day": current_day}
            
            # SearXNG public instances hebben rate limits
            if self.usage_data["searxng"]["count"] >= 100:
                logger.warning("SearXNG daglimiet bereikt")
                return False
            
            self.usage_data["searxng"]["count"] += 1
        
        self.save_usage()
        return True
    
    def get_status(self) -> Dict:
        """Krijg huidige usage status"""
        return {
            "serper": {
                "used": self.usage_data["serper"]["count"],
                "remaining": max(0, 2500 - self.usage_data["serper"]["count"]),
                "period": self.usage_data["serper"]["month"]
            },
            "brave": {
                "used": self.usage_data["brave"]["count"],
                "remaining": max(0, 66 - self.usage_data["brave"]["count"]),
                "period": self.usage_data["brave"]["day"]
            },
            "searxng": {
                "used": self.usage_data["searxng"]["count"],
                "remaining": max(0, 100 - self.usage_data["searxng"]["count"]),
                "period": self.usage_data["searxng"]["day"]
            }
        }


# ============================================
# SEARCH PROVIDERS
# ============================================

class SearchProvider(ABC):
    """Abstract base class voor search providers"""
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Voer een zoekopdracht uit"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check of deze provider beschikbaar is"""
        pass


class SerperProvider(SearchProvider):
    """Serper.dev search provider"""
    
    def __init__(self, api_key: str, tracker: UsageTracker):
        self.api_key = api_key
        self.tracker = tracker
        self.base_url = "https://google.serper.dev/search"
    
    def is_available(self) -> bool:
        """Check of Serper beschikbaar is"""
        if not self.api_key:
            return False
        return self.tracker.check_and_update("serper")
    
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Zoek via Serper API"""
        try:
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "q": query,
                "num": kwargs.get("num_results", 10)
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                # Parse organic results
                for item in data.get("organic", []):
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                        "source": "serper"
                    })
                
                logger.info(f"Serper search succesvol: {len(results)} resultaten")
                return results
            else:
                logger.error(f"Serper API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Serper search failed: {e}")
            return []


class SearXNGProvider(SearchProvider):
    """SearXNG search provider (gratis, open source)"""
    
    # Publieke SearXNG instances (roteer voor load balancing)
    PUBLIC_INSTANCES = [
        "https://searx.be",
        "https://searx.work", 
        "https://search.bus-hit.me",
        "https://search.sapti.me",
        "https://searx.tiekoetter.com"
    ]
    
    def __init__(self, tracker: UsageTracker, instance_url: Optional[str] = None):
        self.tracker = tracker
        self.instance_url = instance_url or self.PUBLIC_INSTANCES[0]
        self.current_instance_idx = 0
    
    def rotate_instance(self):
        """Roteer naar volgende instance"""
        self.current_instance_idx = (self.current_instance_idx + 1) % len(self.PUBLIC_INSTANCES)
        self.instance_url = self.PUBLIC_INSTANCES[self.current_instance_idx]
        logger.info(f"Rotated to SearXNG instance: {self.instance_url}")
    
    def is_available(self) -> bool:
        """Check of SearXNG beschikbaar is"""
        return self.tracker.check_and_update("searxng")
    
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Zoek via SearXNG"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                params = {
                    "q": query,
                    "format": "json",
                    "language": "nl",
                    "engines": "google,bing,duckduckgo"
                }
                
                response = requests.get(
                    f"{self.instance_url}/search",
                    params=params,
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    for item in data.get("results", [])[:10]:
                        results.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("content", ""),
                            "link": item.get("url", ""),
                            "source": "searxng"
                        })
                    
                    logger.info(f"SearXNG search succesvol: {len(results)} resultaten")
                    return results
                else:
                    logger.warning(f"SearXNG instance {self.instance_url} returned {response.status_code}")
                    self.rotate_instance()
                    
            except Exception as e:
                logger.warning(f"SearXNG instance {self.instance_url} failed: {e}")
                self.rotate_instance()
        
        return []


class BraveProvider(SearchProvider):
    """Brave Search provider (heeft gratis tier)"""
    
    def __init__(self, api_key: Optional[str], tracker: UsageTracker):
        self.api_key = api_key
        self.tracker = tracker
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
    
    def is_available(self) -> bool:
        """Check of Brave beschikbaar is"""
        if not self.api_key:
            return False
        return self.tracker.check_and_update("brave")
    
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Zoek via Brave Search API"""
        try:
            headers = {
                "X-Subscription-Token": self.api_key,
                "Accept": "application/json"
            }
            
            params = {
                "q": query,
                "count": kwargs.get("num_results", 10)
            }
            
            response = requests.get(
                self.base_url,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get("web", {}).get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("description", ""),
                        "link": item.get("url", ""),
                        "source": "brave"
                    })
                
                logger.info(f"Brave search succesvol: {len(results)} resultaten")
                return results
            else:
                logger.error(f"Brave API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return []


class GoogleScraperProvider(SearchProvider):
    """Laatste redmiddel: scrape Google search (gebruik voorzichtig!)"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def is_available(self) -> bool:
        """Altijd beschikbaar als laatste optie"""
        return True
    
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Scrape Google search results (laatste redmiddel)"""
        try:
            # Gebruik httpx voor betere async support
            with httpx.Client() as client:
                response = client.get(
                    "https://www.google.com/search",
                    params={"q": query, "hl": "nl"},
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    results = []
                    
                    # Parse search results
                    for g in soup.find_all('div', class_='g')[:5]:  # Alleen top 5
                        title_elem = g.find('h3')
                        snippet_elem = g.find('span', class_='aCOpRe')
                        link_elem = g.find('a')
                        
                        if title_elem and link_elem:
                            results.append({
                                "title": title_elem.get_text(),
                                "snippet": snippet_elem.get_text() if snippet_elem else "",
                                "link": link_elem.get('href', ''),
                                "source": "google_scraper"
                            })
                    
                    logger.info(f"Google scraper: {len(results)} resultaten")
                    return results
                    
        except Exception as e:
            logger.error(f"Google scraper failed: {e}")
        
        return []


# ============================================
# SMART SEARCH TOOL
# ============================================

class SmartSearchTool:
    """
    Intelligente search tool met automatische fallback
    Probeert providers in volgorde tot één werkt
    """
    
    def __init__(
        self,
        serper_api_key: Optional[str] = None,
        brave_api_key: Optional[str] = None,
        searxng_instance: Optional[str] = None
    ):
        # Initialize tracker
        self.tracker = UsageTracker()
        
        # Initialize providers in priority order
        self.providers = []
        
        # 1. Serper (beste resultaten, gratis tot 2,500/maand)
        if serper_api_key or os.getenv("SERPER_API_KEY"):
            self.providers.append(
                SerperProvider(
                    serper_api_key or os.getenv("SERPER_API_KEY"),
                    self.tracker
                )
            )
        
        # 2. SearXNG (volledig gratis, open source)
        self.providers.append(
            SearXNGProvider(self.tracker, searxng_instance)
        )
        
        # 3. Brave (gratis tier beschikbaar)
        if brave_api_key or os.getenv("BRAVE_API_KEY"):
            self.providers.append(
                BraveProvider(
                    brave_api_key or os.getenv("BRAVE_API_KEY"),
                    self.tracker
                )
            )
        
        # 4. Google Scraper (laatste redmiddel)
        self.providers.append(GoogleScraperProvider())
        
        logger.info(f"Smart Search Tool initialized with {len(self.providers)} providers")
    
    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Voer search uit met automatische fallback
        """
        results = []
        used_provider = None
        
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            
            if provider.is_available():
                logger.info(f"Trying search with {provider_name}")
                results = provider.search(query, **kwargs)
                
                if results:
                    used_provider = provider_name
                    logger.info(f"Success with {provider_name}")
                    break
                else:
                    logger.warning(f"{provider_name} returned no results")
            else:
                logger.info(f"{provider_name} not available, trying next")
        
        # Format response
        return {
            "query": query,
            "provider": used_provider,
            "results": results,
            "usage_status": self.tracker.get_status(),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict:
        """Krijg status van alle providers"""
        return {
            "providers": [p.__class__.__name__ for p in self.providers],
            "usage": self.tracker.get_status()
        }
    
    def run(self, query: str) -> str:
        """
        CrewAI compatible run method
        """
        result = self.search(query)
        
        # Format voor CrewAI
        if result["results"]:
            formatted = f"Search results for '{query}' (via {result['provider']}):\n\n"
            for i, r in enumerate(result["results"][:5], 1):
                formatted += f"{i}. {r['title']}\n"
                formatted += f"   {r['snippet']}\n"
                formatted += f"   URL: {r['link']}\n\n"
            return formatted
        else:
            return f"No results found for '{query}'"


# ============================================
# CREWAI INTEGRATION
# ============================================

class CrewAISmartSearchTool(BaseTool):
    """CrewAI compatible smart search tool"""
    name: str = "smart_search"
    description: str = "Search the web with automatic fallback to free providers"
    
    def _run(self, query: str) -> str:
        """Execute search with CrewAI compatibility"""
        smart_search = SmartSearchTool()
        return smart_search.run(query)

def create_smart_search_tool() -> CrewAISmartSearchTool:
    """
    Creëer een CrewAI-compatible tool
    """
    return CrewAISmartSearchTool()


# ============================================
# TEST & DEMO
# ============================================

if __name__ == "__main__":
    # Test de smart search tool
    print("="*50)
    print("SMART SEARCH TOOL - TEST")
    print("="*50)
    
    # Initialize
    tool = SmartSearchTool(
        serper_api_key=os.getenv("SERPER_API_KEY"),
        brave_api_key=os.getenv("BRAVE_API_KEY")
    )
    
    # Show status
    print("\nProvider Status:")
    status = tool.get_status()
    for provider in status["providers"]:
        print(f"  - {provider}")
    
    print("\nUsage Status:")
    for service, data in status["usage"].items():
        print(f"  {service}: {data['used']}/{data['used'] + data['remaining']} used")
    
    # Test search
    test_query = "OpenAI GPT-4 parameters aantal"
    print(f"\nTesting search: '{test_query}'")
    
    result = tool.search(test_query)
    
    print(f"\nUsed provider: {result['provider']}")
    print(f"Results found: {len(result['results'])}")
    
    if result['results']:
        print("\nTop 3 results:")
        for i, r in enumerate(result['results'][:3], 1):
            print(f"\n{i}. {r['title']}")
            print(f"   {r['snippet'][:100]}...")
            print(f"   {r['link']}")
