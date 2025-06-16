import snscrape.modules.twitter as sntwitter
import requests
from datetime import datetime
import urllib3

# Disable warnings about insecure requests (optional)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_job_tweets(limit=50):
    query = "#hiring OR #remotejobs OR #techjobs lang:en"
    tweets = sntwitter.TwitterSearchScraper(query).get_items()
    
    results = []
    for i, tweet in enumerate(tweets):
        if i >= limit:
            break
        results.append({
            "tweet_id": tweet.id,
            "user_id": tweet.user.username,
            "text": tweet.content,
            "created_at": tweet.date.isoformat(),
            "tweet_link": f"https://twitter.com/{tweet.user.username}/status/{tweet.id}"
        })
    return results

def post_to_backend(data):
    for job in data:
        try:
            print(f"Posting tweet {job['tweet_id']} to backend...")
            response = requests.post(
                "http://your-api/jobs",  # Replace with your actual backend URL
                json=job,
                verify=False  # Disable SSL verification here
            )
            response.raise_for_status()
            print(f"✅ Successfully posted tweet {job['tweet_id']}")
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL error while posting tweet {job['tweet_id']}: {ssl_err}")
        except requests.exceptions.RequestException as req_err:
            print(f"❌ Request error while posting tweet {job['tweet_id']}: {req_err}")

if __name__ == "__main__":
    jobs = fetch_job_tweets()
    post_to_backend(jobs)
