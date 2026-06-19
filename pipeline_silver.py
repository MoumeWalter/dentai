import cv2
import numpy as np
from minio import Minio
import os
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)
#test
# Lire une image
image = cv2.imread(r"C:\Users\walte\OneDrive\Documents\Projects\training_data\quadrant-enumeration-disease\xrays\train_0.png")

# Convertir en niveaux de gris (les radios sont en gris)
gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Appliquer CLAHE
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
image_clahe = clahe.apply(gris)

# Redimensionner
image_redim = cv2.resize(image_clahe, (224, 224))

# Sauvegarder pour vérifier visuellement
cv2.imwrite("test_silver.jpg", image_redim)

def traiter_image(image_bytes):
    # 1. Décoder les bytes en image OpenCV
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    
    # 2. Appliquer CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    image_clahe = clahe.apply(image)
    
    # 3. Redimensionner
    image_redim = cv2.resize(image_clahe, (224, 224))
    
    # 4. Encoder en bytes pour upload
    _, buffer = cv2.imencode('.jpg', image_redim)
    return buffer.tobytes()

SILVER_BUCKET = "silver"

if not client.bucket_exists(SILVER_BUCKET):
    client.make_bucket(SILVER_BUCKET)

# Lister toutes les images de bronze/classification/
objects = client.list_objects("bronze", prefix="classification/", recursive=True)

for obj in objects:
    # 1. Télécharger depuis bronze
    response = client.get_object("bronze", obj.object_name)
    image_bytes = response.read()
    response.close()
    
    # 2. Traiter l'image
    image_traitee = traiter_image(image_bytes)
    
    # 3. Upload vers silver (même chemin)
    from io import BytesIO
    client.put_object(
        SILVER_BUCKET,
        obj.object_name,
        BytesIO(image_traitee),
        length=len(image_traitee)
    )

print("Classification traitée !")

import json
from io import BytesIO

# Télécharger annotations.json depuis bronze
response = client.get_object("bronze", "detection/dentex/annotations.json")
annotations_data = json.loads(response.read())
response.close()

print(f"Nombre d'images : {len(annotations_data['images'])}")
print(f"Nombre d'annotations : {len(annotations_data['annotations'])}")
print(f"Exemple image : {annotations_data['images'][0]}")

for img_info in tqdm(annotations_data['images']):
    file_name = img_info['file_name']
    
    # Télécharger
    response = client.get_object("bronze", f"detection/dentex/images/{file_name}")
    image_bytes = response.read()
    response.close()
    
    # Traiter
    image_traitee = traiter_image(image_bytes)
    
    # Upload vers silver
    from io import BytesIO
    client.put_object(
    SILVER_BUCKET,
    f"detection/dentex/images/{file_name}",  # chemin construit ici
    BytesIO(image_traitee),
    length=len(image_traitee)
)
print("DENTEX images traitées !")

images_par_id = {img['id']: img for img in annotations_data['images']}
for ann in annotations_data['annotations']:
    # Trouver l'image correspondante pour avoir width/height
    img_info = images_par_id[ann['image_id']]
    
    scale_x = 224 / img_info['width']
    scale_y = 224 / img_info['height']
    
    x, y, w, h = ann['bbox']
    ann['bbox'] = [x * scale_x, y * scale_y, w * scale_x, h * scale_y]
print("Bboxes recalculées !")

annotations_json = json.dumps(annotations_data).encode('utf-8')

client.put_object(
    SILVER_BUCKET,
    "detection/dentex/annotations.json",
    BytesIO(annotations_json),
    length=len(annotations_json)
)

print("Annotations JSON sauvegardées dans silver !")

