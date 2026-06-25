from fastapi import FastAPI, UploadFile, File, Form
import psycopg2
import os
import io
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import date
import base64
from ultralytics import YOLO
import tempfile

load_dotenv()

# --- Modèles Pydantic pour la validation des données entrantes ---
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

# --- Application FastAPI ---
app = FastAPI(
    title="DentAI API",
    description="API de gestion des données dentaires et de diagnostic IA",
    version="2.0.0"
)

# --- Connexion PostgreSQL ---
# Une seule connexion partagée, ouverte au démarrage.
# En production, on utiliserait un pool de connexions (ex: asyncpg),
# mais une connexion unique suffit pour ce projet.
conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD")
)
cursor = conn.cursor()

# --- Chargement du modèle au démarrage ---
# Variable globale qui contiendra le modèle ResNet18 chargé une seule fois.
# Un appel à /diagnostic réutilise toujours ce même objet en mémoire,
# évitant de recharger les poids (plusieurs secondes) à chaque requête.
# Variables globales pour les deux modèles
CLASSES = ['caries', 'fractured_teeth', 'healthy_teeth', 'impacted_teeth', 'infection']
modele = None
transformation = None
modele_detection = None

@app.on_event("startup")
def charger_modele():
    """
    Chargement unique au démarrage de l'API des deux modèles IA :
    - ResNet18 pour la classification (pathologie présente ?)
    - YOLOv8 pour la détection (où se trouve la pathologie ?)
    """
    global modele, transformation, modele_detection

    # --- ResNet18 (classification) ---
    m = models.resnet18()
    m.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
    m.fc = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(m.fc.in_features, len(CLASSES))
    )
    m.load_state_dict(torch.load("best_model.pth", map_location="cpu"))
    m.eval()
    modele = m

    transformation = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])

    # --- YOLOv8 (détection) ---
    modele_detection = YOLO(
        "runs/detect/dentai_detection_v2/weights/best.pt"
    )

    print("Modèles ResNet18 et YOLOv8 chargés avec succès.")

def appliquer_clahe(image_gray: np.ndarray) -> np.ndarray:
    """
    Applique une égalisation d'histogramme adaptative (CLAHE) sur une image
    en niveaux de gris. Même paramètres que pipeline_silver.py pour rester
    cohérent avec ce que le modèle a vu lors de l'entraînement.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image_gray)


# --- Endpoints existants ---

@app.get("/")
def accueil():
    return {"message": "Bienvenue sur DentAI API v2.0"}

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

# --- Nouvel endpoint : diagnostic IA ---

@app.post("/diagnostic")
async def diagnostic(
    id_radio: int = Form(...),
    radio: UploadFile = File(...)
):
    """
    Reçoit une image radio (multipart/form-data) et un id_radio,
    applique le prétraitement et le modèle de classification,
    insère le résultat dans la table resultat,
    et retourne la pathologie prédite avec son score de confiance.

    Paramètres :
    - id_radio : identifiant de la ligne radio dans PostgreSQL
                 (permet de lier le résultat au bon dossier patient)
    - radio    : fichier image de la radio panoramique (JPG ou PNG)
    """
    # 1. Lire les bytes de l'image uploadée
    contenu = await radio.read()

    # 2. Décoder en image OpenCV (niveaux de gris directement)
    image_array = np.frombuffer(contenu, np.uint8)
    image_gray = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)

    # 3. Appliquer CLAHE (égalisation adaptative d'histogramme)
    image_clahe = appliquer_clahe(image_gray)

    # 4. Convertir en PIL Image pour appliquer les transformations PyTorch
    image_pil = Image.fromarray(image_clahe)

    # 5. Appliquer le pipeline de transformation (resize, ToTensor, Normalize)
    # unsqueeze(0) ajoute la dimension batch : [1, 1, 224, 224]
    tenseur = transformation(image_pil).unsqueeze(0)

    # 6. Prédiction — torch.no_grad() désactive le calcul du gradient,
    # inutile en inférence et coûteux en mémoire
    with torch.no_grad():
        sortie = modele(tenseur)
        probabilites = torch.softmax(sortie, dim=1)
        indice_predit = torch.argmax(probabilites, dim=1).item()
        score_confiance = probabilites[0][indice_predit].item()

    pathologie_predite = CLASSES[indice_predit]

    # 7. Écriture du résultat dans PostgreSQL
    cursor.execute("""
        INSERT INTO resultat (pathologie, score_confiance, Date_resultat, Id_radio)
        VALUES (%s, %s, %s, %s)
        RETURNING id_resultat
    """, (pathologie_predite, round(score_confiance, 2), date.today(), id_radio))
    id_resultat = cursor.fetchone()[0]
    conn.commit()

    # 8. Retour de la prédiction à Streamlit
    return {
        "id_resultat": id_resultat,
        "pathologie": pathologie_predite,
        "score_confiance": round(score_confiance, 2),
        "message": "Diagnostic effectué avec succès"
    }

@app.post("/diagnostic/detection")
async def diagnostic_detection(
    radio: UploadFile = File(...)
):
    """
    Reçoit une image radio, applique YOLOv8 pour détecter et localiser
    les pathologies dentaires, et retourne l'image annotée avec les
    bounding boxes dessinées dessus, encodée en base64.

    Note : les performances de ce modèle sont limitées (mAP50 = 0.0025)
    faute de données d'entraînement suffisantes — documenté au Bloc 4.
    L'endpoint est fonctionnel et illustre le principe de la détection
    d'objets, mais les prédictions ne sont pas cliniquement fiables.
    """
    # 1. Lire et sauvegarder temporairement l'image
    # YOLOv8 travaille sur des fichiers plutôt que sur des bytes en mémoire
    contenu = await radio.read()
    chemin_temp = os.path.join(tempfile.gettempdir(), "radio_temp.jpg")
    with open(chemin_temp, "wb") as f:
        f.write(contenu)

    # 2. Inférence YOLOv8 — retourne une liste de résultats
    # imgsz=640 correspond à la taille utilisée lors de l'entraînement v2
    resultats = modele_detection(chemin_temp, imgsz=640, conf=0.01)

    # 3. Générer l'image annotée avec les bounding boxes dessinées
    # conf=0.01 (seuil très bas) pour maximiser les détections visibles
    # même avec un modèle peu performant, pour la démo
    chemin_annotee = os.path.join(tempfile.gettempdir(), "radio_annotee.jpg")
    resultats[0].save(filename=chemin_annotee)

    # 4. Lire l'image annotée et l'encoder en base64
    # Base64 permet d'envoyer une image dans une réponse JSON,
    # sans avoir besoin d'un endpoint de fichier séparé
    with open(chemin_annotee, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    # 5. Récupérer les détections pour les afficher aussi en texte
    detections = []
    for box in resultats[0].boxes:
        classe_id = int(box.cls[0])
        classe_nom = modele_detection.names[classe_id]
        confiance = float(box.conf[0])
        detections.append({
            "classe": classe_nom,
            "confiance": round(confiance, 3)
        })

    return {
        "image_annotee_base64": image_base64,
        "detections": detections,
        "nb_detections": len(detections),
        "message": (
            "Détection effectuée. Note : performances limitées "
            "(mAP50=0.0025) — voir Bloc 4 pour le diagnostic complet."
        )
    }