# HOI daily content run

Every day, for Arjun Veera's own profiles: 1 short tweet, 1 article (LinkedIn version and X version),
1 LinkedIn carousel, and 1 Instagram reel script for HeyGen. Nothing is posted; the team posts by hand.

## Inputs

- News: Google Drive folder "daily market news" (`1fhCDLbTeJ1-ZmtN9HZ6MLgF716tGLf13`).
  Read it with `python daily_content/fetch_feed.py` (uses the PC's token.json). Saturdays: `--n 7`.
  Use the newest "Signal Feed <date>" doc. If today's isn't there, use yesterday's and say so at the top.
  Use any item, not only the "For Arjun" ones.
- Don't repeat a topic: read the `Content.md` files in the last 3 date folders under the output folder.

## Fact rules (before writing anything)

1. Only use an item if an established outlet reports it (The Hindu, Times of India, Deccan Chronicle,
   Telangana Today, Siasat, Economic Times, Business Standard, Mint, The News Minute, Hyderabad Mail, Hubbis)
   or an official government site. Do one quick web search per item you use to back up the main fact.
   If you can't, hold the item and list it under "Checks".
2. Use numbers exactly as the source prints them. If the feed contradicts itself, hold the item.
   If the feed's date is wrong (old news called "past 24 hours"), use the real date or hold it.
3. Never name private people, officials or political families in raid, demolition or court stories.
4. No predictions about prices, rates or the rupee. No returns or appreciation promises. Not legal or tax advice.
5. Never invent a story, a client, a quote or a number to make a point. "Say you have a ₹50 lakh flat" is fine
   (clearly an example). "Last week a client of mine lost ₹40 lakh" is not, unless it's in the source.

## Plain language: zero thinking needed

Write so a 12 year old and a 70 year old both get it on the first read, without stopping once.

- One idea per sentence. Most sentences under 12 words, none over 18. Paragraphs of 1 to 3 short lines.
- Everyday words only. If a word needs a second to understand, swap it.
  "Liquidity" is "how fast you can sell and get your money". "Encumbrance" is "any loan or case on the land".
- Any technical term gets explained in plain words the first time, or it goes.
  FTL: "the lake's full water line". STP: "the building's own sewage treatment plant". Benami: "property kept in
  someone else's name". MLD: convert to litres ("10 crore litres a day").
- Indian numbers and money: ₹, lakh, crore. Never million or billion. "₹1.2 crore", not "₹12 million".
- Indian English, the way people here actually talk: flat, society, builder, plot, token amount, registration,
  EMI, rent, lift, colony. British spelling: centre, neighbour, metre. No American words (condo, realtor, zip code).
- Make it relatable. Tie each idea to normal life: EMI, school fees, rent going up, the plot your parents bought,
  the cousin who "got a good deal". One everyday example per piece.
- Lead with the fact or the number. Then what it means. Then what to do. Then stop.
- Read-aloud test: it should sound like Arjun explaining over chai, not a news anchor or a consultant.

## No AI writing (check every line)

- Banned words: delve, unlock, seamless, navigate, landscape, leverage, robust, crucial, pivotal, vital, key (as an
  adjective), comprehensive, holistic, empower, elevate, curated, bespoke, iconic, world-class, nestled, testament,
  tapestry, underscore, showcase, foster, enhance, journey, game changer, in today's world, it's important to note,
  at its core, the real question, here's the thing, let's dive in, let's break it down, honestly?, buckle up.
- Banned shapes:
  - "It's not X, it's Y" and "Not only X but also Y".
  - Lists of three for rhythm ("safe, simple and smart").
  - Sentences ending in "-ing" add-ons ("..., showing how the market is changing").
  - Stacked punchy fragments ("No noise. No hype. Just facts.").
  - Fake wisdom lines ("Land is the new gold", "Water is the currency of the future").
  - Vague authority ("experts say", "reports suggest") with no named source.
  - Big conclusions ("The future looks bright", "This changes everything").
  - Bold on random phrases, emojis, Title Case headings, curly quotes, hashtag stuffing.
- No em dashes or en dashes anywhere. Use a full stop, comma or colon. For ranges write "to".

## Brand rules

- HOI is a real estate wealth house. Never say broker, brokerage, agent, agency or channel partner.
- These are Arjun's personal posts: don't mention House of Investors, HOI, its projects or its services.

## Arjun sir's voice

- A senior insider and a top wealth advisor who has seen every cycle. He shares what he knows. He isn't selling.
- No CTA of any kind: no "DM me", "talk to us", "book a visit", "link in bio", "follow for more". No sign-off.
  He never introduces himself.
- Calm, blunt, a little unbothered. States the fact, says what it really means, says what most people get wrong,
  and stops. No hype, no fear-selling, no exclamation marks, no "guys".
- He can disagree with the popular view, but always with a fact behind it.
- Last line: a sharp observation, a question the reader should ask themselves, or a rule of thumb. Never an ask.

## What to write

### 1. Tweet (X)

One tweet, under 200 characters. The fact, then what it means for you. No hashtags.

### 2. Article (on the day's main topic)

- **LinkedIn article:** 400 to 600 words. A plain title that states the point (no clickbait). 3 or 4 short
  sections with plain headings. Open with the fact in the first line. One small table or list of numbers if it helps.
  End on a rule of thumb. On Saturdays, cover the week's biggest theme using the last 7 feeds.
- **X long post:** the same article cut to 150 to 250 words. No headings. Short lines with a blank line between.
  Same last line.

### 3. LinkedIn carousel (a top wealth advisor teaching one thing)

- 5 to 7 slides on one idea. Teach one simple rule or a 3 to 4 step check the reader can use today.
  Numbers first. Every slide must make sense to someone who only reads that slide.
- Slide JSON: `{"date": ..., "carousel": {"footer": "", "slides": [...], "source": "Source: <outlet>, <date>.
  For information only, not investment advice."}}`
- Slide types: cover {kicker, title, sub}, fact {label, big, text}, list {title, items},
  note {label, title, text}, close {title, text, cta}. Start with a cover, end with a close.
  The close slide's "cta" is a short label like "Rule of thumb", never an ask, and no brand line.
- Limits: titles under 9 words, "big" under 10 characters, list items under 14 words.
- Post caption: under 1,300 characters, same plain style, 3 to 5 hashtags at the end.
- Render with `node daily_content/render_carousel.js day.json carousel.pdf`. If it names a slide that overflows,
  shorten that slide and render again. Don't open slide images unless the renderer reports something you can't fix.

### 4. Instagram reel: Arjun sir POV (for HeyGen, fast news explainer)

Format: a fast, clear news explainer. One talking head, the real news on screen behind him, quick cuts,
big captions. Copy the style only: never use another creator's name, catchphrases or footage.

- Length 45 to 60 seconds. Voice: Tenglish (Telugu and English mixed), spoken fast and clear.
- Shape:
  1. **Hook (0 to 3 s):** the most surprising fact, said in the very first line. No "hi", no intro.
  2. **What happened (3 to 15 s):** the news in plain words, with the exact number.
  3. **How it works (15 to 35 s):** explain it with one everyday comparison anyone gets.
  4. **What it means for you (35 to 50 s):** the effect on a normal family buying or owning property.
  5. **Last line:** a rule of thumb. No sign-off, no name, no ask.
- Write it as numbered beats. For each beat give:
  - Spoken line, Tenglish in English letters.
  - The same line with Telugu words in Telugu script and English words in English
    (keep both forms until Saif picks one after the HeyGen test).
  - English caption.
  - On screen: 2 to 5 words of big text, and the visual (a screenshot of the real source headline, a simple
    number card, a map, or plain B-roll). Only screenshot the actual article used, and give its URL.
  - Edit note: cut every 2 to 3 seconds, punch-in zoom on the key number, highlight the key line on the
    headline screenshot, a light sound hit on cuts, no music swell, no emojis.
- Also give an on-screen hook line for the first 2 seconds and an Instagram caption with 3 to 5 hashtags.
- Total script about 120 to 150 words.

### 5. Do not say, Sources, Checks

- **Do not say:** 3 lines on what to avoid for today's topics (wrong numbers, claims the source doesn't make).
- **Sources:** outlet, date and URL for each item used.
- **Checks:** the items held back, and why.

## Save (LOCAL mode, the default)

The prompt names an output folder (`<out>/<date>`). Create it and save:
- `<date> Content.md` with these headings: Tweet (X), LinkedIn article, X long post, LinkedIn carousel,
  Instagram reel: Arjun sir POV, Do not say, Sources, Checks.
- `<date> LinkedIn carousel.pdf` (render straight to this path).
- `<date> carousel.json` (so a slide can be fixed and re-rendered by hand).
Don't upload anything.

CLOUD mode (only if the prompt says so): `python3 daily_content/publish.py --date <date> --doc day.md --pdf carousel.pdf`.

## Final sweep

1. Search the copy for em dashes, en dashes, the banned words and the banned brand words. Fix every hit.
2. Read each piece once as a 12 year old and once as a 70 year old. Fix anything either would stop at.
3. Check every number against its source.
4. Finish with the folder path and a 3 line summary: what you made, which items you held back, and why.
