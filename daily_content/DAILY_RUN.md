# HOI daily content run

Every day: read the newest Signal Feed, write 2 tweets, 1 LinkedIn carousel, and 1 Arjun sir POV reel script.
Save it all to Drive under `HOI Daily Content/<YYYY-MM-DD>/`. Nothing is posted; the team posts by hand.

## Inputs

- News folder (Google Drive, "daily market news"): `1fhCDLbTeJ1-ZmtN9HZ6MLgF716tGLf13`.
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

## What to write

1. **Tweet 1 and Tweet 2.** Each under 270 characters, on different items. A fact, then what the buyer should do.
   No hashtags in tweets.
2. **LinkedIn carousel.** 5 to 7 slides on one idea, plus a post caption (under 1,300 characters, 3 to 5 hashtags).
   Build the slides as JSON (`{"date": ..., "carousel": {"slides": [...], "source": "Source: ..., <date>. For
   information only, not investment advice."}}`). Slide types: cover {kicker, title, sub}, fact {label, big, text},
   list {title, items}, note {title, text}, close {title, text, cta}. Start with a cover and end with a close.
   Keep titles under 9 words, "big" under 10 characters, and list items under 14 words each.
   Render with `node daily_content/render_carousel.js day.json carousel.pdf`, then rasterise the pages
   (`pdftoppm -r 40 -png`) and look at every slide. Fix any overflow before you upload.
3. **Instagram reel, Arjun sir POV (for HeyGen).** 35 to 45 seconds, one idea, first person.
   - On-screen hook for the first 2 seconds.
   - The script in Tenglish, in English letters (about 90 to 110 words).
   - The same script with the Telugu words in Telugu script and the English words in English.
   - English captions, one per script line.
   - An Instagram caption with 3 to 5 hashtags.
   - End line: "Nenu Arjun, House of Investors." plus one simple action.
4. **Do not say** (3 lines for this day's topics) and **Sources** (name, date, URL for each item used).
5. **Checks**: the items held back, and why.

## Save

Write the copy as Markdown (`day.md`) with these headings: Tweet 1 (X), Tweet 2 (X), LinkedIn: carousel,
Instagram reel: Arjun sir POV, Do not say, Sources, Checks. Then:

- If `GOOGLE_TOKEN_JSON` is set: `pip install -q -r requirements.txt` and run
  `python3 daily_content/publish.py --date <date> --doc day.md --pdf carousel.pdf`.
- If not: create the `<date>` folder and the "<date> Content" Google Doc with the Google Drive connector
  (create_file, contentMimeType text/markdown), and add a line at the top of the doc:
  "Carousel PDF not uploaded: GOOGLE_TOKEN_JSON is missing in the cloud environment."

Last, sweep the doc for em/en dashes and the banned words, and finish with the Drive folder link.
