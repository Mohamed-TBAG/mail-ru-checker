import re
import urllib .parse
from urllib .parse import urlparse ,parse_qs
import requests
import logging
class GmailChecker :
    def __init__ (self ,requests_ses ):
        self .session =requests_ses
    def check (self ,email ):
        try :
            username =email .split ('@')[0 ]if '@'in email else email
            logging .info (f"GmailCheck: Starting check for {email }")
            r =self .session .get ('https://accounts.google.com/servicelogin?hl=en-gb')
            qs =parse_qs (urlparse (r .url ).query )
            dsh =qs .get ('dsh',[None ])[0 ]
            ifkv =qs .get ('ifkv',[None ])[0 ]
            if not dsh or not ifkv :
                logging .warning ("GmailCheck: Missing dsh/ifkv params.")
                return True
            url_2 =f'https://accounts.google.com/lifecycle/flows/signup?biz=false&dsh={dsh }&flowEntry=SignUp&flowName=GlifWebSignIn&hl=en-gb&ifkv={ifkv }&theme=glif'
            r =self .session .get (url_2 )
            parsed =parse_qs (urlparse (r .url ).query )
            TL =parsed .get ('TL',[None ])[0 ]
            try :
                AT =re .search (r'"SNlM0e":"([^"]+)"',r .text ).group (1 )
                FdrFJe =re .search (r'"FdrFJe":"([^"]+)"',r .text ).group (1 )
            except AttributeError :
                logging .warning ("GmailCheck: Failed to extract AT/FdrFJe tokens.")
                return True
            u_AT =urllib .parse .quote (AT )
            u_dsh =urllib .parse .quote (dsh )
            u_ifkv =urllib .parse .quote (ifkv )
            u_TL =urllib .parse .quote (TL )if TL else ""
            u_FdrFJe =urllib .parse .quote (FdrFJe )
            h ={
            'Accept':'*/*',
            'Accept-Encoding':'gzip, deflate, br',
            'Accept-Language':'en-US,en;q=0.9',
            'Connection':'keep-alive',
            'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8',
            'Host':'accounts.google.com',
            'Origin':'https://accounts.google.com',
            'Referer':'https://accounts.google.com/',
            'Sec-Fetch-Dest':'empty',
            'Sec-Fetch-Mode':'cors',
            'Sec-Fetch-Site':'same-origin',
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'X-Chrome-ID-Consistency-Request':'version=1,client_id=77185425430.apps.googleusercontent.com,device_id=8f1f3932-1eb5-4090-9f2b-252e0ea14109,signin_mode=all_accounts,signout_mode=show_confirmation',
            'X-Client-Data':'CI+VywE=',
            'X-Same-Domain':'1',
            'sec-ch-ua':'"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-arch':'"x86"',
            'sec-ch-ua-bitness':'"64"',
            'sec-ch-ua-full-version':'"121.0.6167.161"',
            'sec-ch-ua-full-version-list':'"Not A(Brand";v="99.0.0.0", "Google Chrome";v="121.0.6167.161", "Chromium";v="121.0.6167.161"',
            'sec-ch-ua-mobile':'?0',
            'sec-ch-ua-model':'""',
            'sec-ch-ua-platform':'"Windows"',
            'sec-ch-ua-platform-version':'"15.0.0"',
            'sec-ch-ua-wow64':'?0',
            'x-goog-ext-278367001-jspb':'["GlifWebSignIn"]',
            'x-goog-ext-391502476-jspb':f'["{u_dsh }",null,null,"{u_ifkv }"]'}
            p_name =f'f.req=%5B%5B%5B%22E815hb%22%2C%22%5B%5C%22Harold%5C%22%2C%5C%22%5C%22%2C0%2C%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C1%2C0%2C1%2C%5C%22%5C%22%2Cnull%2Cnull%2C1%2C1%5D%2Cnull%2C%5B%5D%2C%5B%5D%2C1%5D%22%2Cnull%2C%22generic%22%5D%5D%5D&at={u_AT }&'
            url_batch ='https://accounts.google.com/lifecycle/_/AccountLifecyclePlatformSignupUi/data/batchexecute'
            params_batch =f'rpcids=E815hb&source-path=%2Flifecycle%2Fsteps%2Fsignup%2Fname&f.sid={u_FdrFJe }&bl=boq_identity-account-creation-evolution-ui_20240208.02_p2&hl=en-gb&TL={u_TL }&_reqid=407217&rt=c'
            self .session .post (f"{url_batch }?{params_batch }",data =p_name ,headers =h )
            url_birth =f'https://accounts.google.com/lifecycle/steps/signup/birthdaygender?TL={u_TL }&dsh={u_dsh }&flowEntry=SignUp&flowName=GlifWebSignIn&hl=en-gb&ifkv={u_ifkv }&theme=glif'
            r =self .session .get (url_birth )
            try :
                FdrFJe =re .search (r'"FdrFJe":"([^"]+)"',r .text ).group (1 )
                u_FdrFJe =urllib .parse .quote (FdrFJe )
            except :
                pass
            p_birth =f'f.req=%5B%5B%5B%22eOY7Bb%22%2C%22%5B%5B1999%2C1%2C1%5D%2C1%2Cnull%2C0%2C%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C1%2C0%2C1%2C%5C%22%5C%22%2Cnull%2Cnull%2C1%2C1%5D%2C%5C%22captcha_token_here%5C%22%2C%5B%5D%5D%22%2Cnull%2C%22generic%22%5D%5D%5D&at={u_AT }&'
            params_birth =f'rpcids=eOY7Bb&source-path=%2Flifecycle%2Fsteps%2Fsignup%2Fbirthdaygender&f.sid={u_FdrFJe }&bl=boq_identity-account-creation-evolution-ui_20240208.02_p2&hl=en-gb&TL={u_TL }&_reqid=309055&rt=c'
            self .session .post (f"{url_batch }?{params_birth }",data =p_birth ,headers =h )
            url_user =f'https://accounts.google.com/lifecycle/steps/signup/username?TL={u_TL }&dsh={u_dsh }&flowEntry=SignUp&flowName=GlifWebSignIn&hl=en-gb&ifkv={u_ifkv }&theme=glif'
            r =self .session .get (url_user )
            try :
                FdrFJe =re .search (r'"FdrFJe":"([^"]+)"',r .text ).group (1 )
                u_FdrFJe =urllib .parse .quote (FdrFJe )
            except :
                pass
            p_check =f'f.req=%5B%5B%5B%22NHJMOd%22%2C%22%5B%5C%22{username }%5C%22%2C1%2C0%2C1%2C%5Bnull%2Cnull%2Cnull%2Cnull%2C0%2C151712%5D%2C0%2C40%5D%22%2Cnull%2C%22generic%22%5D%5D%5D&at={u_AT }&'
            params_check =f'rpcids=NHJMOd&source-path=%2Flifecycle%2Fsteps%2Fsignup%2Fusername&f.sid={u_FdrFJe }&bl=boq_identity-account-creation-evolution-ui_20240208.02_p2&hl=en-gb&TL={u_TL }&_reqid=209557&rt=c'
            r =self .session .post (f"{url_batch }?{params_check }",data =p_check ,headers =h )
            if 'steps/signup/password'in r .text or 'Sorry, your username must be'in r .text or 'only letters (a-z)'in r .text :
                logging .info (f"GmailCheck: {email } is AVAILABLE (or invalid format).")
                return False
            elif '"]]]",null,null,null,"generic"],["di"'in r .text :
                logging .info (f"GmailCheck: {email } is TAKEN.")
                return True
            logging .warning (f"GmailCheck: Unknown response for {email }.")
            return True
        except Exception as e :
            logging .error (f"GmailCheck: Exception for {email }: {e }")
            return True
