from google.cloud import storage
from google.oauth2 import service_account
import google.auth
import os
import json

class GCSClient:
  @staticmethod
  def get_storage_client():

    if (os.getenv("ENVIRONMENT") == "production"):
      GCS_SA = json.loads(os.getenv('GCS_SA'))

      print("ENVIRONMENT")
      print(os.getenv("ENVIRONMENT"))

      # Load credentials from the dictionary
      credentials, project = google.auth.load_credentials_from_dict(GCS_SA)
      
      print()
      print('credentials', credentials)
      print('project', project)
      print()
      
      return storage.Client(credentials=credentials, project=project) 
    else:
      print("*!*!* get_storage_client credential *!*!*")

      GCS_SA_PATH = os.getenv("GCS_SA_PATH")
      print("GCS_SA_PATH", GCS_SA_PATH)
      credentials = service_account.Credentials.from_service_account_file(
        GCS_SA_PATH
      )
      
      return storage.Client(credentials=credentials)
  