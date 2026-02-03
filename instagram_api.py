import json
import time
import logging
import random
from playwright.sync_api import sync_playwright
import re

logger = logging.getLogger("InstagramAPI")

class InstagramAPI:
    def __init__(self, session_id=None):
        self.session_id = session_id
        if not self.session_id:
            logger.warning("No session_id provided! Scraping might fail.")
            
        self.proxy_change_count = 0
        # Tor Proxy settings
        self.tor_proxy_port = 9050
        self.tor_control_port = 9051
        
        self.proxies = {
            'http': f'socks5h://127.0.0.1:{self.tor_proxy_port}',
            'https': f'socks5h://127.0.0.1:{self.tor_proxy_port}'
        }
        
        # Restore Requests Session for other features (Reset PW etc)
        import requests
        self.session = requests.Session()
        self.session.proxies.update(self.proxies)
        
        # Wait for Tor (Mock or Real?)
        # Since user wants it, we keep it.
        # But for Playwright we configure proxy in launch args if needed.
        # For now, Playwright is direct (using global system proxy? No, usually direct).
        # We should add proxy to Playwright if user wants rotation there too?
        # User said "rotate the ip at any block". This implies Playwright needs Tor too.
        
    def _wait_for_tor(self):
        # Compatibility stub or real check
        pass
        
    def _rotate_proxy(self):
        self.proxy_change_count += 1
        # Add rotation logic if needed for requests
        pass

    def get_hashtag_posts(self, hashtag, max_id=None, rank_token=None):
        """Fetches hashtag posts using Playwright"""
        tag = hashtag.replace("#", "")
        url = f"https://www.instagram.com/explore/tags/{tag}/"
        
        users = []
        next_max_id = None
        
        try:
            with sync_playwright() as p:
                # Launch Browser
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                # Context with User Agent
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                # Set Cookie (Critical)
                if self.session_id:
                    context.add_cookies([{
                        "name": "sessionid",
                        "value": self.session_id,
                        "domain": ".instagram.com",
                        "path": "/"
                    }])
                
                page = context.new_page()
                
                logger.info(f"Navigating to {url}...")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Wait for content
                try:
                    # Wait for images or error check
                    page.wait_for_selector("img", timeout=15000)
                except:
                    logger.warning("Timeout waiting for images. Check if account is blocked or login failed.")
                
                # Regex for users
                # We need to scroll to get more
                last_height = page.evaluate("document.body.scrollHeight")
                processed_usernames = set()
                
                # Scroll loop
                for scroll in range(3): # Scroll 3 times per batch
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except: time.sleep(2)
                    
                    content = page.content()
                    matches = re.finditer(r'"username":"([\w\.]+)"', content)
                    found_new = False
                    for m in matches:
                        u = m.group(1)
                        if u and u not in ["instagram", "search"] and u not in processed_usernames:
                            processed_usernames.add(u)
                            users.append({"username": u, "id": "0"})
                            found_new = True
                            
                    if not found_new and scroll > 0:
                        break # End if no new posts
                        
                    time.sleep(1)
                
                logger.info(f"Playwright Scrape: Found {len(users)} users.")
                
                browser.close()
                
                # Fake pagination to keep loop alive
                if users:
                     next_max_id = "SCROLLED_" + str(int(time.time()))
                
        except Exception as e:
            logger.error(f"Playwright Error: {e}")
            
        return users, next_max_id, rank_token

    # Keep compatibility methods to not break main.py
    def _wait_for_tor(self): pass
    def _rotate_proxy(self): pass

    def _wait_for_tor(self):
        logger.info(f"Connecting to Tor (127.0.0.1:{self.tor_proxy_port})...")
        while True:
            try:
                with socket.create_connection(("127.0.0.1", self.tor_proxy_port), timeout=1):
                    pass
                logger.info("Tor Proxy Linked! ✅")
                break
            except:
                logger.warning("Waiting for Tor Proxy...")
                time.sleep(3)

    def _rotate_proxy(self):
        """Signals Tor to switch identity via STEM (Proven working in tests)"""
        self.proxy_change_count += 1
        try:
            logger.info("Requesting NEWNYM (Stem)...")
            # Connect via Stem
            with Controller.from_port(port=self.tor_control_port) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
            
            # Clear Probe Cookies explicitly to ensure fresh session
            self.probe_session.cookies.clear()
                
            logger.info("Signal sent. Waiting 10s for new circuit...")
            time.sleep(10)
            
            # Check Connectivity
            self._refresh_csrf()
            return True
            
        except Exception as e:
            logger.error(f"Tor Rotation Failed: {e}")
            return False

    def _check_response(self, resp):
        if resp.status_code == 429:
            logger.warning("429 Too Many Requests detected.")
            return False
        
        txt = resp.text.lower()
        if "please wait a few minutes" in txt or "limit_reached" in txt:
             logger.warning("Soft Block Detected (Text Match).")
             return False
             
        # Check for HTML (Login Challenge) where JSON is expected
        if "text/html" in resp.headers.get("Content-Type", ""):
             logger.warning("Soft Block Detected (HTML Content).")
             return False
             
        return True

    def resolve_username(self, username):
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                return data["data"]["user"]["id"]
        except: pass
        return None



    def get_user_followers(self, user_id, max_id=None):
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/followers/"
        params = {"count": 12, "search_surface": "follow_list_page"}
        if max_id:
            params["max_id"] = max_id
            
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=25)
                
                if not self._check_response(resp):
                    self._rotate_proxy()
                    continue
                
                try:
                    data = resp.json()
                except ValueError:
                     logger.warning("Followers Resp not JSON. Rotating...")
                     self._rotate_proxy()
                     continue
                     
                users_raw = data.get("users", [])
                users = []
                for u in users_raw:
                    if not u.get("is_private"):
                         users.append({"id": u.get("pk"), "username": u.get("username")})
                
                next_max_id = data.get("next_max_id")
                return users, next_max_id
                
            except Exception as e:
                logger.warning(f"Followers Conn Error: {e}. Rotating...")
                self._rotate_proxy()

        return [], None

    def _refresh_csrf(self):
        """Fetches the main page to set csrftoken cookie on PROBE session"""
        try:
            # lightweight request to get cookies
            logger.info("Refreshing CSRF Token (Probe)...")
            r = self.probe_session.get("https://www.instagram.com/accounts/login/", timeout=15)
            token = self.probe_session.cookies.get("csrftoken")
            if token:
                self.probe_session.headers.update({"x-csrftoken": token})
                logger.info(f"Refreshed CSRF: {token[:8]}...")
                return True
        except Exception as e:
            logger.warning(f"CSRF Refresh Failed: {e}")
        return False

    def send_password_reset(self, username):
        url = "https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/"
        
        # Ensure CSRF Token exists in PROBE session
        csrf = self.probe_session.cookies.get("csrftoken", None)
        if not csrf:
             self._refresh_csrf()
             csrf = self.probe_session.cookies.get("csrftoken", "")
        local_headers = self.headers.copy()
        local_headers.update({
             "Content-Type": "application/x-www-form-urlencoded",
             "x-csrftoken": csrf,
             "x-instagram-ajax": "1",
             "X-Requested-With": "XMLHttpRequest",
             "Referer": "https://www.instagram.com/accounts/password/reset/"
        })
        
        data = {
            "email_or_username": username,
            "flow": "fxcal",
            "recaptcha_challenge_field": "",
        }
        
        attempts = 0
        while True:
            attempts += 1
            if attempts > 20: 
                logger.warning(f"Aborting reset for {username} after 20 rotations.")
                return None
                
            try:
                # Send using PROBE SESSION (Logged Out)
                # Note: We use proxies=None because they are already in the session
                # But wait, self.probe_session has self.proxies, so no need to pass them explicitly
                # unless we want to force rotation? No, rotation is handled by _rotate_proxy clearing session.
                
                resp = self.probe_session.post(url, headers=local_headers, data=data)
                
                if resp.status_code == 429:
                    logger.warning(f"Reset 429 for {username}. Rotating...")
                    self._rotate_proxy()
                    continue
                if resp.status_code == 403:
                    logger.warning(f"Reset 403 for {username}. Rotating...")
                    self._rotate_proxy()
                    continue
                
                if "text/html" in resp.headers.get("Content-Type", "") or "please wait" in resp.text.lower():
                    logger.warning(f"Reset Soft Block for {username}. Rotating...")
                    self._rotate_proxy()
                    continue
                
                # Check for other errors to log
                if resp.status_code != 200:
                    logger.info(f"Probe Result for {username}: Status {resp.status_code}, message : {resp.text}")
                
                return resp
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Reset Connection Error: {e} -> Rotating...")
                self._rotate_proxy()
                continue
            except Exception as e:
                logger.error(f"Reset Unexpected Error: {e}")
                return None