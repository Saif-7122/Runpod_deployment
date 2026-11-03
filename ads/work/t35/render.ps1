$e="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
foreach($k in "p1","p2","p3"){
 & $e --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1.333333 --window-size=1080,1080 --virtual-time-budget=10000 "--screenshot=D:\Runpod_deployment\ads\work\t35\terrace35_11_v3_$k.png" "file:///D:/Runpod_deployment/ads/work/t35/t35_$k.html" 2>$null | Out-Null
}
