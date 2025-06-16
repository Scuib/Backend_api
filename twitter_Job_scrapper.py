import snscrape.modules.twitter as sntwitter
import requests
from datetime import datetime

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
        requests.post("http://your-api/jobs", json=job)#Add the correct URL for your backend API
        # print(f"Posted job tweet {job['tweet_id']} to backend.") #uncomment this to see what's being posted

if __name__ == "__main__":
    jobs = fetch_job_tweets()
    post_to_backend(jobs)
