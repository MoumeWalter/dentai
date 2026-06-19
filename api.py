from fastapi import FastAPI
import psycopg2
import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class PatientCreate(BaseModel):
    nom: str
    prenom: str
    date_naissance: str

class ConsultationCreate(BaseModel):
    date_consultation: str
    id_patient: int
    id_chirurgien: int

class RadioCreate(BaseModel):
    type_radio: str
    chemin_fichier: str
    date_radio: str
    id_consultation: int

app = FastAPI(
    title="DentAI API",
    description="API de gestion des données dentaires",
    version="1.0.0"
)

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD")
)
cursor = conn.cursor()

@app.get("/")
def accueil():
    return {"message": "Bienvenue sur DentAI API"}

@app.get("/patients")
def lister_patients():
    cursor.execute("SELECT * FROM patient")
    patients = cursor.fetchall()
    return {"patients": patients}

@app.get("/patients/{id_patient}")
def get_patient(id_patient: int):
    cursor.execute("SELECT * FROM patient WHERE id_patient = %s", (id_patient,))
    patient = cursor.fetchone()
    return {"patient": {
        "id_patient": patient[0],
        "nom": patient[1],
        "prenom": patient[2],
        "date_naissance": patient[3]
    }}

@app.post("/patients")
def creer_patient(patient: PatientCreate):
    cursor.execute("""
    INSERT INTO patient (Nom, Prenom, Date_naissance)
    VALUES (%s, %s, %s)
    RETURNING id_patient
    """, (patient.nom, patient.prenom, patient.date_naissance))
    nouveau_patient = cursor.fetchone()

    conn.commit()
    return {"id_patient": nouveau_patient[0], "message": "Patient créé !"}

@app.post("/consultations")
def creer_consultations(consultation: ConsultationCreate):
    cursor.execute("""
    INSERT INTO consultation (date_consultation, id_patient, id_chirurgien)
    VALUES (%s, %s, %s)
    RETURNING id_consultation
    """, (consultation.date_consultation, consultation.id_patient, consultation.id_chirurgien))
    nouvelle_consultation = cursor.fetchone()

    conn.commit()
    return {"id_consultation": nouvelle_consultation[0], "message": "Consultation créée !"}

@app.post("/radios")
def creer_radios(radio: RadioCreate):
    cursor.execute("""
    INSERT INTO radio (type_radio, chemin_fichier, date_radio, id_consultation)
    VALUES (%s, %s, %s, %s)
    RETURNING id_radio
    """, (radio.type_radio, radio.chemin_fichier, radio.date_radio, radio.id_consultation))
    nouvelle_radio = cursor.fetchone()

    conn.commit()
    return {"id_radio": nouvelle_radio[0], "message": "Radio créée !"}

@app.get("/resultats/{id_radio}")
def get_resultats(id_radio: int):
    cursor.execute("SELECT * FROM resultat WHERE id_radio = %s", (id_radio,))
    resultat = cursor.fetchone()
    return {"resultat": {
        "id_resultat": resultat[0],
        "pathologie": resultat[1],
        "score_confiance": resultat[2],
        "date_resultat": resultat[3],
        "id_radio": resultat[4]
    }}