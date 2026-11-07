import requests


def fetch_user(session, user_id):
    response = session.get(f"/users/{user_id}")
    return response.json()
