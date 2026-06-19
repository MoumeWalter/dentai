import cv2
import numpy as np
from minio import Minio
import os
from dotenv import load_dotenv
from io import BytesIO
import json
from pymongo import MongoClient
from datetime import datetime, timezone
from tqdm import tqdm

load_dotenv()

# --- Connexion MinIO (reprise à l'identique de tes autres scripts) ---
minio_client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

# --- Connexion MongoDB ---
# On utilise localhost:27018 car c'est le port HÔTE qu'on a choisi dans le
# docker-compose.yml (le conteneur écoute sur 27017 en interne, mais ce port
# est mappé vers 27018 côté machine Windows pour éviter le conflit avec ton
# autre installation Mongo locale).
mongo_client = MongoClient(
    "localhost",
    27018,
    username=os.getenv("MONGO_USER"),
    password=os.getenv("MONGO_PASSWORD")
)

# Une base Mongo se crée implicitement à la première écriture — pas besoin
# d'équivalent à client.make_bucket() ou CREATE DATABASE. On la nomme ici.
db = mongo_client[os.getenv("MONGO_DB")]
collection_images = db["images"]
collection_annotations = db["annotations"]

# --- Téléchargement du JSON COCO final depuis Gold ---
response = minio_client.get_object("gold", "detection/dentex/annotations.json")
annotations_data = json.loads(response.read())
response.close()

print(f"JSON chargé : {len(annotations_data['images'])} images, "
      f"{len(annotations_data['annotations'])} annotations à migrer")


def generer_image_id(id_coco: int) -> str:
    """
    Transforme l'entier id du JSON COCO (ex: 123) en notre format de
    référence métier (ex: "img_000123"), utilisé comme champ `image_id`
    à la fois dans la collection images et dans la collection annotations
    (clé de liaison entre les deux, équivalent d'une foreign key).

    Le zéro-padding sur 6 chiffres (:06d) garantit un tri alphabétique
    cohérent avec l'ordre numérique (img_000123 < img_001000), ce qui
    serait faux sans padding (img_123 > img_1000 alphabétiquement).
    """
    return f"img_{id_coco:06d}"

print(generer_image_id(123))

# Construit AVANT la boucle, une seule fois : dictionnaire pour accès O(1)
# par nom de fichier, au lieu de scanner toute la liste à chaque flip.
# Même logique que images_par_id dans pipeline_silver.py.

CATEGORIES_DENTEX = {
    0: "Impacted",
    1: "Caries",
    2: "Periapical Lesion",
    3: "Deep Caries"
}

def generer_annotation_id(id_coco: int) -> str:
    """
    Même logique que generer_image_id : transforme l'entier COCO en
    référence métier lisible, cohérente dans tout le projet.
    """
    return f"ann_{id_coco:06d}"


for ann in tqdm(annotations_data['annotations']):
    x, y, w, h = ann['bbox']
    category_id = ann['category_id_3']

    annotation_doc = {
        "annotation_id": generer_annotation_id(ann['id']),
        "image_id": generer_image_id(ann['image_id']),
        "category_id": category_id,
        "category_name": CATEGORIES_DENTEX[category_id],
        "bbox": {
            "x": x,
            "y": y,
            "width": w,
            "height": h
        },
        "area": ann['area'],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    collection_annotations.insert_one(annotation_doc)