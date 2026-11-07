import time

import requests


def fetch_user(session, user_id, max_retries=3):
    retry_count = 0
    while True:
        try:
            response = session.get(f"/users/{user_id}", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            retry_count += 1
            if retry_count >= max_retries:
                raise
            time.sleep(2**retry_count)
