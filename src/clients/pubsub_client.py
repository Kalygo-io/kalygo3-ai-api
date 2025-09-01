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
            KB_INGEST_SA = json.loads(os.getenv('KB_INGEST_SA'))

            print('KB_INGEST_SA', KB_INGEST_SA)

            print("ENVIRONMENT")
            print(os.getenv("ENVIRONMENT"))

            # Load credentials from the dictionary
            credentials, project = google.auth.load_credentials_from_dict(KB_INGEST_SA)
            
            print()
            print('credentials', credentials)
            print('project', project)
            print()
            
            return pubsub_v1.PublisherClient(credentials=credentials)
        else:
            KB_INGEST_SA = os.getenv("KB_INGEST_SA")
            credentials = service_account.Credentials.from_service_account_file(
                KB_INGEST_SA
            )
            
            return pubsub_v1.PublisherClient(credentials=credentials)
