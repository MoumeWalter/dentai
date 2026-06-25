import streamlit as st
import requests
import streamlit_authenticator as stauth
import base64
from io import BytesIO
from PIL import Image as PILImage

# -----------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# Doit être le premier appel Streamlit du script
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="DentAPP",
    page_icon="🦷",
    layout="centered"
)

# -----------------------------------------------------------------------
# CONFIGURATION DE L'AUTHENTIFICATION
# Hachages pré-générés via bcrypt — jamais les mots de passe en clair
# dans le code source. En production, ce dictionnaire serait dans un
# fichier YAML externe non versionné.
# -----------------------------------------------------------------------
config = {
    "credentials": {
        "usernames": {
            "dr_martin": {
                "name": "Dr. Martin",
                "password": "$2b$12$rVY98lZxzaGMe89GJMDsfuXbTER8WmSXdN326Do32Uo08fvyltJ0.",
                "role": "chirurgien",
                "id_chirurgien": 1
            },
            "dr_dupont": {
                "name": "Dr. Dupont",
                "password": "$2b$12$qa94AwcL7uCCPBov9X2o9ePXT9x0GLPimBAEA./LE6yrmPsUsUb6W",
                "role": "chirurgien",
                "id_chirurgien": 2
            },
            "secretaire": {
                "name": "Marie Secrétaire",
                "password": "$2b$12$JjpnKcNuLF/WlVkHVvpBj.nirVG6StWVvFtjxF5Tc/bbuPU9wbWj.",
                "role": "secretaire",
                "id_chirurgien": None
            },
            "admin": {
                "name": "Administrateur",
                "password": "$2b$12$ifRPr2PLGFe5NiIyR.GpMeNY3f7TdUiwKyS4jlNAPpJsvRitQMUIO",
                "role": "admin",
                "id_chirurgien": None
            }
        }
    },
    "cookie": {
        "name": "dentapp_cookie",
        "key": "dentai_secret_key_2026",
        "expiry_days": 1
    }
}

# -----------------------------------------------------------------------
# AUTHENTIFICATION — version 0.4.2
# L'authenticator gère le formulaire de connexion, les cookies de session
# et la déconnexion. Les résultats sont stockés dans st.session_state.
# -----------------------------------------------------------------------
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

# Affiche le formulaire de connexion
try:
    authenticator.login()
except Exception as e:
    st.error(f"Erreur d'authentification : {e}")
    st.stop()

# Vérification du statut de connexion via session_state
if st.session_state.get("authentication_status") is False:
    st.error("❌ Identifiant ou mot de passe incorrect.")
    st.stop()

if st.session_state.get("authentication_status") is None:
    st.warning("👋 Veuillez saisir vos identifiants pour accéder à DentAPP.")
    st.stop()

# -----------------------------------------------------------------------
# UTILISATEUR CONNECTÉ
# On récupère le nom et le username depuis session_state,
# puis le rôle depuis la config (non stocké nativement dans session_state)
# -----------------------------------------------------------------------
name = st.session_state.get("name")
username = st.session_state.get("username")
role = config["credentials"]["usernames"][username]["role"]
id_chirurgien = config["credentials"]["usernames"][username]["id_chirurgien"]

# Barre latérale : infos utilisateur + bouton de déconnexion
with st.sidebar:
    st.write(f"👤 Connecté : **{name}**")
    st.write(f"🔑 Rôle : **{role}**")
    st.divider()
    authenticator.logout()

# -----------------------------------------------------------------------
# AVERTISSEMENT CLINIQUE — Bloc 5 : outil d'aide à la décision uniquement
# Visible pour les rôles ayant accès aux données cliniques
# -----------------------------------------------------------------------
if role in ["chirurgien", "admin"]:
    st.warning(
        "⚕️ **Outil d'aide à la décision uniquement.** "
        "Les résultats de DentAPP ne remplacent pas le diagnostic d'un "
        "professionnel de santé qualifié. Toute prédiction doit être "
        "validée par le chirurgien référent avant tout acte médical.",
        icon="⚠️"
    )

st.title("🦷 DentAPP — Diagnostic dentaire assisté par IA")

# -----------------------------------------------------------------------
# VUE SECRÉTAIRE
# Bloc 5 : aucun accès aux données cliniques (radios, résultats)
# Accès limité : nom, prénom, gestion des rendez-vous uniquement
# -----------------------------------------------------------------------
if role == "secretaire":
    st.subheader("📅 Gestion des rendez-vous")
    st.info(
        "Votre rôle vous donne accès à la gestion des consultations uniquement. "
        "Les radios et diagnostics sont réservés aux chirurgiens.",
        icon="ℹ️"
    )
    st.markdown("### Patients enregistrés")
    try:
        response = requests.get("http://127.0.0.1:8000/patients")
        patients = response.json().get("patients", [])
        if patients:
            for p in patients:
                # Affichage nom + prénom + date de naissance uniquement
                # Jamais de radio ni de résultat de diagnostic
                st.write(f"**{p[1]} {p[2]}** — né(e) le {p[3]}")
        else:
            st.info("Aucun patient enregistré.")
    except Exception as e:
        st.error(f"Erreur de connexion à l'API : {e}")

# -----------------------------------------------------------------------
# VUE CHIRURGIEN
# Bloc 5 : accès complet aux données cliniques de ses patients référents
# -----------------------------------------------------------------------
elif role == "chirurgien":
    st.subheader("📋 Soumettre une radio pour diagnostic")

    # Upload de l'image radio
    radio_uploadee = st.file_uploader(
        "Choisissez une radio panoramique (JPG ou PNG)",
        type=["jpg", "jpeg", "png"]
    )

    # Identifiant de la radio dans le dossier patient PostgreSQL
    id_radio = st.number_input(
        "Identifiant de la radio (Id_radio dans le dossier patient)",
        min_value=1,
        step=1,
        help="Cet identifiant relie le diagnostic au dossier patient dans la base de données."
    )

    if radio_uploadee:
        # Affichage préalable de l'image soumise
        st.image(
            radio_uploadee,
            caption="Radio soumise pour analyse",
            use_container_width=True
        )

        # Bouton de diagnostic — le résultat est stocké dans session_state
        # plutôt que dans des variables locales, pour qu'il survive au
        # rechargement Streamlit déclenché par le clic sur le bouton YOLOv8.
        # Sans session_state, cliquer sur "Localiser" ferait oublier à
        # Streamlit que le diagnostic avait déjà été lancé.
        if st.button("🔍 Lancer le diagnostic", type="primary"):
            with st.spinner("Analyse en cours..."):
                try:
                    radio_uploadee.seek(0)
                    fichier_bytes = radio_uploadee.read()

                    # Envoi multipart/form-data à l'API FastAPI
                    response = requests.post(
                        "http://127.0.0.1:8000/diagnostic",
                        data={"id_radio": int(id_radio)},
                        files={"radio": (
                            radio_uploadee.name,
                            fichier_bytes,
                            "image/jpeg"
                        )}
                    )
                    resultat = response.json()

                    if response.status_code == 200:
                        # Persistance du résultat ET des bytes de l'image
                        # dans session_state pour le bouton YOLOv8
                        st.session_state["dernier_diagnostic"] = resultat
                        radio_uploadee.seek(0)
                        st.session_state["derniere_radio"] = radio_uploadee.read()
                        st.session_state["dernier_nom_radio"] = radio_uploadee.name
                    else:
                        st.error(f"Erreur API ({response.status_code}) : {resultat}")

                except Exception as e:
                    st.error(f"Erreur de connexion à l'API : {e}")

        # ---------------------------------------------------------------
        # AFFICHAGE DU RÉSULTAT — hors du bouton diagnostic
        # Placé ici (pas dans le if st.button) pour persister après
        # chaque interaction Streamlit ultérieure (clic YOLOv8, radio, etc.)
        # ---------------------------------------------------------------
        if "dernier_diagnostic" in st.session_state:
            resultat = st.session_state["dernier_diagnostic"]
            pathologie = resultat["pathologie"]
            score = resultat["score_confiance"]

            st.success("✅ Diagnostic effectué avec succès")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Pathologie détectée",
                    pathologie.replace("_", " ").title()
                )
            with col2:
                st.metric(
                    "Score de confiance",
                    f"{score * 100:.0f}%"
                )

            # -----------------------------------------------------------
            # DÉTECTION YOLOv8 — localisation des pathologies
            # Modèle 2 du projet (Bloc 4), performances limitées documentées
            # L'image retournée par l'API contient les bounding boxes
            # dessinées par YOLOv8 sur la radio originale
            # -----------------------------------------------------------
            st.markdown("### 🔬 Localisation des pathologies (YOLOv8)")
            st.caption(
                "⚠️ Performances limitées (mAP50 = 0.0025 lors de l'entraînement) "
                "— les bounding boxes sont indicatives, pas cliniquement fiables. "
                "Voir Bloc 4 du rapport pour le détail des itérations."
            )

            if st.button("📍 Localiser les pathologies sur la radio"):
                with st.spinner("Détection en cours..."):
                    try:
                        # Récupération des bytes de l'image depuis session_state
                        # (l'image originale uploadée, pas le résultat annoté)
                        fichier_bytes_yolo = st.session_state["derniere_radio"]
                        nom_radio = st.session_state["dernier_nom_radio"]

                        # Appel à l'endpoint de détection — retourne l'image
                        # annotée encodée en base64 dans le JSON de réponse
                        response_yolo = requests.post(
                            "http://127.0.0.1:8000/diagnostic/detection",
                            files={"radio": (
                                nom_radio,
                                fichier_bytes_yolo,
                                "image/jpeg"
                            )}
                        )
                        resultat_yolo = response_yolo.json()

                        if response_yolo.status_code == 200:
                            # Décodage base64 → PIL Image → affichage Streamlit
                            img_bytes = base64.b64decode(
                                resultat_yolo["image_annotee_base64"]
                            )
                            img_annotee = PILImage.open(BytesIO(img_bytes))
                            st.image(
                                img_annotee,
                                caption="Radio avec détections YOLOv8",
                                use_container_width=True
                            )

                            # Liste textuelle des détections
                            if resultat_yolo["nb_detections"] > 0:
                                st.write(
                                    f"**{resultat_yolo['nb_detections']} "
                                    f"détection(s) :**"
                                )
                                for d in resultat_yolo["detections"]:
                                    st.write(
                                        f"- {d['classe']} "
                                        f"(confiance : {d['confiance']*100:.1f}%)"
                                    )
                            else:
                                st.info(
                                    "Aucune pathologie localisée sur cette radio "
                                    "(seuil de confiance minimal appliqué : 0.01)."
                                )

                    except Exception as e:
                        st.error(f"Erreur détection : {e}")

            # -----------------------------------------------------------
            # MESSAGE CULTURE DATA — Bloc 5
            # Affiché au moment précis de la validation, là où le
            # comportement du praticien est le plus déterminant pour
            # la qualité future du modèle (voir section 5.6 du rapport)
            # -----------------------------------------------------------
            st.info(
                "💡 **Votre validation compte.** En confirmant ou "
                "corrigeant ce diagnostic, vous contribuez à améliorer "
                "le modèle IA pour tous vos futurs patients. "
                "Merci de vérifier attentivement avant de valider.",
                icon="ℹ️"
            )

            # Validation ou correction par le chirurgien
            st.markdown("### Valider ou corriger le diagnostic")
            choix = st.radio(
                "Le diagnostic proposé est-il correct ?",
                ["✅ Confirmer", "✏️ Corriger"],
                horizontal=True
            )

            if choix == "✏️ Corriger":
                correction = st.selectbox(
                    "Pathologie correcte selon votre examen clinique :",
                    [
                        "caries",
                        "fractured_teeth",
                        "healthy_teeth",
                        "impacted_teeth",
                        "infection"
                    ]
                )
                st.success(f"Correction enregistrée : **{correction}**")
                # Note : l'écriture de la correction en base nécessite
                # un endpoint PUT /resultats/{id_resultat} à ajouter
                # dans api.py (itération future)

            elif choix == "✅ Confirmer":
                st.success(
                    "Diagnostic confirmé et enregistré dans le dossier patient."
                )

# -----------------------------------------------------------------------
# VUE ADMINISTRATEUR
# Bloc 5 : super-privilèges techniques, mais aucun accès au contenu
# clinique individuel (art. 9(2)(h) RGPD + secret professionnel)
# -----------------------------------------------------------------------
elif role == "admin":
    st.subheader("⚙️ Tableau de bord administrateur")
    st.info(
        "Conformément à la politique de gouvernance (Bloc 5), "
        "l'accès au contenu clinique individuel (radios, diagnostics) "
        "est exclu du rôle administrateur — article 9(2)(h) RGPD.",
        icon="🔒"
    )

    st.markdown("### Statistiques globales (anonymisées)")
    try:
        response_patients = requests.get("http://127.0.0.1:8000/patients")
        nb_patients = len(response_patients.json().get("patients", []))

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Patients enregistrés", nb_patients)
        with col2:
            st.metric("Modèle IA actif", "ResNet18 v1")
        with col3:
            st.metric("Statut API", "✅ En ligne")

        st.markdown("### Informations système")
        st.write("**Accuracy du modèle (jeu de test) :** 36%")
        st.write(
            "**Classes détectées :** caries, fractured_teeth, "
            "healthy_teeth, impacted_teeth, infection"
        )
        st.write("**Version de l'API :** DentAI API v2.0")

    except Exception as e:
        st.error(f"Erreur de connexion à l'API : {e}")