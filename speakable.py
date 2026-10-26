"""Turn on-screen text into text a TTS voice reads naturally: '25,000' -> 'twenty-five thousand',
'₹70 lakhs' -> 'seventy lakhs', '450+' -> 'over four hundred and fifty', '+91 81217 77770' -> digit by digit."""
import re

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
        "seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num_words(n):
    n = int(n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return _ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + num_words(rest))
    for size, name in ((10_000_000, "crore"), (100_000, "lakh"), (1000, "thousand")):
        if n >= size:
            rest = n % size
            head = num_words(n // size) + " " + name
            if rest == 0:
                return head
            return head + (" and " if rest < 100 else " ") + num_words(rest)
    return str(n)


def speakable(text):
    t = text
    t = re.sub(r"\+?91[\s-]?(\d{5})[\s-]?(\d{5})", lambda m: " ".join(m.group(1) + m.group(2)), t)  # phone
    t = re.sub(r"PM\s?2\.5", "P M two point five", t)
    t = t.replace("24/7", "twenty-four seven").replace("sq yd", "square yards").replace("sq. yd", "square yards")
    t = re.sub(r"₹\s?", "", t)
    t = re.sub(r"(\d[\d,]*)\+", lambda m: "over " + num_words(m.group(1).replace(",", "")), t)
    t = re.sub(r"(\d+)\s?%", lambda m: num_words(m.group(1)) + " percent", t)
    t = re.sub(r"\d[\d,]*", lambda m: num_words(m.group(0).replace(",", "")), t)
    t = t.replace("&", " and ")
    return re.sub(r"\s+", " ", t).strip()
