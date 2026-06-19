import cv2
import numpy as np
from minio import Minio
import psycopg2
import os
import time
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from dotenv import load_dotenv
from datetime import date

load_dotenv()

minio_client = Minio(
    "localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    secure=False
)

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD")
)
cursor = conn.cursor()

BUCKET_CABINET = "radios-dentaires"
INTERVALLE_SECONDES = 5

CLASSES = ['caries', 'fractured_teeth', 'healthy_teeth', 'impacted_teeth', 'infection']

modele = models.resnet18()
modele.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
modele.fc = nn.Sequential(
    nn.Dropout(0.5),
    nn.Linear(modele.fc.in_features, len(CLASSES))
)
modele.load_state_dict(torch.load("best_model.pth", map_location="cpu"))
modele.eval()

transformation = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5], std=[0.5])
])


def extraire_id_radio(nom_fichier: str) -> int:
    nom_sans_extension = nom_fichier.rsplit('.', 1)[0]
    return int(nom_sans_extension.removeprefix("radio_"))


def appliquer_clahe(image_gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image_gray)


print("Watcher démarré, surveillance du cabinet en cours...")

while True:
    cursor.execute("SELECT Id_radio FROM resultat")
    ids_deja_traites = {row[0] for row in cursor.fetchall()}

    objets_actuels = minio_client.list_objects(
        BUCKET_CABINET, prefix="panoramique/", recursive=True
    )

    for obj in objets_actuels:
        chemin_complet = obj.object_name
        nom_fichier = chemin_complet.split('/')[-1]

        try:
            id_radio = extraire_id_radio(nom_fichier)
        except ValueError:
            continue

        if id_radio in ids_deja_traites:
            continue

        response = minio_client.get_object(BUCKET_CABINET, chemin_complet)
        image_bytes = response.read()
        response.close()

        image_gray = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        image_clahe = appliquer_clahe(image_gray)

        image_pil = Image.fromarray(image_clahe)
        tenseur = transformation(image_pil).unsqueeze(0)

        with torch.no_grad():
            sortie = modele(tenseur)
            probabilites = torch.softmax(sortie, dim=1)
            indice_predit = torch.argmax(probabilites, dim=1).item()
            score_confiance = probabilites[0][indice_predit].item()

        pathologie_predite = CLASSES[indice_predit]

        cursor.execute("""
            INSERT INTO resultat (pathologie, score_confiance, Date_resultat, Id_radio)
            VALUES (%s, %s, %s, %s)
        """, (pathologie_predite, round(score_confiance, 2), date.today(), id_radio))
        conn.commit()

        print(f"Radio {id_radio} analysée : {pathologie_predite} "
              f"(confiance {score_confiance:.2f})")

    time.sleep(INTERVALLE_SECONDES)