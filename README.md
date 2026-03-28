# Data Sciences Knowledge Test (DSKT)

Un test de connaissances interactif en data sciences, développé avec Streamlit et alimenté par une base de plus de 535 questions.

## 🚀 Tester l'application

L'application est déployée et accessible en ligne :

**[→ Accéder au test DSKT](https://datascienceqcm.streamlit.app/)**

## ✨ Fonctionnalités

- **30 questions aléatoires** : 1 question d'échauffement fixe + 29 questions tirées au sort
- **3 niveaux de difficulté** : Facile, Intermédiaire, Avancé
- **Délais adaptés** :
  - Facile : 17 secondes par question
  - Intermédiaire : 16 secondes par question
  - Avancé : 12 secondes par question
- **Réponses multiples** : Jusqu'à 2 réponses possibles par question
- **Système de scoring** :
  - 1 réponse correcte : 1.0 point si correct, 0 sinon
  - 2 réponses attendues : 1.5 points (les deux), 0.5 point (une seule), 0 sinon
- **Export automatique** : Résultats sauvegardés localement et envoyés à Google Sheets
- **Réponses affichées** : 2 secondes pour voir les bonnes réponses avant de passer à la question suivante
- **UUID tracking** : Chaque soumission est identifiée de manière unique

## 📋 Catégories de questions

### Niveau Facile (candidat aux 5 catégories)
- Analyse des données multivariée
- Statistiques
- Gestion de base de données
- Probabilités
- Économétrie

### Niveaux Intermédiaire & Avancé
- Toutes les catégories disponibles (535+ questions)

## 🛠️ Installation locale

### Prérequis
- Python 3.8+
- pip ou conda

### Étapes

1. **Cloner le repository**
   ```bash
   git clone https://github.com/BenaventC/datascienceQCM.git
   cd datascienceQCM
   ```

2. **Créer un environnement virtuel**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration Google Sheets (optionnel)**
   - Créer un fichier `secrets.toml` dans `.streamlit/` avec vos credentials Google
   - Ou définir `GOOGLE_SERVICE_ACCOUNT_FILE` dans les variables d'environnement

5. **Lancer l'application**
   ```bash
   streamlit run app.py
   ```

L'application sera accessible à `http://localhost:8501`

## 📁 Structure du projet

```
.
├── app.py                    # Application Streamlit principale
├── questions.csv             # Base de questions (535+ entrées)
├── examen_resultat.csv       # Résultats locaux (généré automatiquement)
├── requirements.txt          # Dépendances Python
└── README.md                 # Documentation
```

## 📊 Colonnes de questions.csv

| Colonne | Type | Valeurs attendues |
|---------|------|------------------|
| question | str | Texte de la question |
| categorie | str | Catégorie du sujet |
| difficulte | str | `facile`, `intermédiaire` ou `avancé` |
| option_a à option_e | str | Textes des réponses |
| correct_option | str | `A`, `B`, `C`, `D`, `E` ou `A;C` (format 1-2 lettres) |

## 🔒 Configuration Google Sheets

Pour exporter automatiquement vers Google Sheets :

1. Créer un projet Google Cloud
2. Activer les APIs : Sheets + Drive
3. Créer une clé de compte de service (JSON)
4. Créer un fichier `.streamlit/secrets.toml` :
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   # ... (reste des credentials)
   
   GOOGLE_SHEET_NAME = "DSKT_Results"
   ```

## 📝 Résultats

Les résultats sont sauvegardés dans :
- **Local** : `examen_resultat.csv`
- **Cloud** : Google Sheets (si configuré)

Chaque résultat inclut :
- Nom du candidat
- Email
- Score brut
- Nombre total de points
- Taux de réussite (%)
- Niveau choisi
- Timestamp
- UUID unique

## 🤝 Contribution

Les contributions sont bienvenues ! N'hésitez pas à :
- Ajouter de nouvelles questions à `questions.csv`
- Signaler des bugs
- Proposer des améliorations

## 📄 Licence

À définir

## 👨‍💻 Auteur

Projet développé avec Streamlit

---

**Besoin d'aide ?** Consultez la [documentation Streamlit](https://docs.streamlit.io)
