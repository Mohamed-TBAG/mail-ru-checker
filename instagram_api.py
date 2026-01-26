import requests
import json
import random
import re
import time
import logging
from urllib.parse import quote
logging.basicConfig(
    filename='app.log', 
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s: %(message)s')
class InstagramAPI:
    def __init__(self, session_id):
        self.session = requests.Session()
        self.session_id = session_id
        self.headers = {
            "Host": "www.instagram.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Ig-App-Id": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        self.session.cookies.set("sessionid", self.session_id, domain=".instagram.com")
        self.session.cookies.set("ds_user_id", requests.utils.unquote(self.session_id).split(":")[0], domain=".instagram.com")
        self.update_csrf_token()
    def update_csrf_token(self):
        try:
            r = self.session.get("https://www.instagram.com/", headers=self.headers, timeout=10)
            token = r.cookies.get("csrftoken") or "missing"
            self.session.cookies.set("csrftoken", token, domain=".instagram.com")
            self.headers["X-Csrftoken"] = token
        except Exception as e:
            logging.error(f"Warning: Could not fetch CSRF token: {e}")
    def _check_response(self, response):
        if response.status_code == 403:
            logging.error(f"CRITICAL: 403 Forbidden. Invalid Session ID or Login Required for {response.url}")
        elif response.status_code == 429:
            logging.error(f"CRITICAL: 429 Too Many Requests. Pausing for 60 seconds...")
            time.sleep(60)
        return response
    def get_hashtag_posts(self, hashtag, max_id=None, rank_token=None):
        hashtag = hashtag.replace("#", "")
        encoded_query = quote(f"#{hashtag}")
        url = f"https://www.instagram.com/api/v1/fbsearch/web/top_serp/?enable_metadata=true&query={encoded_query}"
        if max_id:
            url += f"&next_max_id={max_id}"
        if rank_token:
            url += f"&rank_token={rank_token}"        
        if not max_id and not rank_token:
            import uuid
            url += f"&search_session_id={str(uuid.uuid4())}"
        try:
            logging.info(f"Requesting Hashtag: #{hashtag} | MaxID: {str(max_id)[:20]}")
            response = self.session.get(url, headers=self.headers, timeout=10)
            self._check_response(response)
            if response.status_code == 200:
                data = response.json()
                users = []
                if "media_grid" in data and "sections" in data["media_grid"]:
                    for section in data["media_grid"]["sections"]:
                        if "layout_content" in section and "medias" in section["layout_content"]:
                            for item in section["layout_content"]["medias"]:
                                if "media" in item and "user" in item["media"]:
                                    user_obj = item["media"]["user"]
                                    if user_obj.get("is_private") == True:
                                        continue   
                                    users.append({"id": user_obj.get("pk") or user_obj.get("id"),"username": user_obj.get("username")})
                
                logging.info(f"Hashtag #{hashtag} Scraped: Found {len(users)} users in this batch.")
                media_grid = data.get("media_grid")
                if media_grid:
                    next_max_id = media_grid.get("next_max_id")
                    rank_token = media_grid.get("rank_token")
                if not next_max_id and "page_info" in data:
                    next_max_id = data.get("page_info", {}).get("end_cursor")
                return users, next_max_id, rank_token
            else:
                logging.error(f"Hashtag Error: {response.status_code} - {response.text[:100]}")
                return [], None, None
        except Exception as e:
            logging.error(response.text[:200])
            logging.error(f"Hashtag Exception: {e}")
            return [], None, None
    def get_user_followers(self, user_id, max_id=None):
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/followers/?count=12&search_surface=follow_list_page"
        if max_id:
            url += f"&max_id={max_id}"
        try:
            logging.info(f"Requesting Followers: {user_id} | MaxID: {max_id[:20] if max_id else 'None'}")
            response = self.session.get(url, headers=self.headers, timeout=10)
            self._check_response(response)
            if response.status_code == 200:
                data = response.json()
                users = []
                if "users" in data:
                    logging.debug(f"DEBUG: users found: {len(data['users'])}")
                    for user_obj in data["users"]:
                        if user_obj.get("is_private") == True:
                            continue
                        users.append({"id": user_obj.get("pk") or user_obj.get("id"),"username": user_obj.get("username")})
                logging.info(f"Followers Scraped: Found {len(users)} users in this batch.")
                next_max_id = data.get("next_max_id")
                if next_max_id == "":
                    next_max_id = None
                if not next_max_id:
                    logging.warning(f"DEBUG: No next_max_id found. Keys: {list(data.keys())}")
                if next_max_id:
                    logging.info(f"DEBUG: next_max_id found: {str(next_max_id)[:20]}")
                else:
                    logging.warning(f"DEBUG: next_max_id NONE found: {next_max_id}")
                return users, next_max_id
            else:
                logging.error(f"Followers Error: {response.status_code} - {response.text[:100]}")
                return [], None
        except Exception as e:
            logging.error(response.status_code,"\n",response.text[:100])
            logging.error(f"Followers Exception: {e}")
            return [], None
    def get_user_info(self, user_id):
        use_stream = True
        email = None
        error = None
        if use_stream:
            use_stream = not use_stream
            email, error = self._get_info_stream(user_id)
        else:
            use_stream = not use_stream
            email, error = self._get_info_standard(user_id)
        return email, error
    def _get_info_standard(self, user_id):
        url = f"https://www.instagram.com/api/v1/users/{user_id}/info/"
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            self._check_response(response)
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as e:
                    logging.error(f"JSON ERROR at standard")
                    try:
                        with open("error_resp.txt", "w", encoding="utf-8") as f:
                            f.write(response.text)
                    except: pass
                    raise e
                if "user" in data:
                    return data["user"].get("public_email"), None
            return None, f"Status {response.status_code}: {response.text[:200]}"
        except Exception as e:
             return None, str(e)
    def _get_info_stream(self, user_id):
        url = f"https://www.instagram.com/api/v1/users/{user_id}/info_stream/"
        try:
            response = self.session.post(url, headers=self.headers, timeout=10)
            self._check_response(response)
            if response.status_code == 200:
                text = response.text                
                match = re.search(r'"public_email"\s*:\s*"([^"]+)"', text)
                if match:
                    email = match.group(1)
                    return email, None
                if re.search(r'"is_business"\s*:\s*(true|false)', text):
                    return None, None
                else:
                    try:
                        with open("error_resp.txt", "w", encoding="utf-8") as f:
                            f.write(text)
                    except: pass
                    return None, "RESPONSE NOT JSON"
            return None, f"Status {response.status_code}: {response.text[:200]}"
        except Exception as e:
            return None, str(e)
    def resolve_username(self, username):
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        try:
            headers = self.headers.copy()
            headers["Referer"] = f"https://www.instagram.com/{username}/"
            response = self.session.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("user", {}).get("id")
        except:
            pass
        return None

    def send_password_reset(self, username):
        url = "https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/"
        data = {
            "email_or_username": username,
            "flow": "fxcal"
        }
        try:
            response = self.session.post(url, headers=self.headers, data=data, timeout=10)
            
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    if resp_json.get("status") == "ok":
                         return f"Reset Sent: {resp_json.get('message')}"
                    else:
                         return f"Reset Fail: {response.text[:30]}"
                except:
                     return f"Reset Fail (Parse): {response.text[:30]}"
            else:
                return f"Reset Error {response.status_code}: {response.text[:30]}"
        except Exception as e:
            return f"Reset Exception: {str(e)[:30]}"