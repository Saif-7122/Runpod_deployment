from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from collections import Counter
c=Credentials.from_authorized_user_file(r"D:\Runpod_deployment\ads\work\t35\token_hoi.json",["https://www.googleapis.com/auth/drive"])
s=build("drive","v3",credentials=c,cache_discovery=False)
L=s.files().list(q="'1hXXzr7xhf4cpGfP70ekGaTk5AtNtQjqM' in parents and trashed=false",fields="files(name)",pageSize=200).execute()["files"]
n=Counter(f["name"] for f in L)
print(len(L),'live; dupes',[k for k,v in n.items() if v>1])
for r in('1x1','9x16','16x9'): print(r,sum(1 for k in n if k.endswith(r+'.png')))
