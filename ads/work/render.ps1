$e="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
foreach($f in @(@("916",1920),@("45",1350),@("11",1080))){
 (Get-Content ad.html -Raw -Encoding utf8) -replace 'class="FMT"',"class=`"s$($f[0])`"" | Set-Content "ad_$($f[0]).html" -Encoding utf8
 & $e --headless --disable-gpu --hide-scrollbars --window-size=1080,$($f[1]) --virtual-time-budget=10000 "--screenshot=D:\Runpod_deployment\ads\work\elite18_$($f[0]).png" "file:///D:/Runpod_deployment/ads/work/ad_$($f[0]).html" 2>$null | Out-Null
}
