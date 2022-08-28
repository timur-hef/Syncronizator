import hashlib
import io
import os

from typing import Dict

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from utils import BASE_FOLDER


class Syncronizer:
    def __init__(self, service):
        self.service = service

    def traverse_drive(self, parent: str, path: str = '') -> None:
        """
        Recursive traverse through objects in Google Drive

        :param parent: id of the parent folder
        :param path: absolute path in Google Drive File System
        """

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

    def download_file(self, file_id: str, path: str, mime_type: str) -> None:
        """
        Download file from Google Drive

        :param file_id: id of the file
        :param path: relative path to the file in a local storage (absolute path in Google Drive)
        :param mime_type: mime type of the file
        """

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
  
    def check_in_local(self, path: str, item: Dict) -> None:
        """
        Check file from drive in local storage. If file is changed you can rewrite it either on local or drive.
        If file doesn't exist in local storage you can either delete it from drive or add it to local storage.

        :param path: relative path in a local storage
        :param item: JSON object representing a file info
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

    def get_file(self, file_id: str) -> None:
        """
        Print out all info about the object (file) in Google Drive

        :param file_id: id of the file
        """

        item = self.service.files().get(fileId=file_id, fields='*').execute()
        
        for k,v in item.items():
            print(k, '    ', v)

    def find_by_name(self, name: str) -> None:
        """
        Find a file in Google Drive by the name anf print info

        :param name: name of the searched file
        """

        query = f"'me' in owners and name = '{name}'"  #  and mimeType = 'application/vnd.google-apps.folder'
        results = self.service.files().list(q=query, fields="nextPageToken, files(id, name, mimeType, md5Checksum)").execute()
        print(results.get('files'))

    @staticmethod
    def calculate_md5_hash(path: str) -> str:
        """
        Calculate md5 checksum of the file in the local storage and return it

        :param path: absolute path to file in the local storage
        """

        with open(path, "rb") as f:
            bytes_data = f.read() 

        return hashlib.md5(bytes_data).hexdigest()
        