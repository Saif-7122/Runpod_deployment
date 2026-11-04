# HOI daily content run

Every day: read the newest Signal Feed, write 2 tweets, 1 LinkedIn carousel, and 1 Arjun sir POV reel script.
Save it all to Drive under `HOI Daily Content/<YYYY-MM-DD>/`. Nothing is posted; the team posts by hand.

## Inputs

- News folder (Google Drive, "daily market news"): `1fhCDLbTeJ1-ZmtN9HZ6MLgF716tGLf13`.
  With `GOOGLE_TOKEN_JSON` set, read it with `python3 daily_content/fetch_feed.py` (Saturdays: `--n 7`);
  otherwise use the Google Drive connector.
  Use the newest "Signal Feed <date>" doc. If today's isn't there, use yesterday's and say so at the top of the doc.
  Use any item in the feed, not only the ones listed "For Arjun".
- Output folder (Google Drive, "HOI Daily Content"): `1PObUk5Z0GpFxYox2eI_b0_RtT_yVEqpz`.
- Before writing, check what the last 3 days' output folders covered and don't repeat a topic.

## Fact rules (apply before writing anything)

1. Only use an item if its source is an established outlet (The Hindu, Times of India, Deccan Chronicle,
   Telangana Today, Siasat, Economic Times, Business Standard, Mint, The News Minute, Hyderabad Mail, Hubbis)
   or an official government site. Do a quick web search to back up the main fact.
   If you can't, hold the item and list it under "Checks".
2. Use the numbers exactly as the feed or source prints them. If the feed contradicts itself, hold the item.
3. Never name private people, officials or political families in raid, demolition or court stories.
   Tell the lesson without the names.
4. No predictions about prices, rates or the rupee. No returns or appreciation promises. Not legal or tax advice.

## Brand rules

- HOI is a real estate wealth house. Never say broker, brokerage, agent, agency or channel partner.
- No em dashes or en dashes anywhere. Use commas or colons.
- Simple Indian English, short sentences, "you", contractions. No AI phrasing ("delve", "unlock", "seamless",
  "in today's world", "it's important to note"). Lead with the number or the fact.

## Arjun sir's voice (all pieces post on his profiles)

- He is a senior industry insider sharing what he knows. Not a salesman, not a brand page.
- **No CTA of any kind.** No "talk to us", "DM me", "book a visit", "link in bio", "follow for more".
- **No advertising.** Don't mention House of Investors, HOI, its projects, its desk or its services.
  No sign-off line. He doesn't introduce himself.
- Attitude: calm, blunt, a little unbothered. He has seen every cycle and doesn't need your business.
  States the fact, says what it really means, says what most people get wrong, and stops.
  No hype, no fear-selling, no exclamation marks, no "guys", no "must watch".
- He can disagree with the popular take, but always with a fact behind it.
- Ending: a sharp last line (an observation, a question the reader should ask themselves, or a rule
  of thumb). Never an ask.

## What to write

1. **Tweet 1 and Tweet 2.** Each under 270 characters, on different items. A fact, then what the buyer should do.
   No hashtags in tweets.
2. **LinkedIn carousel.** 5 to 7 slides on one idea (the close slide has a rule of thumb in "cta", never an ask,
   and no brand line), plus a post caption (under 1,300 characters, 3 to 5 hashtags).
   Build the slides as JSON (`{"date": ..., "carousel": {"footer": "", "slides": [...], "source": "Source: ..., <date>. For
   information only, not investment advice."}}`). Slide types: cover {kicker, title, sub}, fact {label, big, text},
   list {title, items}, note {title, text}, close {title, text, cta}. Start with a cover and end with a close.
   Keep titles under 9 words, "big" under 10 characters, and list items under 14 words each.
   Render with `node daily_content/render_carousel.js day.json carousel.pdf`. It exits with an error that names
   the slide if any text overflows; shorten that slide and render again. Don't open the slide images
   (saves tokens) unless the renderer reports a problem you can't fix from the message.
3. **Instagram reel, Arjun sir POV (for HeyGen).** 35 to 45 seconds, one idea, first person.
   - On-screen hook for the first 2 seconds.
   - The script in Tenglish, in English letters (about 90 to 110 words).
   - The same script with the Telugu words in Telugu script and the English words in English.
   - English captions, one per script line.
   - An Instagram caption with 3 to 5 hashtags.
   - Last line: a sharp observation or rule of thumb. No sign-off, no name, no ask.
4. **LinkedIn article (Saturdays only).** 600 to 900 words on the week's biggest theme, using items from the
   last 7 feeds. A title, 4 or 5 short sections with plain headings, one table or list of numbers if it helps.
   Same voice: no CTA, no brand. Add it to the Saturday doc under "LinkedIn article".
5. **Do not say** (3 lines for this day's topics) and **Sources** (name, date, URL for each item used).
6. **Checks**: the items held back, and why.

## Save

Write the copy as Markdown (`day.md`) with these headings: Tweet 1 (X), Tweet 2 (X), LinkedIn: carousel,
Instagram reel: Arjun sir POV, LinkedIn article (Saturdays), Do not say, Sources, Checks. Then:

- If `GOOGLE_TOKEN_JSON` is set: `pip install -q -r requirements.txt` and run
  `python3 daily_content/publish.py --date <date> --doc day.md --pdf carousel.pdf`.
- If not: create the `<date>` folder and the "<date> Content" Google Doc with the Google Drive connector
  (create_file, contentMimeType text/markdown), and add a line at the top of the doc:
  "Carousel PDF not uploaded: GOOGLE_TOKEN_JSON is missing in the cloud environment."

Last, sweep the doc for em/en dashes and the banned words, and finish with the Drive folder link.
