from google.cloud import storage
from google.oauth2 import service_account
import google.auth
import os
import json

class GCSClient:
  @staticmethod
  def get_storage_client():

    if (os.getenv("ENVIRONMENT") == "production"):
      KB_INGEST_SA = json.loads(os.getenv('KB_INGEST_SA'))

      print("ENVIRONMENT")
      print(os.getenv("ENVIRONMENT"))

      # Load credentials from the dictionary
      credentials, project = google.auth.load_credentials_from_dict(KB_INGEST_SA)
      
      print()
      print('credentials', credentials)
      print('project', project)
      print()
      
      return storage.Client(credentials=credentials, project=project) 
    else:
      print("*!*!* get_storage_client credential *!*!*")

      KB_INGEST_SA = os.getenv("KB_INGEST_SA")
      print("KB_INGEST_SA", KB_INGEST_SA)
      credentials = service_account.Credentials.from_service_account_file(
        KB_INGEST_SA
      )
      
      return storage.Client(credentials=credentials)
  