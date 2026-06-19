import cv2
import numpy as np
from minio import Minio
import psycopg2
import os
import random
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv
from datetime import date
from io import BytesIO

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

# Dossiers du réservoir : la racine contient les images "non traitées",
# le sous-dossier traitees/ reçoit celles déjà simulées (Approche A).
DOSSIER_RESERVOIR = Path(r"C:\Users\walte\OneDrive\Documents\Projects\dentai\New_radio")
DOSSIER_TRAITEES = DOSSIER_RESERVOIR / "traitees"
DOSSIER_TRAITEES.mkdir(exist_ok=True)  # crée le sous-dossier s'il n'existe pas déjà

INTERVALLE_SECONDES = 5  # délai simulé entre deux "arrivées" de radio

# On récupère une seule fois, avant la boucle, les patients et chirurgiens
# existants — pas besoin de les requêter à nouveau à chaque itération,
# leur liste ne change pas pendant que le simulateur tourne.
cursor.execute("SELECT id_patient FROM patient")
patient_ids = [row[0] for row in cursor.fetchall()]

cursor.execute("SELECT id_chirurgien FROM chirurgien")
chirurgien_ids = [row[0] for row in cursor.fetchall()]


def images_restantes():
    """
    Liste les fichiers image présents directement dans DOSSIER_RESERVOIR
    (pas dans traitees/, puisque glob() sur la racine ne descend pas dans
    les sous-dossiers par défaut). C'est cette fonction qui nous dit à
    chaque tour de boucle s'il reste du travail à faire.
    """
    return list(DOSSIER_RESERVOIR.glob("*.png")) + list(DOSSIER_RESERVOIR.glob("*.jpg"))

print(f"{len(images_restantes())} radios en attente dans le réservoir")

# La condition d'arrêt : tant que la liste retournée par images_restantes()
# est non vide. Une liste vide est "falsy" en Python (équivalent à False
# dans un test booléen), donc `while images_restantes():` s'arrête
# automatiquement dès que glob() ne trouve plus rien — pas besoin de
# comparer explicitement à 0.
while images_restantes():
    chemin_image_locale = images_restantes()[0]  # la première de la liste

    # 2. Choisir patient et chirurgien au hasard parmi l'existant
    id_patient = random.choice(patient_ids)
    id_chirurgien = random.choice(chirurgien_ids)

    # 3. Insérer la nouvelle consultation, datée d'aujourd'hui réellement
    cursor.execute("""
        INSERT INTO consultation (Date_consultation, Id_patient, Id_chirurgien)
        VALUES (%s, %s, %s)
        RETURNING id_consultation
    """, (date.today(), id_patient, id_chirurgien))
    id_consultation = cursor.fetchone()[0]

    # 4 et 5. Insérer la radio, avec un chemin temporaire — on a besoin de
    # connaître l'id_radio généré par PostgreSQL AVANT de pouvoir construire
    # le nom de fichier définitif (puisqu'il en dépend). Donc on insère
    # d'abord avec un chemin provisoire, puis on met à jour juste après.
    annee_courante = date.today().year
    cursor.execute("""
        INSERT INTO radio (Type_radio, chemin_fichier, Date_radio, Id_consultation)
        VALUES (%s, %s, %s, %s)
        RETURNING id_radio
    """, ('panoramique', 'temp', date.today(), id_consultation))
    id_radio = cursor.fetchone()[0]

    chemin_fichier = f"panoramique/{annee_courante}/radio_{id_radio}.jpg"

    cursor.execute("""
        UPDATE radio SET chemin_fichier = %s WHERE id_radio = %s
    """, (chemin_fichier, id_radio))

    conn.commit()

    # 6. Lire le fichier local et le déposer dans MinIO au chemin construit
    image = cv2.imread(str(chemin_image_locale))
    _, buffer = cv2.imencode('.jpg', image)
    img_bytes = buffer.tobytes()
    minio_client.put_object(
        "radios-dentaires",
        chemin_fichier,
        BytesIO(img_bytes),
        length=len(img_bytes)
    )

    # Déplacer le fichier local vers traitees/ : il ne sera plus jamais
    # vu par images_restantes() au prochain tour de boucle.
    shutil.move(str(chemin_image_locale), str(DOSSIER_TRAITEES / chemin_image_locale.name))

    print(f"Radio simulée : patient {id_patient}, consultation {id_consultation}, "
          f"radio {id_radio} -> {chemin_fichier}")

    time.sleep(INTERVALLE_SECONDES)

print("Réservoir épuisé, simulateur arrêté.")
cursor.close()
conn.close()