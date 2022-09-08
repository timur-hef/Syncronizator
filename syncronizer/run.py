import os
import requests

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from syncronizer.worker import Syncronizer
from syncronizer.utils import BASE_FOLDER, CONFIG_FOLDER


SCOPES = [
    'https://www.googleapis.com/auth/drive',
]


def get_service():
    """
    Return service for using Google Drive API
    """

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


def main():
    service = get_service()
    sync = Syncronizer(service)

    while True:
        print(
            '--------------------------------------------------------------------\n'
            '1. Scan\n'
            '2. Sync through Drive (new files from Local storage will be removed)\n'
            '3. Sync through Local\n'
            '4. Exit'
        )
        choice = input('Enter number: ')
        print()

        if choice == '1':
            sync.scan()
        elif choice == '2':
            pass
        elif choice == '3':
            pass
        elif choice == '4':
            break
        else:
            print('Wrong number!\n')


if __name__ == '__main__':
    main()
