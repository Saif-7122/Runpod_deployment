import subprocess, os, re
src = open('gen.py', encoding='utf-8').read()
a = src.index("BASE = '''")
b = src.index("NAMES")
ns = {}
exec(src[a:b], ns)
BASE, FEATS, CTA, LOGO = ns['BASE'], ns['FEATS'], ns['CTA'], ns['LOGO']
css = '''
.photo{left:0;top:0;width:1080px;height:1060px;background:url(hD1.jpg) 40% 50%/cover no-repeat;-webkit-mask-image:linear-gradient(180deg,#000 0,#000 86%,transparent 100%)}
.photo2{left:0;top:1215px;width:1080px;height:705px;background:url(hD7.jpg) 50% 55%/cover no-repeat;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 24%,#000 100%)}
.top{left:0;top:0;width:1080px;height:760px;background:linear-gradient(180deg,rgba(10,26,56,.9) 0,rgba(10,26,56,.55) 55%,rgba(10,26,56,0) 100%)}
.mid{left:0;top:930px;width:1080px;height:330px;background:linear-gradient(180deg,rgba(10,26,56,0) 0,rgba(10,26,56,.94) 30%,rgba(10,26,56,.94) 100%)}
.tag{left:65px;top:292px}
.pre{left:65px;top:344px}
.hl{left:63px;top:380px;font-size:150px;line-height:.94;width:950px}
.logo{right:65px;top:282px;width:118px}
.bot{left:65px;right:65px;top:1010px}
'''
body = ('<div class="abs photo"></div><div class="abs top"></div><div class="abs mid"></div><div class="abs photo2"></div>'
        '<div class="abs tag">Now open for bookings</div><div class="abs pre">Every home is a</div>'
        '<div class="abs hl">Corner Home</div>' + LOGO + '<div class="abs bot">' + FEATS + CTA + '</div>')
html = BASE.replace('@W', '1080').replace('@H', '1920') + css + '</style></head><body><div class="ad">' + body + '</div></body></html>'
open('h_test916.html', 'w', encoding='utf-8').write(html)
E = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out = os.path.abspath('test_916_fullbleed.png')
subprocess.run([E, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1.333333',
                '--window-size=1080,1920', '--virtual-time-budget=12000', '--screenshot=' + out,
                'file:///' + os.path.abspath('h_test916.html').replace(chr(92), '/')],
               stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
print(out)
