# main.py - Updated for X.com: Post ALL Today's Jobs (Stateful) with IST Timezone Fix
import sys
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
import pytz # Added for Timezone handling
from dotenv import load_dotenv
from x_posters import post_to_x

load_dotenv()

# Blogger JSON Feed
BLOG_FEED_URL = 'https://www.firstjobtech.in/feeds/posts/default?alt=json'
POSTED_JOBS_FILE = 'posted_jobs.txt'

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
# Helper: Check if job is from today (IST Aware)
# ========================================
def is_today(date_str):
    """
    Checks if the job was published TODAY in IST (Indian Standard Time).
    Blogger returns timestamps in PST/PDT (-08:00 or -07:00).
    We must parse that, convert to IST, and compare with IST Today.
    """
    try:
        if not date_str:
            return False
            
        # 1. Parse ISO date from Blogger (e.g., 2026-02-03T23:55:53.238-08:00)
        dt = datetime.fromisoformat(date_str)

        # 2. Convert to IST
        ist = pytz.timezone("Asia/Kolkata")
        dt_ist = dt.astimezone(ist)
        
        # 3. Get Today's Date in IST
        today_ist = datetime.now(ist).date()
        
        # 4. Compare just the dates
        return dt_ist.date() == today_ist
    except Exception as e:
        print(f"Date parsing error for '{date_str}': {e}")
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

    # Logo rendering restored just in case, but unused in text-only mode
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
                new_w, new_h = w * scale * (8/600), h * scale * (6/600)
                aspect = w / h
                disp_h = 2.0
                disp_w = disp_h * aspect
                if disp_w > 5:
                    disp_w = 5
                    disp_h = disp_w / aspect
                ax.imshow(img, extent=[4 - disp_w/2, 4 + disp_w/2, 2.5 - disp_h/2, 2.5 + disp_h/2], zorder=2)
        except Exception as e:
            print(f"Logo display failed: {e}")

    ax.text(4, 0.9, "New Opportunity! Apply Now", ha='center', va='center', fontsize=11, style='italic', color='#1a1a1a')
    ax.text(4, 0.5, "www.firstjobtech.in", ha='center', va='center', fontsize=10, color='#0066cc', style='italic')

    plt.savefig(image_path, bbox_inches='tight', pad_inches=0.3, dpi=150, facecolor='white')
    plt.close(fig)
    print(f"Image created: {image_path}")

# ========================================
# Caption: Format X post
# ========================================
def format_caption(job):
    title = job['title']
    company = job['company_name']
    url = job['url']
    
    hashtags = f"#JobOpening #Hiring #Careers #{company.replace(' ', '')} #OffCampus".replace('##', '#')

    caption = (
        f"🚀 New Job Alert: {title}\n\n"
        f"🏢 {company}\n"
        f"🔗 Apply: {url}\n\n"
        f"{hashtags}"
    )
    if len(caption) > 280:
        caption = caption[:277] + "..."
    return caption

# ========================================
# Fetch: ALL TODAY'S JOBS
# ========================================
def fetch_today_jobs():
    try:
        print(f"Fetching from: {BLOG_FEED_URL}")
        # Fetching ALL jobs from Today (Stateful check later)
        response = requests.get(BLOG_FEED_URL, timeout=15)
        if response.status_code != 200:
            print(f"Blogger API error: {response.status_code}")
            return []
        
        data = response.json()
        entries = data.get('feed', {}).get('entry', [])
        
        today_jobs = []
        
        for entry in entries:
            raw_id = entry.get('id', {}).get('$t', '')
            job_id = raw_id.split('-')[-1] 
            
            published = entry.get('published', {}).get('$t', '')
            
            # Check if it was published TODAY
            if is_today(published):
                title = entry.get('title', {}).get('$t', 'Job Opening')
                
                link_url = ""
                for link in entry.get('link', []):
                    if link.get('rel') == 'alternate':
                        link_url = link.get('href')
                        break
                
                company_name, logo_url = extract_job_metadata(entry)
                
                job_obj = {
                    'id': job_id,
                    'title': title,
                    'company_name': company_name,
                    'company_logo': logo_url,
                    'url': link_url,
                    'published': published
                }
                
                today_jobs.append(job_obj)
                
        print(f"Found {len(today_jobs)} jobs published TODAY.")
        return today_jobs

    except Exception as e:
        print(f"Fetch error: {e}")
        return []

# ========================================
# Main: Post with delay & deduplication
# ========================================
def main():
    print("AI X.com (Twitter) Job Poster (Stateful - All Today - TEXT ONLY - IST Fix)")
    print("=" * 60)

    if not os.getenv('TWITTER_API_KEY'):
        print("ERROR: Missing Twitter credentials in .env")
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
            # print(f"Skipping duplicate: {job_id}")
            continue

        # Delay logic: Wait BEFORE posting if NOT the first
        if first_post_done:
            print("Waiting 5 minutes before next post...")
            time.sleep(300)

        print(f"\nPosting Job: {job['title']}")
        
        caption = format_caption(job)
        
        # --- IMAGE GENERATION SKIPPED FOR TEXT-ONLY POST ---
        # with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        #     image_path = tmp.name
        # create_job_image(job, image_path)
        
        # Pass image_path=None to force text-only tweet
        if post_to_x(caption, image_path=None):
            save_posted_job(job_id) # Save to file
            success_count += 1
            print(f"✅ Posted Successfully (Text Only)!")
            first_post_done = True
        else:
            print(f"❌ Failed to post.")

        # try:
        #     os.unlink(image_path)
        # except:
        #     pass

    print(f"\nBatch completed. Posted {success_count} new jobs today.")

if __name__ == "__main__":
    main()
