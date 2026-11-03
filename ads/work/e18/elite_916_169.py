import subprocess, os

HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--green:#2d5a3d;--deep:#0f281a;--mint:#bfe0c8;--cream:#eef5ee}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:@Wpx;height:@Hpx;background:var(--deep);overflow:hidden;font-family:'DM Sans',sans-serif;font-variant-numeric:lining-nums}
.ad{position:relative;width:@Wpx;height:@Hpx;overflow:hidden;background:var(--deep)}
.abs{position:absolute}
.ph{background-repeat:no-repeat;background-size:cover}
.hl{font-family:Marcellus,serif;color:#fff;line-height:1.04;text-shadow:0 3px 22px rgba(0,0,0,.45)}
.sub{font-size:30px;font-weight:500;color:#eaf3ea;margin-top:14px;text-shadow:0 2px 12px rgba(0,0,0,.55)}
.logo{width:170px}
.lab{white-space:nowrap;font-size:24px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--mint);text-shadow:0 1px 10px rgba(0,0,0,.5)}
.big{font-weight:500;color:#fff;line-height:1.05;text-shadow:0 2px 12px rgba(0,0,0,.45)}
.btn{background:var(--cream);color:var(--deep);font-weight:700;font-size:34px;padding:22px 56px;border-radius:60px;white-space:nowrap}
.phone{display:flex;align-items:center;gap:14px;color:#fff;font-weight:700;font-size:40px;white-space:nowrap}
.phone svg{width:38px;height:38px;fill:none;stroke:var(--mint);stroke-width:2.2;stroke-linejoin:round}
.fn{font-size:16px;color:#a9c4b0}
svg.i{fill:none;stroke:var(--mint);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
</style></head><body><div class="ad">'''
TAIL = '</div></body></html>'
PH = '<svg viewBox="0 0 24 24"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/></svg>'
PHONE = '<div class="phone">' + PH + '+91 79935 44699</div>'
RUPEE = '<svg class="i" viewBox="0 0 48 48"><circle cx="24" cy="24" r="20"/><path d="M16 14h16M16 20h16M16 14c8 0 10 4 6 8-2 2-5 3-8 3l10 11"/></svg>'
PLOT = '<svg class="i" viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32"/><path d="M8 18h7M8 26h4M8 34h7M30 40v-6M22 40v-4"/></svg>'
PIN = '<svg class="i" viewBox="0 0 48 48"><path d="M24 43S9 29 9 19a15 15 0 0 1 30 0c0 10-15 24-15 24z"/><circle cx="24" cy="19" r="5"/></svg>'
LOGO = '<img class="abs logo" src="logo_light.png">'
FN = '<div class="abs fn" style="left:65px;top:%dpx">*Indicative. Final pricing set by the developer.</div>'


def sz(s, n):
    return s.replace('<svg class="i"', '<svg width="%d" height="%d" class="i"' % (n, n))


def hlsize(hl, base):
    return base if len(hl) <= 22 else base - 14


def txt(hl, sub, size, top=330, w=860):
    return (f'<div class="abs" style="left:63px;top:{top}px;width:{w}px"><div class="hl" style="font-size:{size}px">{hl}</div>'
            f'<div class="sub">{sub}</div></div>')


def A(top, tpos, bot, hl, sub):
    return HEAD + f'''
<div class="abs ph" style="left:0;top:150px;width:1080px;height:1090px;background-image:url({top});background-position:{tpos};-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 14%,#000 82%,transparent 100%)"></div>
<div class="abs ph" style="left:0;top:1120px;width:1080px;height:800px;background-image:url({bot});background-position:50% 50%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 22%,#000 100%)"></div>
<div class="abs" style="left:0;top:1160px;width:1080px;height:760px;background:linear-gradient(180deg,rgba(15,40,26,.55),rgba(15,40,26,.9) 35%,rgba(15,40,26,.95))"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:700px;background:linear-gradient(180deg,rgba(15,40,26,.9),rgba(15,40,26,.6) 55%,rgba(15,40,26,0))"></div>
{txt(hl, sub, hlsize(hl, 104))}
<img class="abs logo" style="right:65px;top:282px" src="logo_light.png">
<div class="abs" style="left:65px;right:65px;top:1215px;display:flex">
  <div style="flex:0 0 290px;display:flex;gap:14px;align-items:center">{sz(RUPEE,44)}<div><div class="lab">Starting from</div><div class="big" style="font-size:40px;margin-top:6px">₹3.5 Cr*</div></div></div>
  <div style="flex:1.4;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(191,224,200,.5)">{sz(PLOT,44)}<div><div class="lab">Plot size</div><div class="big" style="font-size:40px;margin-top:6px;white-space:nowrap">682–1,246 Sq. Yd</div></div></div>
  <div style="flex:1;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(191,224,200,.5)">{sz(PIN,44)}<div><div class="lab">Location</div><div class="big" style="font-size:40px;margin-top:6px;white-space:nowrap">Near Chilkur</div></div></div>
</div>
<div class="abs" style="left:65px;right:65px;top:1400px;display:flex;justify-content:space-between;align-items:center">{PHONE}<div class="btn">Learn More</div></div>
''' + FN % 1500 + TAIL


def B(img, pos, hl, sub):
    return HEAD + f'''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1760px;background-image:url({img});background-position:{pos};-webkit-mask-image:linear-gradient(180deg,#000 0,#000 80%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:1760px;background:linear-gradient(90deg,rgba(15,40,26,.94) 0,rgba(15,40,26,.86) 44%,rgba(15,40,26,.35) 68%,rgba(15,40,26,0) 86%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:520px;background:linear-gradient(180deg,rgba(15,40,26,.6),rgba(15,40,26,0))"></div>
<img class="abs logo" style="right:65px;top:282px" src="logo_light.png">
{txt(hl, sub, hlsize(hl, 92), 330, 700)}
<div class="abs" style="left:65px;top:790px;width:700px">
  <div style="display:flex;align-items:center;gap:22px;padding-bottom:26px;border-bottom:2px solid rgba(191,224,200,.55)"><div style="width:64px">{sz(RUPEE,64)}</div><div><div class="lab">Starting from</div><div class="big" style="font-size:64px;margin-top:6px">₹3.5 Cr*</div></div></div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0;border-bottom:2px solid rgba(191,224,200,.55)"><div style="width:64px">{sz(PLOT,64)}</div><div><div class="lab">Plot size</div><div class="big" style="font-size:46px;margin-top:6px;white-space:nowrap">682–1,246 Sq. Yd</div></div></div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0"><div style="width:64px">{sz(PIN,64)}</div><div><div class="lab">Location</div><div class="big" style="font-size:46px;margin-top:6px">Near Chilkur</div></div></div>
</div>
<div class="abs" style="left:65px;top:1320px;display:flex;flex-direction:column;gap:26px;align-items:flex-start">{PHONE}<div class="btn" style="font-size:38px;padding:26px 70px">Learn More</div></div>
''' + FN % 1520 + TAIL


def C(top, tpos, bot, hl, sub):
    return HEAD + f'''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1260px;background-image:url({top});background-position:{tpos};-webkit-mask-image:linear-gradient(180deg,#000 0,#000 92%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:800px;background:linear-gradient(180deg,rgba(15,40,26,.9),rgba(15,40,26,.5) 60%,rgba(15,40,26,0))"></div>
<div class="abs ph" style="left:0;top:1540px;width:1080px;height:380px;background-image:url({bot});background-position:50% 60%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 34%,#000 100%)"></div>
{txt(hl, sub, hlsize(hl, 104))}
<img class="abs logo" style="right:65px;top:282px" src="logo_light.png">
<div class="abs" style="left:0;top:1200px;width:1080px;height:170px;background:var(--green);display:flex;align-items:center;justify-content:space-between;padding:0 65px">
  <div><div class="lab">Starting from</div><div class="big" style="font-size:72px;margin-top:6px;text-shadow:none">₹3.5 Cr*</div></div>
  <div style="text-align:right;color:#fff"><div style="font-weight:500;font-size:40px;line-height:1.15">682–1,246 Sq. Yd</div><div style="font-weight:500;font-size:40px;margin-top:8px">Near Chilkur</div></div>
</div>
<div class="abs" style="left:0;top:1372px;width:1080px;height:130px;background:var(--deep);display:flex;align-items:center;justify-content:space-between;padding:0 65px">{PHONE}<div class="btn" style="padding:20px 52px">Learn More</div></div>
''' + FN % 1514 + TAIL


def W(img, pos, hl, sub, portrait=False):
    if portrait:
        ph = 'left:640px;top:0;width:640px;height:720px;'
        mp = '-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 35%,#000 100%);'
    else:
        ph = 'left:0;top:0;width:1280px;height:720px;'
        mp = ''
    return HEAD + f'''
<div class="abs ph" style="{ph}background-image:url({img});background-position:{pos};{mp}"></div>
<div class="abs" style="left:0;top:0;width:1280px;height:720px;background:linear-gradient(90deg,rgba(15,40,26,.97) 0,rgba(15,40,26,.9) 36%,rgba(15,40,26,.45) 54%,rgba(15,40,26,0) 72%)"></div>
<div class="abs" style="right:0;top:0;width:420px;height:260px;background:linear-gradient(225deg,rgba(15,40,26,.7),rgba(15,40,26,0) 70%)"></div>
<img class="abs logo" style="right:56px;top:40px;width:140px" src="logo_light.png">
<div class="abs" style="left:56px;top:52px;width:600px"><div class="hl" style="font-size:{72 if len(hl) <= 22 else 62}px">{hl}</div><div class="sub" style="font-size:24px;margin-top:10px">{sub}</div></div>
<div class="abs" style="left:56px;top:330px;width:560px">
  <div style="display:flex;align-items:center;gap:16px;padding-bottom:12px">{sz(RUPEE,34)}<div><div class="lab" style="font-size:20px">Starting from</div><div class="big" style="font-size:30px;margin-top:3px">₹3.5 Cr*</div></div></div>
  <div style="display:flex;align-items:center;gap:16px;padding:12px 0;border-top:1px solid rgba(191,224,200,.4)">{sz(PLOT,34)}<div><div class="lab" style="font-size:20px">Plot size</div><div class="big" style="font-size:30px;margin-top:3px">682–1,246 Sq. Yd</div></div></div>
  <div style="display:flex;align-items:center;gap:16px;padding:12px 0;border-top:1px solid rgba(191,224,200,.4)">{sz(PIN,34)}<div><div class="lab" style="font-size:20px">Location</div><div class="big" style="font-size:30px;margin-top:3px">Near Chilkur</div></div></div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:16px;border-top:1px solid rgba(191,224,200,.4)"><div class="phone" style="font-size:28px">{PHONE.split('>',1)[1].rsplit('</div>',1)[0] if False else ''}{PH}+91 79935 44699</div><div class="btn" style="font-size:22px;padding:14px 38px">Learn More</div></div>
  <div class="fn" style="margin-top:12px;font-size:13px">*Indicative. Final pricing set by the developer.</div>
</div>
''' + TAIL


D = [
    (1, 'the-garden-residence', 'The Garden Residence', 'Ground + first floor villas, 2,930–3,097 sft built-up', 'A', ('50% 60%', 'hero06.jpg')),
    (2, 'sunken-seating', 'Gather Around the Fire', 'Outdoor sunken seating in your own garden', 'C', ('55% 50%', 'hero03.jpg')),
    (3, 'fruit-garden', 'Taste the Seasons', 'Grown within your own garden', 'B', ('62% 50%',)),
    (4, 'kitchen-garden', 'From Tree to Table', 'The luxury of growing your own', 'A', ('50% 60%', 'hero05.jpg')),
    (5, 'street-view', 'A Path That Quiets the Mind', '30 ft wide roads, lined with greenery', 'B', ('55% 50%',)),
    (6, 'quiet-escape', 'A Quiet Escape', 'Swimming pool under the open sky', 'C', ('50% 50%', 'hero04.jpg')),
    (7, 'pickleball', 'Pickleball, at Home', 'A community for mind, body, heart and soul', 'C', ('40% 50%', 'hero02.jpg')),
    (8, 'recharge', 'Recharge Between Victories', 'Solitude amenities, six acres of calm', 'A', ('50% 50%', 'hero09.jpg')),
    (9, 'six-acres', 'Six Acres of Breathing Space', 'Moinabad–Shankarpally’s low-density green zone', 'B', ('60% 50%',)),
    (10, 'solitude-living', 'Solitude Living', 'The luxury few talk about', 'C', ('50% 25%', 'hero03.jpg')),
]
E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
os.makedirs('final', exist_ok=True)


def shot(html, hname, out, w, h, sc):
    html = html.replace('@W', str(w)).replace('@H', str(h))
    open(hname, 'w', encoding='utf-8').write(html)
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=%s' % sc,
                    '--window-size=%d,%d' % (w, h), '--virtual-time-budget=12000', '--screenshot=' + out,
                    'file:///' + os.path.abspath(hname).replace(chr(92), '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


for i, slug, hl, sub, lay, args in D:
    img = 'hero%02d.jpg' % i
    if lay == 'A':
        h916 = A(img, args[0], args[1], hl, sub)
    elif lay == 'B':
        h916 = B(img, args[0], hl, sub)
    else:
        h916 = C(img, args[0], args[1], hl, sub)
    shot(h916, 'e916_%02d.html' % i, os.path.abspath('final/E18_%02d_%s_9x16.png' % (i, slug)), 1080, 1920, 1.333333)
    h169 = W(img, args[0] if i != 10 else '50% 30%', hl, sub, portrait=(i == 10))
    shot(h169, 'e169_%02d.html' % i, os.path.abspath('final/E18_%02d_%s_16x9.png' % (i, slug)), 1280, 720, 1.5)
    print(i)
