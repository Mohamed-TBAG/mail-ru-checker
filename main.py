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
                self.state = AppState.RUNNING
                self.stop_event.clear()
                self.telegram.bot.send_message(chat_id, f"Target '{self.target}' accepted. Starting job...")
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
            f"----------------------\n"
            f"🔍 Scanned: {self.stats['scanned']}\n"
            f"✅ Available: {self.stats['available']}\n"
            f"❌ Taken: {self.stats['taken']}\n"
            f"⚠️ Non-MailRu: {self.stats['non_mailru']}\n"
            f"🔒 Pvt/No Email: {self.stats['private_no_email']}\n"
            f"⚠️ API Errors: {self.stats['errors']}")
    def process_job(self, chat_id):
        self.stats = {k: 0 for k in self.stats}
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
        next_max_id = None
        while not self.stop_event.is_set():
            users = []
            try:
                if mode == "HASHTAG":
                    users, next_max_id, rank_token = self.api.get_hashtag_posts(self.target, next_max_id)
                else:
                    users, next_max_id = self.api.get_user_followers(target_id, next_max_id)
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
            msg = f"✅ **FOUND AVAILABLE**\nUser: @{username}\nEmail: `{email}`\nLink: https://instagram.com/{username}"
            self.telegram.bot.send_message(chat_id, msg)
            logging.info(f"FOUND: {email} (@{username})")
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
    print("Checking license...")
    try:
        PASTEBIN_URL = "https://gist.githubusercontent.com/Mohamed-TBAG/a50872f06daf27bdbd324bb72205c8a4/raw/24c3d6d1f48a8d56c4d34e001d191fe7b96a222f/gistfile1.txt"      
        response = requests.get(PASTEBIN_URL, timeout=15)
        if response.status_code == 200:
            if "mohamedoscar" in response.text:
                print("License Verified! ✅")
                return True
            else:
                print("License Invalid or Expired.")
                return False
    except Exception as e:
        print(f"License check failed: {e}")
    return False
if __name__ == "__main__":
    if check_license():
        app = MainApp()
        print("Bot is polling...")
        try:
            app.telegram.bot.infinity_polling()
        except KeyboardInterrupt:
            app.stop_event.set()
            print("Stopped.")
    else:
        print("\n❌ License Invalid or Expired.")
        print("Please contact the developer to activate this software.")
        input("\nPress Enter to exit...")