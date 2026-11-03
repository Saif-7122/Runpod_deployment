import subprocess, os, shutil
from PIL import Image

shutil.copy(r'D:\Runpod_deployment\ads\work\logo_light.png', 'logo_light.png')
HEROES = {1: 'e_p8.png', 2: 'e_p17.png', 3: 'e_p9.png', 4: 'e_p10.png', 5: 'e_p11.png',
          6: 'e_p23.png', 7: 'e_p25.png', 8: 'e_p19.png', 9: 'e_p4.png', 10: 'e_p2.png'}
for k, v in HEROES.items():
    Image.open(v).convert('RGB').save('hero%02d.jpg' % k, quality=92)

# slug, headline, sub (all from the Elite 18 brochure), bg position
D = [
    (1, 'the-garden-residence', 'The Garden Residence', 'Ground + first floor villas, 2,930–3,097 sft built-up', '50% 60%'),
    (2, 'sunken-seating', 'Gather Around the Fire', 'Outdoor sunken seating in your own garden', '50% 55%'),
    (3, 'fruit-garden', 'Taste the Seasons', 'Grown within your own garden', '50% 55%'),
    (4, 'kitchen-garden', 'From Tree to Table', 'The luxury of growing your own', '50% 60%'),
    (5, 'street-view', 'A Path That Quiets the Mind', '30 ft wide roads, lined with greenery', '50% 55%'),
    (6, 'quiet-escape', 'A Quiet Escape', 'Swimming pool under the open sky', '50% 55%'),
    (7, 'pickleball', 'Pickleball, at Home', 'A community for mind, body, heart and soul', '30% 60%'),
    (8, 'recharge', 'Recharge Between Victories', 'Solitude amenities, six acres of calm', '50% 50%'),
    (9, 'six-acres', 'Six Acres of Breathing Space', 'Moinabad–Shankarpally’s low-density green zone', '50% 50%'),
    (10, 'solitude-living', 'Solitude Living', 'The luxury few talk about', '50% 22%'),
]

HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--green:#2d5a3d;--ink:#14301f;--panel:#f1f6f1;--deep:#0f281a}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1080px;background:var(--panel);overflow:hidden;font-family:'DM Sans',sans-serif;font-variant-numeric:lining-nums}
.ad{position:relative;width:1080px;height:1080px;overflow:hidden;background:var(--panel)}
.abs{position:absolute}
.photo{left:0;top:0;width:1080px;height:850px;background-size:cover;background-repeat:no-repeat}
.shade{left:0;top:0;width:1080px;height:560px;background:linear-gradient(180deg,rgba(15,40,26,.82),rgba(15,40,26,.5) 55%,rgba(15,40,26,0))}
.txt{left:64px;top:76px;width:780px}.hl{font-family:Marcellus,serif;font-size:96px;line-height:1.02;color:#fff;text-shadow:0 3px 22px rgba(0,0,0,.4)}
.sub{margin-top:16px;margin-left:2px;font-size:28px;font-weight:500;letter-spacing:.02em;color:#eaf3ea;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.logo{right:56px;top:50px;width:160px}
.bot{left:56px;right:56px;top:872px}
.row{display:flex;height:60px}
.f{flex:1;display:flex;align-items:center;gap:14px;padding:0 22px;border-left:1.5px solid rgba(45,90,61,.35)}
.f:first-child{border-left:0;padding-left:0}
.f svg{flex:none;width:40px;height:40px;fill:none;stroke:var(--green);stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.f small{display:block;font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:var(--green);font-weight:700;margin-bottom:4px}
.f b{display:block;font-weight:500;font-size:27px;line-height:1.05;white-space:nowrap;color:var(--ink)}
.cta{display:flex;align-items:center;justify-content:space-between;margin-top:20px;padding-top:18px;border-top:1.5px solid rgba(45,90,61,.35)}
.ph{display:flex;align-items:center;gap:12px;color:var(--ink);font-weight:700;font-size:30px}
.ph svg{width:28px;height:28px;fill:none;stroke:var(--green);stroke-width:2.2;stroke-linejoin:round}
.btn{background:var(--green);color:#fff;font-weight:700;font-size:23px;letter-spacing:.05em;padding:15px 44px;border-radius:40px}
.fn{font-size:12px;color:#5b7263;margin-top:10px}
</style></head><body><div class="ad">'''
FEATS = '''<div class="row">
 <div class="f"><svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="20"/><path d="M16 14h16M16 20h16M16 14c8 0 10 4 6 8-2 2-5 3-8 3l10 11"/></svg><div><small>Starting from</small><b>₹3.5 Cr*</b></div></div>
 <div class="f"><svg viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32"/><path d="M8 18h7M8 26h4M8 34h7M30 40v-6M22 40v-4"/></svg><div><small>Plot size</small><b>682–1,246 Sq. Yd</b></div></div>
 <div class="f"><svg viewBox="0 0 48 48"><path d="M24 43S9 29 9 19a15 15 0 0 1 30 0c0 10-15 24-15 24z"/><circle cx="24" cy="19" r="5"/></svg><div><small>Location</small><b>Near Chilkur</b></div></div>
</div>'''
CTA = '''<div class="cta"><div class="ph"><svg viewBox="0 0 24 24"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/></svg>+91 79935 44699</div><div class="btn">Learn More</div></div><div class="fn">*Indicative. Final pricing set by the developer.</div>'''

E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
os.makedirs('final', exist_ok=True)
for i, slug, hl, sub, pos in D:
    two = len(hl) > 20
    hsize = 84 if len(hl) > 24 else 96
    sub_top = 76 + (2 if two else 1) * int(hsize * 1.02) + 18
    html = (HEAD + '<div class="abs photo" style="background-image:url(hero%02d.jpg);background-position:%s"></div>' % (i, pos) +
            '<div class="abs shade"></div><div class="abs txt"><div class="hl" style="font-size:%dpx">%s</div><div class="sub">%s</div></div>' % (hsize, hl, sub) +
            '<img class="abs logo" src="logo_light.png"><div class="abs bot">' + FEATS + CTA + '</div></div></body></html>')
    h = 'e_%02d.html' % i
    open(h, 'w', encoding='utf-8').write(html)
    out = os.path.abspath('final/E18_%02d_%s_1x1.png' % (i, slug))
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1.333333',
                    '--window-size=1080,1080', '--virtual-time-budget=12000', '--screenshot=' + out,
                    'file:///' + os.path.abspath(h).replace(chr(92), '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(out)
