# Handoff: HOI daily content (from the cloud chat, 4 Nov 2026)

Read this first, then `daily_content/DAILY_RUN.md` (the rules each daily run follows).
Everything here was decided with Saif in the cloud session. Don't re-ask what's settled below.

## What we're making

Every day, for **Arjun Veera's** personal profiles (posted by hand by the team, nothing is auto-posted):
- 2 tweets (X)
- 1 LinkedIn carousel (PDF), or a video on days the reel suits LinkedIn too
- 1 Instagram reel script, Arjun sir POV, to be made in **HeyGen** with his AI avatar
- Saturdays only: 1 LinkedIn article (600 to 900 words, the week's biggest theme)

All writing is done by Claude Code itself (no Anthropic API key, no Console credit needed).
Output is saved **locally** in a folder on a drive Saif chooses (`HOI_OUTPUT_DIR`), one folder per date.

## Decisions already made

- Written content: **English only**. Reel voice: **Tenglish** (Telugu and English mixed), with English captions.
- Until the HeyGen test is done, every reel comes in two forms: Tenglish in English letters, and the same
  script with Telugu words in Telugu script. Saif picks one after testing; then drop the other.
- **Arjun's voice:** senior insider who shares knowledge and doesn't care about selling.
  **No CTA, no advertising, no mention of House of Investors or its services, no sign-off.**
  Calm, blunt, a little unbothered. Ends on a sharp observation or rule of thumb, never an ask.
- Saif reviews the scripts himself before anything goes to HeyGen. No approval bot. No X, LinkedIn or
  Instagram API links.
- The **Content Engine** (video pipeline in this repo) and **Signal Desk** (HOI Lead Engine app) are
  **not part of this**. Don't use or fix them for this job.

## News input

- A **Gemini Spark** agent writes a "Signal Feed YYYY-MM-DD" Google Doc each day into the Drive folder
  "daily market news": `1fhCDLbTeJ1-ZmtN9HZ6MLgF716tGLf13` (owner houseofinvestors9@gmail.com).
  It landed around 12 pm and 7 pm IST on the first two days.
- Each item has: Signal (with source link), Why it matters, Brand angle, Founder take, Speed, plus a
  "For Arjun" list at the end. Use **any** item, not only the "For Arjun" ones.
- Read it locally with `python daily_content/fetch_feed.py` (uses the PC's `token.json`; `--n 7` on Saturdays).
- **Quality problems seen in the first feeds** (why the fact rules exist):
  - 4 Nov lead item (High Court rejects AI land records) cited emergent.sh, not a news outlet; a search found
    no such ruling. Fox Sagar item said 35 acres and 15 acres in the same item, and named a political family.
    ACB item named an official. Founder takes overstate ("means nothing", "proving").
- **Suggested fix for the Spark prompt** (Saif to paste into Spark):
  > Only use established news outlets: The Hindu, Times of India, Deccan Chronicle, Telangana Today, Siasat,
  > Economic Times, Business Standard, The News Minute, or official government sites. For every item, give the
  > publish date, the exact numbers as printed in the article, and a "Do not say" line. Do not name private
  > individuals or officials in stories about raids, demolitions or court cases. Keep the founder take to what
  > the article actually says.

## Files (all in `daily_content/`)

| File | What it does |
|---|---|
| `DAILY_RUN.md` | The full rules and steps for one daily run (fact rules, brand rules, Arjun voice, formats, save) |
| `run_daily.ps1` | Task Scheduler entry point: pulls the repo, starts a fresh headless `claude -p` run, logs to `<out>\logs` |
| `render_carousel.js` | Slides JSON to a 1080x1350 PDF. Fails with the slide number if text overflows |
| `example_day.json` | A finished carousel in Arjun's voice (the format to copy) |
| `fetch_feed.py` | Prints the newest Signal Feed docs as text via the Drive API |
| `publish.py` | Cloud-only: uploads a day to Drive. Not needed on the PC |

`drive.py` (repo root) also reads `GOOGLE_TOKEN_JSON` if `token.json` is missing.

**Carousel design:** ivory `#F7F3EC`, charcoal `#1A1A1A`, antique gold `#B48A3C` (numbers, rules, labels only),
stone `#6E6A63`. DM Serif Display for titles, Instrument Sans for body (both in `fonts/`, embedded in the PDF).
Footer is blank by default (no HOI branding on Arjun's profile). Cover and close slides are dark.

## Local setup (office PC)

1. `git fetch origin; git checkout main-rpcp44; git pull`
2. Node.js LTS, then in the repo: `npm install playwright` and `npx playwright install chromium`
3. `token.json` next to `drive.py` (already there from the Content Engine). Claude Code installed and signed in.
4. Choose the output drive: `setx HOI_OUTPUT_DIR "D:\HOI Content"` (any path; default is Documents\HOI Daily Content)
5. Test: `powershell -ExecutionPolicy Bypass -File daily_content\run_daily.ps1`
6. Task Scheduler: daily 7:22 pm, `powershell -ExecutionPolicy Bypass -File "<repo>\daily_content\run_daily.ps1"`,
   "Run only when user is logged on". The PC must be on.

Output per day: `<date> Content.md`, `<date> LinkedIn carousel.pdf`, `<date> carousel.json`.
To fix one slide: edit the JSON, then `node daily_content/render_carousel.js "<json>" "<pdf>"`.

## Token savings already built in

- Fresh short session each day that reads only `DAILY_RUN.md` (not a long chat history).
- Renderer checks overflow itself, so no slide images need to be opened.
- One quick web search only for the 2 or 3 items actually used.
- Long-form article once a week, not daily.

## HeyGen (in progress)

- Saif has a HeyGen account. Arjun sir's avatar isn't made yet.
- He must record HeyGen's consent statement himself, live, in the same session as the footage.
- Footage: vertical 9:16, 1080p or 4K, tripod at eye level, soft front light, plain quiet room, same plain
  outfit with no logo. Speak calmly in Tenglish, pause with mouth closed, small hand movements.
  HeyGen says about 15 s is enough for the current engine; shoot 2 minutes for spare takes.
- Clone his voice from Tenglish speech, not English only.
- Then test one 20 s video from each script form and pick one.
- When ready, put in the PC's `.env`: `HEYGEN_API_KEY`, `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID`.
  Open question for Saif: should Claude send scripts to HeyGen and save the videos, or keep writing scripts only?
- Suggest a small "AI avatar" note in his bio (platform AI labels).

## Pending

1. HeyGen avatar, voice and the three IDs (above).
2. Saif to paste the Spark prompt fix (above).
3. PR for `main-rpcp44` into `main` isn't open (the GitHub tool failed in the cloud):
   https://github.com/Saif-7122/Runpod_deployment/compare/main...main-rpcp44
4. The public repo holds about 612 ad work files under `ads/work/` and `ads/refs/` (from a desktop WIP snapshot),
   including two saved Google Drive pages, one showing a Gmail address. Offer to remove `ads/work/` and add it
   to `.gitignore`. Removing from history needs a rewrite and force push: Saif decides.
5. Once the PC run works, delete the cloud schedule "HOI daily content" (trig_01D8CGUgyzHA3B98rEvXFjbD), which
   fires into the old cloud session daily at 7:22 pm IST. Delete it from claude.ai (scheduled tasks), or tell
   the cloud session to.
6. The Drive output folder "HOI Daily Content" (`1PObUk5Z0GpFxYox2eI_b0_RtT_yVEqpz`) holds the 4 Nov pilot.
   It's no longer used once the PC runs locally.

## Approved sample (Arjun's voice)

Tweet:
> HYDRAA pulled out 7 commercial borewells and broke 6 sumps in Tellapur this week.
>
> Everyone checks the clubhouse. Nobody asks where the water comes from.
>
> Municipal line or tankers. Get it in writing before the token.

Reel lines (Tenglish, English letters):
1. Tellapur lo villa chustunnara? Price kaadu, mundu neellu gurinchi adagandi.
2. Ee week HYDRAA Tellapur lo seven commercial borewells teesesindi. Six sumps kooda break chesindi.
3. Andaru brochure lo clubhouse chustaru. Water source evaru chudaru.
4. Konni projects tankers meeda nadustayi. Tankers aagipothe, neellu ekkada nunchi?
5. Municipal line unda, leka tankers aa? Okka question. Answer writing lo undali.
6. Entha pedda villa aina, neellu lekapothe adi problem ye.

## Saif's standing preferences

Simple Indian English, short sentences, "you", contractions. No em or en dashes. No filler, no AI phrasing.
Lead with the answer. HOI is a wealth house: never broker, brokerage, agent, agency or channel partner.
