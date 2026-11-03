import subprocess, os

HEAD = '''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=general-sans@300,400,500,600,700&display=swap" rel="stylesheet">
<style>
@font-face{font-family:'Bardo';src:url(Bardo.otf)}
:root{--navy:#0a1a38;--gold:#ac915f;--goldl:#d9bd85;--mute:#b6c0d4}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;background:var(--navy);overflow:hidden;font-family:'General Sans',sans-serif;font-variant-numeric:lining-nums}
.ad{position:relative;width:1080px;height:1920px;overflow:hidden;background:var(--navy)}
.abs{position:absolute}
.ph{background-repeat:no-repeat;background-size:cover}
.tag{font-size:21px;letter-spacing:.2em;text-transform:uppercase;color:var(--goldl);font-weight:600;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.pre{font-size:30px;letter-spacing:.06em;text-transform:uppercase;color:#fff;font-weight:400;text-shadow:0 2px 14px rgba(0,0,0,.55)}
.hl{font-family:Marcellus,serif;color:#fff;text-transform:uppercase;letter-spacing:.02em;line-height:1.02;text-shadow:0 3px 24px rgba(0,0,0,.45)}
.logo{width:124px}
.lab{white-space:nowrap;font-size:26px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:#e6c98c;text-shadow:0 1px 10px rgba(0,0,0,.5)}
.big{font-weight:500;color:#fff;line-height:1.05;text-shadow:0 2px 12px rgba(0,0,0,.45)}
.btn{background:var(--gold);color:var(--navy);font-weight:700;font-size:34px;letter-spacing:.04em;padding:22px 56px;border-radius:60px;white-space:nowrap}
.phone{display:flex;align-items:center;gap:14px;color:#fff;font-weight:700;font-size:40px;letter-spacing:.01em;white-space:nowrap}
.phone svg{width:38px;height:38px;fill:none;stroke:var(--goldl);stroke-width:2.2;stroke-linejoin:round}
.fn{font-size:16px;color:var(--mute)}
svg.i{fill:none;stroke:var(--goldl);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
</style></head><body><div class="ad">'''
TAIL = '</div></body></html>'
LOGO = '<img class="abs logo" src="logo_t35.png">'
PH = '<svg viewBox="0 0 24 24"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/></svg>'
PHONE = '<div class="phone">' + PH + '+91 79935 44699</div>'
RUPEE = '<svg class="i" viewBox="0 0 48 48"><circle cx="24" cy="24" r="20"/><path d="M16 14h16M16 20h16M16 14c8 0 10 4 6 8-2 2-5 3-8 3l10 11"/></svg>'
PLOT = '<svg class="i" viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32"/><path d="M8 18h7M8 26h4M8 34h7M30 40v-6M22 40v-4"/></svg>'
PIN = '<svg class="i" viewBox="0 0 48 48"><path d="M24 43S9 29 9 19a15 15 0 0 1 30 0c0 10-15 24-15 24z"/><circle cx="24" cy="19" r="5"/></svg>'
FN = '<div class="abs fn" style="left:65px;top:%dpx">*Indicative. Final pricing set by the developer.</div>'

# Variant A: top photo + headline, bold price block and chips over lower photo
A = HEAD + '''
<div class="abs ph" style="left:0;top:230px;width:1080px;height:1010px;background-image:url(hD4.jpg);background-position:36% 50%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 16%,#000 82%,transparent 100%)"></div>
<div class="abs ph" style="left:0;top:1120px;width:1080px;height:800px;background-image:url(hL.jpg);background-position:50% 50%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 22%,#000 100%)"></div>
<div class="abs" style="left:0;top:1160px;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.55),rgba(10,26,56,.9) 35%,rgba(10,26,56,.95))"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<div class="abs pre" style="left:65px;top:340px">Evenings at the Terrace</div>
<div class="abs hl" style="left:63px;top:380px;font-size:112px;white-space:nowrap">Golden Hour</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs" style="left:65px;right:65px;top:1215px;display:flex;gap:0">
  <div style="flex:0 0 280px;display:flex;gap:14px;align-items:center">'''+RUPEE.replace('<svg class="i"','<svg width="44" height="44" class="i"')+'''<div><div class="lab">Starts from</div><div class="big" style="font-size:40px;margin-top:6px">₹3 Cr*</div></div></div>
  <div style="flex:1.5;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(217,189,133,.5)">'''+PLOT.replace('<svg class="i"','<svg width="44" height="44" class="i"')+'''<div><div class="lab">3 BHK homes</div><div class="big" style="font-size:40px;margin-top:6px;white-space:nowrap">2,385–3,105 Sq. Ft.</div></div></div>
  <div style="flex:1;display:flex;gap:14px;align-items:center;padding-left:24px;border-left:1px solid rgba(217,189,133,.5)">'''+PIN.replace('<svg class="i"','<svg width="44" height="44" class="i"')+'''<div><div class="lab">Location</div><div class="big" style="font-size:40px;margin-top:6px">Khajaguda</div></div></div>
</div>
<div class="abs" style="left:65px;right:65px;top:1400px;display:flex;justify-content:space-between;align-items:center">''' + PHONE + '''<div class="btn">Learn More</div></div>
''' + FN % 1500 + TAIL

# Variant B: left text column over one tall photo; bold stacked facts
B = HEAD + '''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1760px;background-image:url(hD8.jpg);background-position:76% 50%;-webkit-mask-image:linear-gradient(180deg,#000 0,#000 80%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:1760px;background:linear-gradient(90deg,rgba(10,26,56,.94) 0,rgba(10,26,56,.86) 44%,rgba(10,26,56,.35) 68%,rgba(10,26,56,0) 86%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:520px;background:linear-gradient(180deg,rgba(10,26,56,.6),rgba(10,26,56,0))"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs pre" style="left:65px;top:346px">Podium café and sit-outs</div>
<div class="abs hl" style="left:63px;top:388px;font-size:100px;width:760px">Unhurried Mornings</div>
<div class="abs" style="left:65px;top:760px;width:700px">
  <div style="display:flex;align-items:center;gap:22px;padding-bottom:26px;border-bottom:2px solid rgba(217,189,133,.55)">
    <div style="width:64px">''' + RUPEE.replace('<svg class="i"', '<svg width="64" height="64" class="i"') + '''</div>
    <div><div class="lab">Starts from</div><div class="big" style="font-size:64px;margin-top:6px">₹3 Cr*</div></div>
  </div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0;border-bottom:2px solid rgba(217,189,133,.55)">
    <div style="width:64px">''' + PLOT.replace('<svg class="i"', '<svg width="64" height="64" class="i"') + '''</div>
    <div><div class="lab">3 BHK homes</div><div class="big" style="font-size:46px;margin-top:6px;white-space:nowrap">2,385–3,105 Sq. Ft.</div></div>
  </div>
  <div style="display:flex;align-items:center;gap:22px;padding:26px 0">
    <div style="width:64px">''' + PIN.replace('<svg class="i"', '<svg width="64" height="64" class="i"') + '''</div>
    <div><div class="lab">Location</div><div class="big" style="font-size:46px;margin-top:6px">Khajaguda</div></div>
  </div>
</div>
<div class="abs" style="left:65px;top:1290px;display:flex;flex-direction:column;gap:26px;align-items:flex-start">''' + PHONE + '''<div class="btn" style="font-size:38px;padding:26px 70px">Learn More</div></div>
''' + FN % 1500 + TAIL

# Variant C: gold price band across the page
C = HEAD + '''
<div class="abs ph" style="left:0;top:0;width:1080px;height:1260px;background-image:url(hD3.jpg);background-position:30% 50%;-webkit-mask-image:linear-gradient(180deg,#000 0,#000 92%,transparent 100%)"></div>
<div class="abs" style="left:0;top:0;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.9),rgba(10,26,56,.5) 60%,rgba(10,26,56,0))"></div>
<div class="abs ph" style="left:0;top:1540px;width:1080px;height:380px;background-image:url(hD7.jpg);background-position:50% 60%;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 34%,#000 100%)"></div>
<div class="abs tag" style="left:65px;top:292px">Now open for bookings</div>
<div class="abs pre" style="left:65px;top:340px">Life at the Terrace</div>
<div class="abs hl" style="left:63px;top:380px;font-size:100px;width:800px">Play Above the City</div>
<img class="abs logo" style="right:65px;top:282px" src="logo_t35.png">
<div class="abs" style="left:0;top:1200px;width:1080px;height:170px;background:var(--gold);display:flex;align-items:center;justify-content:space-between;padding:0 65px">
  <div><div class="lab" style="color:var(--navy);text-shadow:none">Starts from</div><div class="big" style="color:var(--navy);font-size:72px;margin-top:6px">₹3 Cr*</div></div>
  <div style="text-align:right;color:var(--navy)">
    <div style="font-weight:500;font-size:40px;line-height:1.15">2,385–3,105 Sq. Ft.</div>
    <div style="font-weight:500;font-size:40px;margin-top:8px">Khajaguda</div>
  </div>
</div>
<div class="abs" style="left:65px;right:65px;top:1262px;"></div>
<div class="abs" style="left:0;top:1372px;width:1080px;height:130px;background:var(--navy);display:flex;align-items:center;justify-content:space-between;padding:0 65px">''' + PHONE + '''<div class="btn" style="padding:20px 52px">Learn More</div></div>
''' + FN % 1514 + TAIL

E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
for name, html in (('A', A), ('B', B), ('C', C)):
    fn = 'h_var916_%s.html' % name
    open(fn, 'w', encoding='utf-8').write(html)
    out = os.path.abspath('var916c_%s.png' % name)
    subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1.333333',
                    '--window-size=1080,1920', '--virtual-time-budget=12000', '--screenshot=' + out,
                    'file:///' + os.path.abspath(fn).replace(chr(92), '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(out)
