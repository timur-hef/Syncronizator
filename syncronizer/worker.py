import hashlib
import io
import os

from typing import Dict

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from syncronizer.utils import BASE_FOLDER


class Syncronizer:
    def __init__(self, service):
        self.service = service
        self.__new_drive = []
        self.__new_local = []
        self.__updated = []
        self.__errors = []


    def scan(self):
        print('Scanning Drive...')
        self._traverse_drive()

        print('Scanning local storage...')
        self._traverse_local()

        print()
        print(f'New files [Drive] - {len(self.__new_drive)}:\n')
        for item in self.__new_drive:
            print(item)

        print()
        print(f'New files [Local] - {len(self.__new_local)}:\n')
        for item in self.__new_local:
            print(item)

        print()
        print(f'Updated files - {len(self.__updated)}:\n')
        for item in self.__updated:
            print(item)

        print()
        print(f'Errors - {len(self.__errors)}:\n')
        for item in self.__errors:
            print(item)
        
        self.reset_numbers()

    def _traverse_drive(self, parent: str = 'root', path: str = '') -> None:
        """
        Recursive traverse through objects in Google Drive

        :param parent: id of the parent folder
        :param path: absolute path in Google Drive File System
        """

        try:
            query = f"'me' in owners and '{parent}' in parents and trashed = false"
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
                        self._traverse_drive(item['id'], new_path)
                    else:
                        self._check_in_local(new_path, item)

                if not page_token:
                    flag = False
                
        except HttpError as error:
            self.__errors.append(path)
            print(f'An error occurred: {error}')

    def _traverse_local(self, current_path = BASE_FOLDER, current_dir_id = 'root') -> None:
        """
        Recursive traverse through objects in local storage
        """

        try:
            for elem in os.listdir(current_path):
                abs_path = os.path.join(current_path, elem)

                if os.path.isdir(abs_path):
                    if current_dir_id is not None:
                        filters = [
                            "'me' in owners",
                            f"name = '{elem}'",
                            "trashed = false",
                            "mimeType = 'application/vnd.google-apps.folder'",
                            f"'{current_dir_id}' in parents",
                        ]

                        query = ' and '.join(filters)

                        result = self.service.files().list(q=query, fields="nextPageToken, files(id)").execute()
                        items = result.get('files')
                        dir_id = items[0]['id'] if items else None
                
                    self._traverse_local(
                        current_path=os.path.join(current_path, elem),
                        current_dir_id=dir_id
                    )
                else:
                    if current_dir_id is None:
                        self.__new_local.append(abs_path)
                        continue

                    query = f"'me' in owners and name = '{elem}' and '{current_dir_id}' in parents"
                    result = self.service.files().list(q=query, fields="nextPageToken, files(id, name, mimeType, md5Checksum)").execute()
                    item = result.get('files')
                    if not item:
                        self.__new_local.append(abs_path)
        except Exception as e:
            self.__errors.append(abs_path)
            print(f'An error occurred: {e}')

    def _download(self, file_id: str, path: str, mime_type: str) -> None:
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
                print(f"Downloading file {path}...  {round(status.progress()*100)}%", end='\r')

            print()
            data = obj.getvalue()
            
            print('Writing into disk...')
            with open(path, 'wb') as f:
                f.write(data)
            print('Done')

        except HttpError as error:
            print(F'An error when downloading file {file_id} occurred: {error}')

    def _upload(self, path, mimetype, name):
        """
        Upload file to Google Drive. Download will be in multiple requests with chunks size 4 MB
        """

        file_metadata = {'name': name}
        media = MediaFileUpload(
            path, 
            mimetype=mimetype, 
            resumable=True,
            chunksize=1024*1024*4,
        )

        some = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
        )
        
        response = None
        while response is None:
            status, response = some.next_chunk()
            if status:
                print (f"Uploading file... {round(status.progress() * 100)}%", end='\r')

        print()
        print('File {} has been uploaded!')
  
    def _check_in_local(self, path: str, item: Dict) -> None:
        """
        Check file from drive in local storage. If file is changed you can rewrite it either on local or drive.
        If file doesn't exist in local storage you can either delete it from drive or add it to local storage.

        :param path: relative path in a local storage
        :param item: JSON object representing a file info
        """

        local_path = os.path.join(BASE_FOLDER, path)
        if not os.path.exists(local_path):
            self.__new_drive.append(path)

        elif item["md5Checksum"] != self._calculate_md5_hash(local_path):
            self.__updated.append(path)

    def _get_file(self, file_id: str) -> None:
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

        query = f"'me' in owners and name = '{name}' and trashed = false"
        results = self.service.files().list(q=query, fields="nextPageToken, files(*)").execute()

        item = results.get('files')
        
        if not item:
            print(f'{name} was not found in Google Drive')
        else:
            for k,v in item[0].items():
                print(k, '    ', v)

        return item

    @staticmethod
    def _calculate_md5_hash(path: str) -> str:
        """
        Calculate md5 checksum of the file in the local storage and return it

        :param path: absolute path to file in the local storage
        """

        with open(path, "rb") as f:
            bytes_data = f.read() 

        return hashlib.md5(bytes_data).hexdigest()

    def reset_numbers(self):
        self.__new_drive.clear()
        self.__new_local.clear()
        self.__updated.clear()
        self.__errors.clear()
