import json
import os
from pathlib import Path
from minio import Minio
from dotenv import load_dotenv
from tqdm import tqdm
import shutil
import random
from ultralytics import YOLO

load_dotenv()

client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

# Dossier local de destination
OUTPUT_PATH = Path(r"C:\Users\walte\OneDrive\Documents\Projects\dentai\Gold_Data\detection_yolo")

# Créer la structure YOLO
for split in ["train", "val", "test"]:
    (OUTPUT_PATH / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUTPUT_PATH / "labels" / split).mkdir(parents=True, exist_ok=True)

import yaml

data_yaml = {
    "path": str(OUTPUT_PATH),
    "train": "images/train",
    "val": "images/val",
    "test": "images/test",
    "nc": 4,
    "names": {
        0: "impacted",
        1: "caries",
        2: "periapical_lesion",
        3: "deep_caries"
    }
}

with open(OUTPUT_PATH / "data.yaml", "w") as f:
    yaml.dump(data_yaml, f, default_flow_style=False)

def coco_to_yolo(bbox, img_width, img_height):
    x, y, w, h = bbox
    x_center = (x + w / 2) / img_width
    y_center = (y + h / 2) / img_height
    w_norm   = w / img_width
    h_norm   = h / img_height
    return x_center, y_center, w_norm, h_norm

print("data.yaml créé !")

random.seed(42)

# Charger annotations.json depuis MinIO gold
response = client.get_object("gold", "detection/dentex/annotations.json")
annotations_data = json.loads(response.read())
response.close()

# Créer dictionnaire {image_id: annotations}
anns_par_image = {}
for ann in annotations_data['annotations']:
    img_id = ann['image_id']
    if img_id not in anns_par_image:
        anns_par_image[img_id] = []
    anns_par_image[img_id].append(ann)

# Traiter chaque image
for img_info in tqdm(annotations_data['images']):
    img_id = img_info['id']
    file_name = img_info['file_name']
    img_width = img_info['width']
    img_height = img_info['height']

    # Assigner un split aléatoire
    split = random.choices(["train", "val", "test"], weights=[0.7, 0.15, 0.15])[0]

    # Télécharger l'image depuis gold
    chemin_local = OUTPUT_PATH / "images" / split / file_name
    client.fget_object("gold", f"detection/dentex/images/{file_name}", str(chemin_local))

    # Créer le fichier label YOLO
    label_path = OUTPUT_PATH / "labels" / split / (Path(file_name).stem + ".txt")
    
    with open(label_path, "w") as f:
        for ann in anns_par_image.get(img_id, []):
            x_c, y_c, w_n, h_n = coco_to_yolo(ann['bbox'], img_width, img_height)
            class_id = ann['category_id_3']
            f.write(f"{class_id} {x_c:.6f} {y_c:.6f} {w_n:.6f} {h_n:.6f}\n")

print("Dataset YOLO préparé !")


# Charger YOLOv8 nano (le plus léger, idéal sans GPU)
model = YOLO("yolov8n.pt")

results = model.train(
    data=r"C:\Users\walte\OneDrive\Documents\Projects\dentai\Gold_Data\detection_yolo\data.yaml",
    epochs=20,
    imgsz=640,
    batch=8,
    name="dentai_detection_v2",
    patience=5
)