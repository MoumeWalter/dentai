from minio import Minio
import os
from dotenv import load_dotenv
from pathlib import Path
from tqdm import tqdm

load_dotenv()

client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

LOCAL_PATH = Path(r"C:\Users\walte\OneDrive\Documents\Projects\dentai\Gold_Data")

objects = client.list_objects("gold", prefix="classification/", recursive=True)

for obj in tqdm(list(objects)):
    chemin_local = LOCAL_PATH / obj.object_name
    chemin_local.parent.mkdir(parents=True, exist_ok=True)
    client.fget_object("gold", obj.object_name, str(chemin_local))

print("Téléchargement terminé !")