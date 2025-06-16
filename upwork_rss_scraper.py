import feedparser
import requests
import sqlite3
import os

# Database setup
DB_FILE = "upwork_jobs.db"
TABLE_NAME = "jobs"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            title TEXT,
            description TEXT,
            published TEXT,
            category TEXT,
            source TEXT
        )
    """)
    conn.commit()
    conn.close()

def job_exists(link):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"SELECT 1 FROM {TABLE_NAME} WHERE link=?", (link,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_to_db(job):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT OR IGNORE INTO {TABLE_NAME} (link, title, description, published, category, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        job["link"],
        job["title"],
        job["description"],
        job["published"],
        job["category"],
        job["source"]
    ))
    conn.commit()
    conn.close()

def fetch_upwork_jobs(query, limit=50, keyword_filters=None):
    rss_url = f"https://www.upwork.com/ab/feed/jobs/rss?q={query}&sort=recency"
    feed = feedparser.parse(rss_url)

    results = []
    for entry in feed.entries[:limit]:
        title = entry.title
        description = entry.summary
        link = entry.link

        # Filter: Must contain a keyword in title or description
        if keyword_filters:
            if not any(keyword.lower() in (title + description).lower() for keyword in keyword_filters):
                continue

        # Deduplication: Skip if already in DB
        if job_exists(link):
            continue

        job = {
            "title": title,
            "link": link,
            "description": description,
            "published": entry.published,
            "source": "Upwork",
            "category": query
        }

        results.append(job)
    return results

def post_to_backend(data):
    for job in data:
        try:
            requests.post("http://your-api/jobs", json=job)
        except Exception as e:
            print(f"Error posting job: {e}")

if __name__ == "__main__":
    init_db()

    tech_queries = [
        "python",
        "machine learning",
        "data science",
        "web development",
        "frontend developer",
        "backend developer",
        "mobile app development",
        "devops",
        "ui ux design",
        "cloud computing"
    ]

    # Optional: Use these to filter job relevance (add your own keywords)
    keyword_filters = ["django", "react", "api", "flask", "aws", "tensorflow", "fastapi"]

    all_jobs = []
    for query in tech_queries:
        jobs = fetch_upwork_jobs(query=query, limit=50, keyword_filters=keyword_filters)
        for job in jobs:
            save_to_db(job)
        all_jobs.extend(jobs)

    post_to_backend(all_jobs)
