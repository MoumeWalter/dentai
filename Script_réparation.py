from minio import Minio
import psycopg2
import os
import random
from faker import Faker
from dotenv import load_dotenv
from datetime import date

load_dotenv()
fake = Faker('fr_FR')

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

# Étape 2 : lister les vrais fichiers du bucket
objets = list(minio_client.list_objects("radios-dentaires", recursive=True))
chemins_reels = [obj.object_name for obj in objets]
print(f"{len(chemins_reels)} fichiers trouvés dans MinIO")

# Étape 3 : récupérer les Id_radio existants
cursor.execute("SELECT Id_radio FROM radio ORDER BY Id_radio")
ids_radio = [row[0] for row in cursor.fetchall()]
print(f"{len(ids_radio)} lignes radio à corriger")

# Étape 4 : vérification de cohérence AVANT de toucher à quoi que ce soit.
# Si les deux nombres ne correspondent pas, on arrête tout plutôt que de
# laisser random.sample lever une erreur à moitié dans le traitement, ce
# qui laisserait la base dans un état partiellement corrigé.
if len(chemins_reels) != len(ids_radio):
    raise ValueError(
        f"Incohérence : {len(chemins_reels)} fichiers MinIO mais "
        f"{len(ids_radio)} lignes radio. Vérifie avant de continuer."
    )

# Étape 5 : tirage sans répétition, un fichier unique par ligne radio
chemins_tires = random.sample(chemins_reels, len(chemins_reels))

# Étape 6 : zip() associe les deux listes terme à terme — le premier
# Id_radio avec le premier chemin tiré, le second avec le second, etc.
# C'est la façon idiomatique en Python d'itérer sur deux listes en
# parallèle, plutôt que de gérer un index manuel avec range(len(...)).
for id_radio, chemin in zip(ids_radio, chemins_tires):
    annee = int(chemin.split('/')[1])  # ex: "panoramique/2022/10.jpg" -> 2022
    date_radio = fake.date_between(
        start_date=date(annee, 1, 1),
        end_date=min(date(annee, 12, 31), date.today())
    )

    cursor.execute("""
        UPDATE radio
        SET chemin_fichier = %s, Date_radio = %s
        WHERE Id_radio = %s
    """, (chemin, date_radio, id_radio))

conn.commit()
print("Correction terminée : chaque ligne radio pointe maintenant vers un vrai fichier MinIO")

cursor.close()
conn.close()