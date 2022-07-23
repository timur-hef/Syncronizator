import hashlib
import io
import requests
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload



SCOPES = [
    'https://www.googleapis.com/auth/drive',
]

BASE_FOLDER = os.environ.get('SYNC_FOLDER')
CONFIG_FOLDER = os.environ.get('SYNC_CONFIG')


def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_file = os.path.join(CONFIG_FOLDER, 'token.json')
    credentials_file = os.path.join(CONFIG_FOLDER, 'credentials.json')

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    return service


class Syncronizer:
    def __init__(self, service):
        self.service = service

    def traverse_drive(self, parent, path=''):
        try:
            query = f"'me' in owners and '{parent}' in parents and trashed = false"  #  and mimeType = 'application/vnd.google-apps.folder'
            flag = True
            page_token = None

            while flag:
                results = self.service.files().list(
                    q=query, 
                    pageToken=page_token, 
                    fields="nextPageToken, files(id, name, mimeType, md5Checksum, parents)"
                ).execute()

                page_token = results.get('nextPageToken')
                items = results.get('files')

                if not items:
                    print(f'Folder is empty: {path}')
                    return

                for item in items:
                    new_path = os.path.join(path, item['name'])

                    if item.get('mimeType') == 'application/vnd.google-apps.folder':
                        self.traverse_drive(item['id'], new_path)
                    else:
                        self.check_in_local(new_path, item)

                if not page_token:
                    flag = False
                
        except HttpError as error:
            print(f'An error occurred: {error}')

    def download_file(self, file_id, path, mime_type):
        try:
            if mime_type == 'application/vnd.google-apps.document':
                request = self.service.files().export_media(fileId=file_id, mimeType=mime_type)
            else:
                request = self.service.files().get_media(fileId=file_id)
            obj = io.BytesIO()
            downloader = MediaIoBaseDownload(obj, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

            data = obj.getvalue()
            
            with open(path, 'wb') as f:
                f.write(data)

        except HttpError as error:
            print(F'An error when downloading file {file_id} occurred: {error}')
  
    def check_in_local(self, path, item):
        """
        Check file from drive in local storage. If file is changed you can rewrite it either on local or drive.
        If file doesn't exist in local storage you can either delete it from drive or add it to local storage.
        """
        local_path = os.path.join(BASE_FOLDER, path)
        if not os.path.exists(local_path):
            print(f'File does not exist on local: {path} -- {item["id"]}')
            while True:
                decision = input("1. Download to local\n2. Delete from Drive\n")
                if decision == '1':
                    self.download_file(item['id'], local_path, item['mimeType'])
                    print(f"File {item['name']} downloaded from Drive succellfully!")
                    break
                elif decision == '2':
                    self.service.files().delete(fileId=item['id']).execute()
                    print(f"File {item['name']} deleted from Drive succellfully!")
                    break
                else:
                    print("Wrong number, only 1 or 2")

        elif item["md5Checksum"] != self.calculate_md5_hash(local_path):
            print(f'File was updated: {path} -- {item["id"]}')

    def get_file(self, file_id):
        item = self.service.files().get(fileId=file_id, fields='*').execute()
        
        for k,v in item.items():
            print(k, '    ', v)

    def find_by_name(self, name):
        query = f"'me' in owners and name = '{name}'"  #  and mimeType = 'application/vnd.google-apps.folder'
        results = self.service.files().list(q=query, fields="nextPageToken, files(id, name, mimeType, md5Checksum)").execute()
        print(results.get('files'))

    @staticmethod
    def calculate_md5_hash(path):
        with open(path, "rb") as f:
            bytes_data = f.read() 

        return hashlib.md5(bytes_data).hexdigest()


if __name__ == '__main__':
    service = main()
    sync = Syncronizer(service)

    sync.traverse_drive('root')
    