import subprocess, os

src = open('variants916.py', encoding='utf-8').read()
ns = {}
exec(src[:src.index('# Variant A')], ns)
HEAD, TAIL, PHONE, RUPEE, PLOT, PIN, FN = (ns[k] for k in ('HEAD', 'TAIL', 'PHONE', 'RUPEE', 'PLOT', 'PIN', 'FN'))


def ic(svg):
    return svg.replace('<svg class="i"', '<svg width="44" height="44" class="i"')


def ic64(svg):
    return svg.replace('<svg class="i"', '<svg width="64" height="64" class="i"')


def layout_A(top, tpos, off, bot, pre, hl):
    size = 112 if len(hl) <= 12 else 100
    wrap = 'white-space:nowrap' if len(hl) <= 12 else 'width:900px'
    return HEAD + f'''
<div class="abs ph" style="left:0;top:{off}px;width:1080px;height:{1240-off}px;background-image:url({top});background-position:{tpos};-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 16%,#000 82%,transparent 100%)"></div>
<div class="abs ph" style="left:0;top:1120px;width:1080px;height:800px;background-image:url({bot});background-position:50% 50%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 22%,#000 100%)"></div>
<div class="abs" style="left:0;top:1160px;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.55),rgba(10,26,56,.9) 35%,rgba(10,26,56,.95))"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:640px;background:linear-gradient(180deg,rgba(10,26,56,.88),rgba(10,26,56,.6) 55%,rgba(10,26,56,0))"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<div class="abs pre" style="left:65px;top:340px">{pre}</div>
<div class="abs hl" style="left:63px;top:380px;font-size:{size}px;{wrap}">{hl}</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs" style="left:65px;right:65px;top:1215px;display:flex;gap:0">
  <div style="flex:0 0 280px;display:flex;gap:14px;align-items:center">{ic(RUPEE)}<div><div class="lab">Starts from</div><div class="big" style="font-size:40px;margin-top:6px">₹3 Cr*</div></div></div>
  <div style="flex:1.5;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(217,189,133,.5)">{ic(PLOT)}<div><div class="lab">3 BHK homes</div><div class="big" style="font-size:40px;margin-top:6px;white-space:nowrap">2,385–3,105 Sq. Ft.</div></div></div>
  <div style="flex:1;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(217,189,133,.5)">{ic(PIN)}<div><div class="lab">Location</div><div class="big" style="font-size:40px;margin-top:6px">Khajaguda</div></div></div>
</div>
<div class="abs" style="left:65px;right:65px;top:1400px;display:flex;justify-content:space-between;align-items:center">{PHONE}<div class="btn">Learn More</div></div>
''' + FN % 1500 + TAIL


def layout_B(img, pos, pre, hl):
    return HEAD + f'''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1760px;background-image:url({img});background-position:{pos};-webkit-mask-image:linear-gradient(180deg,#000 0,#000 80%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:1760px;background:linear-gradient(90deg,rgba(10,26,56,.94) 0,rgba(10,26,56,.86) 44%,rgba(10,26,56,.35) 68%,rgba(10,26,56,0) 86%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:520px;background:linear-gradient(180deg,rgba(10,26,56,.6),rgba(10,26,56,0))"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs pre" style="left:65px;top:346px">{pre}</div>
<div class="abs hl" style="left:63px;top:388px;font-size:100px;width:760px">{hl}</div>
<div class="abs" style="left:65px;top:760px;width:700px">
  <div style="display:flex;align-items:center;gap:22px;padding-bottom:26px;border-bottom:2px solid rgba(217,189,133,.55)"><div style="width:64px">{ic64(RUPEE)}</div><div><div class="lab">Starts from</div><div class="big" style="font-size:64px;margin-top:6px">₹3 Cr*</div></div></div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0;border-bottom:2px solid rgba(217,189,133,.55)"><div style="width:64px">{ic64(PLOT)}</div><div><div class="lab">3 BHK homes</div><div class="big" style="font-size:46px;margin-top:6px;white-space:nowrap">2,385–3,105 Sq. Ft.</div></div></div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0"><div style="width:64px">{ic64(PIN)}</div><div><div class="lab">Location</div><div class="big" style="font-size:46px;margin-top:6px">Khajaguda</div></div></div>
</div>
<div class="abs" style="left:65px;top:1290px;display:flex;flex-direction:column;gap:26px;align-items:flex-start">{PHONE}<div class="btn" style="font-size:38px;padding:26px 70px">Learn More</div></div>
''' + FN % 1500 + TAIL


def layout_C(top, tpos, bot, pre, hl):
    return HEAD + f'''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1260px;background-image:url({top});background-position:{tpos};-webkit-mask-image:linear-gradient(180deg,#000 0,#000 92%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.9),rgba(10,26,56,.5) 60%,rgba(10,26,56,0))"></div>
<div class="abs ph" style="left:0;top:1540px;width:1080px;height:380px;background-image:url({bot});background-position:50% 60%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 34%,#000 100%)"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<div class="abs pre" style="left:65px;top:340px">{pre}</div>
<div class="abs hl" style="left:63px;top:380px;font-size:100px;width:800px">{hl}</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs" style="left:0;top:1200px;width:1080px;height:170px;background:var(--gold);display:flex;align-items:center;justify-content:space-between;padding:0 65px">
  <div><div class="lab" style="color:var(--navy);text-shadow:none">Starts from</div><div class="big" style="color:var(--navy);font-size:72px;margin-top:6px;text-shadow:none">₹3 Cr*</div></div>
  <div style="text-align:right;color:var(--navy)"><div style="font-weight:500;font-size:40px;line-height:1.15">2,385–3,105 Sq. Ft.</div><div style="font-weight:500;font-size:40px;margin-top:8px">Khajaguda</div></div>
</div>
<div class="abs" style="left:0;top:1372px;width:1080px;height:130px;background:var(--navy);display:flex;align-items:center;justify-content:space-between;padding:0 65px">{PHONE}<div class="btn" style="padding:20px 52px">Learn More</div></div>
''' + FN % 1514 + TAIL


D = [
    (1, 'corner-home', lambda: layout_A('hD1.jpg', '40% 50%', 150, 'hD7.jpg', 'Every home is a', 'Corner Home')),
    (2, 'above-the-city', lambda: layout_C('hC.jpg', '60% 50%', 'hD6.jpg', 'Your family’s address', 'Above the City')),
    (3, 'play-above', lambda: layout_C('hD3.jpg', '30% 50%', 'hD7.jpg', 'Life at the Terrace', 'Play Above the City')),
    (4, 'golden-hour', lambda: layout_A('hD4.jpg', '36% 50%', 230, 'hL.jpg', 'Evenings at the Terrace', 'Golden Hour')),
    (5, 'movie-nights', lambda: layout_C('hD5.jpg', '55% 50%', 'hD6.jpg', 'Sky cinema under the stars', 'Movie Nights')),
    (6, 'game-night', lambda: layout_B('hD6.jpg', '70% 50%', 'A bowling alley on the terrace', 'Game Night Upstairs')),
    (7, 'pool-mornings', lambda: layout_B('hD7.jpg', '60% 50%', 'Swimming pool and kids’ pool', 'Mornings Start at the Pool')),
    (8, 'unhurried', lambda: layout_B('hD8.jpg', '76% 50%', 'Podium café and sit-outs', 'Unhurried Mornings')),
    (9, 'neighbours', lambda: layout_A('hL.jpg', '60% 50%', 150, 'hD4.jpg', '260 homes. One community.', 'Meet Your Neighbours')),
    (10, 'parents', lambda: layout_C('hP.jpg', '60% 20%', 'hD7.jpg', 'Guest suites. Eight lifts.', 'Parents Stay Longer')),
]
E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
os.makedirs('final916', exist_ok=True)
for i, slug, fn_ in D:
    html = fn_()
    h = 'h_roll916_%02d.html' % i
    open(h, 'w', encoding='utf-8').write(html)
    out = os.path.abspath('final916/T35_%02d_%s_9x16.png' % (i, slug))
    if os.path.exists(out):
        os.remove(out)
    subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1.333333',
                    '--window-size=1080,1920', '--virtual-time-budget=12000', '--screenshot=' + out,
                    'file:///' + os.path.abspath(h).replace(chr(92), '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(out)
