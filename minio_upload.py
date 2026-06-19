from minio import Minio
import os
from dotenv import load_dotenv
from pathlib import Path
import psycopg2

load_dotenv()

client = Minio(
    "localhost:9000",  # adresse de MinIO
    access_key=os.getenv("MINIO_ROOT_USER"), # Id admin
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"), # mdp
    secure=False      # pas de HTTPS en local
)

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD")
)

cursor = conn.cursor()
print("Connexion réussie !")

dataset_path = Path(r"C:\Users\walte\OneDrive\Documents\Projects\dentai\PatientRadios")
# Lister toutes les images
images = list(dataset_path.glob("**/*.jpg")) + \
         list(dataset_path.glob("**/*.png"))

print(f"Nombre d'images trouvées : {len(images)}")

# Prendre seulement 150 images
images_selectionnees = images[:150]

# Récupérer les ids_radio et chemins depuis PostgreSQL
cursor.execute("""
    SELECT id_radio, date_radio 
    FROM radio 
    ORDER BY id_radio 
    LIMIT 150
""")
rows = cursor.fetchall()
BUCKET_NAME = "radios-dentaires"

for (radio_id, date_radio), image in zip(rows, images_selectionnees):
    nouveau_chemin = f"panoramique/{date_radio.year}/{image.name}"
    
    # Uploader dans MinIO
    client.fput_object(
        BUCKET_NAME,      # nom du bucket
        nouveau_chemin,   # chemin dans MinIO
        str(image)   # chemin local sur ton PC
    )
    
    # Mettre à jour PostgreSQL
    cursor.execute("""
        UPDATE radio 
        SET chemin_fichier = %s 
        WHERE id_radio = %s
    """, (nouveau_chemin, radio_id))

conn.commit()
print("Upload terminé!")
cursor.close()
conn.close()