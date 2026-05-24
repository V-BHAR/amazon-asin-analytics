# COMPLETE AMAZON ASIN ANALYTICS BACKEND (app.py)


import os
import uuid
import time
import logging
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from bs4 import BeautifulSoup

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    send_file
)

from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

# ======================================================
# CONFIG
# ======================================================

class Config:

    SECRET_KEY = os.urandom(24).hex()

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    UPLOAD_FOLDER = Path("uploads")

    OUTPUT_FOLDER = Path("outputs")

    LOG_FOLDER = Path("logs")

    ALLOWED_EXTENSIONS = {
        "csv",
        "xlsx",
        "xls"
    }

    MAX_ASINS = 50000

    MAX_WORKERS = 5

    @classmethod
    def init_directories(cls):

        cls.UPLOAD_FOLDER.mkdir(
            exist_ok=True,
            parents=True
        )

        cls.OUTPUT_FOLDER.mkdir(
            exist_ok=True,
            parents=True
        )

        cls.LOG_FOLDER.mkdir(
            exist_ok=True,
            parents=True
        )

Config.init_directories()

# ======================================================
# LOGGING
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ======================================================
# FLASK
# ======================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = Config.SECRET_KEY

app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='threading'
)

# ======================================================
# JOB MANAGER
# ======================================================

class JobManager:

    def __init__(self):

        self.jobs = {}

        self.executor = ThreadPoolExecutor(
            max_workers=Config.MAX_WORKERS
        )

    def create_job(
        self,
        job_id,
        asins,
        selected_fields
    ):

        self.jobs[job_id] = {

            'status': 'processing',

            'processed': 0,

            'successful': 0,

            'failed': 0,

            'available': 0,

            'unavailable': 0,

            'current_asin': '',

            'total_asins': len(asins),

            'results': [],

            'selected_fields': selected_fields,

            'start_time': datetime.now(),

            'output_file': None
        }

    def get_job(self, job_id):

        return self.jobs.get(job_id)

job_manager = JobManager()

# ======================================================
# FIELD MAP
# ======================================================

FIELD_MAPPING = {

    "Product Title":
    "product_title",

    "Product Price":
    "product_price",

    "Product Rating":
    "product_rating",

    "Total Reviews Count":
    "total_reviews_count",

    "Product Brand":
    "product_brand",

    "Seller Name":
    "seller_name",

    "Product Availability":
    "is_available",

    "Available Product ASINs":
    "available_asin",

    "Unavailable Product ASINs":
    "unavailable_asin",

    "Product Stock Status":
    "stock_status",

    "Best Seller Rank":
    "best_seller_rank",

    "Product Sub Category Rank":
    "product_sub_category_rank",

    "Amazon Choice Badge":
    "amazon_choice_badge",

    "Best Seller Badge":
    "best_seller_badge",

    "Limited Time Deal Badge":
    "limited_time_deal_badge",

    "Product Description":
    "product_description",

    "Bullet Points":
    "bullet_points",

    "A+ Content Available":
    "a_plus_content_available",

    "Product Images Count":
    "product_images_count",

    "Prime Eligible":
    "prime_eligible",

    "Delivery Status":
    "delivery_status",

    "Buy Box Available":
    "buy_box_available",

    "Coupon Available":
    "coupon_available",

    "Discount Percentage":
    "discount_percentage"
}

# ======================================================
# HELPERS
# ======================================================

def allowed_file(filename):

    return (
        '.' in filename
        and
        filename.rsplit('.', 1)[1].lower()
        in Config.ALLOWED_EXTENSIONS
    )

def save_upload_file(file):

    filename = secure_filename(file.filename)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    unique_filename = (
        f"{timestamp}_{filename}"
    )

    file_path = (
        Config.UPLOAD_FOLDER /
        unique_filename
    )

    file.save(file_path)

    return unique_filename, file_path

def read_asins_from_file(
    file_path,
    filename
):

    if filename.endswith('.csv'):

        df = pd.read_csv(file_path)

    else:

        df = pd.read_excel(file_path)

    asin_column = None

    for col in df.columns:

        if 'asin' in col.lower():

            asin_column = col

            break

    if asin_column is None:

        asin_column = df.columns[0]

    asins = (
        df[asin_column]
        .astype(str)
        .str.strip()
        .tolist()
    )

    cleaned_asins = []

    for asin in asins:

        if asin and asin != 'nan':

            cleaned_asins.append(asin)

    return cleaned_asins[:Config.MAX_ASINS]

# ======================================================
# AMAZON SCRAPER
# ======================================================

def scrape_amazon_product(asin):

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0 Safari/537.36'
        ),
        'Accept-Language': 'en-IN,en;q=0.9'
    }

    url = f'https://www.amazon.in/dp/{asin}'

    response = requests.get(
        url,
        headers=headers,
        timeout=25
    )

    soup = BeautifulSoup(
        response.text,
        'lxml'
    )

    title = ''
    price = ''
    rating = ''
    reviews = ''
    brand = ''
    seller = ''
    availability = False
    stock_status = ''
    best_seller_rank = ''
    sub_category_rank = ''
    product_description = ''
    bullet_points = ''
    product_images_count = 0
    prime_eligible = False
    delivery_status = ''
    buy_box_available = False
    coupon_available = False
    discount_percentage = ''
    amazon_choice_badge = False
    best_seller_badge = False
    limited_time_deal_badge = False
    a_plus_content_available = False

    # ==================================================
    # TITLE
    # ==================================================

    title_element = soup.select_one(
        '#productTitle'
    )

    if title_element:

        title = title_element.text.strip()

    # ==================================================
    # PRICE
    # ==================================================

    price_element = soup.select_one(
        '.a-price-whole'
    )

    if price_element:

        price = (
            price_element.text
            .replace(',', '')
            .strip()
        )

    # ==================================================
    # RATING
    # ==================================================

    rating_element = soup.select_one(
        '#acrPopover .a-icon-alt'
    )

    if rating_element:

        rating = rating_element.text.strip()

    # ==================================================
    # REVIEWS
    # ==================================================

    reviews_element = soup.select_one(
        '#acrCustomerReviewText'
    )

    if reviews_element:

        reviews = (
            reviews_element.text
            .replace('ratings', '')
            .replace('rating', '')
            .replace(',', '')
            .strip()
        )

    # ==================================================
    # BRAND
    # ==================================================

    brand_element = soup.select_one(
        '#bylineInfo'
    )

    if brand_element:

        brand = brand_element.text.strip()

    # ==================================================
    # AVAILABILITY
    # ==================================================

    availability_element = soup.select_one(
        '#availability span'
    )

    if availability_element:

        availability_text = (
            availability_element.text
            .strip()
            .lower()
        )

        stock_status = availability_text

        if (
            'in stock' in availability_text
            or
            'available' in availability_text
        ):

            availability = True

        if 'currently unavailable' in availability_text:

            availability = False

    # ==================================================
    # SELLER
    # ==================================================

    seller_element = soup.select_one(
        '#sellerProfileTriggerId'
    )

    if seller_element:

        seller = seller_element.text.strip()

    # ==================================================
    # PRIME
    # ==================================================

    prime_element = soup.select_one(
        '.a-icon-prime'
    )

    if prime_element:

        prime_eligible = True

    # ==================================================
    # BUY BOX
    # ==================================================

    buybox_element = soup.select_one(
        '#buy-now-button'
    )

    if buybox_element:

        buy_box_available = True

    # ==================================================
    # COUPON
    # ==================================================

    coupon_element = soup.select_one(
        '#couponTextpctch'
    )

    if coupon_element:

        coupon_available = True

    # ==================================================
    # DISCOUNT
    # ==================================================

    discount_element = soup.select_one(
        '.savingsPercentage'
    )

    if discount_element:

        discount_percentage = (
            discount_element.text.strip()
        )

    # ==================================================
    # DESCRIPTION
    # ==================================================

    description_element = soup.select_one(
        '#productDescription'
    )

    if description_element:

        product_description = (
            description_element.text.strip()
        )

    # ==================================================
    # BULLET POINTS
    # ==================================================

    bullet_elements = soup.select(
        '#feature-bullets ul li'
    )

    bullet_texts = []

    for bullet in bullet_elements:

        text = bullet.text.strip()

        if text:

            bullet_texts.append(text)

    bullet_points = ' | '.join(bullet_texts)

    # ==================================================
    # A+ CONformatted_ranks = []TENT
    # ==================================================

    aplus_element = soup.select_one(
        '#aplus'
    )

    if aplus_element:

        a_plus_content_available = True

    # ==================================================
    # IMAGES COUNT
    # ==================================================

    image_elements = soup.select(
        '#altImages img'
    )

    product_images_count = len(image_elements)

    # ==================================================
    # SALES RANK
    # ==================================================
    # =========================================
    # BEST SELLER RANK + SUB CATEGORY RANK
    # =========================================

    import re

    detail_text = soup.get_text(
        " ",
        strip=True
    )

    rank_matches = re.findall(
        r'#([0-9,]+)\s+in\s+([A-Za-z &]+)',
        detail_text
    )

    best_seller_rank = ""
    sub_category_rank = ""

    if rank_matches:

        if len(rank_matches) >= 1:

            first_rank = rank_matches[0]

            best_seller_rank = (
                f"#{first_rank[0]} in {first_rank[1]}"
            )

        if len(rank_matches) >= 2:

            second_rank = rank_matches[1]

            sub_category_rank = (
                f"#{second_rank[0]} in {second_rank[1]}"
            )    # ==================================================
    # BADGES
    # ==================================================

    amazon_choice_element = soup.find(
        string=lambda t:
        t and "Amazon's Choice" in t
    )

    if amazon_choice_element:

        amazon_choice_badge = True

    best_seller_element = soup.find(
        string=lambda t:
        t and 'Best Seller' in t
    )

    if best_seller_element:

        best_seller_badge = True

    deal_element = soup.find(
        string=lambda t:
        t and 'Limited time deal' in t
    )

    if deal_element:

        limited_time_deal_badge = True

    return {

        'asin': asin,

        'status': 'success',

        'timestamp': datetime.now().isoformat(),

        'product_title': title,

        'product_price': price,

        'product_rating': rating,

        'total_reviews_count': reviews,

        'product_brand': brand,

        'seller_name': seller,

        'is_available': availability,

        'available_asin': asin if availability else '',

        'unavailable_asin': asin if not availability else '',

        'stock_status': stock_status,

        'best_seller_rank': best_seller_rank,

        'product_sub_category_rank': sub_category_rank,

        'product_description': product_description,

        'bullet_points': bullet_points,

        'a_plus_content_available': a_plus_content_available,

        'product_images_count': product_images_count,

        'prime_eligible': prime_eligible,

        'delivery_status': delivery_status,

        'buy_box_available': buy_box_available,

        'coupon_available': coupon_available,

        'discount_percentage': discount_percentage,

        'amazon_choice_badge': amazon_choice_badge,

        'best_seller_badge': best_seller_badge,

        'limited_time_deal_badge': limited_time_deal_badge
    }

# ======================================================
# ROUTES
# ======================================================

@app.route('/')
def index():

    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file_api():

    try:

        if 'file' not in request.files:

            return jsonify({
                'error': 'No file uploaded'
            }), 400

        file = request.files['file']

        if file.filename == '':

            return jsonify({
                'error': 'No file selected'
            }), 400

        if not allowed_file(file.filename):

            return jsonify({
                'error': 'Invalid file type'
            }), 400

        unique_filename, file_path = (
            save_upload_file(file)
        )

        asins = read_asins_from_file(
            file_path,
            unique_filename
        )

        return jsonify({

            'success': True,

            'filename': unique_filename,

            'total_asins': len(asins),

            'asins': asins
        })

    except Exception as e:

        logger.error(str(e))

        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/start-scraping', methods=['POST'])
def start_scraping_api():

    try:

        data = request.get_json()

        asins = data.get('asins', [])

        selected_fields = data.get(
            'selected_fields',
            []
        )

        if not asins:

            return jsonify({
                'error': 'No ASINs'
            }), 400

        job_id = str(uuid.uuid4())

        job_manager.create_job(
            job_id,
            asins,
            selected_fields
        )

        def process():

            results = []

            total = len(asins)

            for index, asin in enumerate(asins):

                try:

                    result = scrape_amazon_product(asin)

                    filtered_item = {

                        'asin': result['asin'],

                        'status': result['status'],

                        'timestamp': result['timestamp']
                    }

                    for field in selected_fields:

                        actual_key = FIELD_MAPPING.get(field)

                        if actual_key:

                            filtered_item[field] = (
                                result.get(actual_key, '')
                            )

                    results.append(filtered_item)

                    job = job_manager.jobs[job_id]

                    job['results'] = results

                    job['processed'] += 1

                    job['successful'] += 1

                    job['current_asin'] = asin

                    if result['is_available']:

                        job['available'] += 1

                    else:

                        job['unavailable'] += 1

                    progress = round(
                        ((index + 1) / total) * 100,
                        2
                    )

                    socketio.emit(
                        'progress_update',
                        {
                            'job_id': job_id,
                            'processed': index + 1,
                            'total_asins': total,
                            'available': job['available'],
                            'unavailable': job['unavailable'],
                            'successful': job['successful'],
                            'failed': job['failed'],
                            'current_asin': asin,
                            'progress_percentage': progress
                        }
                    )

                    time.sleep(1)

                except Exception as e:

                    logger.error(
                        f'{asin} Error: {str(e)}'
                    )

                    job = job_manager.jobs[job_id]

                    job['failed'] += 1

            df = pd.DataFrame(results)

            output_file = (
                Config.OUTPUT_FOLDER /
                f'{job_id}.xlsx'
            )

            df.to_excel(
                output_file,
                index=False
            )

            job['output_file'] = str(output_file)

            job['status'] = 'completed'

            socketio.emit(
                'job_completed',
                {
                    'job_id': job_id,
                    'download_url': f'/api/export/{job_id}'
                }
            )

        job_manager.executor.submit(process)

        return jsonify({

            'success': True,

            'job_id': job_id
        })

    except Exception as e:

        logger.error(str(e))

        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/export/<job_id>')
def export_results_api(job_id):

    try:

        job = job_manager.get_job(job_id)

        if not job:

            return jsonify({
                'error': 'Job not found'
            }), 404

        output_file = job.get('output_file')

        if not output_file:

            return jsonify({
                'error': 'Output not ready'
            }), 400

        return send_file(
            output_file,
            as_attachment=True
        )

    except Exception as e:

        logger.error(str(e))

        return jsonify({
            'error': str(e)
        }), 500

# ======================================================
# SOCKET EVENTS
# ======================================================

@socketio.on('connect')
def handle_connect():

    socketio.emit(
        'connected',
        {
            'message': 'Connected'
        }
    )

# ======================================================
# MAIN
# ======================================================

if __name__ == '__main__':

    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )