"""
AMAZON ASIN INTELLIGENCE & PRODUCT ANALYTICS PLATFORM
ENTERPRISE-GRADE SCRAPER MODULE (scraper.py)
VERSION: 4.0.0 - FULLY OPTIMIZED WITH ADVANCED ANTI-DETECTION
"""

import asyncio
import random
import re
import time
import json
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from datetime import datetime
from urllib.parse import urlparse, quote
import logging
from contextlib import asynccontextmanager
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from playwright.async_api import ( # pyright: ignore[reportMissingImports]
    async_playwright, 
    Browser, 
    BrowserContext, 
    Page, 
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    Route
)

# Configure logger
logger = logging.getLogger(__name__)


# ===========================
# ENUMS AND DATA CLASSES
# ===========================

class ProductStatus(Enum):
    """Product availability status"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    ERROR = "error"
    CAPTCHA = "captcha"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"


class ScrapingError(Enum):
    """Scraping error types"""
    NONE = "none"
    TIMEOUT = "timeout"
    CAPTCHA = "captcha"
    BLOCKED = "blocked"
    NETWORK = "network"
    PARSE_ERROR = "parse_error"
    INVALID_ASIN = "invalid_asin"


@dataclass
class ScrapingResult:
    """Structured scraping result"""
    asin: str
    status: ProductStatus
    error_type: ScrapingError = ScrapingError.NONE
    error_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    response_time_ms: int = 0
    page_size_bytes: int = 0


# ===========================
# ENHANCED CONFIGURATION
# ===========================

class ScraperConfig:
    """Enterprise-grade configuration for the Amazon scraper"""
    
    # Browser settings - PRODUCTION OPTIMIZED
    HEADLESS = True  # Production mode
    HEADLESS_DEBUG = False  # Set to True for debugging
    BROWSER_POOL_SIZE = 5
    MAX_CONTEXTS_PER_BROWSER = 3
    MAX_PAGES_PER_CONTEXT = 2
    
    # Viewport settings (realistic device profiles)
    VIEWPORT_WIDTH_MIN = 1280
    VIEWPORT_WIDTH_MAX = 1920
    VIEWPORT_HEIGHT_MIN = 720
    VIEWPORT_HEIGHT_MAX = 1080
    
    # Device profiles for rotation
    DEVICE_PROFILES = [
        {'viewport': {'width': 1366, 'height': 768}, 'device_scale_factor': 1},
        {'viewport': {'width': 1536, 'height': 864}, 'device_scale_factor': 1},
        {'viewport': {'width': 1920, 'height': 1080}, 'device_scale_factor': 1},
        {'viewport': {'width': 1440, 'height': 900}, 'device_scale_factor': 1},
        {'viewport': {'width': 1280, 'height': 1024}, 'device_scale_factor': 1},
    ]
    
    # Timeout settings (milliseconds) - Production tuned
    NAVIGATION_TIMEOUT = 45000  # 45 seconds
    ELEMENT_TIMEOUT = 15000  # 15 seconds
    NETWORK_IDLE_TIMEOUT = 10000  # 10 seconds
    PAGE_LOAD_TIMEOUT = 30000  # 30 seconds
    
    # Retry settings with exponential backoff
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2.0
    RETRY_DELAY_MAX = 30.0
    RETRY_BACKOFF_FACTOR = 2
    
    # Delays for human-like behavior (seconds)
    MIN_PRE_NAVIGATION_DELAY = 0.5
    MAX_PRE_NAVIGATION_DELAY = 2.0
    MIN_POST_NAVIGATION_DELAY = 1.0
    MAX_POST_NAVIGATION_DELAY = 3.0
    MIN_BETWEEN_REQUESTS = 1.0
    MAX_BETWEEN_REQUESTS = 4.0
    
    # Human-like interaction settings
    SCROLL_STEP_MIN = 100
    SCROLL_STEP_MAX = 400
    SCROLL_DELAY_MIN = 0.05
    SCROLL_DELAY_MAX = 0.2
    MOUSE_MOVEMENTS_ENABLED = True
    TYPING_DELAY_MIN = 0.05
    TYPING_DELAY_MAX = 0.15
    
    # User agents pool (rotated per request)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0',
    ]
    
    # Accept language profiles
    ACCEPT_LANGUAGES = [
        'en-US,en;q=0.9',
        'en-GB,en;q=0.9',
        'en-CA,en;q=0.9',
        'en-AU,en;q=0.9',
    ]
    
    # Marketplace domains
    MARKETPLACES = {
        'US': 'amazon.com',
        'UK': 'amazon.co.uk',
        'CA': 'amazon.ca',
        'AU': 'amazon.com.au',
        'DE': 'amazon.de',
        'FR': 'amazon.fr',
        'IT': 'amazon.it',
        'ES': 'amazon.es',
        'IN': 'amazon.in',
    }
    
    DEFAULT_MARKETPLACE = 'US'
    
    # Unavailability indicators (comprehensive list)
    UNAVAILABLE_INDICATORS = [
        "currently unavailable",
        "out of stock",
        "page not found",
        "we don't know when or if this item will be back in stock",
        "not available",
        "temporarily out of stock",
        "item unavailable",
        "product unavailable",
        "sold out",
        "out of stock -",
        "stock: out",
        "availability: out",
        "this item is no longer available",
        "product not found",
        "sorry, we couldn't find that page",
        "dog page",
    ]
    
    # Availability indicators
    AVAILABILITY_INDICATORS = [
        "in stock",
        "in stock.",
        "only left in stock",
        "available from these sellers",
        "ships from",
        "sold by",
    ]
    
    # Available selectors (prioritized)
    AVAILABLE_SELECTORS = [
        '#add-to-cart-button',
        'input[name="submit.add-to-cart"]',
        '#buy-now-button',
        '.a-button[aria-labelledby*="submit"]',
        '#submit.add-to-cart',
        '.a-button.a-button-primary',
        '[data-action="add-to-cart"]',
        '.add-to-cart-button',
        '#addToCart',
        '.buy-now-button',
        '[aria-label="Add to Cart"]',
        '[aria-label="Buy Now"]',
    ]
    
    # Price extraction selectors (prioritized)
    PRICE_SELECTORS = [
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '.a-price .a-offscreen',
        '.a-price-whole',
        '[data-asin-price]',
        '.apexPriceToPay .a-price-whole',
        '.priceToPay .a-price-whole',
        '.a-price[data-a-size="xl"] .a-offscreen',
    ]
    
    # Price patterns (regex)
    PRICE_PATTERNS = [
        r'<span[^>]*class="a-price"[^>]*>.*?<span[^>]*class="a-offscreen"[^>]*>([^<]+)</span>',
        r'id="priceblock_ourprice"[^>]*>([^<]+)',
        r'id="priceblock_dealprice"[^>]*>([^<]+)',
        r'"priceToPay"[^}]*"amount":"([^"]+)"',
        r'<span[^>]*class="a-price-whole"[^>]*>([^<]+)</span>',
        r'data-asin-price="([^"]+)"',
        r'"price":\s*"([\d,]+\.?\d*)"',
    ]
    
    # Rating patterns
    RATING_PATTERNS = [
        r'"ratingValue":\s*"([\d.]+)"',
        r'"ratingValue":\s*([\d.]+)',
        r'([\d.]+)\s*out of 5 stars',
        r'<span[^>]*class="a-icon-alt"[^>]*>([\d.]+)\s*out of 5 stars</span>',
        r'average rating[\s]*([\d.]+)',
    ]
    
    # Review count patterns
    REVIEW_PATTERNS = [
        r'"reviewCount":\s*"([\d,]+)"',
        r'"reviewCount":\s*([\d,]+)',
        r'(\d+(?:,\d+)*)\s*(?:ratings|reviews|global ratings)',
        r'<span[^>]*id="acrCustomerReviewText"[^>]*>([^<]+)</span>',
        r'(\d+(?:,\d+)*) customer ratings',
        r'(\d+(?:,\d+)*) global ratings',
    ]
    
    # BSR patterns
    BSR_PATTERNS = [
        r'Best Sellers Rank:.*?#(\d+(?:,\d+)*)',
        r'"rank":\s*"#(\d+(?:,\d+)*)"',
        r'#(\d+(?:,\d+)*)\s+in\s+[^<]+',
        r'Best Sellers Rank</span>.*?#(\d+(?:,\d+)*)',
        r'Product Rank:\s*#(\d+(?:,\d+)*)',
    ]
    
    # Category rank patterns
    CATEGORY_RANK_PATTERN = r'#(\d+(?:,\d+)*)\s+in\s+([^<#]+?)(?:\s*\(|$)'
    
    # Stealth scripts
    STEALTH_SCRIPTS = [
        """
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // Add plugins
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        
        // Add languages
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        
        // Add chrome property
        window.chrome = { runtime: {} };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Override connection
        Object.defineProperty(navigator, 'connection', { get: () => ({ rtt: 50, saveData: false }) });
        
        // Add webgl vendor
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter(parameter);
        };
        """,
    ]
    
    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE = 30
    RATE_LIMIT_BURST = 5
    RATE_LIMIT_DELAY = 2.0
    
    # Health check settings
    HEALTH_CHECK_INTERVAL = 60
    MAX_IDLE_TIME = 300
    
    # Cache settings
    CACHE_ENABLED = True
    CACHE_TTL_SECONDS = 3600
    CACHE_MAX_SIZE = 10000


# ===========================
# CACHE MANAGER
# ===========================

class ScraperCache:
    """In-memory cache for scraped data"""
    
    def __init__(self, max_size: int = ScraperConfig.CACHE_MAX_SIZE, ttl: int = ScraperConfig.CACHE_TTL_SECONDS):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Dict]:
        """Get from cache"""
        if not ScraperConfig.CACHE_ENABLED:
            return None
        
        if key in self.cache:
            data, timestamp = self.cache[key]
            if (datetime.now() - timestamp).seconds < self.ttl:
                self.hits += 1
                return data
            else:
                del self.cache[key]
        
        self.misses += 1
        return None
    
    def set(self, key: str, data: Dict):
        """Set in cache"""
        if not ScraperConfig.CACHE_ENABLED:
            return
        
        # Evict oldest if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.cache[key] = (data, datetime.now())
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(hit_rate, 2)
        }


# ===========================
# ENHANCED AMAZON SCRAPER CLASS
# ===========================

class AmazonScraper:
    """
    Enterprise-grade Amazon product scraper with advanced anti-detection
    """
    
    def __init__(self, headless: bool = None, proxy: Optional[str] = None, marketplace: str = 'US'):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode (default from config)
            proxy: Optional proxy server URL
            marketplace: Amazon marketplace (US, UK, CA, AU, DE, FR, IT, ES, IN)
        """
        self.headless = headless if headless is not None else ScraperConfig.HEADLESS
        self.proxy = proxy
        self.marketplace = marketplace.upper()
        self.domain = ScraperConfig.MARKETPLACES.get(self.marketplace, ScraperConfig.MARKETPLACES['US'])
        
        self.browser: Optional[Browser] = None
        self.playwright = None
        self._context_pool: List[BrowserContext] = []
        self._context_lock = asyncio.Lock()
        self.cache = ScraperCache()
        self.request_count = 0
        self.request_timestamps = []
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.init_browser()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def init_browser(self) -> None:
        """
        Initialize browser with advanced anti-detection configuration
        """
        try:
            logger.info(f"Initializing browser for marketplace {self.marketplace} ({self.domain}) (headless={self.headless})")
            
            self.playwright = await async_playwright().start()
            
            # Browser launch arguments for stealth
            launch_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--start-maximized',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor,IsolateOrigins,site-per-process',
                '--disable-notifications',
                '--disable-popup-blocking',
                '--disable-infobars',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-default-apps',
                '--disable-component-extensions-with-background-pages',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-first-run',
                '--no-pings',
                '--safebrowsing-disable-auto-update',
                '--disable-client-side-phishing-detection',
                '--disable-component-update',
            ]
            
            if self.headless:
                launch_args.append('--headless=new')
            
            if self.proxy:
                launch_args.append(f'--proxy-server={self.proxy}')
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args
            )
            
            # Initialize context pool
            await self._init_context_pool()
            
            logger.info(f"Browser initialized successfully for {self.domain}")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            raise
            
    async def _init_context_pool(self) -> None:
        """Initialize pool of browser contexts"""
        async with self._context_lock:
            for i in range(ScraperConfig.MAX_CONTEXTS_PER_BROWSER):
                context = await self._create_context()
                self._context_pool.append(context)
            logger.info(f"Created {len(self._context_pool)} browser contexts")
    
    async def _get_context(self) -> BrowserContext:
        """Get an available browser context from the pool"""
        async with self._context_lock:
            if not self._context_pool:
                # Create new context if pool is empty
                return await self._create_context()
            return self._context_pool.pop()
    
    async def _return_context(self, context: BrowserContext) -> None:
        """Return a browser context to the pool"""
        async with self._context_lock:
            # Clear cookies and local storage for next use
            try:
                await context.clear_cookies()
                await context.add_init_script(ScraperConfig.STEALTH_SCRIPTS[0])
            except:
                pass
            self._context_pool.append(context)
    
    async def _create_context(self) -> BrowserContext:
        """
        Create a new browser context with stealth configuration
        
        Returns:
            BrowserContext: Configured browser context
        """
        # Random device profile
        device_profile = random.choice(ScraperConfig.DEVICE_PROFILES)
        viewport = device_profile['viewport']
        
        # Random viewport variation
        if random.random() > 0.5:
            viewport = {
                'width': viewport['width'] + random.randint(-200, 200),
                'height': viewport['height'] + random.randint(-100, 100)
            }
        
        context = await self.browser.new_context(
            viewport=viewport,
            user_agent=self._get_random_user_agent(),
            locale='en-US',
            timezone_id='America/New_York',
            device_scale_factor=device_profile.get('device_scale_factor', 1),
            extra_http_headers={
                'Accept-Language': random.choice(ScraperConfig.ACCEPT_LANGUAGES),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': f'https://{self.domain}/',
            }
        )
        
        # Add stealth scripts
        for script in ScraperConfig.STEALTH_SCRIPTS:
            await context.add_init_script(script)
        
        # Set default timeout
        context.set_default_timeout(ScraperConfig.NAVIGATION_TIMEOUT)
        
        # Intercept and modify requests if needed
        await context.route('**/*', self._handle_route)
        
        return context
    
    async def _handle_route(self, route: Route) -> None:
        """Handle route interception for stealth"""
        # Block unnecessary resources to speed up scraping
        block_resources = ['image', 'media', 'font', 'stylesheet']
        request = route.request
        
        # Block analytics and tracking
        if any(pattern in request.url.lower() for pattern in ['analytics', 'tracking', 'beacon', 'metrics']):
            await route.abort()
            return
        
        # Continue with normal request
        await route.continue_()
    
    async def check_rate_limit(self) -> bool:
        """Check if rate limit is exceeded"""
        now = time.time()
        
        # Clean old timestamps
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60]
        
        # Check burst
        if len(self.request_timestamps) > ScraperConfig.RATE_LIMIT_BURST:
            delay = ScraperConfig.RATE_LIMIT_DELAY
            logger.debug(f"Rate limit burst detected, waiting {delay}s")
            await asyncio.sleep(delay)
            return True
        
        # Check per minute limit
        if len(self.request_timestamps) >= ScraperConfig.RATE_LIMIT_REQUESTS_PER_MINUTE:
            delay = 60 - (now - self.request_timestamps[0])
            if delay > 0:
                logger.debug(f"Rate limit reached, waiting {delay:.1f}s")
                await asyncio.sleep(delay)
        
        self.request_timestamps.append(now)
        self.request_count += 1
        return True
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent to avoid detection"""
        return random.choice(ScraperConfig.USER_AGENTS)
    
    async def get_page(self, url: str, retry_count: int = 0) -> Tuple[Optional[Page], ScrapingResult]:
        """
        Get a page with retry mechanism and anti-detection
        
        Args:
            url: URL to navigate to
            retry_count: Current retry attempt count
            
        Returns:
            Tuple of (Page object or None, ScrapingResult with initial data)
        """
        asin = self._extract_asin_from_url(url)
        result = ScrapingResult(asin=asin, status=ProductStatus.UNKNOWN)
        start_time = time.time()
        
        try:
            # Check rate limit
            await self.check_rate_limit()
            
            # Get context from pool
            context = await self._get_context()
            page = await context.new_page()
            
            # Random delay before navigation
            await asyncio.sleep(random.uniform(
                ScraperConfig.MIN_PRE_NAVIGATION_DELAY,
                ScraperConfig.MAX_PRE_NAVIGATION_DELAY
            ))
            
            # Navigate to URL
            logger.debug(f"Navigating to: {url}")
            response = await page.goto(
                url, 
                wait_until='domcontentloaded', 
                timeout=ScraperConfig.NAVIGATION_TIMEOUT
            )
            
            # Check response status
            if response:
                result.response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status == 404:
                    result.status = ProductStatus.NOT_FOUND
                    result.error_type = ScrapingError.PARSE_ERROR
                    result.error_message = "Page not found (404)"
                    await page.close()
                    await self._return_context(context)
                    return None, result
                
                if response.status >= 500:
                    result.status = ProductStatus.ERROR
                    result.error_type = ScrapingError.NETWORK
                    result.error_message = f"Server error: {response.status}"
                    await page.close()
                    await self._return_context(context)
                    
                    if retry_count < ScraperConfig.MAX_RETRIES:
                        return await self.get_page(url, retry_count + 1)
                    return None, result
            
            # Random delay after navigation
            await asyncio.sleep(random.uniform(
                ScraperConfig.MIN_POST_NAVIGATION_DELAY,
                ScraperConfig.MAX_POST_NAVIGATION_DELAY
            ))
            
            # Check page content for blocking
            page_content = await page.content()
            result.page_size_bytes = len(page_content)
            
            # Check for CAPTCHA
            if "Robot Check" in page_content or "captcha" in page_content.lower():
                logger.warning(f"CAPTCHA detected for {url}")
                result.status = ProductStatus.CAPTCHA
                result.error_type = ScrapingError.CAPTCHA
                result.error_message = "CAPTCHA detected"
                
                # Take screenshot for debugging
                screenshot_path = f"captcha_{asin}_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path)
                logger.info(f"CAPTCHA screenshot saved to {screenshot_path}")
                
                await page.close()
                await self._return_context(context)
                return None, result
            
            # Check for Amazon blocking page
            if "access denied" in page_content.lower() or "sorry" in page_content.lower():
                result.status = ProductStatus.BLOCKED
                result.error_type = ScrapingError.BLOCKED
                result.error_message = "Access denied by Amazon"
                await page.close()
                await self._return_context(context)
                return None, result
            
            # Simulate human-like scrolling
            await self._human_like_scroll(page)
            
            # Optional: Simulate mouse movements
            if ScraperConfig.MOUSE_MOVEMENTS_ENABLED and random.random() > 0.7:
                await self._simulate_mouse_movement(page)
            
            result.status = ProductStatus.AVAILABLE  # Temporarily set to available
            logger.debug(f"Page loaded successfully: {url}")
            
            # Return page and context for later cleanup
            page.context = context  # Attach context to page for cleanup
            return page, result
            
        except PlaywrightTimeoutError as e:
            logger.warning(f"Timeout loading {url}: {str(e)}")
            result.status = ProductStatus.ERROR
            result.error_type = ScrapingError.TIMEOUT
            result.error_message = f"Timeout: {str(e)}"
            result.retry_count = retry_count
            
            if retry_count < ScraperConfig.MAX_RETRIES:
                wait_time = min(
                    ScraperConfig.RETRY_DELAY_BASE * (ScraperConfig.RETRY_BACKOFF_FACTOR ** retry_count),
                    ScraperConfig.RETRY_DELAY_MAX
                )
                logger.info(f"Retrying in {wait_time:.1f}s (attempt {retry_count + 1}/{ScraperConfig.MAX_RETRIES})")
                await asyncio.sleep(wait_time)
                return await self.get_page(url, retry_count + 1)
            return None, result
            
        except PlaywrightError as e:
            logger.error(f"Playwright error loading {url}: {str(e)}")
            result.status = ProductStatus.ERROR
            result.error_type = ScrapingError.NETWORK
            result.error_message = str(e)
            return None, result
            
        except Exception as e:
            logger.error(f"Unexpected error loading {url}: {str(e)}")
            result.status = ProductStatus.ERROR
            result.error_type = ScrapingError.NETWORK
            result.error_message = str(e)
            return None, result
    
    async def _human_like_scroll(self, page: Page) -> None:
        """Simulate human-like scrolling behavior"""
        try:
            await page.evaluate(f"""
                (async () => {{
                    const scrollHeight = document.body.scrollHeight;
                    let currentPosition = 0;
                    const minStep = {ScraperConfig.SCROLL_STEP_MIN};
                    const maxStep = {ScraperConfig.SCROLL_STEP_MAX};
                    const minDelay = {ScraperConfig.SCROLL_DELAY_MIN};
                    const maxDelay = {ScraperConfig.SCROLL_DELAY_MAX};
                    
                    while (currentPosition < scrollHeight) {{
                        const step = Math.random() * (maxStep - minStep) + minStep;
                        currentPosition += step;
                        window.scrollTo({{
                            top: currentPosition,
                            behavior: 'smooth'
                        }});
                        await new Promise(resolve => 
                            setTimeout(resolve, Math.random() * (maxDelay - minDelay) + minDelay)
                        );
                    }}
                    
                    // Scroll back up a bit randomly
                    if (Math.random() > 0.5) {{
                        window.scrollTo({{
                            top: scrollHeight * 0.5,
                            behavior: 'smooth'
                        }});
                        await new Promise(resolve => setTimeout(resolve, 200));
                    }}
                }})();
            """)
        except Exception as e:
            logger.debug(f"Scroll simulation failed: {str(e)}")
    
    async def _simulate_mouse_movement(self, page: Page) -> None:
        """Simulate random mouse movements"""
        try:
            viewport = page.viewport_size
            if viewport:
                for _ in range(random.randint(1, 3)):
                    x = random.randint(100, viewport['width'] - 100)
                    y = random.randint(100, viewport['height'] - 100)
                    await page.mouse.move(x, y, steps=random.randint(5, 15))
                    await asyncio.sleep(random.uniform(0.1, 0.5))
        except Exception as e:
            logger.debug(f"Mouse movement simulation failed: {str(e)}")
    
    def _extract_asin_from_url(self, url: str) -> str:
        """Extract ASIN from product URL"""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/product/([A-Z0-9]{10})',
            r'/asin/([A-Z0-9]{10})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return "unknown"
    
    async def check_availability(self, page: Page, asin: str) -> Tuple[ProductStatus, str]:
        """
        Check if product is available
        
        Args:
            page: Page object
            asin: Product ASIN
            
        Returns:
            Tuple of (ProductStatus, status_message)
        """
        try:
            # Get page content
            content = await page.content()
            content_lower = content.lower()
            
            # Check for unavailable indicators
            for indicator in ScraperConfig.UNAVAILABLE_INDICATORS:
                if indicator in content_lower:
                    return ProductStatus.UNAVAILABLE, "Product Unavailable"
            
            # Check for availability indicators
            for indicator in ScraperConfig.AVAILABILITY_INDICATORS:
                if indicator in content_lower:
                    # Verify with selector check
                    for selector in ScraperConfig.AVAILABLE_SELECTORS:
                        try:
                            element = await page.query_selector(selector)
                            if element and await element.is_visible():
                                # Verify product title exists
                                title_elem = await page.query_selector('#productTitle')
                                if title_elem:
                                    title_text = await title_elem.text_content()
                                    if title_text and title_text.strip():
                                        return ProductStatus.AVAILABLE, "Available"
                        except:
                            continue
                    return ProductStatus.AVAILABLE, "Likely Available"
            
            # Check if product title exists but no stock info
            title_elem = await page.query_selector('#productTitle')
            if title_elem:
                title_text = await title_elem.text_content()
                if title_text and title_text.strip():
                    return ProductStatus.UNKNOWN, "Availability Unknown"
            
            return ProductStatus.UNAVAILABLE, "Product Not Found"
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return ProductStatus.ERROR, f"Error: {str(e)[:100]}"
    
    async def extract_product_data(self, page: Page, asin: str, selected_fields: Set[str]) -> Dict[str, Any]:
        """
        Extract selected product data with enhanced parsing
        
        Args:
            page: Page object
            asin: Product ASIN
            selected_fields: Set of fields to extract
            
        Returns:
            Dictionary with extracted data
        """
        # Check cache first
        cache_key = f"{asin}_{hashlib.md5(str(sorted(selected_fields)).encode()).hexdigest()}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for ASIN {asin}")
            return cached_data
        
        # Initialize result with basic info
        data = {
            'asin': asin,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'is_available': False,
            'availability_status': 'Unknown',
            'Product Availability': 'Unknown',
            'Product Stock Status': 'Unknown'
        }
        
        try:
            # Get page content once for regex extraction
            content = await page.content()
            
            # Check availability first
            status, availability_status = await self.check_availability(page, asin)
            data['is_available'] = status == ProductStatus.AVAILABLE
            data['availability_status'] = availability_status
            data['Product Availability'] = "Available" if data['is_available'] else "Unavailable"
            data['Product Stock Status'] = "In Stock" if data['is_available'] else "Out of Stock"
            
            # Extract all fields in parallel for performance
            extraction_tasks = []
            
            # Always extract core fields if available
            extraction_tasks.append(self._extract_title_safe(page, content, data))
            extraction_tasks.append(self._extract_price_safe(page, content, data))
            
            if 'Product Rating' in selected_fields:
                extraction_tasks.append(self._extract_rating_safe(page, content, data))
                
            if 'Total Reviews Count' in selected_fields:
                extraction_tasks.append(self._extract_reviews_safe(page, content, data))
                
            if 'Product Brand' in selected_fields:
                extraction_tasks.append(self._extract_brand_safe(page, content, data))
                
            if 'Best Seller Rank' in selected_fields:
                extraction_tasks.append(self._extract_bsr_safe(content, data))
                
            if 'Product Category' in selected_fields:
                extraction_tasks.append(self._extract_category_safe(content, data))
                
            if 'Product Sub Category Rank' in selected_fields:
                extraction_tasks.append(self._extract_sub_category_safe(content, data))
                
            if 'Product Description' in selected_fields:
                extraction_tasks.append(self._extract_description_safe(page, data))
                
            if 'Bullet Points' in selected_fields:
                extraction_tasks.append(self._extract_bullet_points_safe(page, data))
                
            if 'Seller Name' in selected_fields:
                extraction_tasks.append(self._extract_seller_safe(page, data))
                
            if 'Prime Eligible' in selected_fields:
                extraction_tasks.append(self._detect_prime_safe(page, content, data))
                
            if 'Coupon Available' in selected_fields:
                extraction_tasks.append(self._extract_coupon_safe(page, content, data))
                
            if 'Discount Percentage' in selected_fields:
                extraction_tasks.append(self._extract_discount_safe(data))
                
            if 'Amazon Choice Badge' in selected_fields:
                extraction_tasks.append(self._detect_amazon_choice_safe(content, data))
                
            if 'Best Seller Badge' in selected_fields:
                extraction_tasks.append(self._detect_best_seller_safe(content, data))
                
            if 'Limited Time Deal Badge' in selected_fields:
                extraction_tasks.append(self._detect_limited_deal_safe(content, data))
                
            if 'Buy Box Available' in selected_fields:
                extraction_tasks.append(self._detect_buy_box_safe(page, data))
                
            if 'Product Images Count' in selected_fields:
                extraction_tasks.append(self._extract_image_count_safe(page, data))
                
            if 'A+ Content Available' in selected_fields:
                extraction_tasks.append(self._detect_aplus_content_safe(content, data))
                
            if 'Delivery Status' in selected_fields:
                extraction_tasks.append(self._extract_delivery_status_safe(page, data))
                
            if 'Product URL' in selected_fields:
                data['Product URL'] = f"https://{self.domain}/dp/{asin}"
                
            if 'Available Product ASIN' in selected_fields and data['is_available']:
                data['Available Product ASIN'] = asin
                
            if 'Unavailable Product ASIN' in selected_fields and not data['is_available']:
                data['Unavailable Product ASIN'] = asin
            
            # Wait for all extraction tasks to complete
            await asyncio.gather(*extraction_tasks, return_exceptions=True)
            
            # Clean up data
            data = self._clean_data(data)
            
            data['status'] = 'success' if data['is_available'] else 'unavailable'
            
            # Cache the result
            self.cache.set(cache_key, data)
            
            logger.debug(f"Successfully extracted data for ASIN: {asin}")
            
        except Exception as e:
            logger.error(f"Error extracting data for {asin}: {str(e)}")
            data['status'] = 'error'
            data['error_message'] = str(e)[:500]
        
        return data
    
    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize extracted data"""
        cleaned = {}
        for key, value in data.items():
            if value is None:
                cleaned[key] = ''
            elif isinstance(value, str):
                # Remove extra whitespace and newlines
                cleaned[key] = ' '.join(value.split())
            elif isinstance(value, (int, float)):
                cleaned[key] = value
            else:
                cleaned[key] = value
        return cleaned
    
    # Safe extraction methods with error handling
    async def _extract_title_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract product title safely"""
        try:
            title = await self._extract_title(page)
            if not title:
                title = self._extract_title_from_content(content)
            data['Product Title'] = title.strip() if title else ''
        except Exception as e:
            logger.debug(f"Title extraction failed: {str(e)}")
            data['Product Title'] = ''
    
    async def _extract_price_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract price and MRP safely"""
        try:
            price_data = await self._extract_price(page, content)
            if price_data.get('Product Price'):
                data['Product Price'] = price_data['Product Price']
            if price_data.get('MRP'):
                data['MRP'] = price_data['MRP']
            if price_data.get('Discount Percentage'):
                data['Discount Percentage'] = price_data['Discount Percentage']
            if price_data.get('Currency'):
                data['Currency'] = price_data['Currency']
        except Exception as e:
            logger.debug(f"Price extraction failed: {str(e)}")
            data['Product Price'] = ''
            data['MRP'] = ''
            data['Discount Percentage'] = ''
    
    async def _extract_rating_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract rating safely"""
        try:
            rating = await self._extract_rating(page, content)
            if rating:
                data['Product Rating'] = rating
            else:
                data['Product Rating'] = ''
        except Exception as e:
            logger.debug(f"Rating extraction failed: {str(e)}")
            data['Product Rating'] = ''
    
    async def _extract_reviews_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract reviews count safely"""
        try:
            reviews = await self._extract_review_count(page, content)
            data['Total Reviews Count'] = reviews if reviews > 0 else 0
        except Exception as e:
            logger.debug(f"Reviews extraction failed: {str(e)}")
            data['Total Reviews Count'] = 0
    
    async def _extract_brand_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract brand safely"""
        try:
            brand = await self._extract_brand(page)
            if not brand:
                brand = self._extract_brand_from_content(content)
            data['Product Brand'] = brand if brand else ''
        except Exception as e:
            logger.debug(f"Brand extraction failed: {str(e)}")
            data['Product Brand'] = ''
    
    async def _extract_bsr_safe(self, content: str, data: Dict) -> None:
        """Extract Best Seller Rank safely"""
        try:
            bsr = await self._extract_bsr(content)
            data['Best Seller Rank'] = bsr if bsr else ''
        except Exception as e:
            logger.debug(f"BSR extraction failed: {str(e)}")
            data['Best Seller Rank'] = ''
    
    async def _extract_category_safe(self, content: str, data: Dict) -> None:
        """Extract product category safely"""
        try:
            category = await self._extract_category(content)
            data['Product Category'] = category if category else ''
        except Exception as e:
            logger.debug(f"Category extraction failed: {str(e)}")
            data['Product Category'] = ''
    
    async def _extract_sub_category_safe(self, content: str, data: Dict) -> None:
        """Extract sub-category rank safely"""
        try:
            sub_category_rank = await self._extract_sub_category_rank(content)
            data['Product Sub Category Rank'] = sub_category_rank if sub_category_rank else ''
        except Exception as e:
            logger.debug(f"Sub-category rank extraction failed: {str(e)}")
            data['Product Sub Category Rank'] = ''
    
    async def _extract_description_safe(self, page: Page, data: Dict) -> None:
        """Extract description safely"""
        try:
            desc = await self._extract_description(page)
            data['Product Description'] = desc if desc else ''
        except Exception as e:
            logger.debug(f"Description extraction failed: {str(e)}")
            data['Product Description'] = ''
    
    async def _extract_bullet_points_safe(self, page: Page, data: Dict) -> None:
        """Extract bullet points safely"""
        try:
            bullets = await self._extract_bullet_points(page)
            data['Bullet Points'] = bullets if bullets else ''
        except Exception as e:
            logger.debug(f"Bullet points extraction failed: {str(e)}")
            data['Bullet Points'] = ''
    
    async def _extract_seller_safe(self, page: Page, data: Dict) -> None:
        """Extract seller name safely"""
        try:
            seller = await self._extract_seller(page)
            data['Seller Name'] = seller if seller else 'Amazon'
        except Exception as e:
            logger.debug(f"Seller extraction failed: {str(e)}")
            data['Seller Name'] = 'Amazon'
    
    async def _detect_prime_safe(self, page: Page, content: str, data: Dict) -> None:
        """Detect Prime eligibility safely"""
        try:
            is_prime = await self._detect_prime(page, content)
            data['Prime Eligible'] = "Yes" if is_prime else "No"
        except Exception as e:
            logger.debug(f"Prime detection failed: {str(e)}")
            data['Prime Eligible'] = "No"
    
    async def _extract_coupon_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract coupon availability safely"""
        try:
            coupon = await self._extract_coupon(page, content)
            data['Coupon Available'] = coupon if coupon else "No"
            if coupon and coupon != "No":
                data['Coupon Value'] = coupon
        except Exception as e:
            logger.debug(f"Coupon extraction failed: {str(e)}")
            data['Coupon Available'] = "No"
    
    async def _extract_discount_safe(self, data: Dict) -> None:
        """Extract discount percentage safely"""
        try:
            if 'Product Price' in data and 'MRP' in data:
                price = data.get('Product Price')
                mrp = data.get('MRP')
                if price and mrp and price != '' and mrp != '':
                    try:
                        price_float = float(price)
                        mrp_float = float(mrp)
                        if mrp_float > 0:
                            discount = ((mrp_float - price_float) / mrp_float) * 100
                            data['Discount Percentage'] = f"{round(discount, 0)}%"
                    except:
                        pass
        except Exception as e:
            logger.debug(f"Discount extraction failed: {str(e)}")
    
    async def _detect_amazon_choice_safe(self, content: str, data: Dict) -> None:
        """Detect Amazon Choice badge safely"""
        try:
            is_choice = await self._detect_amazon_choice(content)
            data['Amazon Choice Badge'] = "Yes" if is_choice else "No"
        except Exception as e:
            logger.debug(f"Amazon Choice detection failed: {str(e)}")
            data['Amazon Choice Badge'] = "No"
    
    async def _detect_best_seller_safe(self, content: str, data: Dict) -> None:
        """Detect Best Seller badge safely"""
        try:
            is_best_seller = await self._detect_best_seller(content)
            data['Best Seller Badge'] = "Yes" if is_best_seller else "No"
        except Exception as e:
            logger.debug(f"Best Seller detection failed: {str(e)}")
            data['Best Seller Badge'] = "No"
    
    async def _detect_limited_deal_safe(self, content: str, data: Dict) -> None:
        """Detect Limited Time Deal badge safely"""
        try:
            has_deal = 'limited time deal' in content.lower() or 'limited deal' in content.lower()
            data['Limited Time Deal Badge'] = "Yes" if has_deal else "No"
        except Exception as e:
            logger.debug(f"Limited deal detection failed: {str(e)}")
            data['Limited Time Deal Badge'] = "No"
    
    async def _detect_buy_box_safe(self, page: Page, data: Dict) -> None:
        """Detect Buy Box availability safely"""
        try:
            buybox = await page.query_selector('#buybox')
            has_buybox = buybox is not None and await buybox.is_visible()
            data['Buy Box Available'] = "Yes" if has_buybox else "No"
        except Exception as e:
            logger.debug(f"Buy Box detection failed: {str(e)}")
            data['Buy Box Available'] = "No"
    
    async def _extract_image_count_safe(self, page: Page, data: Dict) -> None:
        """Extract image count safely"""
        try:
            count = await self._extract_image_count(page)
            data['Product Images Count'] = count
        except Exception as e:
            logger.debug(f"Image count extraction failed: {str(e)}")
            data['Product Images Count'] = 0
    
    async def _detect_aplus_content_safe(self, content: str, data: Dict) -> None:
        """Detect A+ Content availability safely"""
        try:
            has_aplus = 'aplus' in content.lower() or 'a+ content' in content.lower()
            data['A+ Content Available'] = "Yes" if has_aplus else "No"
        except Exception as e:
            logger.debug(f"A+ Content detection failed: {str(e)}")
            data['A+ Content Available'] = "No"
    
    async def _extract_delivery_status_safe(self, page: Page, data: Dict) -> None:
        """Extract delivery status safely"""
        try:
            delivery = await self._extract_delivery_status(page)
            data['Delivery Status'] = delivery if delivery else ''
        except Exception as e:
            logger.debug(f"Delivery status extraction failed: {str(e)}")
            data['Delivery Status'] = ''
    
    # Core extraction methods
    async def _extract_title(self, page: Page) -> str:
        """Extract product title"""
        try:
            title_elem = await page.query_selector('#productTitle')
            if title_elem:
                title = await title_elem.text_content()
                if title:
                    return title.strip()
        except Exception:
            pass
        return ""
    
    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from HTML content using regex"""
        match = re.search(r'id="productTitle"[^>]*>([^<]+)', content)
        if match:
            return match.group(1).strip()
        return ""
    
    async def _extract_price(self, page: Page, content: str) -> Dict:
        """Extract product price, MRP, and discount"""
        price_data = {'Product Price': '', 'MRP': '', 'Discount Percentage': '', 'Currency': 'USD'}
        
        try:
            # Try selectors first
            for selector in ScraperConfig.PRICE_SELECTORS:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.text_content()
                        if text:
                            # Extract currency
                            if '₹' in text:
                                price_data['Currency'] = 'INR'
                            elif '£' in text:
                                price_data['Currency'] = 'GBP'
                            elif '€' in text:
                                price_data['Currency'] = 'EUR'
                            elif '$' in text:
                                price_data['Currency'] = 'USD'
                            
                            # Extract number
                            price_match = re.search(r'[\d,]+\.?\d*', text.replace('₹', '').replace('£', '').replace('€', '').replace('$', ''))
                            if price_match:
                                price_data['Product Price'] = price_match.group().replace(',', '')
                                break
                except:
                    continue
            
            # If not found, try regex patterns
            if not price_data['Product Price']:
                for pattern in ScraperConfig.PRICE_PATTERNS:
                    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                    if match:
                        price_text = match.group(1)
                        price_match = re.search(r'[\d,]+\.?\d*', price_text)
                        if price_match:
                            price_data['Product Price'] = price_match.group().replace(',', '')
                            break
            
            # Extract MRP (list price)
            mrp_patterns = [
                r'list price[^>]*>.*?<span[^>]*>([\d,]+\.?\d*)',
                r'M\.R\.P\.[^>]*>.*?<span[^>]*>([\d,]+\.?\d*)',
                r'<span[^>]*class="a-price a-text-price"[^>]*>.*?<span[^>]*class="a-offscreen"[^>]*>([^<]+)</span>',
            ]
            for pattern in mrp_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    mrp_text = match.group(1)
                    mrp_match = re.search(r'[\d,]+\.?\d*', mrp_text)
                    if mrp_match:
                        price_data['MRP'] = mrp_match.group().replace(',', '')
                        break
            
        except Exception as e:
            logger.debug(f"Price extraction error: {str(e)}")
        
        return price_data
    
    async def _extract_rating(self, page: Page, content: str) -> Optional[float]:
        """Extract product rating"""
        try:
            for pattern in ScraperConfig.RATING_PATTERNS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return float(match.group(1))
        except Exception as e:
            logger.debug(f"Rating extraction error: {str(e)}")
        return None
    
    async def _extract_review_count(self, page: Page, content: str) -> int:
        """Extract total reviews count"""
        try:
            for pattern in ScraperConfig.REVIEW_PATTERNS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return int(match.group(1).replace(',', ''))
        except Exception as e:
            logger.debug(f"Reviews extraction error: {str(e)}")
        return 0
    
    async def _extract_brand(self, page: Page) -> str:
        """Extract product brand"""
        try:
            brand_elem = await page.query_selector('#bylineInfo')
            if brand_elem:
                brand_text = await brand_elem.text_content()
                if brand_text:
                    brand_text = brand_text.replace('Brand:', '').replace('Visit the', '').strip()
                    if brand_text and len(brand_text) < 100:
                        return brand_text
        except Exception:
            pass
        return ""
    
    def _extract_brand_from_content(self, content: str) -> str:
        """Extract brand from HTML content"""
        match = re.search(r'bylineInfo[^>]*>([^<]+)', content)
        if match:
            brand = match.group(1).replace('Brand:', '').replace('Visit the', '').strip()
            if len(brand) < 100:
                return brand
        return ""
    
    async def _extract_bsr(self, content: str) -> str:
        """Extract Best Seller Rank"""
        try:
            for pattern in ScraperConfig.BSR_PATTERNS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).replace(',', '')
        except Exception:
            pass
        return ""
    
    async def _extract_category(self, content: str) -> str:
        """Extract product category hierarchy"""
        try:
            categories = []
            matches = re.findall(ScraperConfig.CATEGORY_RANK_PATTERN, content, re.IGNORECASE)
            for match in matches[:5]:
                categories.append(match[1].strip())
            return ' > '.join(categories) if categories else ""
        except Exception:
            return ""
    
    async def _extract_sub_category_rank(self, content: str) -> str:
        """Extract sub-category rank"""
        try:
            matches = re.findall(ScraperConfig.CATEGORY_RANK_PATTERN, content, re.IGNORECASE)
            if len(matches) >= 2:
                return f"#{matches[1][0]} in {matches[1][1]}"
            elif len(matches) >= 1:
                return f"#{matches[0][0]} in {matches[0][1]}"
        except Exception:
            pass
        return ""
    
    async def _extract_description(self, page: Page) -> str:
        """Extract product description"""
        try:
            desc_elem = await page.query_selector('#productDescription')
            if desc_elem:
                desc = await desc_elem.text_content()
                if desc:
                    return desc.strip()
        except Exception:
            pass
        return ""
    
    async def _extract_bullet_points(self, page: Page) -> str:
        """Extract bullet points"""
        try:
            bullet_points = []
            bullets = await page.query_selector_all('#feature-bullets li span, .a-unordered-list .a-list-item')
            for bullet in bullets[:10]:
                text = await bullet.text_content()
                if text and text.strip():
                    bullet_points.append(text.strip())
            return ' | '.join(bullet_points) if bullet_points else ""
        except Exception:
            pass
        return ""
    
    async def _extract_seller(self, page: Page) -> str:
        """Extract seller name"""
        try:
            seller_elem = await page.query_selector('#sellerProfileTriggerId, #sellerName, .seller-name')
            if seller_elem:
                seller_text = await seller_elem.text_content()
                if seller_text:
                    return seller_text.strip()
        except Exception:
            pass
        return ""
    
    async def _detect_prime(self, page: Page, content: str) -> bool:
        """Detect Prime eligibility"""
        try:
            if 'prime' in content.lower():
                prime_elem = await page.query_selector('[aria-label="Amazon Prime"], [aria-label*="Prime"], .a-icon-prime')
                return prime_elem is not None
        except Exception:
            pass
        return False
    
    async def _extract_coupon(self, page: Page, content: str) -> str:
        """Extract coupon availability and value"""
        try:
            if 'coupon' in content.lower():
                coupon_match = re.search(r'Save\s+([^<]+)\s+coupon', content, re.IGNORECASE)
                if coupon_match:
                    return coupon_match.group(1)
                return "Yes"
        except Exception:
            pass
        return "No"
    
    async def _detect_amazon_choice(self, content: str) -> bool:
        """Detect Amazon Choice badge"""
        try:
            return 'amazon\'s choice' in content.lower() or 'amazon choice' in content.lower()
        except Exception:
            return False
    
    async def _detect_best_seller(self, content: str) -> bool:
        """Detect Best Seller badge"""
        try:
            return '#1 best seller' in content.lower() or 'best seller' in content.lower()
        except Exception:
            return False
    
    async def _extract_image_count(self, page: Page) -> int:
        """Extract number of product images"""
        try:
            images = await page.query_selector_all('#altImages img, #imgTagWrapperId img, .imgTagWrapper img, .imageThumbnail')
            return len(images) if images else 0
        except Exception:
            return 0
    
    async def _extract_delivery_status(self, page: Page) -> str:
        """Extract delivery status message"""
        try:
            delivery_elem = await page.query_selector('#mir-layout-DELIVERY_BLOCK, .delivery-message')
            if delivery_elem:
                return (await delivery_elem.text_content()).strip()
        except Exception:
            pass
        return ""
    
    async def close(self) -> None:
        """Close browser and cleanup"""
        try:
            # Close all contexts
            async with self._context_lock:
                for context in self._context_pool:
                    try:
                        await context.close()
                    except:
                        pass
                self._context_pool.clear()
            
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            logger.info(f"Browser closed successfully. Cache stats: {self.cache.get_stats()}")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return self.cache.get_stats()


# ===========================
# BATCH PROCESSING FUNCTIONS
# ===========================

async def process_single_asin(
    scraper: AmazonScraper, 
    asin: str, 
    selected_fields: Set[str], 
    job_id: str, 
    job_manager,
    max_retries: int = ScraperConfig.MAX_RETRIES
) -> Dict[str, Any]:
    """
    Process a single ASIN with retry logic
    
    Args:
        scraper: AmazonScraper instance
        asin: Product ASIN
        selected_fields: Set of fields to extract
        job_id: Job identifier
        job_manager: Job manager instance
        max_retries: Maximum number of retries
        
    Returns:
        Extracted product data
    """
    # Update current ASIN in job
    job = job_manager.get_job(job_id)
    if job:
        job['current_asin'] = asin
    
    url = f"https://{scraper.domain}/dp/{asin}"
    
    for attempt in range(max_retries):
        page = None
        try:
            # Get page
            page, result = await scraper.get_page(url, attempt)
            
            if page and result.status not in [ProductStatus.CAPTCHA, ProductStatus.BLOCKED, ProductStatus.ERROR]:
                # Extract data
                data = await scraper.extract_product_data(page, asin, selected_fields)
                
                # Update job statistics
                if job:
                    job['processed'] += 1
                    if data.get('status') == 'success':
                        job['successful'] += 1
                        if data.get('is_available'):
                            job['available'] += 1
                        else:
                            job['unavailable'] += 1
                    else:
                        job['failed'] += 1
                
                # Clean up
                if page:
                    await page.close()
                    if hasattr(page, 'context'):
                        await scraper._return_context(page.context)
                
                return data
            
            # Handle captcha or blocking
            if result.status == ProductStatus.CAPTCHA:
                if attempt < max_retries - 1:
                    wait_time = random.uniform(30, 60)
                    logger.warning(f"CAPTCHA detected for {asin}, waiting {wait_time:.0f}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        'asin': asin,
                        'status': 'error',
                        'error_type': 'captcha',
                        'error_message': 'CAPTCHA detected after multiple attempts',
                        'timestamp': datetime.now().isoformat(),
                        'is_available': False,
                        'availability_status': 'CAPTCHA Blocked'
                    }
            
            if result.status == ProductStatus.BLOCKED:
                return {
                    'asin': asin,
                    'status': 'error',
                    'error_type': 'blocked',
                    'error_message': 'Access blocked by Amazon',
                    'timestamp': datetime.now().isoformat(),
                    'is_available': False,
                    'availability_status': 'Access Blocked'
                }
            
            # Handle other errors
            if page:
                await page.close()
                if hasattr(page, 'context'):
                    await scraper._return_context(page.context)
            
            if attempt < max_retries - 1:
                wait_time = min(
                    ScraperConfig.RETRY_DELAY_BASE * (ScraperConfig.RETRY_BACKOFF_FACTOR ** attempt),
                    ScraperConfig.RETRY_DELAY_MAX
                )
                logger.info(f"Retrying {asin} in {wait_time:.1f}s (attempt {attempt + 2}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            
            return {
                'asin': asin,
                'status': 'error',
                'error_type': result.error_type.value if result.error_type else 'unknown',
                'error_message': result.error_message or 'Failed to load product page',
                'timestamp': datetime.now().isoformat(),
                'is_available': False,
                'availability_status': 'Page Load Failed'
            }
            
        except Exception as e:
            logger.error(f"Error processing ASIN {asin} on attempt {attempt + 1}: {str(e)}")
            
            if page:
                try:
                    await page.close()
                    if hasattr(page, 'context'):
                        await scraper._return_context(page.context)
                except:
                    pass
            
            if attempt < max_retries - 1:
                wait_time = min(
                    ScraperConfig.RETRY_DELAY_BASE * (ScraperConfig.RETRY_BACKOFF_FACTOR ** attempt),
                    ScraperConfig.RETRY_DELAY_MAX
                )
                await asyncio.sleep(wait_time)
                continue
            
            return {
                'asin': asin,
                'status': 'error',
                'error_type': 'exception',
                'error_message': str(e)[:500],
                'timestamp': datetime.now().isoformat(),
                'is_available': False,
                'availability_status': 'Processing Error'
            }
    
    # Fallback return
    return {
        'asin': asin,
        'status': 'error',
        'error_message': 'Max retries exceeded',
        'timestamp': datetime.now().isoformat(),
        'is_available': False,
        'availability_status': 'Max Retries Exceeded'
    }


async def process_asins_batch(
    scraper: AmazonScraper,
    asins: List[str],
    selected_fields: Set[str],
    batch_size: int = 10,
    max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """
    Process a batch of ASINs with concurrency control
    
    Args:
        scraper: AmazonScraper instance
        asins: List of ASINs to process
        selected_fields: Set of fields to extract
        batch_size: Size of each batch
        max_concurrent: Maximum concurrent tasks
        
    Returns:
        List of extracted product data
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(asin):
        async with semaphore:
            page, result = await scraper.get_page(f"https://{scraper.domain}/dp/{asin}")
            if page:
                data = await scraper.extract_product_data(page, asin, selected_fields)
                await page.close()
                return data
            return {
                'asin': asin,
                'status': 'error',
                'error_message': 'Failed to get page',
                'timestamp': datetime.now().isoformat(),
                'is_available': False
            }
    
    # Process in batches
    for i in range(0, len(asins), batch_size):
        batch = asins[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(asins)-1)//batch_size + 1}")
        
        tasks = [process_with_semaphore(asin) for asin in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Batch processing error: {result}")
                results.append({
                    'status': 'error',
                    'error_message': str(result),
                    'timestamp': datetime.now().isoformat(),
                    'is_available': False
                })
            else:
                results.append(result)
        
        # Add delay between batches
        if i + batch_size < len(asins):
            await asyncio.sleep(random.uniform(2, 5))
    
    return results