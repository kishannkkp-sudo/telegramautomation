# main.py - Telegram Job Poster (FirstJobTech)
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
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

# Configuration
BLOG_FEED_URL = 'https://www.firstjobtech.in/feeds/posts/default?alt=json'
POSTED_JOBS_FILE = 'posted_jobs.txt'

# Secrets
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
# Helper: Check if job is from today
# ========================================
def is_today(date_str):
    try:
        if 'T' in date_str:
            date_part = date_str.split('T')[0]
            job_date = datetime.strptime(date_part, '%Y-%m-%d').date()
            return job_date == date.today()
        return False
    except Exception as e:
        print(f"Date parsing error: {e}")
        return False

# ========================================
# Helper: Extract Logo & Company
# ========================================
def extract_job_metadata(entry):
    title_text = entry.get('title', {}).get('$t', '')
    content_html = entry.get('content', {}).get('$t', '')

    company_name = "Company"
    if " - " in title_text:
        parts = title_text.split(" - ")
        if len(parts) > 1:
            raw_company = parts[1]
            clean_company = re.sub(r'(Recruitment|Hiring|Off Campus|Job|Careers).*', '', raw_company, flags=re.IGNORECASE).strip()
            if clean_company:
                company_name = clean_company
    
    logo_url = None
    img_match = re.search(r'<img[^>]+src="([^">]+)"', content_html)
    if img_match:
        logo_url = img_match.group(1)

    return company_name, logo_url

# ========================================
# Image: Create job poster
# ========================================
def create_job_image(job, image_path):
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor('white')
        ax.set_xlim(0, 8)
        ax.set_ylim(0, 6)
        ax.axis('off')

        title = job.get('title', '')
        company = job.get('company_name', 'Company')

        from textwrap import fill
        wrapped_title = fill(title, width=30)
        
        ax.text(4, 5.2, wrapped_title, ha='center', va='center', fontsize=14, fontweight='bold', color='#1a1a1a', wrap=True)
        ax.text(4, 4.5, f"at {company}", ha='center', va='center', fontsize=12, color='#555555', wrap=True)

        # Logo rendering (Fixed logic)
        logo_url = job.get('company_logo')
        if logo_url:
            try:
                resp = requests.get(logo_url, timeout=10)
                if resp.status_code == 200:
                    image_data = io.BytesIO(resp.content)
                    img = mpimg.imread(image_data, format='jpg')
                    h, w = img.shape[:2]
                    max_dim = 2.5
                    scale = max_dim / max(w, h)
                    aspect = w / h
                    disp_h = 2.0
                    disp_w = disp_h * aspect
                    if disp_w > 5:
                        disp_w = 5
                        disp_h = disp_w / aspect
                    ax.imshow(img, extent=[4 - disp_w/2, 4 + disp_w/2, 2.5 - disp_h/2, 2.5 + disp_h/2], zorder=2)
            except Exception as e:
                print(f"Logo render warning: {e}")

        ax.text(4, 0.9, "New Opportunity! Apply Now", ha='center', va='center', fontsize=11, style='italic', color='#1a1a1a')
        ax.text(4, 0.5, "www.firstjobtech.in", ha='center', va='center', fontsize=10, color='#0066cc', style='italic')

        plt.savefig(image_path, bbox_inches='tight', pad_inches=0.3, dpi=150, facecolor='white')
        plt.close(fig)
        print(f"Image created: {image_path}")
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

    url_photo = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    url_text = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        # Try posting with image
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
                files = {'photo': photo}
                resp = requests.post(url_photo, data=payload, files=files, timeout=20)
                
                if resp.status_code == 200:
                    print(f"✅ Posted photo to Telegram!")
                    return True
                else:
                    print(f"Photo upload failed ({resp.status_code}): {resp.text}")
                    # Fallback will happen below if we return False? 
                    # Actually let's fallback immediately.

        # Fallback to Text Only
        print("ℹ️ Posting text only...")
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': caption, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
        resp = requests.post(url_text, data=payload, timeout=20)
        
        if resp.status_code == 200:
            print(f"✅ Posted text using Telegram!")
            return True
        else:
            print(f"❌ Telegram Text Post Failed ({resp.status_code}): {resp.text}")
            return False

    except Exception as e:
        print(f"❌ Telegram API Exception: {e}")
        return False

# ========================================
# Fetch & Main
# ========================================
def format_caption(job):
    title = job['title']
    company = job['company_name']
    url = job['url']
    
    # HTML formatting for Telegram
    caption = (
        f"<b>🚀 New Job Alert: {title}</b>\n\n"
        f"🏢 <b>Company:</b> {company}\n\n"
        f"🔗 <b>Apply Here:</b> <a href='{url}'>Click to Apply</a>\n\n"
        f"<i>More jobs at firstjobtech.in</i>\n\n"
        f"#JobOpening #Hiring #Careers #{company.replace(' ', '')}"
    )
    return caption

def fetch_today_jobs():
    try:
        print(f"Fetching from: {BLOG_FEED_URL}")
        response = requests.get(BLOG_FEED_URL, timeout=15)
        if response.status_code != 200:
            return []
        
        data = response.json()
        entries = data.get('feed', {}).get('entry', [])
        today_jobs = []
        
        for entry in entries:
            raw_id = entry.get('id', {}).get('$t', '')
            job_id = raw_id.split('-')[-1] 
            published = entry.get('published', {}).get('$t', '')
            
            if is_today(published):
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
                
        print(f"Found {len(today_jobs)} jobs published TODAY.")
        return today_jobs
    except Exception as e:
        print(f"Fetch error: {e}")
        return []

def main():
    print("AI Telegram Job Poster (FirstJobTech)")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Missing TELEGRAM_BOT_TOKEN in .env")
        return

    posted_jobs = load_posted_jobs()
    today_jobs = fetch_today_jobs()

    if not today_jobs:
        print("No jobs found for today.")
        return

    success_count = 0
    first_post_done = False

    for job in today_jobs:
        job_id = str(job['id'])
        if job_id in posted_jobs:
            continue

        if first_post_done:
            print("Waiting 5 minutes before next post...")
            time.sleep(300)

        print(f"\nPosting Job: {job['title']}")
        caption = format_caption(job)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image_path = tmp.name
        
        create_job_image(job, image_path)

        if post_to_telegram(caption, image_path):
            save_posted_job(job_id)
            success_count += 1
            first_post_done = True
        
        try:
            os.unlink(image_path)
        except:
            pass

    print(f"\nBatch completed. Posted {success_count} jobs.")

if __name__ == "__main__":
    main()
