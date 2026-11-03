import json, subprocess, os, sys

D = json.load(open('designs.json', encoding='utf-8'))
BASE = '''<!doctype html><html><head><meta charset="utf-8">
<link href="https://api.fontshare.com/v2/css?f[]=general-sans@300,400,500,600&display=swap" rel="stylesheet">
<style>
@font-face{font-family:'Bardo';src:url(Bardo.otf)}
:root{--navy:#0a1a38;--gold:#ac915f;--goldl:#cdb27c;--mute:#9aa6bd}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:@Wpx;height:@Hpx;background:var(--navy);overflow:hidden;font-family:'General Sans',sans-serif;font-variant-numeric:lining-nums}
.ad{position:relative;width:@Wpx;height:@Hpx;overflow:hidden;background:var(--navy)}
.abs{position:absolute}
.photo,.blur{background-repeat:no-repeat;background-size:cover}
.tag{font-size:17px;letter-spacing:.2em;text-transform:uppercase;color:var(--goldl);font-weight:500}
.pre{font-size:27px;letter-spacing:.06em;text-transform:uppercase;color:#fff;font-weight:300}
.hl{font-family:Bardo,serif;color:#fff;text-transform:uppercase;letter-spacing:.012em;line-height:.92}
.row{display:flex}
.f{flex:1;display:flex;align-items:center;gap:14px;padding:0 22px;border-left:1px solid rgba(172,145,95,.5)}
.f:first-child{border-left:0;padding-left:0}
.f svg{flex:none;width:40px;height:40px;fill:none;stroke:var(--gold);stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.f small{display:block;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--mute);font-weight:500;margin-bottom:5px}
.f b{display:block;font-weight:500;font-size:27px;line-height:1.02;white-space:nowrap;color:#fff}
.cta{display:flex;align-items:center;justify-content:space-between;margin-top:22px;padding-top:20px;border-top:1px solid rgba(172,145,95,.4)}
.ph{display:flex;align-items:center;gap:12px;color:#fff;font-weight:500;font-size:27px;letter-spacing:.03em}
.ph svg{width:28px;height:28px;fill:none;stroke:var(--gold);stroke-width:2;stroke-linejoin:round}
.btn{background:var(--gold);color:var(--navy);font-weight:600;font-size:22px;letter-spacing:.06em;padding:15px 44px;border-radius:40px}
.fn{font-size:12px;color:var(--mute);margin-top:14px}
'''
FEATS = '''<div class="row" style="height:64px">
 <div class="f"><svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="20"/><path d="M16 14h16M16 20h16M16 14c8 0 10 4 6 8-2 2-5 3-8 3l10 11"/></svg><div><small>Starts from</small><b>₹3 Cr*</b></div></div>
 <div class="f"><svg viewBox="0 0 48 48"><rect x="8" y="8" width="32" height="32"/><path d="M8 18h7M8 26h4M8 34h7M30 40v-6M22 40v-4"/></svg><div><small>3 BHK Homes</small><b>2,385–3,105 Sq. Ft.</b></div></div>
 <div class="f"><svg viewBox="0 0 48 48"><path d="M24 43S9 29 9 19a15 15 0 0 1 30 0c0 10-15 24-15 24z"/><circle cx="24" cy="19" r="5"/></svg><div><small>Location</small><b>Khajaguda</b></div></div>
</div>'''
FEATS_169 = FEATS.replace(' style="height:64px"', '')
CTA = '''<div class="cta"><div class="ph"><svg viewBox="0 0 24 24"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/></svg>+91 79935 44699</div><div class="btn">Learn More</div></div><div class="fn">*Indicative. Final pricing set by the developer.</div>'''
LOGO = '<img class="abs logo" src="logo_t35.png">'
NAMES = {'11': '1x1', '916': '9x16', '169': '16x9'}


def page(slug, ratio, img, pre, hl, pos):
    portrait = slug == 'parents'
    if ratio == '11':
        W, H, sc = 1080, 1080, 1.333333
        css = '''.photo{left:0;top:0;width:1080px;height:860px;background-position:@POS;-webkit-mask-image:linear-gradient(180deg,#000 0,#000 82%,transparent 100%)}
.shade{left:0;top:0;width:1080px;height:520px;background:linear-gradient(180deg,rgba(10,26,56,.9),rgba(10,26,56,.55) 55%,rgba(10,26,56,0))}
.tag{left:64px;top:62px}.pre{left:64px;top:116px}.hl{left:62px;top:150px;font-size:@HLpx;width:960px}
.logo{right:64px;top:54px;width:118px}.bot{left:64px;right:64px;top:860px}'''
        hlsize = 128 if len(hl) <= 16 else 136
        pre_html = '<div class="abs pre">' + pre + '</div>'
        if portrait:
            css = css.replace('.photo{left:0;top:0;width:1080px', '.photo{left:430px;top:0;width:650px')
            css = css.replace('-webkit-mask-image:linear-gradient(180deg,#000 0,#000 82%,transparent 100%)',
                              '-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 30%,#000 100%),linear-gradient(180deg,#000 0,#000 86%,transparent 100%);-webkit-mask-composite:source-in;mask-composite:intersect')
            css += '.shade{display:none}.hl{width:470px;top:236px;font-size:92px;line-height:.98}'
            pre_html = '<div class="abs" style="left:66px;top:664px;font-size:21px;letter-spacing:.14em;text-transform:uppercase;color:#cdb27c;font-weight:500">' + pre + '</div>'
        body = ('<div class="abs photo" style="background-image:url(%s)"></div><div class="abs shade"></div>'
                '<div class="abs tag">Now open for bookings</div>%s<div class="abs hl">%s</div>%s'
                '<div class="abs bot">%s%s</div>') % (img, pre_html, hl, LOGO, FEATS, CTA)
        css = css.replace('@HL', str(hlsize)).replace('@POS', pos)
    elif ratio == '916':
        W, H, sc = 1080, 1920, 1.333333
        css = '''.blur{left:-60px;top:-60px;width:1200px;height:2040px;display:none}
.photo{left:0;top:@TOPpx;width:1080px;height:1100px;background-position:@POS;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 14%,#000 78%,transparent 100%)}
.shade{left:0;top:0;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.92),rgba(10,26,56,.6) 60%,rgba(10,26,56,0))}
.shade2{left:0;top:880px;width:1080px;height:520px;background:linear-gradient(180deg,rgba(10,26,56,0),rgba(10,26,56,.9) 38%,rgba(10,26,56,.92))}
.tag{left:65px;top:292px}.pre{left:65px;top:346px}.hl{left:63px;top:380px;font-size:150px;width:950px}
.logo{right:65px;top:282px;width:118px}.bot{left:65px;right:65px;top:1020px}'''.replace('@POS', pos).replace('@TOP', str({'golden-hour':230}.get(slug,0)))
        body = ('<div class="abs blur" style="background-image:url(%s)"></div><div class="abs photo" style="background-image:url(%s)"></div>'
                '<div class="abs shade"></div><div class="abs shade2"></div><div class="abs tag">Now open for bookings</div>'
                '<div class="abs pre">%s</div><div class="abs hl">%s</div>%s<div class="abs bot">%s%s</div>') % (img, img, pre, hl, LOGO, FEATS, CTA)
    else:
        W, H, sc = 1280, 720, 1.5
        if portrait:
            ph = 'left:640px;top:0;width:640px;height:720px;'
            maskp = '-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 35%,#000 100%);'
        else:
            ph = 'left:0;top:0;width:1280px;height:720px;'
            maskp = ''
        css = ('.photo{' + ph + 'background-position:@POS;' + maskp + '}\n' + '''.shade{left:0;top:0;width:1280px;height:720px;background:linear-gradient(90deg,rgba(10,26,56,.97) 0,rgba(10,26,56,.9) 34%,rgba(10,26,56,.45) 52%,rgba(10,26,56,0) 70%)}
.tag{left:56px;top:46px}.pre{left:56px;top:92px;font-size:22px}.hl{left:54px;top:126px;font-size:104px;width:600px}
.logo{right:56px;top:44px;width:104px}.shade3{right:0;top:0;width:420px;height:260px;background:linear-gradient(225deg,rgba(10,26,56,.75),rgba(10,26,56,0) 70%)}
.bot{left:56px;top:400px;width:560px}
.bot .row{flex-direction:column;height:auto}
.bot .f{padding:11px 0;border-left:0;border-top:1px solid rgba(172,145,95,.4)}
.bot .f:first-child{border-top:0;padding-top:0}
.bot .f svg{width:34px;height:34px}.bot .f b{font-size:24px}.bot .f small{margin-bottom:3px}
.bot .cta{margin-top:12px;padding-top:16px}.bot .ph{font-size:24px}.bot .btn{font-size:20px;padding:13px 36px}
.bot .fn{margin-top:12px}''').replace('@POS', pos)
        body = ('<div class="abs photo" style="background-image:url(%s)"></div><div class="abs shade"></div><div class="abs shade3"></div>'
                '<div class="abs tag">Now open for bookings</div><div class="abs pre">%s</div><div class="abs hl">%s</div>%s'
                '<div class="abs bot">%s%s</div>') % (img, pre, hl, LOGO, FEATS_169, CTA)
    html = BASE.replace('@W', str(W)).replace('@H', str(H)) + css + '</style></head><body><div class="ad">' + body + '</div></body></html>'
    fn = 'h_%s_%s.html' % (slug, ratio)
    open(fn, 'w', encoding='utf-8').write(html)
    return fn, W, H, sc


E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
only = sys.argv[1:]
os.makedirs('final', exist_ok=True)
for i, (slug, img, pre, hl, p11, p916, p169) in enumerate(D, 1):
    for ratio, pos in (('11', p11), ('916', p916), ('169', p169)):
        key = '%02d_%s_%s' % (i, slug, ratio)
        if only and not any(o in key for o in only):
            continue
        fn, W, H, sc = page(slug, ratio, img, pre, hl, pos)
        out = os.path.abspath('final/T35_%02d_%s_%s.png' % (i, slug, NAMES[ratio]))
        subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=%s' % sc,
                        '--window-size=%d,%d' % (W, H), '--virtual-time-budget=12000', '--screenshot=' + out,
                        'file:///' + os.path.abspath(fn).replace('\\', '/')], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        print(out)
