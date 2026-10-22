# BloomCare 1.2.0 — free website aur integrations ka setup

21 October 2026. Is guide ko isi order mein follow karein. Apna domain khareedna zaroori nahi: **Render Free web service + Neon Free PostgreSQL** use karein. Render aapko apna HTTPS `onrender.com` address dega. ZIP mein website, API aur dono screening stages ke liye ek combined Docker build aur `render.yaml` diya gaya hai.

**Live website abhi create nahi hui.** Provider accounts/keys aap apne dashboards mein enter kareingi. Yeh code aur setup package hai; kisi real inbox, Twilio delivery ya public video call ko yahan successful claim nahi kiya gaya.

## Pehle samajh lein: kis cheez ki zaroorat hai?

| Service | Kaam | Zaroori? |
| --- | --- | --- |
| Render Free | Website, API, model inference; free HTTPS address | Online app ke liye |
| Neon Free | Accounts, patient records aur report bytes ka PostgreSQL storage | Online app ke liye |
| Brevo HTTPS email API | Email verification aur Forgot password links | Public accounts/recovery ke liye |
| Groq | Assistant aur consented care guides | In AI features ke liye |
| STUN/TURN provider, e.g. Metered | Different networks par video connectivity | Reliable remote video ke liye TURN configure karein |
| Twilio WhatsApp | App se automatic opted-in care alerts | Optional; manual PDF/WhatsApp sharing ke liye nahi |

Free plans mein quotas hote hain. **Render Free production medical hosting ke liye provider ki recommendation nahi hai.** Yeh portfolio/demo deployment ke liye hai: 15 minutes idle hone par sleep aur next request par lagbhag one-minute cold start ho sakta hai. Reminder processing app awake hone par hoti hai; sleeping service background reminder delivery ki guarantee nahi de sakti. Free Render PostgreSQL 30 din mein expire hota hai, isliye yahan **Neon** choose kiya hai. Neon ki compute/storage limits bhi dashboard mein check karein; free allowance khatam hone par service ruk sakti hai. Models ki clinical limitations current release mein same hain.

## 1. ZIP update aur clean cloud copy

Apni existing Windows installation ke liye:

```bat
cd /d D:\Desktop\BloomCare
.\scripts\update-final.cmd
```

Pehle servers stop karein, ZIP ki files isi project root mein replace karein; Docker Desktop running ho. Successful message **v1.2.0 complete update passed** hona chahiye. Phir backend/frontend alag CMD windows mein start karke Ctrl+F5 karein. Local accounts aur passwords preserve hote hain. Fresh install ke liye README ka foundation setup use karein.

Cloud upload ke liye **alag clean folder** banayein, e.g. `D:\Desktop\BloomCare-Cloud`. Isi downloaded ZIP ko wahan extract karein. Apni purani working installation ki `.env`, database, backups, reports, `.venv` ya `node_modules` copy na karein. `backend`, `frontend`, `ml`, `deploy`, `scripts`, `docs` aur `render.yaml` seedha repository root par hon; extra nested BloomCare folder nahi.

Yeh cloud path naya Neon database initialize karega. Aapka local database apne PC par rahega; purane accounts/reports automatically online migrate nahi hote. Is guide mein kisi existing database ko overwrite/restore nahi kiya jata.

## 2. Brevo: email verification aur Forgot password

Render Free outbound SMTP ports 25/465/587 block karta hai. Is build mein **Brevo ka HTTPS API** use hoga; SMTP credentials paste karne se yeh hosting issue solve nahi hota.

1. [Brevo](https://www.brevo.com/) par free account banayein aur account email verify karein. Transactional email activation/approval agar dashboard maange to complete karein.
2. **Settings → Senders, Domains, IPs → Senders → Add a sender**. From name `BloomCare`, aur From email woh mailbox jo aap control karti hain. Aaya hua verification code **Brevo mein** paste karke sender verify karein.
3. Domain na hone par provider ki allowed verified-mailbox option use karein. Brevo free email domains ke sender ko compliant address se temporarily replace kar sakta hai. Apna branded sender/DKIM chahiye to baad mein domain authenticate karna hoga. Sender approval aur inbox/spam delivery ko test kiye baghair email ko ready na samjhein.
4. **Settings → SMTP & API → API Keys** mein nayi **API key** banayein. Yeh **SMTP key nahi** hai. Isko private rakhein.
5. Do values ready rakhein: verified sender email aur API key. Agle Render step mein `EMAIL_FROM` aur `BREVO_API_KEY` fields mein paste hongi.

Brevo ke currently advertised free plan mein 300 emails/day ka cap hai; apna actual dashboard allowance aur approval check karein.

**Forgot password kaise chalega?** Website par **Sign in → Forgot password? → apni registered email**. Inbox ka latest reset link kholein, naya password aur confirmation enter karein. Link 30 minutes mein expire hota hai aur ek hi baar use hota hai. Purane sessions revoke ho jate hain; phir sign in karein. Email verification link 24 hours ka hai. Link kholna akela password change nahi karta. Email na aaye to Spam aur Brevo transactional logs dekhein, phir fresh link request karein. Unknown aur known address ka public response same hota hai, isliye “request accepted” inbox delivery ka proof nahi.

**Local Windows par bhi Brevo use karna ho:**

```bat
.\scripts\configure-integrations.cmd email-brevo
```

Local application origin `http://127.0.0.1:5173` rakhein, verified sender aur API key wizard mein dein. Backend restart karein. Existing local SMTP setup use karna ho to pehle wala `email` command available hai. Local wizard ki files Render dashboard ko automatically update nahi kartin.

## 3. Neon: free PostgreSQL

1. [Neon](https://neon.com/) par sign in → **New project** → project `BloomCare`. Free plan, PostgreSQL 16, Render Singapore ke qareeb available region choose karein.
2. **Connect** kholein. Primary/main branch aur application database select karein. Is single-server/migration setup ke liye **Direct connection** choose karein.
3. Sirf connection URL copy karein: `postgresql://...?...sslmode=require...`. `psql` command ya surrounding quotation marks copy na karein.
4. Is URL ko Render ke **DATABASE_URL** field mein paste karein. Driver prefix app khud normalize karegi; SSL/query options preserve honge.
5. Connection URL password jaisi secret hai. Isko chat, GitHub README ya screenshot mein publish na karein. Database creation naya/empty project mein karein.

Application migrations, accounts, reports aur report-file bytes Neon mein store hote hain. Cloud model build ke andar banta hai; provider ki temporary disk par aapka patient database depend nahi karta. Current free Neon pricing page 1 GB PostgreSQL storage/project aur 100 CU-hours/project/month dikhati hai; quotas dashboard se monitor karein. Backup/restore acceptance ab bhi karein: Windows/local backup steps [FINALIZE-TODAY.md](FINALIZE-TODAY.md) mein hain; online database ke liye Neon restore/snapshot/export instructions follow karein aur separate branch/database mein restore verify karein.

## 4. Clean source ko GitHub par rakhein

Sab se asaan route GitHub Desktop hai:

1. GitHub par naya **private** repository `BloomCare-Cloud` banayein. Purani BloomCare repository ko overwrite karna zaroori nahi.
2. GitHub Desktop se naya repo `D:\Desktop\BloomCare-Cloud` mein clone karein.
3. ZIP ki clean contents is cloned folder ke root mein extract karein. Desktop ki Changes list mein source aur `render.yaml` dikhna chahiye. Kisi `.env` ya private runtime file ko commit na karein; ignore rules bhi included hain.
4. Commit message `BloomCare 1.2.0 delivery` → **Push origin**. GitHub par root mein `render.yaml`, `deploy/render.Dockerfile` aur backend/frontend folders confirm karein.

## 5. Render: website online karein, domain ki zaroorat nahi

1. [Render dashboard](https://dashboard.render.com/) par sign in. GitHub repo access connect karein.
2. **New → Blueprint** select karein; apna `BloomCare-Cloud` repository aur main branch choose karein. Blueprint file root ka **render.yaml** hai.
3. Service ka plan **Free**, runtime **Docker**, aur Dockerfile **./deploy/render.Dockerfile** verify karein. Is blueprint mein paid disk/worker ya Render database nahi hai. Agar UI paid resource maange to plan/resource selection correct karein.
4. Render jo private fields maangta hai unhein fill karein:

| Render key | Yahan kya paste karna hai |
| --- | --- |
| `DATABASE_URL` | Neon Connect se direct PostgreSQL URL, SSL options ke saath |
| `EMAIL_FROM` | Brevo mein verified sender email |
| `BREVO_API_KEY` | Brevo API key, SMTP key nahi |
| `BOOTSTRAP_ADMIN_EMAIL` | Apni real reachable email; pehla admin isi mailbox ka owner hoga |

`JWT_SECRET_SEED` Render automatically generate karega. Code is 256-bit seed se stable session key derive karta hai; isko har deploy par rotate/delete na karein. Blueprint `COOKIE_SECURE=true`, `AUTH_REQUIRE_EMAIL_VERIFICATION=true` aur `EMAIL_PROVIDER=brevo` set karta hai. Account email configure kiye baghair public startup refuse karega.

5. **Deploy/Apply** karein. Build dependencies install karega, frontend compile karega, bundled checksum-pinned public data se reviewed maternal model train/verify karega aur original PE forest include karega. Startup additive migrations head `0013_account_security` tak run karega. Local private model/trust upload ki zaroorat nahi.
6. Live hone par Render ka **apna diya hua URL** kholein, e.g. `https://bloomcare-unique-name.onrender.com`. Yeh example hai, reserved/live address ka claim nahi. Actual URL Render page par copy karein. App isi actual origin ko recovery links aur allowed origins ke liye automatically use karegi.
7. `/api/health/ready` par `{"status":"ready"}` aur Help & support mein interface/server **1.2.0** confirm karein. HTTPS URL hi use karein.

**Pehla admin:** Empty database par bootstrap email se admin account banta hai, lekin koi default/shared password nahi hota. Website ke **Forgot password?** mein `BOOTSTRAP_ADMIN_EMAIL` wali email enter karein. Inbox ke link se apna password set karein; isse mailbox verification bhi complete hoti hai. Ab **Sign in as → Admin** se login karein. Login ke baad Render **Environment** se `BOOTSTRAP_ADMIN_EMAIL` remove karke redeploy kar sakti hain. Existing patient ko bootstrap se admin promote nahi kiya jata. Same initialized admin ke saath restarts idempotent hain.

Patient aur doctor website se apni real emails se register aur verify karein. Doctor ko admin account se approve karein; email verification doctor approval ka replacement nahi.

**Agar build/start fail ho:** Events/Logs mein last error dekhein. “Configure selected email provider” ke liye key/from address; database timeout ke liye Neon project active/connection URL; missing file ke liye repository root aur Dockerfile check karein. Render Free mein shell access nahi, isliye bootstrap aur automatic migrations diye hain. Agar memory/CPU limit hit ho to dashboard event retain karein aur suitable compute choose karein; free service ke load capacity ko verified production capacity na samjhein.

Render public edge par rate limiting trusted `CF-Connecting-IP` use karti hai; arbitrary `X-Forwarded-For` ko auth identity nahi maana jata. Is proxy setting ko plain local/public server par enable na karein. Caddy/VPS option apne alag private proxy rules use karta hai.

## 6. Groq: assistant aur care guides

1. [Groq API Keys](https://console.groq.com/keys) par key banayein ya apni existing working key use karein.
2. Render service → **Environment → Add environment variable**:

| Key | Value |
| --- | --- |
| `GROQ_API_KEY` | Groq ki private key |
| `GROQ_MODEL` | Apna available/working model ID; current app default `openai/gpt-oss-20b` |

3. Save and redeploy. Key frontend file ya `VITE_...` variable mein nahi jayegi.
4. Patient Assistant mein ek simple question aur required consent submit karein. Assessment care guide ko uske apne button se check karein. Provider quota/model errors aayen to Groq dashboard par same model ID/usage check karein.

## 7. Video: STUN/TURN configure karein

1. [Metered TURN](https://www.metered.ca/turn-server/) ya apne TURN provider ka account kholein. Current free plan/allowance dashboard par verify karein. Metered advertises 20 GB/month free TURN; region/usage limits apply.
2. TURN dashboard se server URLs, username aur credential generate/copy karein. **Dashboard ke apne values** use karein; neeche placeholders ko waise ka waise paste na karein.
3. Render Environment mein **WEBRTC_ICE_SERVERS** ki value one-line JSON array rakhein:

```json
[{"urls":["turn:YOUR_PROVIDER_HOST:3478","turns:YOUR_PROVIDER_HOST:443?transport=tcp"],"username":"YOUR_TURN_USERNAME","credential":"YOUR_TURN_PASSWORD"}]
```

Provider ne jo supported URLs diye hain **sirf wahi** rakhein. Ports/host invent na karein. Agar provider ready-made `iceServers` deta hai to sirf array copy karein, `const`, function ya outer `{iceServers: ...}` nahi. Server account API key yahan paste na karein; yeh specifically TURN connection credentials hain. App credentials authenticated call participants ko WebRTC ke liye deti hai; quota-limited/expiring credentials aur provider rotation policy use karein.

4. Save and redeploy. Admin → Connected services mein Relay settings saved aana configuration check hai, actual call result nahi.
5. Patient appointment request kare, doctor accept kare, record-sharing access active rahe. Doctor top ke **Video consultation** se call start kare; patient same accepted appointment khole. Camera/mic permissions allow karein. Do devices, ek Wi-Fi aur doosra mobile data, dono taraf audio/video check karein. Camera denied/network failure message bhi check karein. STUN alone restrictive networks ki guarantee nahi.

## 8. WhatsApp: manual share aur automatic Twilio alerts alag hain

**Manual:** Reports/assessment se PDF download/share karke WhatsApp mein attach karein. Iske liye Twilio key ya business sender ki zaroorat nahi. Device share menu available ho to WhatsApp select karein; warna downloaded PDF attach karein. App recipient ko automatic file bhejne ka claim nahi karti.

**Automatic alert:** Twilio [WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox) open karein. Twilio trial/credit/pricing apne console mein check karein; sandbox bhi standard WhatsApp pricing ke mutabiq bill ho sakta hai, yeh unlimited free messaging nahi.

1. Twilio mein email/phone verification complete karein. **Messaging → Try it out → WhatsApp** (ya Try out WhatsApp) se sandbox activate karein.
2. Har opted-in recipient apne WhatsApp se console ka exact **join YOUR-CODE** message console ke sandbox number par bheje. Aaj ke test se pehle rejoin karein; free-form alert join/user message ke 24-hour window ke andar bhejein.
3. Console se Account SID, Auth Token aur sandbox sender number lein. Render Environment mein:

| Key | Value |
| --- | --- |
| `TWILIO_ACCOUNT_SID` | `AC...` Account SID |
| `TWILIO_AUTH_TOKEN` | Private Auth Token |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:` + console sender ka full international number |
| `TWILIO_ALLOWED_RECIPIENTS` | Sirf opted-in joined full numbers, e.g. `+92...,+44...`; yahan `whatsapp:` prefix nahi |
| `TWILIO_CONTENT_SID` | Sandbox/active-session free-form test mein **unset** rakhein |

4. Save and redeploy. Patient apna allowed contact choose kare, explicit alert consent de, phir alert bheje. Status **QUEUED** ko delivered na samjhein; refresh karke provider ka actual status dekhein. Uncertain timeout par blindly resend na karein.
5. Public production WhatsApp ke liye registered/approved sender aur outside-window approved Content template chahiye. Template ki two variables: `1` maternal category, `2` PE category/status. Us approved template ka `HX...` Content SID set hota hai. Sandbox number par custom template invent karke use nahi kiya ja sakta.

## 9. Handover se pehle final acceptance

- Patient, approved doctor aur admin ko separate browser profiles mein kholein. Website registration, verify, Forgot password, login, logout aur expiry/one-use reset link check karein.
- Real measured observations ya clearly synthetic demo values se record/assessment, PE coverage, remove mistaken record, reports/PDF aur sharing/revocation check karein. Model limits ko bypass na karein.
- Ek Groq reply, saved care guide, real two-device video call aur chosen WhatsApp path verify karein.
- Online database backup/restore ko **separate branch/database** mein verify karein. Original database par destructive restore trial na karein.
- Render/Neon usage, health/error monitoring aur source rollback package retain karein. Current free-tier cold-start/reminder limitation ko handover mein mention karein.

Yeh steps pass hone par public **demo/portfolio** acceptance record complete ho sakta hai. Real medical diagnosis/clinical deployment ka claim independent validation aur suitable operational hosting ke baghair nahi banta.

## Official references, checked 21 October 2026

- [Render Free: sleep, limits, SMTP, expiring free database](https://render.com/docs/free)
- [Render web-service HTTPS subdomains](https://render.com/docs/web-services)
- [Blueprint configuration and generated secrets](https://render.com/docs/blueprint-spec)
- [Render injected URL variables](https://render.com/docs/environment-variables)
- [Render trusted client-IP guidance](https://render.com/articles/host-pocketbase-on-render)
- [Neon connection details](https://github.com/neondatabase/website/blob/main/content/docs/get-started/connect-neon.md)
- [Neon Free pricing/limits](https://neon.com/pricing)
- [Brevo verified sender setup](https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email)
- [Brevo sender-domain requirements](https://help.brevo.com/hc/en-us/articles/14925263522578-Comply-with-Gmail-Yahoo-and-Microsoft-s-requirements-for-email-senders)
- [Brevo free-plan email limits](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
- [Brevo HTTPS transactional API](https://developers.brevo.com/reference/send-transac-email)
- [Twilio Sandbox and session rules](https://www.twilio.com/docs/whatsapp/sandbox)
- [Groq quickstart](https://console.groq.com/docs/quickstart)
- [Metered TURN](https://www.metered.ca/turn-server/)
