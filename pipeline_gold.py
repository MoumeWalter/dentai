import cv2
import numpy as np
from minio import Minio
import os
from dotenv import load_dotenv
from io import BytesIO
from tqdm import tqdm
import json

load_dotenv()

client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

GOLD_BUCKET = "gold"

if not client.bucket_exists(GOLD_BUCKET):
    client.make_bucket(GOLD_BUCKET)

def flip_horizontal(image):
    return cv2.flip(image, 1)

def rotation_legere(image, angle=10):
    h, w = image.shape
    centre = (w // 2, h // 2)
    matrice = cv2.getRotationMatrix2D(centre, angle, 1.0)
    return cv2.warpAffine(image, matrice, (w, h))

def ajuster_luminosite(image, valeur=30):
    return cv2.add(image, valeur)
# Lister toutes les images de silver/classification/
objects = client.list_objects("silver", prefix="classification/", recursive=True)

for obj in tqdm(list(objects)):
    # Télécharger depuis silver
    response = client.get_object("silver", obj.object_name)
    image_bytes = response.read()
    response.close()
    
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    
    # Construire le dictionnaire chemin -> image (original + augmentations)
    chemin_base = obj.object_name.rsplit('.', 1)[0]  # enlève l'extension
    
    versions = {
        obj.object_name: image,
        f"{chemin_base}_flip.jpg": flip_horizontal(image),
        f"{chemin_base}_rot.jpg": rotation_legere(image),
        f"{chemin_base}_bright.jpg": ajuster_luminosite(image)
    }
    
    for chemin, img_v in versions.items():
        _, buffer = cv2.imencode('.jpg', img_v)
        img_bytes = buffer.tobytes()
        client.put_object(GOLD_BUCKET, chemin, BytesIO(img_bytes), length=len(img_bytes))

print("Classification augmentée dans Gold !")

#deetection dentex
response = client.get_object("silver", "detection/dentex/annotations.json")
annotations_data = json.loads(response.read())
response.close()

nouvelles_images = []
nouvelles_annotations = []

# IDs de départ pour les nouvelles entrées (éviter les doublons)
next_image_id = max(img['id'] for img in annotations_data['images']) + 1
next_ann_id = max(ann['id'] for ann in annotations_data['annotations']) + 1

for img_info in tqdm(annotations_data['images']):
    file_name = img_info['file_name']
    
    # Télécharger depuis silver
    response = client.get_object("silver", f"detection/dentex/images/{file_name}")
    image_bytes = response.read()
    response.close()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    
    # 1. Upload ORIGINALE vers gold (inchangée)
    _, buffer = cv2.imencode('.jpg', image)
    img_bytes = buffer.tobytes()
    client.put_object(GOLD_BUCKET, f"detection/dentex/images/{file_name}", BytesIO(img_bytes), length=len(img_bytes))
    nouvelles_images.append(img_info)  # on garde l'entrée originale
    
    # 2. Créer le FLIP
    image_flip = flip_horizontal(image)
    flip_name = f"flip_{file_name}"
    
    # Upload flip
    _, buffer = cv2.imencode('.jpg', image_flip)
    img_bytes = buffer.tobytes()
    client.put_object(GOLD_BUCKET, f"detection/dentex/images/{flip_name}", BytesIO(img_bytes), length=len(img_bytes))
    
    # Nouvelle entrée image pour le flip
    nouvelle_image_info = {
        "id": next_image_id,
        "file_name": flip_name,
        "width": img_info['width'],
        "height": img_info['height']
    }
    nouvelles_images.append(nouvelle_image_info)

    # Traiter les annotations de cette image pour le flip
    annotations_image = [ann for ann in annotations_data['annotations'] if ann['image_id'] == img_info['id']]

    for ann in annotations_image:
        x, y, w, h = ann['bbox']
        nouveau_x = img_info['width'] - x - w
        
        nouvelle_annotation = {
            "id": next_ann_id,
            "image_id": next_image_id,
            "bbox": [nouveau_x, y, w, h],
            "category_id_3": ann['category_id_3'],
            "area": ann['area'],
            "iscrowd": 0
        }
        nouvelles_annotations.append(nouvelle_annotation)
        next_ann_id += 1

    # Conserver aussi les annotations originales
    nouvelles_annotations.extend(annotations_image)

    next_image_id += 1

annotations_data['images'] = nouvelles_images
annotations_data['annotations'] = nouvelles_annotations

annotations_json = json.dumps(annotations_data).encode('utf-8')

client.put_object(
    GOLD_BUCKET,
    "detection/dentex/annotations.json",
    BytesIO(annotations_json),
    length=len(annotations_json)
)

print(f"DENTEX Gold : {len(nouvelles_images)} images, {len(nouvelles_annotations)} annotations")