
import psycopg
import os

conn_info = os.getenv("POSTGRES_URL")
sync_connection = psycopg.connect(conn_info)

# class PsychopgClient:
#   _instance = None

#   def __new__(cls, *args, **kwargs):
#     if cls._instance is None:
#       cls._instance = super(PsychopgClient, cls).__new__(cls, *args, **kwargs)
#     return cls._instance

#   @staticmethod
#   def get_client():
#     conn_info = os.getenv("POSTGRES_URL")
#     sync_connection = psycopg.connect(conn_info)
#     return sync_connection

# class PsychopgClient:
#   @staticmethod
#   def get_client():
#     conn_info = os.getenv("POSTGRES_URL")
#     sync_connection = psycopg.connect(conn_info)