# JARVIS — voice aur chat

Mic on ho to `Jarvis` kehkar conversation shuru karo. Uske baad baat karte raho, har turn par naam repeat nahi karna. `ab wait kar` ya `baad mein baat karte hain` se pause hoga; phir wake-word/button zaroori hoga. Dashboard ke command box ya chat box mein command likhkar Enter bhi kar sakte ho; chat mein `Jarvis` prefix zaroori nahi. Dono same laptop controls aur recent contact context use karte hain.

Naam miss ho raha ho to **Talk to Jarvis** dabao. Conversation explicit pause tak khuli rahegi. Mic mute ho to pehle Mic ON karo. Button aur continuous/pause behavior ki real Qt bridge se verification hui hai; laptop par tumhari har physical voice utterance ki reliability abhi guaranteed nahi hai.

Transcription mein naam `Jervis` aaye to bhi direct address accept hoga. Random milte-julte words ko wake command nahi maana jata. Pending shutdown/restart prompt ke 30 seconds mein exact `haan`/`cancel` voice reply ke liye naam repeat karna zaroori nahi; us waqt unrelated voice sentence approval nahi banta.

App ki greeting khatam hone do aur `LISTENING` status par bolo. `Jarvis, Chrome kholo` ya sirf `Jarvis` se conversation shuru hogi. Silence ya turn completion ise band nahi karti. Dono chat inputs aur multi-step arithmetic actual app bridge se verified hain.

Try karo:

- `Jarvis, Chrome kholo`
- `Jarvis, calculate 27 * 13`
- `Jarvis, WhatsApp par Divyansh ke messages padho`
- `Jarvis, Discord par ExactUsername ki chat kholo`
- `Jarvis, screen pe kya hai`
- `Jarvis, 10 minute baad paani peena yaad dilana`
- `assign Landing page review to ExactName` — local task board mein naam ke saath save hoga; notification alag action hai.
- `professor ko leave ke liye email draft likho` — poora draft chat mein milega; send/active app mein typing nahi hogi.
- `laptop restart kar do` — 30 seconds mein `haan` ya `cancel` bolo/likho. Unrelated naya command purani confirmation hata deta hai. Confirm karne par Windows ko request jayegi; unsaved kaam pehle save karo.

Daily planning ke liye dashboard mein **Aaj ka plan** dabao, ya chat/voice se bolo:

- `aaj ka plan: C loops practice, gym, maths revision` — local task board mein goals save honge.
- `aaj ka plan` — actual saved goals aur completion dikhega.
- `done: C loops practice` — aaj ke plan ka exact matching task complete hoga.
- `aaj ka progress: loops ki practice hui, maths mein doubt hai` — progress note save hoga; task bina tumhare explicit completion ke done nahi banega.
- `daily review 21:30 rakho` — evening review ka time badlega; default 21:00 hai.
- `abhi nahi` — ek ghante ke liye daily check-ins pause.
- `aaj mat pooch` — aaj ke liye pause; `resume check-ins` se wapas chalu.
- `remember timetable: Monday 09:00-10:00 C programming; Tuesday 2pm-3pm Maths` — tumhari actual class rows save hongi. Apne timings do; ye example tumhara timetable nahi hai.

Tumhari preference ke hisaab se ek casual check-in roz hai. Planning, meaningful absence ke baad return question, class question aur evening progress review free moments par aayenge. Typing, recent conversation, ongoing command aur 23:00–07:00 quiet hours mein daily questions nahi bolenge. User activity unknown ya laptop par kaafi der se activity na ho to bhi nahi. Ye app khula hone par kaam karta hai; closed app ko scheduler se wake nahi karta.

Check-in chat mein bhi dikhega. Uska bolna khatam hone ke baad 30 seconds mein ek voice reply bina naam repeat kiye de sakte ho, ya chat mein likho. Goals aur recent self-reported check-in notes local files mein persist hote hain; conversation ke liye existing AI provider ko relevant context mil sakta hai. Timetable milne tak demo college timings se class check-ins nahi aayenge. Attendance poochega, assume nahi karega.

Friend, caring aur teaching tone conversation ke hisaab se adapt karne ke instructions voice/chat dono mein hain; alag personality modes nahi. Hinglish, occasional consented light teasing, uncertainty par seedha sawal aur mistakes par reasoned correction use karega. Mood hints tumhare words se aate hain; perfect mood detection ya har generated reply ki quality guaranteed nahi hai.

Exact contact ki chat khulne ya uske messages successfully padhne ke baad, agle 2 minute mein:

- `usko message bhejo Main 10 minute mein aa raha hoon`
- `reply kar On my way`
- `uske messages padho`
- `uski chat kholo`

Voice se contact select karke reply chat mein likh sakte ho; chat se contact select karke `Jarvis, usko message bhejo…` bol bhi sakte ho. Contact/platform unclear, purana ya verify nahi hua ho to JARVIS exact naam poochega. Message ke text ko contact pronoun samajhkar replace nahi karega.

`WhatsApp par message bhejo` par JARVIS missing details poochhega. Exact contact do, phir message ka text do. Ye unfinished request 2 minute tak yaad rakhta hai; `cancel` se rok sakte ho. Ek saath bhi likh sakte ho: `WhatsApp par ExactContact ko message bhejo Main 10 minute mein aa raha hoon`. Voice aur chat ke beech details de sakte ho. Message bhejne se pehle contact aur empty composer verify hona zaroori hai; failed verification ko sent nahi kahega.

Tumhari approval se chat/tool replies Gemini TTS ki Charon voice use karte hain; native voice conversation bhi Charon par hai. Extra TTS request mein sirf reply text aur constant voice/style metadata jaata hai, extra memory/screen/files nahi. Natural voice unavailable ho to notice dikhega aur text chat mein rahega; robotic Windows voice silently switch nahi hogi. Internet/provider delay ab bhi ho sakta hai.

`Jarvis, stop` se bolna rukta hai. Chat mein `stop` uske bolte waqt bhi kaam karta hai. Ye already-running external action ko undo nahi karta.

Voice laptop action par sirf AI ka “opened/done” bolna completion nahi maana jata. Agar assistant command attempt hi nahi hua, unsupported acknowledgement/audio rok kar same shared pipeline command chalati hai. Actual tool fail ya unverified ho to uska result sunaya jata hai; attempted message/call automatically dobara nahi hoti. General conversation ka native audio chalta rehta hai.

Discord jaise apps ki updater/loading window “opened” ki verification nahi hai. Main app ki actual owned foreground window chahiye. Update lamba chale to readiness pending batayega; duplicate updater launch nahi karega.

Completed short Charon replies ka bounded cache sirf current process ki RAM mein hai. Partial, failed ya cancelled audio cache nahi hoti. Stop purani speech cancel karta hai; playback small writes mein hota hai. `ruk` current speech rokta hai, conversation pause nahi karta.

Speaker mode mein JARVIS bolte waqt mic ko pause karta hai, taaki apni awaaz dobara command na samajh le. Headphones ke liye interruption mode alag se enable kiya ja sakta hai. Mic off karne ke baad chat mein `mic on` likho ya mic button dabao.
Voice generate hone ke wait mein mic ab input le sakta hai. Actual sound playback/echo tail mein protection rahegi. Nayi addressed baat aane par woh purani pending speech cancel karega. Chat ki recent baat ka context agle voice answer mein shared pipeline se milega; purane commands dobara execute nahi honge.

Wake/button se shuru hone ke baad conversation ke agle turns bina naam ke accept hote hain. Ye speaker identity verification nahi hai: active conversation mein nearby speech bhi turn ban sakti hai. Unmuted mic cloud voice session ko audio bhejta hai; finish hone par pause/mute kar sakte ho. Screen/camera analysis sirf explicit command par hota hai.

Real incoming-call answering aur native call-handler acceptance ki limitations `ASSISTANT_VERIFICATION_2026-10-01.md` mein recorded hain. Successful automated tests ko har account/action ka real-world verification mat samjho.

Live internet lookup voice/chat dono se: `Jarvis, latest Python release official documentation search karo`, `internet pe dhund ke bata Python docs`, ya `what is the current price of RTX 5070`. Chat mein wake word zaroori nahi. Sources ke actual links aur check ka time milta hai; recent cached result alag labelled hota hai, aur current queries cache bypass karti hain. Unrelated scraper results reject hote hain. Search unavailable ho to latest answer ko verified nahi kahega.

Voice ka transient connection tootne par reconnect notice aayega; valid resume handle ho to conversation resume hoti hai, rejected handle par fresh connection try hota hai. Is process mein purana message/call automatically dobara nahi bhejta. Remote service/network outages phir bhi possible hain.

Internet accuracy update: squad, ODI-century totals aur current public roles jaise badalte facts ke liye actual source pages padhe jaate hain. Sirf search snippet milna verified answer nahi hai. Source date aur check time answer mein dikhte hain. Fresh/date-supported page ya supporting passage na mile to JARVIS saaf kahega ki latest jawab verify nahi hua. Ye “series hai hi nahi” ya purana number guess karne ki permission nahi hai.

Internet reliability update: Hindi/Hinglish ke sawal ke search terms saaf kiye jaate hain, lekin jawab tumhare original sawal ke scope par check hota hai. `ind vs nz` jaise abbreviations expand hote hain. Har sourced answer ka doosra pass ODI/Test, year/opponent, denial aur conflicting evidence check karta hai. Kamzor evidence par ek focused retry hota hai; phir bhi proof na mile to guess nahi karega. Publication date aur local check time alag hain. Real probes mein search + dono checks ko lagbhag 10–21 seconds lage; provider/network ke hisaab se time badal sakta hai.

Respectful rough banter voice aur chat dono mein shared hai. `unfiltered mode on` se friendly gaali/teasing enable hoti hai; `gaali band karo`, `mujhe gaali mat de` ya `unfiltered mode off` se band hoti hai. Setting restart ke baad bhi yaad rehti hai. Ye sirf tone preference hai: research evidence, message text aur laptop confirmations isse nahi badalte. Galat baat par reason aur better alternative milega, sirf haan nahi.

Tum `mood off hai` ya `abhi roast mat kar` bolo to gentle response aana chahiye. Camera facial expression se feelings ya mental state infer nahi karta. `camera dekh mera mood kaisa hai` par photo lene ke bajaye neutral haal poochhega; normal explicit camera observation visible objects/actions tak rahegi. Camera background awareness apne aap enable nahi hui hai. Existing once-a-day casual check-in mein neutral haal-chaal ka sawal bhi aa sakta hai; busy/quiet-hour gates apply hote hain.

Camera access update: `camera on` hardware se fresh local frame check karke on-demand access enable karta hai. `camera dekh kya dikh raha hai` par actual checked observation milegi; `camera off` access setting aur any active camera awareness/hand tracker ko band karta hai. Camera button bhi isi verified pipeline ka use karta hai. Camera on ka matlab continuous recording nahi hai. Existing hand tracking Controls mein alag explicit button se start/stop hoti hai; use camera ki stream chahiye, isliye kisi doosre camera consumer ke saath conflict possible hai.

`access status` ya `meri permissions dikhao` se actual registered tools, camera preference aur OS/admin status milta hai. Tool registration account login ya delivery verification ka proof nahi hai. Apps/files/browser/system controls current Windows rights par chalte hain; disruptive actions ki exact confirmation aur protected changes ki OS permission apply hoti hai. Current build mein 70 tools registered hain; camera index non-secret runtime preferences mein save hota hai.

`screen analyse karo` ya `meri screen dekhiyo` par fresh image li jaati hai. JARVIS saamne ho to woh thodi der hide hokar peeche visible app capture karta hai, phir wapas aa jaata hai. Jo page dikhana hai use JARVIS ke peeche khula rakho. Screen ka quoted text offline OCR se bhi check hota hai; hidden/unreadable page aur JARVIS ki purani chat announcement ka proof nahi hain. Voice mein bhi wahi checked observation sunayi jaayegi. Local-only policy ya sensitive screen ke existing controls apply hote hain.
