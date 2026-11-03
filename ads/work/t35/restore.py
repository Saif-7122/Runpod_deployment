from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
c=Credentials.from_authorized_user_file(r"D:\Runpod_deployment\ads\work\t35\token_hoi.json",["https://www.googleapis.com/auth/drive"])
s=build("drive","v3",credentials=c,cache_discovery=False)
F="14zhROytV0PBO5rIdLkZMYQvJULS8pMiD"
L=s.files().list(q=f"'{F}' in parents and trashed=true",fields="files(id,name)",pageSize=200).execute()["files"]
for f in L:
    if f["name"].endswith("_16x9.png"):
        s.files().update(fileId=f["id"],body={"trashed":False}).execute();print("restored",f["name"])
live=s.files().list(q=f"'{F}' in parents and trashed=false",fields="files(name)",pageSize=200).execute()["files"]
print(len(live),'live;',sum(1 for f in live if f["name"].endswith("_16x9.png")),'16x9',sum(1 for f in live if f["name"].endswith("_9x16.png")),'9x16',sum(1 for f in live if f["name"].endswith("_1x1.png")),'1x1')
