# main.py - Telegram Job Poster (FirstJobTech) [IST SAFE]

import time
import requests
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import io
import tempfile
import os
from datetime import datetime
from dotenv import load_dotenv
import pytz

load_dotenv()

# ========================================
# CONFIG
# ========================================
BLOG_FEED_URL = 'https://www.firstjobtech.in/feeds/posts/default?alt=json'
POSTED_JOBS_FILE = 'posted_jobs.txt'
IST = pytz.timezone("Asia/Kolkata")

# Telegram Secrets
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ========================================
# Helper: Track posted jobs
# ========================================
def load_posted_jobs():
    if not os.path.exists(POSTED_JOBS_FILE):
        return set()
    with open(POSTED_JOBS_FILE, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def save_posted_job(job_id):
    with open(POSTED_JOBS_FILE, 'a') as f:
        f.write(f"{job_id}\n")

# ========================================
# Helper: Check if Blogger post is TODAY (IST)
# ========================================
def is_today(date_str):
    try:
        # Example: 2026-02-03T23:55:53.238-08:00
        dt = datetime.fromisoformat(date_str)
        dt_ist = dt.astimezone(IST)
        return dt_ist.date() == datetime.now(IST).date()
    except Exception as e:
        print(f"Date parsing error: {date_str} -> {e}")
        return False

# ========================================
# Helper: Extract Company & Logo
# ========================================
def extract_job_metadata(entry):
    title_text = entry.get('title', {}).get('$t', '')
    content_html = entry.get('content', {}).get('$t', '')

    company_name = "Company"
    if " - " in title_text:
        parts = title_text.split(" - ")
        if len(parts) > 1:
            raw_company = parts[1]
            clean_company = re.sub(
                r'(Recruitment|Hiring|Off Campus|Job|Careers).*',
                '',
                raw_company,
                flags=re.IGNORECASE
            ).strip()
            if clean_company:
                company_name = clean_company

    logo_url = None
    img_match = re.search(r'<img[^>]+src="([^">]+)"', content_html)
    if img_match:
        logo_url = img_match.group(1)

    return company_name, logo_url

# ========================================
# Image Generator
# ========================================
def create_job_image(job, image_path):
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor('white')
        ax.axis('off')

        from textwrap import fill
        title = fill(job['title'], width=30)
        company = job['company_name']

        ax.text(0.5, 0.85, title, ha='center', va='center',
                fontsize=14, fontweight='bold', transform=ax.transAxes)
        ax.text(0.5, 0.75, f"at {company}", ha='center',
                fontsize=12, transform=ax.transAxes)

        logo_url = job.get('company_logo')
        if logo_url:
            try:
                resp = requests.get(logo_url, timeout=10)
                if resp.status_code == 200:
                    img = mpimg.imread(io.BytesIO(resp.content))
                    ax.imshow(img, extent=[0.25, 0.75, 0.25, 0.55])
            except Exception as e:
                print(f"Logo render warning: {e}")

        ax.text(0.5, 0.15, "Apply Now", ha='center',
                fontsize=11, style='italic', transform=ax.transAxes)
        ax.text(0.5, 0.08, "www.firstjobtech.in", ha='center',
                fontsize=10, color='#0066cc', transform=ax.transAxes)

        plt.savefig(image_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return True
    except Exception as e:
        print(f"Image creation failed: {e}")
        return False

# ========================================
# Telegram Poster
# ========================================
def post_to_telegram(caption, image_path=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials.")
        return False

    photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    text_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                payload = {
                    'chat_id': TELEGRAM_CHAT_ID,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }
                resp = requests.post(photo_url, data=payload, files={'photo': photo}, timeout=20)
                if resp.status_code == 200:
                    print("✅ Posted photo to Telegram")
                    return True

        # Fallback: Text only
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': caption,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        resp = requests.post(text_url, data=payload, timeout=20)
        if resp.status_code == 200:
            print("✅ Posted text to Telegram")
            return True

        print(f"❌ Telegram error: {resp.text}")
        return False

    except Exception as e:
        print(f"❌ Telegram API Exception: {e}")
        return False

# ========================================
# Caption Formatter
# ========================================
def format_caption(job):
    company_tag = job['company_name'].replace(' ', '')
    return (
        f"<b>🚀 New Job Alert: {job['title']}</b>\n\n"
        f"🏢 <b>Company:</b> {job['company_name']}\n\n"
        f"🔗 <b>Apply Here:</b> <a href='{job['url']}'>Click to Apply</a>\n\n"
        f"<i>More jobs at firstjobtech.in</i>\n\n"
        f"#Hiring #Jobs #{company_tag} #Careers"
    )

# ========================================
# Fetch TODAY jobs only (IST)
# ========================================
def fetch_today_jobs():
    print(f"Fetching Blogger feed: {BLOG_FEED_URL}")
    response = requests.get(BLOG_FEED_URL, timeout=15)

    if response.status_code != 200:
        print("Feed fetch failed")
        return []

    data = response.json()
    entries = data.get('feed', {}).get('entry', [])
    today_jobs = []

    for entry in entries:
        published = entry.get('published', {}).get('$t', '')
        if not is_today(published):
            continue

        raw_id = entry.get('id', {}).get('$t', '')
        job_id = raw_id.split('-')[-1]

        title = entry.get('title', {}).get('$t', 'Job Opening')
        link_url = next((l.get('href') for l in entry.get('link', []) if l.get('rel') == 'alternate'), "")
        company_name, logo_url = extract_job_metadata(entry)

        today_jobs.append({
            'id': job_id,
            'title': title,
            'company_name': company_name,
            'company_logo': logo_url,
            'url': link_url,
            'published': published
        })

        print(f"✓ Today job found: {title}")

    print(f"Total jobs TODAY (IST): {len(today_jobs)}")
    return today_jobs

# ========================================
# MAIN
# ========================================
def main():
    print("AI Telegram Job Poster (FirstJobTech)")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN missing")
        return

    posted_jobs = load_posted_jobs()
    today_jobs = fetch_today_jobs()

    if not today_jobs:
        print("No jobs found for today.")
        return

    first_post = True
    success = 0

    for job in today_jobs:
        if job['id'] in posted_jobs:
            continue

        if not first_post:
            print("Waiting 5 minutes before next post...")
            time.sleep(300)

        caption = format_caption(job)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image_path = tmp.name

        create_job_image(job, image_path)

        if post_to_telegram(caption, image_path):
            save_posted_job(job['id'])
            success += 1
            first_post = False

        try:
            os.unlink(image_path)
        except:
            pass

    print(f"\nBatch completed. Posted {success} jobs.")

if __name__ == "__main__":
    main()
