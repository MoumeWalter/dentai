import psycopg2
import os
import uuid
import random
from faker import Faker
from dotenv import load_dotenv 
from datetime import date
load_dotenv()

fake = Faker('fr_FR')  # données en français

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD")
)

cursor = conn.cursor()
print("Connexion réussie !")



def generer_chirurgiens(n=5):
    ids = []
    for _ in range(n):
        nom = fake.last_name()
        prenom = fake.first_name()
        email = fake.email()
        mdp_hashe = fake.sha256()
        
        cursor.execute("""
            INSERT INTO chirurgien (Nom, Prenom, email, mdp_hashé)
            VALUES (%s, %s, %s, %s)
            RETURNING Id_chirurgien
        """, (nom, prenom, email, mdp_hashe))
        
        ids.append(cursor.fetchone()[0])
    
    conn.commit()
    return ids

def generer_patients(n=50):
    ids = []
    for _ in range(n):
        nom = fake.last_name()
        prenom = fake.first_name()
        date_naissance = fake.date_of_birth(minimum_age=18, maximum_age=90)

        cursor.execute("""
            INSERT INTO patient (Nom, Prenom, Date_naissance)
            VALUES (%s, %s, %s)
            RETURNING id_patient
        """, (nom, prenom, date_naissance))

        ids.append(cursor.fetchone()[0])

    conn.commit()
    return ids

def generer_consultations(patient_ids, chirurgien_ids, n=200):
    ids = []
    for _ in range(n):
        date_consultation = fake.date_between(
        start_date=date(2022, 1, 1), 
        end_date=date.today())
        id_patient = random.choice(patient_ids)
        id_chirurgien = random.choice(chirurgien_ids)
        
        cursor.execute("""
            INSERT INTO consultation (Date_consultation, Id_patient, Id_chirurgien)
            VALUES (%s, %s, %s)
            RETURNING id_consultation
        """, (date_consultation, id_patient, id_chirurgien))

        ids.append(cursor.fetchone()[0])

    conn.commit()
    return ids

def generer_radios(consultation_ids, n=150):
    ids = []
    radio = ['panoramique']
    for _ in range(n):
        type_radio = random.choice(radio)
        date_radio= fake.date_between(
        start_date=date(2022, 1, 1), 
        end_date=date.today())
        chemin_fichier = f"{type_radio}/{date_radio.year}/radio_{uuid.uuid4().hex[:8]}_{date_radio.strftime('%Y%m%d')}.jpg"
        id_consultation = random.choice(consultation_ids)
        
        cursor.execute("""
            INSERT INTO radio (Type_radio, chemin_fichier, Date_radio, Id_consultation)
            VALUES (%s, %s, %s, %s)
            RETURNING id_radio
        """, (type_radio, chemin_fichier, date_radio, id_consultation))

        ids.append(cursor.fetchone()[0])

    conn.commit()
    return ids

def generer_resultats(radio_ids, n=120):
    ids = []
    pathologies = [
    'carie',
    'dent_fracturee',
    'dent_incluse',
    'infection',
    'lesion_endodontique',
    'lesion_parodontale',
    'sain'
]
    for _ in range(n):
        pathologie = random.choice(pathologies)
        score_confiance = round(random.uniform(0.5, 1.0), 2)
        date_resultat = fake.date_between(
        start_date=date(2022, 1, 1), 
        end_date=date.today())
        id_radio = random.choice(radio_ids)
        
        cursor.execute("""
            INSERT INTO resultat (pathologie, score_confiance, Date_resultat, Id_radio)
            VALUES (%s, %s, %s, %s)
            RETURNING id_resultat
        """, (pathologie, score_confiance, date_resultat, id_radio))

        ids.append(cursor.fetchone()[0])

    conn.commit()
    return ids

if __name__ == "__main__":
    chirurgien_ids = generer_chirurgiens(5)
    patient_ids = generer_patients(50)
    consultation_ids = generer_consultations(patient_ids, chirurgien_ids, n=200)
    radio_ids = generer_radios(consultation_ids, n=150)
    generer_resultats(radio_ids, n=120)
    
    print("Données générées avec succès !")
    cursor.close()
    conn.close()