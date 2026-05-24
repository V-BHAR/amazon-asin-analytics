"""
Amazon Product Scraper Module
Handles all Amazon product data extraction with anti-detection measures
"""

import asyncio
import random
import re
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from urllib.parse import urlparse
import logging
from contextlib import asynccontextmanager

from playwright.async_api import (
    async_playwright, 
    Browser, 
    BrowserContext, 
    Page, 
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError
)

# Configure logger
logger = logging.getLogger(__name__)

# ===========================
# CONFIGURATION
# ===========================

class ScraperConfig:
    """Configuration for the Amazon scraper"""
    
    # Browser settings
    HEADLESS = False  # Set to False for debugging, True for production
    VIEWPORT_WIDTH_MIN = 1024
    VIEWPORT_WIDTH_MAX = 1920
    VIEWPORT_HEIGHT_MIN = 768
    VIEWPORT_HEIGHT_MAX = 1080
    
    # Timeout settings (milliseconds)
    NAVIGATION_TIMEOUT = 60000  # 60 seconds
    ELEMENT_TIMEOUT = 10000  # 10 seconds
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_MIN = 2.0
    RETRY_DELAY_MAX = 5.0
    
    # Delays (seconds)
    MIN_PRE_NAVIGATION_DELAY = 1.0
    MAX_PRE_NAVIGATION_DELAY = 3.0
    MIN_POST_NAVIGATION_DELAY = 2.0
    MAX_POST_NAVIGATION_DELAY = 4.0
    
    # Human-like behavior
    SCROLL_STEP_MIN = 100
    SCROLL_STEP_MAX = 300
    SCROLL_DELAY_MIN = 0.1
    SCROLL_DELAY_MAX = 0.3
    
    # User agents
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    # Unavailability indicators
    UNAVAILABLE_INDICATORS = [
        "currently unavailable",
        "out of stock",
        "page not found",
        "we don't know when or if this item will be back in stock",
        "not available",
        "temporarily out of stock",
        "item unavailable"
    ]
    
    # Availability selectors
    AVAILABLE_SELECTORS = [
        '#add-to-cart-button',
        'input[name="submit.add-to-cart"]',
        '#buy-now-button',
        '.a-button[aria-labelledby*="submit"]',
        '#submit.add-to-cart',
        '.a-button.a-button-primary'
    ]
    
    # Price extraction patterns
    PRICE_PATTERNS = [
        r'<span[^>]*class="a-price"[^>]*>.*?<span[^>]*class="a-offscreen"[^>]*>([^<]+)</span>',
        r'id="priceblock_ourprice"[^>]*>([^<]+)',
        r'id="priceblock_dealprice"[^>]*>([^<]+)',
        r'"priceToPay"[^}]*"amount":"([^"]+)"',
        r'<span[^>]*class="a-price-whole"[^>]*>([^<]+)</span>',
        r'<span[^>]*class="a-price"[^>]*>.*?<span[^>]*class="a-price-fraction"[^>]*>([^<]+)</span>',
    ]
    
    # Rating patterns
    RATING_PATTERNS = [
        r'"ratingValue":\s*"([\d.]+)"',
        r'"ratingValue":\s*([\d.]+)',
        r'([\d.]+)\s*out of 5 stars',
        r'<span[^>]*class="a-icon-alt"[^>]*>([\d.]+)\s*out of 5 stars</span>'
    ]
    
    # Review count patterns
    REVIEW_PATTERNS = [
        r'"reviewCount":\s*"([\d,]+)"',
        r'"reviewCount":\s*([\d,]+)',
        r'(\d+(?:,\d+)*)\s*(?:ratings|reviews|global ratings)',
        r'<span[^>]*id="acrCustomerReviewText"[^>]*>([^<]+)</span>'
    ]
    
    # BSR patterns
    BSR_PATTERNS = [
        r'Best Sellers Rank:.*?#(\d+(?:,\d+)*)',
        r'"rank":\s*"#(\d+(?:,\d+)*)"',
        r'#(\d+(?:,\d+)*)\s+in\s+[^<]+',
        r'Best Sellers Rank</span>.*?#(\d+(?:,\d+)*)'
    ]


# ===========================
# AMAZON SCRAPER CLASS
# ===========================

class AmazonScraper:
    """
    Advanced Amazon product scraper with anti-detection measures
    """
    
    def __init__(self, headless: bool = None, proxy: Optional[str] = None):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode (default from config)
            proxy: Optional proxy server URL
        """
        self.headless = headless if headless is not None else ScraperConfig.HEADLESS
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.playwright = None
        self._context: Optional[BrowserContext] = None
        
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
            logger.info(f"Initializing browser (headless={self.headless})")
            
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
                '--disable-features=VizDisplayCompositor',
                '--disable-notifications',
                '--disable-popup-blocking',
                '--disable-infobars',
            ]
            
            if self.proxy:
                launch_args.append(f'--proxy-server={self.proxy}')
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args
            )
            
            logger.info("Browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            raise
            
    async def _create_context(self) -> BrowserContext:
        """
        Create a new browser context with stealth configuration
        
        Returns:
            BrowserContext: Configured browser context
        """
        viewport = {
            'width': random.randint(ScraperConfig.VIEWPORT_WIDTH_MIN, ScraperConfig.VIEWPORT_WIDTH_MAX),
            'height': random.randint(ScraperConfig.VIEWPORT_HEIGHT_MIN, ScraperConfig.VIEWPORT_HEIGHT_MAX)
        }
        
        context = await self.browser.new_context(
            viewport=viewport,
            user_agent=self._get_random_user_agent(),
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )
        
        # Add stealth scripts
        await context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Add plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Add languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Add chrome property
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        return context
        
    async def get_page(self, url: str, retry_count: int = 0) -> Optional[Page]:
        """
        Get a page with retry mechanism and anti-detection
        
        Args:
            url: URL to navigate to
            retry_count: Current retry attempt count
            
        Returns:
            Page object or None if failed
        """
        try:
            # Create new context for each page (avoids detection)
            self._context = await self._create_context()
            page = await self._context.new_page()
            
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
            
            # Random delay after navigation
            await asyncio.sleep(random.uniform(
                ScraperConfig.MIN_POST_NAVIGATION_DELAY,
                ScraperConfig.MAX_POST_NAVIGATION_DELAY
            ))
            
            # Check for blocking pages
            page_content = await page.content()
            
            if "Robot Check" in page_content or "captcha" in page_content.lower():
                logger.warning(f"CAPTCHA detected for {url}")
                await page.screenshot(path=f"captcha_{int(time.time())}.png")
                
                if retry_count < ScraperConfig.MAX_RETRIES - 1:
                    logger.info(f"Waiting for manual intervention...")
                    await asyncio.sleep(30)  # Wait for possible manual solve
                    return await self.get_page(url, retry_count + 1)
                return page  # Return page even with CAPTCHA (user might solve)
            
            # Check for 404
            if response and response.status == 404:
                logger.warning(f"Page not found: {url}")
                return None
            
            # Check for connection issues
            if response and response.status >= 500:
                logger.warning(f"Server error {response.status} for {url}")
                if retry_count < ScraperConfig.MAX_RETRIES:
                    await asyncio.sleep(random.uniform(
                        ScraperConfig.RETRY_DELAY_MIN,
                        ScraperConfig.RETRY_DELAY_MAX
                    ))
                    return await self.get_page(url, retry_count + 1)
                return None
            
            # Simulate human-like scrolling
            await self._human_like_scroll(page)
            
            logger.debug(f"Page loaded successfully: {url}")
            return page
            
        except PlaywrightTimeoutError as e:
            logger.warning(f"Timeout loading {url}: {str(e)}")
            
            if retry_count < ScraperConfig.MAX_RETRIES:
                wait_time = random.uniform(
                    ScraperConfig.RETRY_DELAY_MIN,
                    ScraperConfig.RETRY_DELAY_MAX
                )
                logger.info(f"Retrying in {wait_time:.1f}s (attempt {retry_count + 1}/{ScraperConfig.MAX_RETRIES})")
                await asyncio.sleep(wait_time)
                return await self.get_page(url, retry_count + 1)
            else:
                logger.error(f"Failed to load {url} after {ScraperConfig.MAX_RETRIES} attempts")
                return None
                
        except PlaywrightError as e:
            logger.error(f"Playwright error loading {url}: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error loading {url}: {str(e)}")
            return None
            
    async def _human_like_scroll(self, page: Page) -> None:
        """
        Simulate human-like scrolling behavior
        
        Args:
            page: Page to scroll
        """
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
                    
                    // Scroll back up slowly
                    for (let i = scrollHeight; i > 0; i -= 200) {{
                        window.scrollTo({{
                            top: i,
                            behavior: 'smooth'
                        }});
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }}
                }})();
            """)
        except Exception as e:
            logger.debug(f"Scroll simulation failed: {str(e)}")
            
    def _get_random_user_agent(self) -> str:
        """
        Get random user agent to avoid detection
        
        Returns:
            Random user agent string
        """
        return random.choice(ScraperConfig.USER_AGENTS)
        
    async def check_availability(self, page: Page, asin: str) -> Tuple[bool, str]:
        """
        Check if product is available
        
        Args:
            page: Page object
            asin: Product ASIN
            
        Returns:
            Tuple of (is_available, status_message)
        """
        try:
            # Get page content
            content = await page.content()
            content_lower = content.lower()
            
            # Check for unavailable indicators
            for indicator in ScraperConfig.UNAVAILABLE_INDICATORS:
                if indicator in content_lower:
                    return False, "Product Unavailable"
            
            # Check for available selectors
            for selector in ScraperConfig.AVAILABLE_SELECTORS:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            # Verify product title exists
                            title_elem = await page.query_selector('#productTitle')
                            if title_elem:
                                title_text = await title_elem.text_content()
                                if title_text and title_text.strip():
                                    return True, "Available"
                except:
                    continue
            
            # Check HTML content for add to cart
            if "add to cart" in content_lower and "buy now" in content_lower:
                return True, "Available"
            
            # Check if product title exists but no stock info
            title_elem = await page.query_selector('#productTitle')
            if title_elem:
                title_text = await title_elem.text_content()
                if title_text and title_text.strip():
                    # Title exists but uncertain availability
                    return False, "Availability Unknown"
            
            return False, "Product Not Found"
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return False, f"Error: {str(e)[:100]}"
            
    async def extract_product_data(self, page: Page, asin: str, fields: Set[str]) -> Dict[str, Any]:
        """
        Extract selected product data
        
        Args:
            page: Page object
            asin: Product ASIN
            fields: Set of fields to extract
            
        Returns:
            Dictionary with extracted data
        """
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
            is_available, availability_status = await self.check_availability(page, asin)
            data['is_available'] = is_available
            data['availability_status'] = availability_status
            data['Product Availability'] = "Available" if is_available else "Unavailable"
            data['Product Stock Status'] = "In Stock" if is_available else "Out of Stock"
            
            if is_available:
                # Extract each selected field
                extraction_tasks = []
                
                if 'Product Title' in fields:
                    extraction_tasks.append(self._extract_title_safe(page, content, data))
                    
                if 'Product Price' in fields or 'Discount Percentage' in fields:
                    extraction_tasks.append(self._extract_price_safe(page, content, data))
                    
                if 'Product Rating' in fields:
                    extraction_tasks.append(self._extract_rating_safe(page, content, data))
                    
                if 'Total Reviews Count' in fields:
                    extraction_tasks.append(self._extract_reviews_safe(page, content, data))
                    
                if 'Product Brand' in fields:
                    extraction_tasks.append(self._extract_brand_safe(page, content, data))
                    
                if 'Best Seller Rank' in fields:
                    extraction_tasks.append(self._extract_bsr_safe(content, data))
                    
                if 'Product Description' in fields:
                    extraction_tasks.append(self._extract_description_safe(page, data))
                    
                if 'Bullet Points' in fields:
                    extraction_tasks.append(self._extract_bullet_points_safe(page, data))
                    
                if 'Seller Name' in fields:
                    extraction_tasks.append(self._extract_seller_safe(page, data))
                    
                if 'Prime Eligible' in fields:
                    extraction_tasks.append(self._detect_prime_safe(page, content, data))
                    
                if 'Coupon Available' in fields:
                    extraction_tasks.append(self._detect_coupon_safe(page, content, data))
                    
                if 'Amazon Choice Badge' in fields:
                    extraction_tasks.append(self._detect_amazon_choice_safe(content, data))
                    
                if 'Best Seller Badge' in fields:
                    extraction_tasks.append(self._detect_best_seller_safe(content, data))
                    
                if 'Product Images Count' in fields:
                    extraction_tasks.append(self._extract_image_count_safe(page, data))
                    
                if 'Product URL' in fields:
                    data['Product URL'] = f"https://amazon.com/dp/{asin}"
                    
                if 'Available Product ASINs' in fields:
                    data['Available Product ASINs'] = asin
                    
                # Wait for all extraction tasks to complete
                await asyncio.gather(*extraction_tasks, return_exceptions=True)
                
                data['status'] = 'success'
                logger.debug(f"Successfully extracted data for ASIN: {asin}")
                
            else:
                # Handle unavailable product
                data['status'] = 'unavailable'
                if 'Unavailable Product ASINs' in fields:
                    data['Unavailable Product ASINs'] = asin
                    
                logger.debug(f"Product unavailable for ASIN: {asin} - {availability_status}")
                
        except Exception as e:
            logger.error(f"Error extracting data for {asin}: {str(e)}")
            data['status'] = 'error'
            data['error_message'] = str(e)[:500]
            
        return data
        
    # Safe extraction methods with error handling
    async def _extract_title_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract product title safely"""
        try:
            title = await self._extract_title(page)
            if not title:
                title = self._extract_title_from_content(content)
            if title:
                data['Product Title'] = title.strip()
            else:
                data['Product Title'] = ''
        except Exception as e:
            logger.debug(f"Title extraction failed: {str(e)}")
            data['Product Title'] = ''
            
    async def _extract_price_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract price safely"""
        try:
            price_data = await self._extract_price(page, content)
            if price_data.get('Product Price'):
                data['Product Price'] = price_data['Product Price']
            if price_data.get('Discount Percentage'):
                data['Discount Percentage'] = price_data['Discount Percentage']
        except Exception as e:
            logger.debug(f"Price extraction failed: {str(e)}")
            data['Product Price'] = None
            data['Discount Percentage'] = None
            
    async def _extract_rating_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract rating safely"""
        try:
            rating_data = await self._extract_rating(page, content)
            if rating_data.get('Product Rating'):
                data['Product Rating'] = rating_data['Product Rating']
        except Exception as e:
            logger.debug(f"Rating extraction failed: {str(e)}")
            data['Product Rating'] = None
            
    async def _extract_reviews_safe(self, page: Page, content: str, data: Dict) -> None:
        """Extract reviews count safely"""
        try:
            reviews = await self._extract_review_count(page, content)
            if reviews:
                data['Total Reviews Count'] = reviews
            else:
                data['Total Reviews Count'] = 0
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
            
    async def _detect_coupon_safe(self, page: Page, content: str, data: Dict) -> None:
        """Detect coupon availability safely"""
        try:
            has_coupon = await self._detect_coupon(page, content)
            data['Coupon Available'] = "Yes" if has_coupon else "No"
        except Exception as e:
            logger.debug(f"Coupon detection failed: {str(e)}")
            data['Coupon Available'] = "No"
            
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
            
    async def _extract_image_count_safe(self, page: Page, data: Dict) -> None:
        """Extract image count safely"""
        try:
            count = await self._extract_image_count(page)
            data['Product Images Count'] = count
        except Exception as e:
            logger.debug(f"Image count extraction failed: {str(e)}")
            data['Product Images Count'] = 0
            
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
        """Extract product price and discount"""
        price_data = {'Product Price': None, 'Discount Percentage': None}
        
        try:
            # Try selectors first
            price_selectors = ['#priceblock_ourprice', '#priceblock_dealprice', '.a-price .a-offscreen']
            for selector in price_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        text = await elem.text_content()
                        if text:
                            price_match = re.search(r'[\d,]+\.?\d*', text)
                            if price_match:
                                price_data['Product Price'] = float(price_match.group().replace(',', ''))
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
                            price_data['Product Price'] = float(price_match.group().replace(',', ''))
                            break
                            
            # Extract discount
            if price_data['Product Price']:
                mrp_match = re.search(r'M\.R\.P\.:.*?<span[^>]*>([\d,]+\.?\d*)', content, re.IGNORECASE)
                if mrp_match:
                    mrp = float(mrp_match.group(1).replace(',', ''))
                    if mrp > price_data['Product Price']:
                        discount = ((mrp - price_data['Product Price']) / mrp) * 100
                        price_data['Discount Percentage'] = round(discount, 2)
                        
        except Exception as e:
            logger.debug(f"Price extraction error: {str(e)}")
            
        return price_data
        
    async def _extract_rating(self, page: Page, content: str) -> Dict:
        """Extract product rating"""
        rating_data = {'Product Rating': None}
        
        try:
            for pattern in ScraperConfig.RATING_PATTERNS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    rating_data['Product Rating'] = float(match.group(1))
                    break
        except Exception as e:
            logger.debug(f"Rating extraction error: {str(e)}")
            
        return rating_data
        
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
            bullets = await page.query_selector_all('#feature-bullets li span')
            for bullet in bullets[:5]:
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
            seller_elem = await page.query_selector('#sellerProfileTriggerId')
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
                prime_elem = await page.query_selector('[aria-label="Amazon Prime"], [aria-label*="Prime"]')
                return prime_elem is not None
        except Exception:
            pass
        return False
        
    async def _detect_coupon(self, page: Page, content: str) -> bool:
        """Detect coupon availability"""
        try:
            if 'coupon' in content.lower():
                coupon_elem = await page.query_selector('[aria-label*="Coupon"], .coupon-label')
                return coupon_elem is not None
        except Exception:
            pass
        return False
        
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
            images = await page.query_selector_all('#altImages img, #imgTagWrapperId img, .imgTagWrapper img')
            return len(images) if images else 0
        except Exception:
            return 0
            
    async def close(self) -> None:
        """Close browser and cleanup"""
        try:
            if self._context:
                await self._context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")


# ===========================
# BATCH PROCESSING FUNCTION
# ===========================

async def process_asins_async(
    job_id: str, 
    asins: List[str], 
    selected_fields: Set[str], 
    job_manager, 
    socketio
) -> None:
    """
    Process multiple ASINs asynchronously
    
    Args:
        job_id: Unique job identifier
        asins: List of ASINs to process
        selected_fields: Set of fields to extract
        job_manager: Job manager instance
        socketio: SocketIO instance for real-time updates
    """
    from app import Config  # Import here to avoid circular imports
    
    logger.info(f"Starting batch processing for job {job_id} with {len(asins)} ASINs")
    
    async with AmazonScraper(headless=ScraperConfig.HEADLESS) as scraper:
        # Process in chunks
        for chunk_start in range(0, len(asins), Config.CHUNK_SIZE):
            chunk_end = min(chunk_start + Config.CHUNK_SIZE, len(asins))
            chunk = asins[chunk_start:chunk_end]
            
            logger.info(f"Processing chunk {chunk_start//Config.CHUNK_SIZE + 1}/{(len(asins)-1)//Config.CHUNK_SIZE + 1} for job {job_id}")
            
            # Process chunk concurrently
            tasks = []
            for asin in chunk:
                tasks.append(process_single_asin(scraper, asin, selected_fields, job_id, job_manager))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, dict):
                    job_manager.add_result(job_id, result)
                elif isinstance(result, Exception):
                    logger.error(f"Task failed for job {job_id}: {str(result)}")
                    job_manager.add_result(job_id, {
                        'asin': 'unknown',
                        'status': 'error',
                        'error_message': str(result),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Send progress update via SocketIO
            job = job_manager.get_job(job_id)
            if job:
                progress_percentage = (job['processed'] / job['total_asins'] * 100) if job['total_asins'] > 0 else 0
                
                socketio.emit('progress_update', {
                    'job_id': job_id,
                    'processed': job['processed'],
                    'total': job['total_asins'],
                    'percentage': round(progress_percentage, 2),
                    'successful': job['successful'],
                    'failed': job['failed'],
                    'available': job['available'],
                    'unavailable': job['unavailable'],
                    'current_asin': job['current_asin']
                })
                
                logger.info(f"Job {job_id} progress: {job['processed']}/{job['total_asins']} ({progress_percentage:.1f}%)")
            
            # Add delay between chunks to avoid rate limiting
            if chunk_end < len(asins):
                await asyncio.sleep(Config.RATE_LIMIT_DELAY)
    
    # Mark job as completed
    job_manager.complete_job(job_id)
    
    # Send final completion event
    socketio.emit('job_completed', {
        'job_id': job_id,
        'total_processed': job_manager.get_job(job_id)['processed'],
        'total_successful': job_manager.get_job(job_id)['successful'],
        'total_failed': job_manager.get_job(job_id)['failed']
    })
    
    logger.info(f"Job {job_id} completed successfully")


async def process_single_asin(
    scraper: AmazonScraper, 
    asin: str, 
    selected_fields: Set[str], 
    job_id: str, 
    job_manager
) -> Dict[str, Any]:
    """
    Process a single ASIN
    
    Args:
        scraper: AmazonScraper instance
        asin: Product ASIN
        selected_fields: Set of fields to extract
        job_id: Job identifier
        job_manager: Job manager instance
        
    Returns:
        Extracted product data
    """
    # Update current ASIN in job
    job = job_manager.get_job(job_id)
    if job:
        job['current_asin'] = asin
    
    url = f"https://amazon.com/dp/{asin}"
    
    try:
        # Get page
        page = await scraper.get_page(url)
        
        if page:
            # Extract data
            data = await scraper.extract_product_data(page, asin, selected_fields)
            
            # Close page
            await page.close()
            
            return data
        else:
            # Page loading failed
            return {
                'asin': asin,
                'status': 'error',
                'error_message': 'Failed to load product page',
                'timestamp': datetime.now().isoformat(),
                'is_available': False,
                'availability_status': 'Page Load Failed'
            }
            
    except Exception as e:
        logger.error(f"Error processing ASIN {asin}: {str(e)}")
        return {
            'asin': asin,
            'status': 'error',
            'error_message': str(e)[:500],
            'timestamp': datetime.now().isoformat(),
            'is_available': False,
            'availability_status': 'Processing Error'
        }