import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_create_media():
    ig_id = os.getenv("IG_BUSINESS_ID")
    token = os.getenv("IG_ACCESS_TOKEN")

    # URL provided by the user
    image_url = "https://magnific1.ddns.net/keepcalm_101_1777152485_d9bd3f43.png"
    caption = "Spring is a reminder to look closer.\nSometimes your life is already improving—you just need a gentler pace to see it.\n\nWhen you’re overwhelmed, your brain only scans for problems.\nPractice shifting attention: what’s stable, kind, and steadily showing up?\n\nToday, do a 3-line gratitude check:\n1) One small good thing.\n2) One thing I handled well.\n3) One resource I can lean on again tomorrow.\n#keepcalmnbepositive"

    url = f"https://graph.instagram.com/v20.0/{ig_id}/media"

    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }

    print(f"Testing URL: {url}")
    print(f"Image URL: {image_url}")

    resp = requests.post(url, params=params)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Body: {resp.text}")

if __name__ == "__main__":
    test_create_media()
