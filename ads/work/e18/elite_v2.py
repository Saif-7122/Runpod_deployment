import subprocess, os

HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--green:#2d5a3d;--deep:#0f281a;--mint:#c4e6cd;--cream:#eef5ee}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:@Wpx;height:@Hpx;background:var(--deep);overflow:hidden;font-family:'DM Sans',sans-serif;font-variant-numeric:lining-nums}
.ad{position:relative;width:@Wpx;height:@Hpx;overflow:hidden;background:var(--deep)}
.abs{position:absolute}
.ph{background-repeat:no-repeat;background-size:cover}
.hl{font-family:Marcellus,serif;color:#fff;line-height:1.04;text-shadow:0 2px 24px rgba(0,0,0,.85),0 0 8px rgba(0,0,0,.55)}
.sub{font-size:30px;font-weight:500;color:#fff;margin-top:14px;text-shadow:0 2px 14px rgba(0,0,0,.75)}
.logo{filter:drop-shadow(0 2px 8px rgba(0,0,0,.55))}
.glass{background:rgba(14,38,26,.60);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.14);border-radius:24px}
.lab{white-space:nowrap;font-size:22px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--mint)}
.big{font-weight:500;color:#fff;line-height:1.08}
.btn{background:var(--cream);color:var(--deep);font-weight:700;font-size:32px;padding:20px 50px;border-radius:60px;white-space:nowrap}
.phone{display:flex;align-items:center;gap:12px;color:#fff;font-weight:700;font-size:38px;white-space:nowrap}
.phone svg{width:36px;height:36px;fill:none;stroke:var(--mint);stroke-width:2.2;stroke-linejoin:round}
.fn{font-size:16px;color:#fff;text-shadow:0 1px 8px rgba(0,0,0,.8)}
svg.i{fill:none;stroke:var(--mint);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}
</style></head><body><div class="ad">'''
TAIL = '</div></body></html>'
PH = '<svg viewBox="0 0 24 24"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/></svg>'
PHONE = '<div class="phone">' + PH + '+91 79935 44699</div>'
RUPEE = '<svg class="i" viewBox="0 0 48 48"><circle cx="24" cy="24" r="20"/><path d="M16 14h16M16 20h16M16 14c8 0 10 4 6 8-2 2-5 3-8 3l10 11"/></svg>'
PLOT = '<svg class="i" viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32"/><path d="M8 18h7M8 26h4M8 34h7M30 40v-6M22 40v-4"/></svg>'
PIN = '<svg class="i" viewBox="0 0 48 48"><path d="M24 43S9 29 9 19a15 15 0 0 1 30 0c0 10-15 24-15 24z"/><circle cx="24" cy="19" r="5"/></svg>'
LOC = 'Near Chilkur, Hyderabad'
FNT = '*Indicative. Final pricing set by the developer.'


def sz(s, n):
    return s.replace('<svg class="i"', '<svg width="%d" height="%d" class="i"' % (n, n))


def bg(img, pos, img2=None):
    s = f'<div class="abs ph" style="left:0;top:0;width:1080px;height:1920px;background-image:url({img});background-position:{pos}"></div>'
    if img2:  # low-res hero: sharp top photo + second photo blended below, no empty space
        s = (f'<div class="abs ph" style="left:0;top:0;width:1080px;height:1100px;background-image:url({img});background-position:{pos}"></div>'
             f'<div class="abs ph" style="left:0;top:960px;width:1080px;height:960px;background-image:url({img2});background-position:50% 50%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 45%,#000 100%)"></div>')
    return s


def head(hl, sub, base=104):
    size = base if len(hl) <= 22 else base - 14
    return (f'<div class="abs" style="left:0;top:0;width:1080px;height:560px;background:linear-gradient(180deg,rgba(10,26,26,.38),rgba(10,26,26,0))"></div>'
            f'<img class="abs logo" style="right:56px;top:290px;width:150px" src="logo_light.png">'
            f'<div class="abs" style="left:56px;top:326px;width:830px"><div class="hl" style="font-size:{size}px">{hl}</div><div class="sub">{sub}</div></div>')


def feat_row():
    return f'''<div style="display:grid;grid-template-columns:.8fr 1.1fr 1.5fr;align-items:center">
  <div style="display:flex;gap:12px;align-items:center">{sz(RUPEE,40)}<div><div class="lab">Starting from</div><div class="big" style="font-size:34px;margin-top:6px">₹3.5 Cr*</div></div></div>
  <div style="display:flex;gap:12px;align-items:center;padding-left:20px;border-left:1px solid rgba(196,230,205,.45)">{sz(PLOT,40)}<div><div class="lab">Plot size</div><div class="big" style="font-size:34px;margin-top:6px;white-space:nowrap">682–1,246 Sq. Yd</div></div></div>
  <div style="display:flex;gap:12px;align-items:center;padding-left:20px;border-left:1px solid rgba(196,230,205,.45)">{sz(PIN,40)}<div><div class="lab">Location</div><div class="big" style="font-size:34px;margin-top:6px">{LOC}</div></div></div>
</div>'''


def L1(bgh, hl, sub):
    return HEAD + bgh + head(hl, sub) + f'''
<div class="abs glass" style="left:40px;right:40px;top:1380px;padding:34px 32px">{feat_row()}</div>''' + f'''
<div class="abs glass" style="left:0;right:0;top:1660px;height:260px;border-radius:0;border-width:1px 0 0 0;background:rgba(14,38,26,.78);padding:0 56px 64px;display:flex;align-items:center;justify-content:space-between">{PHONE}<div class="btn">Learn More</div></div>
<div class="abs fn" style="left:56px;top:1868px">{FNT}</div>''' + TAIL


def L2(bgh, hl, sub):
    return HEAD + bgh + head(hl, sub) + f'''
<div class="abs glass" style="left:40px;top:1130px;width:600px;padding:34px 34px 34px">
  <div style="display:flex;align-items:center;gap:18px;padding-bottom:22px;border-bottom:1px solid rgba(196,230,205,.4)">{sz(RUPEE,52)}<div><div class="lab">Starting from</div><div class="big" style="font-size:54px;margin-top:5px">₹3.5 Cr*</div></div></div>
  <div style="display:flex;align-items:center;gap:18px;padding:22px 0;border-bottom:1px solid rgba(196,230,205,.4)">{sz(PLOT,52)}<div><div class="lab">Plot size</div><div class="big" style="font-size:42px;margin-top:5px;white-space:nowrap">682–1,246 Sq. Yd</div></div></div>
  <div style="display:flex;align-items:center;gap:18px;padding:22px 0">{sz(PIN,52)}<div><div class="lab">Location</div><div class="big" style="font-size:42px;margin-top:5px">{LOC}</div></div></div>
</div>''' + f'''
<div class="abs glass" style="left:0;right:0;top:1660px;height:260px;border-radius:0;border-width:1px 0 0 0;background:rgba(14,38,26,.78);padding:0 56px 64px;display:flex;align-items:center;justify-content:space-between">{PHONE}<div class="btn">Learn More</div></div>
<div class="abs fn" style="left:56px;top:1868px">{FNT}</div>''' + TAIL


def L3(bgh, hl, sub):
    return HEAD + bgh + head(hl, sub) + f'''
<div class="abs" style="left:0;top:1400px;width:1080px;height:200px;background:rgba(45,90,61,.94);display:flex;align-items:center;justify-content:space-between;padding:0 56px">
  <div><div class="lab">Starting from</div><div class="big" style="font-size:78px;margin-top:6px">₹3.5 Cr*</div></div>
  <div style="text-align:right;color:#fff;font-size:38px;font-weight:500;line-height:1.2"><div>682–1,246 Sq. Yd</div><div style="margin-top:6px">{LOC}</div></div>
</div>
''' + f'''
<div class="abs glass" style="left:0;right:0;top:1660px;height:260px;border-radius:0;border-width:1px 0 0 0;background:rgba(14,38,26,.78);padding:0 56px 64px;display:flex;align-items:center;justify-content:space-between">{PHONE}<div class="btn">Learn More</div></div>
<div class="abs fn" style="left:56px;top:1868px">{FNT}</div>''' + TAIL


def W(img, pos, hl, sub, left=0, width=1280):
    size = 62 if len(hl) <= 22 else 52
    return HEAD + f'''
<div class="abs ph" style="left:{left}px;top:0;width:{width}px;height:720px;background-image:url({img});background-position:{pos}"></div>
<img class="abs logo" style="right:44px;top:34px;width:130px" src="logo_light.png">
<div class="abs glass" style="left:36px;top:36px;width:540px;height:648px;padding:32px 34px;display:flex;flex-direction:column;justify-content:space-between">
  <div><div class="hl" style="font-size:{size}px">{hl}</div><div class="sub" style="font-size:22px;margin-top:10px">{sub}</div></div>
  <div>
    <div style="display:flex;align-items:center;gap:16px;padding-bottom:11px">{sz(RUPEE,34)}<div><div class="lab" style="font-size:18px">Starting from</div><div class="big" style="font-size:30px;margin-top:3px">₹3.5 Cr*</div></div></div>
    <div style="display:flex;align-items:center;gap:16px;padding:11px 0;border-top:1px solid rgba(196,230,205,.4)">{sz(PLOT,34)}<div><div class="lab" style="font-size:18px">Plot size</div><div class="big" style="font-size:30px;margin-top:3px">682–1,246 Sq. Yd</div></div></div>
    <div style="display:flex;align-items:center;gap:16px;padding:11px 0;border-top:1px solid rgba(196,230,205,.4)">{sz(PIN,34)}<div><div class="lab" style="font-size:18px">Location</div><div class="big" style="font-size:30px;margin-top:3px">{LOC}</div></div></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;padding-top:14px;border-top:1px solid rgba(196,230,205,.4)"><div class="phone" style="font-size:26px">{PH}+91 79935 44699</div><div class="btn" style="font-size:20px;padding:13px 34px">Learn More</div></div>
    <div class="fn" style="margin-top:10px;font-size:12px">{FNT}</div>
  </div>
</div>''' + TAIL


D = [
    (1, 'the-garden-residence', 'The Garden Residence', 'Ground + first floor villas, 2,930–3,097 sft built-up', L1, '50% 50%', None, dict(pos='35% 50%', left=360, width=920)),
    (2, 'sunken-seating', 'Gather Around the Fire', 'Outdoor sunken seating in your own garden', L3, '50% 50%', 'hero03.jpg', dict(pos='60% 50%', left=300, width=980)),
    (3, 'fruit-garden', 'Taste the Seasons', 'Grown within your own garden', L2, '62% 50%', None, dict(pos='50% 50%')),
    (4, 'kitchen-garden', 'From Tree to Table', 'The luxury of growing your own', L1, '50% 50%', None, dict(pos='50% 50%')),
    (5, 'street-view', 'A Path That Quiets the Mind', '30 ft wide roads, lined with greenery', L2, '55% 50%', None, dict(pos='50% 50%')),
    (6, 'quiet-escape', 'A Quiet Escape', 'Swimming pool under the open sky', L3, '60% 50%', None, dict(pos='60% 50%')),
    (7, 'pickleball', 'Pickleball, at Home', 'A community for mind, body, heart and soul', L3, '40% 50%', 'hero04.jpg', dict(pos='65% 50%', left=300, width=980)),
    (8, 'recharge', 'Recharge Between Victories', 'Solitude amenities, six acres of calm', L1, '47% 50%', None, dict(pos='45% 50%', left=420, width=860)),
    (9, 'six-acres', 'Six Acres of Breathing Space', 'Moinabad–Shankarpally’s low-density green zone', L2, '58% 50%', None, dict(pos='50% 50%')),
    (10, 'solitude-living', 'Solitude Living', 'The luxury few talk about', L3, '50% 30%', None, dict(pos='50% 30%', left=500, width=780)),
]
E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
os.makedirs('v2', exist_ok=True)


def shot(html, hname, out, w, h, sc):
    html = html.replace('@W', str(w)).replace('@H', str(h))
    open(hname, 'w', encoding='utf-8').write(html)
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=%s' % sc,
                    '--window-size=%d,%d' % (w, h), '--virtual-time-budget=12000', '--screenshot=' + out,
                    'file:///' + os.path.abspath(hname).replace(chr(92), '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


for i, slug, hl, sub, lay, pos, img2, w in D:
    img = 'hero%02d.jpg' % i
    shot(lay(bg(img, pos, img2), hl, sub), 'v2_916_%02d.html' % i, os.path.abspath('v2/E18_%02d_%s_9x16.png' % (i, slug)), 1080, 1920, 1.333333)
    shot(W(img, w['pos'], hl, sub, w.get('left', 0), w.get('width', 1280)), 'v2_169_%02d.html' % i, os.path.abspath('v2/E18_%02d_%s_16x9.png' % (i, slug)), 1280, 720, 1.5)
    print(i)
