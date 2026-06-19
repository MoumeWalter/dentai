CREATE TABLE patient (
    Id_patient SERIAL PRIMARY KEY,
    Nom VARCHAR(50) NOT NULL,
    Prenom VARCHAR(50) NOT NULL,
    Date_naissance DATE NOT NULL
);

CREATE TABLE chirurgien (
    Id_chirurgien SERIAL PRIMARY KEY,
    Nom VARCHAR(50) NOT NULL,
    Prenom VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL,
    mdp_hashé VARCHAR(60) NOT NULL
);

CREATE TABLE consultation (
    Id_consultation SERIAL PRIMARY KEY,
    Date_consultation DATE NOT NULL,
    Id_patient INT NOT NULL,
    FOREIGN KEY (Id_patient) REFERENCES patient(Id_patient),
    Id_chirurgien INT NOT NULL,
    FOREIGN KEY (Id_chirurgien) REFERENCES chirurgien(Id_chirurgien)
);

CREATE TABLE radio (
    Id_radio SERIAL PRIMARY KEY,
    Type_radio VARCHAR(30) NOT NULL,
    chemin_fichier VARCHAR(80) NOT NULL,
    Date_radio DATE NOT NULL,
    Id_consultation INT NOT NULL,
    FOREIGN KEY (Id_consultation) REFERENCES consultation(Id_consultation)
);

CREATE TABLE resultat (
    Id_resultat SERIAL PRIMARY KEY,
    pathologie VARCHAR(30) NOT NULL,
    score_confiance FLOAT NOT NULL,
    Date_resultat DATE NOT NULL,
    Id_radio INT NOT NULL,
    FOREIGN KEY (Id_radio) REFERENCES radio(Id_radio)
);