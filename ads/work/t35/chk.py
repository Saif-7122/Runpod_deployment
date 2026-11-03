from pathlib import Path
from collections import Counter
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
c=Credentials.from_authorized_user_file(r"D:\Runpod_deployment\ads\work\t35\token_hoi.json",["https://www.googleapis.com/auth/drive"])
s=build("drive","v3",credentials=c,cache_discovery=False)
L=s.files().list(q="'14zhROytV0PBO5rIdLkZMYQvJULS8pMiD' in parents and trashed=false",fields="files(id,name)",pageSize=200).execute()["files"]
n=Counter(f["name"] for f in L)
print(len(L),'live;', 'dupes:',[k for k,v in n.items() if v>1])
print(sum(1 for k in n if k.endswith('9x16.png')),'9x16', sum(1 for k in n if k.endswith('1x1.png')),'1x1', sum(1 for k in n if k.endswith('16x9.png')),'16x9')
