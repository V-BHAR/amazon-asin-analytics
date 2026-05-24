# COMPLETE AMAZON ASIN INTELLIGENCE & PRODUCT ANALYTICS PLATFORM
# ENTERPRISE-GRADE PRODUCTION BACKEND (app.py)
# VERSION: 4.0.0 - FULLY OPTIMIZED WITH ASYNC PLAYWRIGHT + BROWSER POOLING

import os
import sys
import uuid
import time
import json
import logging
import asyncio
import aiofiles
import traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set, Tuple
from functools import wraps
from collections import deque
import hashlib
import re
import random
import string

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    send_file,
    Response,
    stream_with_context,
    make_response
)
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

# Playwright imports
from playwright.async_api import ( # pyright: ignore[reportMissingImports]
    async_playwright, 
    Browser, 
    BrowserContext, 
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError
)

# ======================================================
# PRODUCTION CONFIGURATION
# ======================================================

class Config:
    """Enterprise-grade configuration with all production settings"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB for large files
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # File Upload Configuration
    UPLOAD_FOLDER = Path("uploads")
    OUTPUT_FOLDER = Path("outputs")
    LOG_FOLDER = Path("logs")
    TEMP_FOLDER = Path("temp")
    PROGRESS_FOLDER = Path("progress")
    
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "xlsm"}
    MAX_ASINS = 100000  # Increased to 100k
    MAX_FILE_SIZE_MB = 200
    
    # Scraping Configuration - PRODUCTION READY
    MAX_WORKERS = int(os.environ.get('MAX_WORKERS', 15))  # Increased from 5
    BATCH_SIZE = 100  # Process 100 ASINs per batch
    REQUEST_DELAY_MIN = 1  # seconds
    REQUEST_DELAY_MAX = 3  # seconds
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds
    
    # Playwright Browser Pool Configuration
    BROWSER_POOL_SIZE = int(os.environ.get('BROWSER_POOL_SIZE', 5))
    CONTEXTS_PER_BROWSER = 3
    PAGES_PER_CONTEXT = 2
    BROWSER_IDLE_TIMEOUT = 60  # seconds
    BROWSER_STEALTH_MODE = True
    
    # Timeouts
    PAGE_LOAD_TIMEOUT = 30000  # milliseconds (30 seconds)
    NAVIGATION_TIMEOUT = 45000  # 45 seconds
    ELEMENT_TIMEOUT = 10000  # 10 seconds
    
    # Proxy Configuration (Optional)
    USE_PROXY = os.environ.get('USE_PROXY', 'False').lower() == 'true'
    PROXY_LIST = os.environ.get('PROXY_LIST', '').split(',') if os.environ.get('PROXY_LIST') else []
    ROTATE_PROXY = True
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_PER_IP = 100
    
    # Cache Configuration
    ENABLE_CACHE = True
    CACHE_TTL = 3600  # 1 hour
    CACHE_DIR = Path("cache")
    
    # Export Configuration
    SUPPORTED_EXPORT_FORMATS = ['xlsx', 'csv', 'json', 'parquet']
    CHUNK_SIZE_EXPORT = 10000
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = 30
    LOG_MAX_SIZE_MB = 100
    
    @classmethod
    def init_directories(cls):
        """Initialize all required directories"""
        for folder in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.LOG_FOLDER, 
                       cls.TEMP_FOLDER, cls.PROGRESS_FOLDER, cls.CACHE_DIR]:
            folder.mkdir(exist_ok=True, parents=True)
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        assert cls.MAX_WORKERS > 0, "MAX_WORKERS must be > 0"
        assert cls.BROWSER_POOL_SIZE > 0, "BROWSER_POOL_SIZE must be > 0"
        assert cls.BATCH_SIZE > 0, "BATCH_SIZE must be > 0"

# Initialize directories
Config.init_directories()
Config.validate()

# ======================================================
# ENTERPRISE LOGGING SYSTEM
# ======================================================

class EnterpriseLogger:
    """Structured logging with rotation and multiple outputs"""
    
    def __init__(self):
        self.logger = logging.getLogger('AmazonScraper')
        self.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        try:
            from logging.handlers import RotatingFileHandler
            log_file = Config.LOG_FOLDER / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=Config.LOG_MAX_SIZE_MB * 1024 * 1024,
                backupCount=Config.LOG_RETENTION_DAYS
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to setup file logging: {e}")
        
        # Error log file
        error_log_file = Config.LOG_FOLDER / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        self.logger.addHandler(error_handler)
        
        self.logger.propagate = False
    
    def get_logger(self):
        return self.logger

logger = EnterpriseLogger().get_logger()

# ======================================================
# CACHE MANAGER
# ======================================================

class CacheManager:
    """In-memory and disk cache for product data"""
    
    def __init__(self):
        self.memory_cache = {}
        self.cache_dir = Config.CACHE_DIR
        
    def get(self, key: str) -> Optional[Dict]:
        """Get from cache"""
        if not Config.ENABLE_CACHE:
            return None
        
        # Check memory cache
        if key in self.memory_cache:
            data, timestamp = self.memory_cache[key]
            if (datetime.now() - timestamp).seconds < Config.CACHE_TTL:
                logger.debug(f"Cache hit (memory): {key}")
                return data
        
        # Check disk cache
        cache_file = self.cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Cache hit (disk): {key}")
                    # Update memory cache
                    self.memory_cache[key] = (data, datetime.now())
                    return data
            except Exception as e:
                logger.warning(f"Failed to read cache: {e}")
        
        return None
    
    def set(self, key: str, data: Dict):
        """Set in cache"""
        if not Config.ENABLE_CACHE:
            return
        
        # Memory cache
        self.memory_cache[key] = (data, datetime.now())
        
        # Disk cache
        try:
            cache_file = self.cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.json"
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")
    
    def clear(self):
        """Clear all caches"""
        self.memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except:
                pass

cache_manager = CacheManager()

# ======================================================
# ASYNC PLAYWRIGHT BROWSER POOL
# ======================================================

class BrowserPool:
    """Enterprise browser pooling with recycling and health checks"""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browsers: deque = deque()
        self.in_use: Set[Browser] = set()
        self.lock = asyncio.Lock()
        self.initialized = False
        self.health_check_running = False
    
    async def initialize(self):
        """Initialize the browser pool"""
        if self.initialized:
            return
        
        async with self.lock:
            if self.initialized:
                return
            
            self.playwright = await async_playwright().start()
            
            # Launch browsers
            for i in range(Config.BROWSER_POOL_SIZE):
                browser = await self._launch_browser()
                self.browsers.append(browser)
            
            self.initialized = True
            logger.info(f"Browser pool initialized with {Config.BROWSER_POOL_SIZE} browsers")
            
            # Start health checker
            asyncio.create_task(self._health_check())
    
    async def _launch_browser(self) -> Browser:
        """Launch a single browser with stealth options"""
        launch_options = {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-first-run',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
            ]
        }
        
        if Config.BROWSER_STEALTH_MODE:
            launch_options['args'].extend([
                '--disable-automation',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-component-extensions-with-background-pages',
                '--disable-features=TranslateUI',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-pings'
            ])
        
        try:
            browser = await self.playwright.chromium.launch(**launch_options)
            logger.debug(f"Browser launched successfully")
            return browser
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise
    
    async def get_browser(self) -> Browser:
        """Get an available browser from the pool"""
        await self.initialize()
        
        async with self.lock:
            while len(self.browsers) == 0:
                await asyncio.sleep(0.1)
            
            browser = self.browsers.popleft()
            self.in_use.add(browser)
            
            # Health check before returning
            if not await self._check_browser_health(browser):
                logger.warning("Browser unhealthy, replacing...")
                await browser.close()
                browser = await self._launch_browser()
            
            return browser
    
    async def return_browser(self, browser: Browser):
        """Return a browser to the pool"""
        async with self.lock:
            if browser in self.in_use:
                self.in_use.remove(browser)
                self.browsers.append(browser)
    
    async def _check_browser_health(self, browser: Browser) -> bool:
        """Check if browser is still healthy"""
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto('about:blank', timeout=5000)
            await page.close()
            await context.close()
            return True
        except:
            return False
    
    async def _health_check(self):
        """Periodic health check of all browsers"""
        self.health_check_running = True
        while self.health_check_running:
            await asyncio.sleep(30)
            async with self.lock:
                for browser in list(self.browsers) + list(self.in_use):
                    if not await self._check_browser_health(browser):
                        logger.warning("Browser unhealthy, removing...")
                        try:
                            await browser.close()
                            if browser in self.browsers:
                                self.browsers.remove(browser)
                            if browser in self.in_use:
                                self.in_use.remove(browser)
                            # Replace with new browser
                            new_browser = await self._launch_browser()
                            self.browsers.append(new_browser)
                        except:
                            pass
    
    async def close_all(self):
        """Close all browsers"""
        self.health_check_running = False
        async with self.lock:
            for browser in list(self.browsers) + list(self.in_use):
                try:
                    await browser.close()
                except:
                    pass
            self.browsers.clear()
            self.in_use.clear()
        
        if self.playwright:
            await self.playwright.stop()
        
        self.initialized = False
        logger.info("All browsers closed")

browser_pool = BrowserPool()

# ======================================================
# ADVANCED SCRAPER WITH PLAYWRIGHT
# ======================================================

class AmazonScraper:
    """Enterprise Amazon scraper with async Playwright"""
    
    def __init__(self):
        self.user_agents = self._load_user_agents()
        self.session = self._create_session()
    
    def _load_user_agents(self) -> List[str]:
        """Load realistic user agents"""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
        ]
    
    def _create_session(self):
        """Create requests session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=50, pool_maxsize=50)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    async def scrape_product(self, asin: str, job_id: str = None) -> Dict[str, Any]:
        """Scrape single product with Playwright"""
        
        # Check cache first
        cache_key = f"product_{asin}"
        cached_data = cache_manager.get(cache_key)
        if cached_data:
            return cached_data
        
        browser = None
        context = None
        page = None
        
        try:
            # Get browser from pool
            browser = await browser_pool.get_browser()
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(self.user_agents),
                locale='en-IN',
                timezone_id='Asia/Kolkata',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # Add stealth scripts
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                window.chrome = {
                    runtime: {}
                };
            """)
            
            page = await context.new_page()
            
            # Navigate to product page
            url = f'https://www.amazon.in/dp/{asin}'
            await page.goto(url, timeout=Config.NAVIGATION_TIMEOUT, wait_until='domcontentloaded')
            
            # Random delay to avoid detection
            await asyncio.sleep(random.uniform(Config.REQUEST_DELAY_MIN, Config.REQUEST_DELAY_MAX))
            
            # Check for CAPTCHA or blocking
            page_content = await page.content()
            if 'captcha' in page_content.lower() or 'robot' in page_content.lower():
                logger.warning(f"CAPTCHA detected for ASIN: {asin}")
                return self._create_error_response(asin, "CAPTCHA detected")
            
            # Extract all data
            result = await self._extract_all_data(page, asin)
            
            # Check availability
            result['is_available'] = await self._check_availability(page)
            result['available_asin'] = asin if result['is_available'] else ''
            result['unavailable_asin'] = asin if not result['is_available'] else ''
            
            # Cache the result
            cache_manager.set(cache_key, result)
            
            return result
            
        except PlaywrightTimeoutError:
            logger.error(f"Timeout for ASIN: {asin}")
            return self._create_error_response(asin, "Timeout")
        except Exception as e:
            logger.error(f"Error scraping {asin}: {str(e)}\n{traceback.format_exc()}")
            return self._create_error_response(asin, str(e))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser_pool.return_browser(browser)
    
    async def _extract_all_data(self, page: Page, asin: str) -> Dict[str, Any]:
        """Extract all required product data"""
        
        result = {
            'asin': asin,
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'product_title': '',
            'product_price': '',
            'mrp': '',
            'discount_percentage': '',
            'product_rating': '',
            'total_reviews_count': '',
            'product_brand': '',
            'product_category': '',
            'product_sub_category_rank': '',
            'best_seller_rank': '',
            'product_description': '',
            'bullet_points': '',
            'seller_name': '',
            'prime_eligible': False,
            'buy_box_available': False,
            'coupon_available': False,
            'delivery_status': '',
            'stock_status': '',
            'product_images_count': 0,
            'product_url': f'https://www.amazon.in/dp/{asin}',
            'a_plus_content_available': False,
            'amazon_choice_badge': False,
            'best_seller_badge': False,
            'sponsored_detection': False,
            'limited_time_deal_badge': False
        }
        
        # Extract title
        try:
            title_elem = await page.query_selector('#productTitle')
            if title_elem:
                result['product_title'] = (await title_elem.text_content()).strip()
        except: pass
        
        # Extract price and MRP
        try:
            price_elem = await page.query_selector('.a-price-whole')
            if price_elem:
                price_text = await price_elem.text_content()
                result['product_price'] = price_text.replace(',', '').strip()
            
            # MRP (strikethrough price)
            mrp_elem = await page.query_selector('.a-price.a-text-price')
            if mrp_elem:
                mrp_text = await mrp_elem.text_content()
                result['mrp'] = mrp_text.replace('₹', '').replace(',', '').strip()
                
                # Calculate discount
                if result['product_price'] and result['mrp']:
                    try:
                        price_float = float(result['product_price'])
                        mrp_float = float(result['mrp'])
                        if mrp_float > 0:
                            discount = ((mrp_float - price_float) / mrp_float) * 100
                            result['discount_percentage'] = f"{discount:.0f}%"
                    except: pass
        except: pass
        
        # Extract rating
        try:
            rating_elem = await page.query_selector('#acrPopover .a-icon-alt')
            if rating_elem:
                rating_text = await rating_elem.text_content()
                result['product_rating'] = rating_text.split()[0]
        except: pass
        
        # Extract reviews count
        try:
            reviews_elem = await page.query_selector('#acrCustomerReviewText')
            if reviews_elem:
                reviews_text = await reviews_elem.text_content()
                result['total_reviews_count'] = reviews_text.replace('ratings', '').replace('rating', '').replace(',', '').strip()
        except: pass
        
        # Extract brand
        try:
            brand_elem = await page.query_selector('#bylineInfo')
            if brand_elem:
                brand_text = await brand_elem.text_content()
                result['product_brand'] = brand_text.replace('Brand:', '').strip()
        except: pass
        
        # Extract seller
        try:
            seller_elem = await page.query_selector('#sellerProfileTriggerId')
            if seller_elem:
                result['seller_name'] = (await seller_elem.text_content()).strip()
        except: pass
        
        # Check Prime eligibility
        try:
            prime_elem = await page.query_selector('.a-icon-prime')
            result['prime_eligible'] = prime_elem is not None
        except: pass
        
        # Check Buy Box
        try:
            buybox_elem = await page.query_selector('#buy-now-button')
            result['buy_box_available'] = buybox_elem is not None
        except: pass
        
        # Check coupon
        try:
            coupon_elem = await page.query_selector('#couponTextpctch')
            result['coupon_available'] = coupon_elem is not None
        except: pass
        
        # Extract description
        try:
            desc_elem = await page.query_selector('#productDescription')
            if desc_elem:
                result['product_description'] = (await desc_elem.text_content()).strip()
        except: pass
        
        # Extract bullet points
        try:
            bullet_elems = await page.query_selector_all('#feature-bullets ul li')
            bullet_texts = []
            for bullet in bullet_elems[:10]:  # Max 10 bullet points
                text = (await bullet.text_content()).strip()
                if text:
                    bullet_texts.append(text)
            result['bullet_points'] = ' | '.join(bullet_texts)
        except: pass
        
        # Count images
        try:
            image_elems = await page.query_selector_all('#altImages img')
            result['product_images_count'] = len(image_elems)
        except: pass
        
        # Extract best seller rank and category ranks
        try:
            page_text = await page.text_content()
            
            # Find all rank patterns
            rank_pattern = r'#([0-9,]+)\s+in\s+([A-Za-z\s&]+)'
            rank_matches = re.findall(rank_pattern, page_text)
            
            if rank_matches:
                # First is usually best seller rank
                if len(rank_matches) >= 1:
                    result['best_seller_rank'] = f"#{rank_matches[0][0]} in {rank_matches[0][1]}"
                # Second is sub-category rank
                if len(rank_matches) >= 2:
                    result['product_sub_category_rank'] = f"#{rank_matches[1][0]} in {rank_matches[1][1]}"
                
                # Extract category hierarchy
                categories = []
                for rank in rank_matches[:3]:
                    categories.append(rank[1])
                result['product_category'] = ' > '.join(categories) if categories else ''
        except: pass
        
        # Check badges
        page_html = await page.content()
        result['amazon_choice_badge'] = "Amazon's Choice" in page_html
        result['best_seller_badge'] = 'Best Seller' in page_html
        result['limited_time_deal_badge'] = 'Limited time deal' in page_html
        result['sponsored_detection'] = 'Sponsored' in page_html and 'sponsored' in page_html.lower()
        
        # Check A+ content
        result['a_plus_content_available'] = 'aplus' in page_html.lower()
        
        # Delivery status
        try:
            delivery_elem = await page.query_selector('#mir-layout-DELIVERY_BLOCK')
            if delivery_elem:
                result['delivery_status'] = (await delivery_elem.text_content()).strip()
        except: pass
        
        return result
    
    async def _check_availability(self, page: Page) -> bool:
        """Check if product is available"""
        try:
            # Check for availability message
            availability_elem = await page.query_selector('#availability span')
            if availability_elem:
                availability_text = (await availability_elem.text_content()).lower()
                
                # Available indicators
                available_keywords = ['in stock', 'available', 'in stock.', 'in stock,', 'in stock!']
                unavailable_keywords = ['currently unavailable', 'out of stock', 'temporarily out of stock', 
                                       'we don\'t know when', 'item not available', 'page not found']
                
                for keyword in available_keywords:
                    if keyword in availability_text:
                        return True
                
                for keyword in unavailable_keywords:
                    if keyword in availability_text:
                        return False
            
            # Check for add to cart button
            add_to_cart = await page.query_selector('#add-to-cart-button')
            buy_now = await page.query_selector('#buy-now-button')
            
            if add_to_cart or buy_now:
                return True
            
            # Check if it's a dog/error page
            title = await page.title()
            if '404' in title or 'Page Not Found' in title:
                return False
            
            return False
            
        except:
            return False
    
    def _create_error_response(self, asin: str, error_msg: str) -> Dict[str, Any]:
        """Create error response for failed scraping"""
        return {
            'asin': asin,
            'status': 'failed',
            'timestamp': datetime.now().isoformat(),
            'error': error_msg,
            'is_available': False,
            'available_asin': '',
            'unavailable_asin': asin,
            'product_title': '',
            'product_price': '',
            'product_rating': '',
            'total_reviews_count': '',
            'product_brand': '',
            'seller_name': '',
            'best_seller_rank': '',
            'product_sub_category_rank': ''
        }

# Initialize scraper
scraper = AmazonScraper()

# ======================================================
# JOB MANAGER WITH PERSISTENCE
# ======================================================

class JobManager:
    """Manage scraping jobs with persistence and recovery"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        self.active_jobs: Set[str] = set()
        self.lock = asyncio.Lock()
        
        # Load existing jobs from disk
        self._load_jobs()
    
    def _load_jobs(self):
        """Load jobs from disk on startup"""
        progress_dir = Config.PROGRESS_FOLDER
        for job_file in progress_dir.glob("job_*.json"):
            try:
                with open(job_file, 'r') as f:
                    job_data = json.load(f)
                    job_id = job_data['job_id']
                    self.jobs[job_id] = job_data
                    logger.info(f"Loaded job {job_id} from disk")
            except Exception as e:
                logger.error(f"Failed to load job {job_file}: {e}")
    
    def _save_job(self, job_id: str):
        """Save job to disk for persistence"""
        try:
            job_file = Config.PROGRESS_FOLDER / f"job_{job_id}.json"
            with open(job_file, 'w') as f:
                json.dump(self.jobs[job_id], f, default=str)
        except Exception as e:
            logger.error(f"Failed to save job {job_id}: {e}")
    
    def create_job(self, job_id: str, asins: List[str], selected_fields: List[str], filename: str):
        """Create a new job"""
        self.jobs[job_id] = {
            'job_id': job_id,
            'status': 'pending',
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'available': 0,
            'unavailable': 0,
            'current_asin': '',
            'total_asins': len(asins),
            'asins': asins,
            'results': [],
            'selected_fields': selected_fields,
            'start_time': datetime.now(),
            'end_time': None,
            'output_file': None,
            'filename': filename,
            'error_logs': []
        }
        self._save_job(job_id)
        logger.info(f"Job {job_id} created with {len(asins)} ASINs")
        return job_id
    
    def update_job(self, job_id: str, **kwargs):
        """Update job data"""
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
            self._save_job(job_id)
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    async def process_job_async(self, job_id: str):
        """Process job asynchronously with browser pool"""
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        self.active_jobs.add(job_id)
        job['status'] = 'processing'
        self._save_job(job_id)
        
        asins = job['asins']
        selected_fields = job['selected_fields']
        total = len(asins)
        
        # Process in batches
        results = []
        
        for batch_start in range(0, total, Config.BATCH_SIZE):
            batch_end = min(batch_start + Config.BATCH_SIZE, total)
            batch_asins = asins[batch_start:batch_end]
            
            logger.info(f"Processing batch {batch_start//Config.BATCH_SIZE + 1} for job {job_id}")
            
            # Process batch concurrently
            tasks = []
            for asin in batch_asins:
                task = scraper.scrape_product(asin, job_id)
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(batch_results):
                asin = batch_asins[idx]
                index = batch_start + idx
                
                if isinstance(result, Exception):
                    logger.error(f"Failed to scrape {asin}: {result}")
                    job['failed'] += 1
                    job['error_logs'].append({
                        'asin': asin,
                        'error': str(result),
                        'timestamp': datetime.now().isoformat()
                    })
                    filtered_result = self._filter_fields({
                        'asin': asin,
                        'status': 'failed',
                        'timestamp': datetime.now().isoformat(),
                        'is_available': False,
                        'available_asin': '',
                        'unavailable_asin': asin
                    }, selected_fields)
                else:
                    job['successful'] += 1
                    if result.get('is_available', False):
                        job['available'] += 1
                    else:
                        job['unavailable'] += 1
                    filtered_result = self._filter_fields(result, selected_fields)
                
                results.append(filtered_result)
                job['results'] = results
                job['processed'] = index + 1
                job['current_asin'] = asin
                
                # Update every 10 ASINs
                if (index + 1) % 10 == 0:
                    self._save_job(job_id)
                    
                    # Send progress update via SocketIO
                    progress_percentage = ((index + 1) / total) * 100
                    socketio.emit('progress_update', {
                        'job_id': job_id,
                        'processed': index + 1,
                        'total_asins': total,
                        'available': job['available'],
                        'unavailable': job['unavailable'],
                        'successful': job['successful'],
                        'failed': job['failed'],
                        'current_asin': asin,
                        'progress_percentage': progress_percentage
                    }, namespace='/')
            
            # Small delay between batches
            await asyncio.sleep(2)
        
        # Job completed
        job['status'] = 'completed'
        job['end_time'] = datetime.now()
        
        # Export results
        output_file = await self._export_results(job_id, results, selected_fields)
        job['output_file'] = str(output_file)
        
        self._save_job(job_id)
        self.active_jobs.discard(job_id)
        
        # Send completion notification
        socketio.emit('job_completed', {
            'job_id': job_id,
            'download_url': f'/api/export/{job_id}',
            'total_processed': job['processed'],
            'total_successful': job['successful'],
            'total_failed': job['failed'],
            'total_available': job['available'],
            'total_unavailable': job['unavailable']
        }, namespace='/')
        
        logger.info(f"Job {job_id} completed successfully")
    
    def _filter_fields(self, result: Dict, selected_fields: List[str]) -> Dict:
        """Filter result to only selected fields"""
        filtered = {
            'asin': result.get('asin', ''),
            'status': result.get('status', ''),
            'timestamp': result.get('timestamp', ''),
            'is_available': result.get('is_available', False)
        }
        
        field_mapping = {
            "Product Title": "product_title",
            "Product Price": "product_price",
            "MRP": "mrp",
            "Discount Percentage": "discount_percentage",
            "Product Rating": "product_rating",
            "Total Reviews Count": "total_reviews_count",
            "Product Brand": "product_brand",
            "Product Category": "product_category",
            "Product Sub Category Rank": "product_sub_category_rank",
            "Best Seller Rank": "best_seller_rank",
            "Product Description": "product_description",
            "Bullet Points": "bullet_points",
            "Seller Name": "seller_name",
            "Prime Eligible": "prime_eligible",
            "Buy Box Available": "buy_box_available",
            "Coupon Available": "coupon_available",
            "Delivery Status": "delivery_status",
            "Stock Status": "stock_status",
            "Product Images Count": "product_images_count",
            "Product URL": "product_url",
            "A+ Content Available": "a_plus_content_available",
            "Amazon Choice Badge": "amazon_choice_badge",
            "Best Seller Badge": "best_seller_badge",
            "Sponsored Detection": "sponsored_detection",
            "Limited Time Deal Badge": "limited_time_deal_badge",
            "Available Product ASIN": "available_asin",
            "Unavailable Product ASIN": "unavailable_asin"
        }
        
        if selected_fields:
            for field in selected_fields:
                if field in field_mapping:
                    filtered[field] = result.get(field_mapping[field], '')
        else:
            # Return all fields
            for display_name, actual_key in field_mapping.items():
                filtered[display_name] = result.get(actual_key, '')
        
        return filtered
    
    async def _export_results(self, job_id: str, results: List[Dict], selected_fields: List[str]) -> Path:
        """Export results to Excel/CSV"""
        if not results:
            return None
        
        df = pd.DataFrame(results)
        
        # Clean data
        df = df.replace({np.nan: '', None: ''})
        
        # Generate output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Config.OUTPUT_FOLDER / f"{job_id}_{timestamp}.xlsx"
        
        # Export to Excel with formatting
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Amazon Products', index=False)
            
            # Auto-adjust column widths
            workbook = writer.book
            worksheet = writer.sheets['Amazon Products']
            
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.set_column(idx, idx, min(max_length + 2, 50))
        
        logger.info(f"Exported {len(results)} results to {output_file}")
        return output_file

job_manager = JobManager()

# ======================================================
# FLASK APPLICATION SETUP
# ======================================================

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# SocketIO with async mode
socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='asgi',
    ping_timeout=60,
    ping_interval=25,
    logger=logger,
    engineio_logger=False
)

# ======================================================
# FILE HANDLING HELPERS
# ======================================================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def save_upload_file(file: FileStorage) -> Tuple[str, Path]:
    """Save uploaded file with secure filename"""
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    unique_filename = f"{timestamp}_{filename}"
    file_path = Config.UPLOAD_FOLDER / unique_filename
    file.save(file_path)
    return unique_filename, file_path

def read_asins_from_file(file_path: Path, filename: str) -> List[str]:
    """Read ASINs from Excel or CSV file"""
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str, engine='openpyxl')
        
        # Find ASIN column
        asin_column = None
        for col in df.columns:
            if 'asin' in col.lower():
                asin_column = col
                break
        
        if asin_column is None:
            asin_column = df.columns[0]
        
        # Extract and clean ASINs
        asins = df[asin_column].astype(str).str.strip().str.upper().tolist()
        
        # Filter valid ASINs (10 characters, alphanumeric)
        valid_asins = []
        for asin in asins:
            if asin and asin != 'nan' and len(asin) == 10 and asin.isalnum():
                valid_asins.append(asin)
            elif asin and asin != 'nan':
                # Try to clean invalid ASINs
                cleaned = re.sub(r'[^A-Z0-9]', '', asin)
                if len(cleaned) == 10:
                    valid_asins.append(cleaned)
        
        logger.info(f"Found {len(valid_asins)} valid ASINs from {len(asins)} rows")
        return valid_asins[:Config.MAX_ASINS]
    
    except Exception as e:
        logger.error(f"Failed to read ASINs: {e}")
        raise

# ======================================================
# API ROUTES
# ======================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_jobs': len(job_manager.active_jobs),
        'total_jobs': len(job_manager.jobs),
        'browser_pool_initialized': browser_pool.initialized
    })

@app.route('/api/upload', methods=['POST'])
def upload_file_api():
    """Upload file and extract ASINs"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(Config.ALLOWED_EXTENSIONS)}'}), 400
        
        # Save file
        unique_filename, file_path = save_upload_file(file)
        
        # Read ASINs
        asins = read_asins_from_file(file_path, unique_filename)
        
        if not asins:
            return jsonify({'error': 'No valid ASINs found in file'}), 400
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'total_asins': len(asins),
            'asins': asins[:100]  # Return first 100 for preview
        })
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-scraping', methods=['POST'])
def start_scraping_api():
    """Start scraping job"""
    try:
        data = request.get_json()
        asins = data.get('asins', [])
        selected_fields = data.get('selected_fields', [])
        filename = data.get('filename', '')
        
        if not asins:
            return jsonify({'error': 'No ASINs provided'}), 400
        
        # Limit ASINs
        if len(asins) > Config.MAX_ASINS:
            asins = asins[:Config.MAX_ASINS]
        
        job_id = str(uuid.uuid4())
        job_manager.create_job(job_id, asins, selected_fields, filename)
        
        # Start async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def run_async():
            asyncio.run(job_manager.process_job_async(job_id))
        
        job_manager.executor.submit(run_async)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_asins': len(asins)
        })
    
    except Exception as e:
        logger.error(f"Start scraping error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_id>')
def get_job_status(job_id):
    """Get job status"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job_id,
            'status': job['status'],
            'processed': job['processed'],
            'total_asins': job['total_asins'],
            'successful': job['successful'],
            'failed': job['failed'],
            'available': job['available'],
            'unavailable': job['unavailable'],
            'current_asin': job.get('current_asin', ''),
            'progress_percentage': (job['processed'] / job['total_asins'] * 100) if job['total_asins'] > 0 else 0,
            'output_file': job.get('output_file'),
            'start_time': job.get('start_time'),
            'end_time': job.get('end_time')
        })
    
    except Exception as e:
        logger.error(f"Get job error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs')
def list_jobs():
    """List all jobs"""
    try:
        jobs_list = []
        for job_id, job in job_manager.jobs.items():
            jobs_list.append({
                'job_id': job_id,
                'status': job['status'],
                'processed': job['processed'],
                'total_asins': job['total_asins'],
                'filename': job.get('filename', ''),
                'start_time': job.get('start_time'),
                'end_time': job.get('end_time')
            })
        
        # Sort by start time descending
        jobs_list.sort(key=lambda x: x['start_time'] or datetime.min, reverse=True)
        
        return jsonify({'jobs': jobs_list[:50]})  # Return last 50 jobs
    
    except Exception as e:
        logger.error(f"List jobs error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<job_id>')
def export_results_api(job_id):
    """Export job results"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        output_file = job.get('output_file')
        if not output_file or not Path(output_file).exists():
            return jsonify({'error': 'Output file not found'}), 404
        
        format_type = request.args.get('format', 'xlsx')
        
        if format_type == 'csv':
            # Convert to CSV
            df = pd.read_excel(output_file)
            csv_output = Config.OUTPUT_FOLDER / f"{job_id}.csv"
            df.to_csv(csv_output, index=False)
            return send_file(csv_output, as_attachment=True, download_name=f"{job_id}_export.csv")
        
        elif format_type == 'json':
            # Convert to JSON
            df = pd.read_excel(output_file)
            json_output = Config.OUTPUT_FOLDER / f"{job_id}.json"
            df.to_json(json_output, orient='records', indent=2)
            return send_file(json_output, as_attachment=True, download_name=f"{job_id}_export.json")
        
        else:  # xlsx
            return send_file(output_file, as_attachment=True, download_name=f"{job_id}_export.xlsx")
    
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-filtered/<job_id>')
def export_filtered_api(job_id):
    """Export filtered results (available only / unavailable only)"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        filter_type = request.args.get('filter', 'all')  # all, available, unavailable
        
        df = pd.DataFrame(job['results'])
        
        if filter_type == 'available':
            df = df[df['is_available'] == True]
        elif filter_type == 'unavailable':
            df = df[df['is_available'] == False]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Config.OUTPUT_FOLDER / f"{job_id}_{filter_type}_{timestamp}.xlsx"
        
        df.to_excel(output_file, index=False)
        
        return send_file(output_file, as_attachment=True)
    
    except Exception as e:
        logger.error(f"Filtered export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancel-job/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel running job"""
    try:
        if job_id not in job_manager.active_jobs:
            return jsonify({'error': 'Job not active'}), 400
        
        job_manager.update_job(job_id, status='cancelled', end_time=datetime.now())
        job_manager.active_jobs.discard(job_id)
        
        return jsonify({'success': True, 'message': 'Job cancelled'})
    
    except Exception as e:
        logger.error(f"Cancel job error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/available-fields')
def get_available_fields():
    """Get list of available extraction fields"""
    fields = [
        "Product Title", "Product Price", "MRP", "Discount Percentage",
        "Product Rating", "Total Reviews Count", "Product Brand",
        "Product Category", "Product Sub Category Rank", "Best Seller Rank",
        "Product Description", "Bullet Points", "Seller Name",
        "Prime Eligible", "Buy Box Available", "Coupon Available",
        "Delivery Status", "Stock Status", "Product Images Count",
        "Product URL", "A+ Content Available", "Amazon Choice Badge",
        "Best Seller Badge", "Sponsored Detection", "Limited Time Deal Badge"
    ]
    return jsonify({'fields': fields})

# ======================================================
# SOCKET.IO EVENTS
# ======================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to server', 'timestamp': datetime.now().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('subscribe_job')
def handle_subscribe_job(data):
    """Subscribe to job updates"""
    job_id = data.get('job_id')
    if job_id:
        logger.info(f"Client {request.sid} subscribed to job {job_id}")
        emit('subscribed', {'job_id': job_id})

# ======================================================
# SHUTDOWN HANDLER
# ======================================================

import atexit

def shutdown_handler():
    """Clean shutdown of browser pool"""
    logger.info("Shutting down...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(browser_pool.close_all())
    loop.close()
    logger.info("Shutdown complete")

atexit.register(shutdown_handler)

# ======================================================
# MAIN ENTRY POINT
# ======================================================

if __name__ == '__main__':
    try:
        logger.info("=" * 60)
        logger.info("AMAZON ASIN INTELLIGENCE PLATFORM v4.0.0")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  - MAX_WORKERS: {Config.MAX_WORKERS}")
        logger.info(f"  - BROWSER_POOL_SIZE: {Config.BROWSER_POOL_SIZE}")
        logger.info(f"  - BATCH_SIZE: {Config.BATCH_SIZE}")
        logger.info(f"  - MAX_ASINS: {Config.MAX_ASINS}")
        logger.info("=" * 60)
        
        # Run the app
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False  # Disable reloader for production
        )
    
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        shutdown_handler()
    except Exception as e:
        logger.error(f"Fatal error: {e}\n{traceback.format_exc()}")
        sys.exit(1)