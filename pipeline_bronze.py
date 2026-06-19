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

BUCKET_NAME = "bronze"

if not client.bucket_exists(BUCKET_NAME):
    client.make_bucket(BUCKET_NAME)
    print(f"Bucket {BUCKET_NAME} créé !")
else:
    print(f"Bucket {BUCKET_NAME} existe déjà !")

def upload_bronze(chemin_local, chemin_minio):
    client.fput_object(
        BUCKET_NAME,
        chemin_minio,
        str(chemin_local)
    )

# Suppression dataset2 (classes inconue , irrelevent)
objects = client.list_objects(BUCKET_NAME, prefix="detection/dataset_opg/", recursive=True)
for obj in objects:
    client.remove_object(BUCKET_NAME, obj.object_name)
    
print("Dataset OPG Object Detection supprimé du bronze !")

dataset1_path = Path(r"C:\Users\walte\OneDrive\Documents\Projects\Dental OPG XRAY Dataset\Dental OPG (Classification)")

classes = ["Caries", "Fractured Teeth", "Healthy Teeth", "Impacted teeth", "Infection"]

for classe in classes:
    dossier_classe = dataset1_path / classe
    images = list(dossier_classe.glob("*.jpg"))
    
    for image in images:
        chemin_minio = f"classification/{classe.lower().replace(' ', '_')}/{image.name}"
        upload_bronze(image, chemin_minio)
    
    print(f"{classe} : {len(images)} images uploadées")

#dataset2_path = Path(r"C:\Users\walte\OneDrive\Documents\Projects\Dental OPG XRAY Dataset\Dental OPG (Object Detection)\Augmented Dataset")
#
#splits = ["train", "test", "valid"]
#
#for split in splits:
#   images_path = dataset2_path / split / "images"
#   labels_path = dataset2_path / split / "labels"
#    
#    images = list(images_path.glob("*.jpg"))
#    
#    for image in images:
        # Upload de l'image
#        chemin_minio_image = f"detection/dataset_opg/{split}/images/{image.name}"
#        upload_bronze(image, chemin_minio_image)
        
        # Upload du label correspondant
#        label_file = labels_path / (image.stem + ".txt")
#        if label_file.exists():
#            chemin_minio_label = f"detection/dataset_opg/{split}/labels/{label_file.name}"
#            upload_bronze(label_file, chemin_minio_label)
#    
#    print(f"{split} : {len(images)} images uploadées")

dentex_path = Path(r"C:\Users\walte\OneDrive\Documents\Projects\training_data\quadrant-enumeration-disease")

images_path = dentex_path / "xrays"
images = list(images_path.glob("*.png"))

for image in images:
    chemin_minio = f"detection/dentex/images/{image.name}"
    upload_bronze(image, chemin_minio)

print(f"DENTEX : {len(images)} images uploadées")

# Upload du JSON d'annotations
json_file = dentex_path / "train_quadrant_enumeration_disease.json"
upload_bronze(json_file, "detection/dentex/annotations.json")