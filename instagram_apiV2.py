import requests
import json
import random
import re
import time
import logging
from urllib .parse import quote
from stem import Signal
from stem .control import Controller
import socket
logging .basicConfig (
filename ='avalibleity.log',
level =logging .INFO ,
format ='%(asctime)s %(levelname)s: %(message)s')
class InstagramAPI :
    def __init__ (self ,session_id ):
        self .session_id =session_id
        self .tor_proxy_port =9050
        self .tor_control_port =9051
        self .proxies ={'http':f'socks5h://127.0.0.1:{self .tor_proxy_port }','https':f'socks5h://127.0.0.1:{self .tor_proxy_port }'}
        self .session =requests .Session ()
        self .session .proxies .update (self .proxies )
        self .probe_session =requests .Session ()
        self .probe_session .proxies .update (self .proxies )
        self ._wait_for_tor ()
        self .headers ={
        "Host":"www.instagram.com",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept":"*/*",
        "Accept-Language":"en-US,en;q=0.9",
        "X-Ig-App-Id":"936619743392459",
        "X-Requested-With":"XMLHttpRequest",
        "Sec-Fetch-Site":"same-origin",
        "Sec-Fetch-Mode":"cors",
        "Sec-Fetch-Dest":"empty",}
        self .session .cookies .set ("sessionid",self .session_id ,domain =".instagram.com")
        if requests .utils .unquote (self .session_id ).split (":"):
             self .session .cookies .set ("ds_user_id",requests .utils .unquote (self .session_id ).split (":")[0 ],domain =".instagram.com")
        self .update_csrf_token ()
    def _wait_for_tor (self ):
        logging .info (f"Connecting to Tor (127.0.0.1:{self .tor_proxy_port })...")
        while True :
            try :
                with socket .create_connection (("127.0.0.1",self .tor_proxy_port ),timeout =1 ):
                    pass
                logging .info ("Tor Proxy Linked! ✅")
                break
            except :
                logging .warning ("Waiting for Tor Proxy...")
                time .sleep (3 )
    def _rotate_proxy (self ):
        try :
            logging .info ("Requesting New IP (Tor)...")
            try :
                import re
                import binascii
                with socket .socket (socket .AF_INET ,socket .SOCK_STREAM )as s :
                    s .settimeout (5 )
                    s .connect (("127.0.0.1",self .tor_control_port ))
                    s .sendall (b'PROTOCOLINFO 1\r\n')
                    resp =b""
                    while b"250 OK"not in resp :
                         chunk =s .recv (4096 )
                         if not chunk :break
                         resp +=chunk
                    resp_str =resp .decode ('utf-8',errors ='ignore')
                    cookie_path =None
                    if 'COOKIEFILE="'in resp_str :
                         match =re .search (r'COOKIEFILE="([^"]+)"',resp_str )
                         if match :
                             cookie_path =match .group (1 )
                             cookie_path =cookie_path .replace ("\\\\","\\")
                    if cookie_path :
                        try :
                            with open (cookie_path ,"rb")as f :
                                cookie_data =f .read ()
                            s .sendall (b'AUTHENTICATE '+binascii .hexlify (cookie_data )+b'\r\n')
                        except Exception as e :
                            logging .warning (f"Failed to read Tor Cookie: {e }. Trying empty auth.")
                            s .sendall (b'AUTHENTICATE ""\r\n')
                    else :
                        s .sendall (b'AUTHENTICATE ""\r\n')
                    resp =s .recv (1024 )
                    if b"250 OK"not in resp :
                        logging .warning (f"Tor Auth Failed (Raw): {resp }")
                    else :
                        s .sendall (b'SIGNAL NEWNYM\r\n')
                        resp =s .recv (1024 )
                        if b"250 OK"in resp :
                            logging .info ("Tor Signal Sent (Raw) ✅")
                        else :
                            logging .warning (f"Tor Signal Fail (Raw): {resp }")
            except Exception as e :
                logging .warning (f"Tor Signal Socket Error: {e }")
            time .sleep (10 )
            self .update_csrf_token ()
            self .probe_session .cookies .clear ()
            self ._refresh_probe_csrf ()
            return True
        except Exception as e :
            logging .error (f"Tor Rotation Critical: {e }")
            return False
    def update_csrf_token (self ):
        try :
            r =self .session .get ("https://www.instagram.com/",headers =self .headers ,timeout =10 )
            token =r .cookies .get ("csrftoken")or "missing"
            self .session .cookies .set ("csrftoken",token ,domain =".instagram.com")
            self .headers ["X-Csrftoken"]=token
        except Exception as e :
            logging .error (f"Warning: Could not fetch CSRF token: {e }")
    def _check_response (self ,response ):
        if response .status_code ==403 :
            logging .error (f"CRITICAL: 403 Forbidden. Invalid Session ID or Login Required for {response .url }")
        elif response .status_code ==429 :
            logging .error (f"CRITICAL: 429 Too Many Requests. Pausing for 60 seconds...")
            time .sleep (60 )
        return response
    def get_hashtag_posts (self ,hashtag ,max_id =None ,rank_token =None ):
        hashtag =hashtag .strip ('#')
        url =f"https://www.instagram.com/api/v1/tags/{hashtag }/sections/"
        if not rank_token :
            import uuid
            rank_token =str (uuid .uuid4 ())
        data_payload ={
        "include_persistent":"0",
        "surface":"grid",
        "tab":"recent",
        "rank_token":rank_token
        }
        if max_id :
            data_payload ["max_id"]=max_id
        try :
            logging .info (f"Requesting Hashtag: #{hashtag } | MaxID: {str (max_id )[:20 ]}")
            response =self .session .post (url ,headers =self .headers ,data =data_payload ,timeout =10 )
            self ._check_response (response )
            if response .status_code ==200 :
                data =response .json ()
                users =[]
                if "sections"in data :
                    for section in data ["sections"]:
                        if "layout_content"in section and "medias"in section ["layout_content"]:
                            for item in section ["layout_content"]["medias"]:
                                if "media"in item :
                                    media =item ["media"]
                                    if "user"in media :
                                        user_obj =media ["user"]
                                        if not user_obj .get ("is_private"):
                                            users .append ({
                                            "id":user_obj .get ("pk")or user_obj .get ("id"),
                                            "username":user_obj .get ("username"),
                                            "media_id":media .get ("pk"),
                                            "media_code":media .get ("code")
                                            })
                logging .info (f"Hashtag #{hashtag } Scraped: Found {len (users )} users in this batch.")
                next_max_id =data .get ("next_max_id")
                if not next_max_id and "more_available"in data and data ["more_available"]:
                     pass
                return users ,next_max_id ,rank_token
            else :
                logging .error (f"Hashtag Error: {response .status_code } - {response .text [:100 ]}")
                return [],None ,None
        except Exception as e :
            logging .error (f"Hashtag Exception: {e }")
            return [],None ,None
    def get_media_comments (self ,media_id ):
        users =[]
        url =f"https://www.instagram.com/api/v1/media/{media_id }/comments/"
        params ={"can_support_threading":"true","permalink_enabled":"false"}
        try :
            response =self .session .get (url ,headers =self .headers ,params =params ,timeout =10 )
            self ._check_response (response )
            if response .status_code ==200 :
                try :
                    data =response .json ()
                except Exception as e :
                    logging .error (f"ERROR in commenters json response: {response .text }")
                    raise e
                comments_list =data .get ("comments",[])
                if not comments_list and "preview_comments"in data :
                    comments_list =data .get ("preview_comments",[])
                if comments_list :
                    for comment in comments_list :
                        user_obj =comment .get ("user")
                        if user_obj and not user_obj .get ("is_private"):
                             users .append ({"id":user_obj .get ("pk")or user_obj .get ("id"),"username":user_obj .get ("username")})
            if not users :
                 url_info =f"https://www.instagram.com/api/v1/media/{media_id }/info/"
                 resp_info =self .session .get (url_info ,headers =self .headers ,timeout =10 )
                 if resp_info .status_code ==200 :
                    try :
                        info_data =resp_info .json ()
                    except Exception as e :
                        logging .error (f"ERROR in commenters json response: {response .text }")
                        raise e
                    if "items"in info_data and len (info_data ["items"])>0 :
                        item =info_data ["items"][0 ]
                        c_list =item .get ("preview_comments")or item .get ("comments")or []
                        for comment in c_list :
                            user_obj =comment .get ("user")
                            if user_obj and not user_obj .get ("is_private"):
                                users .append ({"id":user_obj .get ("pk")or user_obj .get ("id"),"username":user_obj .get ("username")})
            if users :
                logging .info (f"Post {media_id } Comments Scraped: Found {len (users )} users.")
            else :
                 logging .debug (f"No comments found for {media_id } (Endpoints checked).")
            return users
        except Exception as e :
            logging .error (f"Comments Exception: {e }")
            return []
    def get_user_followers (self ,user_id ,max_id =None ):
        url =f"https://www.instagram.com/api/v1/friendships/{user_id }/followers/?count=12&search_surface=follow_list_page"
        if max_id :
            url +=f"&max_id={max_id }"
        try :
            logging .info (f"Requesting Followers: {user_id } | MaxID: {max_id [:20 ]if max_id else 'None'}")
            response =self .session .get (url ,headers =self .headers ,timeout =10 )
            self ._check_response (response )
            if response .status_code ==200 :
                data =response .json ()
                users =[]
                if "users"in data :
                    logging .debug (f"DEBUG: users found: {len (data ['users'])}")
                    for user_obj in data ["users"]:
                        if user_obj .get ("is_private")==True :
                            continue
                        users .append ({"id":user_obj .get ("pk")or user_obj .get ("id"),"username":user_obj .get ("username")})
                logging .info (f"Followers Scraped: Found {len (users )} users in this batch.")
                next_max_id =data .get ("next_max_id")
                if next_max_id =="":
                    next_max_id =None
                if not next_max_id :
                    logging .warning (f"DEBUG: No next_max_id found. Keys: {list (data .keys ())}")
                if next_max_id :
                    logging .info (f"DEBUG: next_max_id found: {str (next_max_id )[:20 ]}")
                else :
                    logging .warning (f"DEBUG: next_max_id NONE found: {next_max_id }")
                return users ,next_max_id
            else :
                logging .error (f"Followers Error: {response .status_code } - {response .text [:100 ]}")
                return [],None
        except Exception as e :
            logging .error (response .status_code ,"\n",response .text [:100 ])
            logging .error (f"Followers Exception: {e }")
            return [],None
    def _refresh_probe_csrf (self ):
        try :
             r =self .probe_session .get ("https://www.instagram.com/accounts/login/",headers =self .headers ,timeout =10 )
             token =r .cookies .get ("csrftoken")
             if token :
                 self .probe_session .headers ["x-csrftoken"]=token
                 self .probe_session .cookies .set ("csrftoken",token ,domain =".instagram.com")
        except :pass
    def send_password_reset (self ,username ):
        url ="https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/"
        if not self .probe_session .cookies .get ("csrftoken"):
             self ._refresh_probe_csrf ()
        p_headers =self .headers .copy ()
        p_headers ["X-Csrftoken"]=self .probe_session .cookies .get ("csrftoken","")
        data ={
        "email_or_username":username ,
        "flow":"fxcal",
        "recaptcha_challenge_field":"",
        }
        try :
            response =self .probe_session .post (url ,headers =p_headers ,data =data ,timeout =10 )
            return response
        except Exception as e :
            logging .error (f"Reset Exception: {str (e )[:30 ]}")
            return None
