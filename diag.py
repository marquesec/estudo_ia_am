# testekey.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": os.environ["GOOGLE_API_KEY"]},
)
print(r.status_code)
print(r.text[:300])