from google.cloud import pubsub_v1
from google.oauth2 import service_account
import google.auth
import os
import json

class PubSubClient:
    @staticmethod
    def get_publisher_client():
        """Get a Pub/Sub publisher client with appropriate credentials."""
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
            
            return pubsub_v1.PublisherClient(credentials=credentials)
        else:
            GCS_SA_PATH = os.getenv("GCS_SA_PATH")
            credentials = service_account.Credentials.from_service_account_file(
                GCS_SA_PATH
            )
            
            return pubsub_v1.PublisherClient(credentials=credentials)
    