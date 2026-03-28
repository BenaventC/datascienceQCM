import streamlit as st
import pandas as pd
import numpy as np
import os
import random
import re
import time
import unicodedata
from datetime import datetime
from uuid import uuid4
import gspread
from google.oauth2.service_account import Credentials

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# Configuration de la page
st.set_page_config(page_title="Data Sciences Knowledge Test (DSKT)", page_icon="📊")

# Fichiers
QUESTIONS_FILE = "questions.csv"
RESULTS_FILE_NAME = "examen_resultat.csv"
TOTAL_QUESTION_COUNT = 30
WARMUP_QUESTION_COUNT = 1
RANDOM_QUESTION_COUNT = TOTAL_QUESTION_COUNT - WARMUP_QUESTION_COUNT
DIFFICULTY_RANK = {
    "facile": 1,
    "intermédiaire": 2,
    "intermediaire": 2,
    "avancé": 3,
    "avance": 3,
}
TIME_LIMIT_BY_LEVEL = {
    "facile": 20,
    "intermédiaire": 16,
    "intermediaire": 16,
    "avancé": 12,
    "avance": 12,
}
EASY_ALLOWED_CATEGORIES = {
    "analyse des donnees multivariee",
    "statistiques",
    "gestion de base de donnees",
    "probabilite",
    "probabilites",
    "econometrie",
}
WARMUP_QUESTION = {
    "question": "Qu'est-ce qu'une moyenne ?",
    "categorie": "statistiques",
    "difficulte": "facile",
    "option_a": "La somme des valeurs divisée par leur nombre",
    "option_b": "La valeur la plus fréquente",
    "option_c": "La valeur centrale d'une série triée",
    "option_d": "La différence entre le maximum et le minimum",
    "option_e": "Le carré de l'écart-type",
    "correct_option": "A",
}

# --- Connexion à Google Sheets avec gspread ---
SPREADSHEET_NAME_DEFAULT = "DSKT_Results"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
GSHEET_MAX_RETRIES = 3
GSHEET_RETRY_DELAY_SECONDS = 2

def get_gsheet_worksheet():
    creds = None

    # Priorité 1: Streamlit secrets (idéal pour Streamlit Cloud)
    try:
        service_account_info = st.secrets.get("gcp_service_account")
        if service_account_info:
            creds = Credentials.from_service_account_info(dict(service_account_info), scopes=SCOPES)
    except Exception:
        pass

    # Priorité 2: chemin vers JSON via variable d'environnement / .env
    if creds is None:
        service_account_file = get_config_value("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
        if service_account_file and os.path.exists(service_account_file):
            creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)

    if creds is None:
        raise ValueError(
            "Configuration Google Sheets manquante. Définissez st.secrets['gcp_service_account'] "
            "ou GOOGLE_SERVICE_ACCOUNT_FILE."
        )

    spreadsheet_name = get_config_value("GOOGLE_SHEET_NAME", SPREADSHEET_NAME_DEFAULT).strip() or SPREADSHEET_NAME_DEFAULT

    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_name)
    worksheet = sheet.sheet1  # ou .worksheet('Nom de l'onglet')
    return worksheet

def envoyer_donnees_google_sheet(donnees):
    worksheet = get_gsheet_worksheet()
    # Ajoute la date/heure si elle n'est pas déjà dans la liste.
    if len(donnees) < 7:
        donnees = list(donnees) + [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    # Ajoute un UUID unique si absent.
    if len(donnees) < 8:
        donnees = list(donnees) + [str(uuid4())]
    last_error = None
    for attempt in range(1, GSHEET_MAX_RETRIES + 1):
        try:
            worksheet.append_row(donnees)  # donnees = liste Python
            return
        except Exception as e:
            last_error = e
            # Retry ciblé en cas de quota (429)
            if "429" in str(e) and attempt < GSHEET_MAX_RETRIES:
                time.sleep(GSHEET_RETRY_DELAY_SECONDS * attempt)
                continue
            raise

    if last_error is not None:
        raise last_error

def get_config_value(key, default=""):
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    try:
        secret_value = st.secrets.get(key)
        if secret_value is not None:
            return str(secret_value)
    except Exception:
        pass
    return default


def get_results_file_path():
    # Permet d'ecrire directement dans un dossier synchronise (ex: Google Drive Desktop).
    output_dir = get_config_value("LOCAL_RESULTS_DIR", "").strip()
    file_name = get_config_value("LOCAL_RESULTS_FILE_NAME", RESULTS_FILE_NAME).strip() or RESULTS_FILE_NAME

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, file_name)

    return file_name


def load_questions():
    if os.path.exists(QUESTIONS_FILE):
        return pd.read_csv(QUESTIONS_FILE)
    return pd.DataFrame()

def is_valid_dauphine_email(email):
    if not email:
        return True
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return re.match(pattern, email.strip()) is not None


def save_result(name, email, score, total):
    results_file = get_results_file_path()
    success_rate = round((score / total) * 100, 2) if total else 0.0
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    submission_uuid = str(uuid4())
    new_result = pd.DataFrame([{
        "Nom": name,
        "Email": email,
        "Score": score,
        "Total": total,
        "Taux_reussite_%": success_rate,
        "Date": date_str,
        "UUID": submission_uuid,
    }])

    if not os.path.exists(results_file):
        new_result.to_csv(results_file, index=False)
    else:
        existing = pd.read_csv(results_file)
        if "Taux_reussite_%" not in existing.columns and {"Score", "Total"}.issubset(existing.columns):
            existing["Taux_reussite_%"] = (
                (existing["Score"] / existing["Total"].replace(0, pd.NA)) * 100
            ).round(2).fillna(0.0)
        combined = pd.concat([existing, new_result], ignore_index=True, sort=False)
        combined.to_csv(results_file, index=False)

    # Envoi vers Google Sheets (sans lecture préalable pour éviter les quotas de lecture)
    try:
        categorie = st.session_state.get("selected_level", "")
        envoyer_donnees_google_sheet([
            name,
            email,
            score,
            total,
            success_rate,
            categorie,
            date_str,
            submission_uuid,
        ])
    except Exception as e:
        print(f"Erreur lors de l'envoi vers Google Sheets : {e}")

    local_msg = "Enregistré."
    return local_msg


def parse_correct_letters(raw_value):
    # Accepte des formats comme A, A;C, A,C, A|C ou A/C
    value = str(raw_value).strip().upper()
    parts = [p for p in re.split(r"[^A-E]+", value) if p]
    unique_letters = []
    for letter in parts:
        if letter in {"A", "B", "C", "D", "E"} and letter not in unique_letters:
            unique_letters.append(letter)
    return unique_letters


def get_correct_texts(row):
    letter_to_text = {
        "A": row["option_a"],
        "B": row["option_b"],
        "C": row["option_c"],
        "D": row["option_d"],
        "E": row["option_e"],
    }
    letters = parse_correct_letters(row["correct_option"])
    return [letter_to_text[l] for l in letters if l in letter_to_text]


def calculate_question_points(correct_texts, selected_texts):
    if not correct_texts:
        return 0.0

    correct_set = set(correct_texts)
    selected_set = set(selected_texts)

    # Cas 2 bonnes réponses attendues
    if len(correct_texts) == 2:
        # Si une réponse sélectionnée est fausse, la question vaut 0.
        if any(answer not in correct_set for answer in selected_texts):
            return 0.0

        # Les deux bonnes réponses ont été cochées.
        if len(selected_set) == 2 and selected_set == correct_set:
            return 1.5

        # Une seule bonne réponse cochée.
        if len(selected_set) == 1 and next(iter(selected_set)) in correct_set:
            return 0.5

        return 0.0

    # Cas 1 bonne réponse attendue
    if len(correct_texts) == 1:
        return 1.0 if len(selected_set) == 1 and next(iter(selected_set)) in correct_set else 0.0

    return 0.0


def validate_correct_options(df):
    invalid_rows = []
    for idx, row in df.iterrows():
        letters = parse_correct_letters(row["correct_option"])
        if not (1 <= len(letters) <= 2):
            invalid_rows.append(idx + 2)  # +2: en-tete CSV + index 1-based

    return invalid_rows


def normalize_difficulty(value):
    return str(value).strip().lower()


def normalize_text(value):
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def get_time_limit_for_level(level):
    return TIME_LIMIT_BY_LEVEL.get(normalize_difficulty(level), 16)


def validate_difficulty_values(df):
    invalid_rows = []
    for idx, row in df.iterrows():
        level = normalize_difficulty(row["difficulte"])
        if level not in DIFFICULTY_RANK:
            invalid_rows.append(idx + 2)
    return invalid_rows


def filter_questions_by_level(df, selected_level):
    normalized_selected = normalize_difficulty(selected_level)
    allowed_ranks_by_level = {
        "facile": {DIFFICULTY_RANK["facile"]},
        "intermédiaire": {DIFFICULTY_RANK["facile"], DIFFICULTY_RANK["intermédiaire"]},
        "intermediaire": {DIFFICULTY_RANK["facile"], DIFFICULTY_RANK["intermédiaire"]},
        "avancé": {DIFFICULTY_RANK["intermédiaire"], DIFFICULTY_RANK["avancé"]},
        "avance": {DIFFICULTY_RANK["intermédiaire"], DIFFICULTY_RANK["avancé"]},
    }
    allowed_ranks = allowed_ranks_by_level.get(normalized_selected, set())

    def is_eligible(level):
        rank = DIFFICULTY_RANK.get(normalize_difficulty(level))
        return rank in allowed_ranks

    filtered_df = df[df["difficulte"].apply(is_eligible)]

    # En niveau facile, on limite l'echantillonnage a des categories precises.
    if normalized_selected == "facile":
        return filtered_df[
            filtered_df["categorie"].apply(
                lambda category: normalize_text(category) in EASY_ALLOWED_CATEGORIES
            )
        ]

    # Pour intermediaire/avance, toutes les categories restent disponibles.
    return filtered_df


def build_quiz_dataframe(eligible_df):
    # Force un nouveau random state à chaque tirage pour garantir l'aléatoire.
    # Cela évite que Streamlit gèle le random state global.
    np.random.seed(None)
    random.seed()
    sampled_df = eligible_df.sample(n=RANDOM_QUESTION_COUNT, random_state=None).reset_index(drop=True)
    warmup_df = pd.DataFrame([WARMUP_QUESTION])
    return pd.concat([warmup_df, sampled_df], ignore_index=True)


def next_question(total_questions):
    st.session_state.current_question += 1
    st.session_state.question_start_ts = time.time()
    if st.session_state.current_question >= total_questions:
        st.session_state.quiz_finished = True
    st.rerun()


def reset_quiz_state():
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.session_state.current_question = 0
    st.session_state.question_start_ts = None
    st.session_state.answers = {}
    st.session_state.shuffled_options = {}
    st.session_state.auto_assigned = []
    st.session_state.result_saved = False
    st.session_state.selected_level = "facile"
    st.session_state.quiz_df = None
    st.session_state.showing_answer_for = None
    st.session_state.answer_display_start_time = None

def main():
    # --- Bouton de test Google Sheets supprimé ---

    st.title("Data Sciences Knowledge Test (DSKT)")
    st.markdown(
        """
        <div style="margin-top: -0.35rem; margin-bottom: 1rem;">
            <p style="font-size: 1.1rem; margin-bottom: 0.2rem;">
                Répondez aux questions suivantes pour tester vos connaissances.
            </p>
            <p style="font-size: 1rem; color: #555; margin: 0;">
                Ceci est une expérimentation d'un test général de connaissances dans les champs des data sciences.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
            :root {
                --color-primary: #e8a87c;
                --color-primary-hover: #df9564;
                --color-secondary: #8ea6c9;
                --color-success: #8bbf9f;
                --color-warning-bg: #fff7e8;
                --color-warning-text: #b7844d;
                --color-error-bg: #fdeff1;
                --color-error-text: #c27a84;
                --color-bg: #fffdfb;
                --color-surface: #ffffff;
                --color-text: #5b4b46;
                --color-text-muted: #9a8e89;
                --color-border: #f0e6df;
            }

            .stApp {
                background: linear-gradient(180deg, #fffdfb 0%, #fff7f2 100%);
                color: var(--color-text);
            }

            [data-testid="stHeader"] {
                background: transparent;
            }

            [data-testid="stSidebar"] {
                background-color: var(--color-surface);
                border-right: 1px solid var(--color-border);
            }

            .stButton > button[kind="primary"] {
                background-color: var(--color-primary);
                border-color: var(--color-primary);
                color: white;
                font-weight: 600;
                border-radius: 10px;
            }
            .stButton > button[kind="primary"]:hover {
                background-color: var(--color-primary-hover);
                border-color: var(--color-primary-hover);
                color: white;
            }
            .attention-box {
                background: var(--color-warning-bg);
                border-left: 6px solid var(--color-warning-text);
                color: var(--color-warning-text);
                padding: 0.75rem 0.9rem;
                border-radius: 0.35rem;
                margin: 0.45rem 0 0.6rem 0;
                font-size: 0.98rem;
            }
            .timer-box {
                background: #eef8f1;
                border-left: 6px solid var(--color-success);
                color: #5d8a6d;
                padding: 0.62rem 0.85rem;
                border-radius: 0.35rem;
                margin: 0.45rem 0 0.75rem 0;
                font-weight: 600;
            }
            .question-text {
                font-size: 1.35rem;
                font-weight: 600;
                line-height: 1.5;
                margin-bottom: 0.35rem;
                color: var(--color-text);
            }
            div[data-testid="stCheckbox"] label p {
                font-size: 1.08rem;
                color: var(--color-text);
            }
            .stCaption {
                color: var(--color-text-muted);
            }

            /* Champs de saisie: fond clair + texte noir */
            .stTextInput input,
            .stTextArea textarea,
            .stNumberInput input,
            [data-testid="stTextInputRootElement"] input,
            [data-testid="stNumberInput"] input {
                background-color: #ffffff !important;
                color: #000000 !important;
                border: 1px solid var(--color-border) !important;
            }

            .stTextInput input::placeholder,
            .stTextArea textarea::placeholder,
            .stNumberInput input::placeholder {
                color: #6b7280 !important;
                opacity: 1;
            }

            .stTextInput input:focus,
            .stTextArea textarea:focus,
            .stNumberInput input:focus {
                background-color: #ffffff !important;
                color: #000000 !important;
                border-color: var(--color-primary) !important;
                box-shadow: 0 0 0 1px var(--color-primary) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    df = load_questions()

    if df.empty:
        st.error("Le fichier de questions est introuvable ou vide.")
        return

    required_columns = {
        "question",
        "categorie",
        "difficulte",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "option_e",
        "correct_option",
    }
    if not required_columns.issubset(set(df.columns)):
        st.error(
            "Le fichier questions.csv doit contenir les colonnes: "
            "question, categorie, difficulte, option_a, option_b, option_c, option_d, option_e, correct_option."
        )
        return

    invalid_rows = validate_correct_options(df)
    if invalid_rows:
        preview = ", ".join(str(x) for x in invalid_rows[:10])
        st.error(
            "La colonne correct_option doit contenir 1 ou 2 lettres parmi A-E "
            f"(ex: A ou A;C). Lignes invalides: {preview}"
        )
        return

    invalid_difficulty_rows = validate_difficulty_values(df)
    if invalid_difficulty_rows:
        preview = ", ".join(str(x) for x in invalid_difficulty_rows[:10])
        st.error(
            "La colonne difficulte doit contenir: facile, intermédiaire ou avancé. "
            f"Lignes invalides: {preview}"
        )
        return

    # Formulaire d'identification
    st.markdown("**Votre nom**")
    user_name = st.text_input("Entrez votre nom complet :")
    st.markdown("**Votre mail**")
    user_email = st.text_input("Entrez votre adresse email (optionnel) :")
    is_email_ok = True
    if user_email:
        is_email_ok = is_valid_dauphine_email(user_email)
        if not is_email_ok:
            st.warning("Adresse email invalide (format attendu: nom@domaine.ext)")

    if "quiz_started" not in st.session_state:
        st.session_state.quiz_started = False
        st.session_state.quiz_finished = False
        st.session_state.current_question = 0
        st.session_state.question_start_ts = None
        st.session_state.candidate_name = ""
        st.session_state.candidate_email = ""
        st.session_state.answers = {}
        st.session_state.shuffled_options = {}
        st.session_state.auto_assigned = []
        st.session_state.result_saved = False
        st.session_state.selected_level = "facile"
        st.session_state.quiz_df = None

    if not st.session_state.quiz_started:
        selected_level = st.selectbox(
            "Choisissez votre niveau d'évaluation :",
            ["facile", "intermédiaire", "avancé"],
            index=0,
        )
        selected_time_limit = get_time_limit_for_level(selected_level)
        eligible_count = len(filter_questions_by_level(df, selected_level))

        st.markdown(
            f"""
            <div class="attention-box">
                Attention: vous aurez {selected_time_limit} secondes par question pour le niveau {selected_level}.
                Si vous ne validez pas votre reponse a temps,
                la machine choisira aleatoirement a votre place. Vous pouvez selectionner 1 ou 2 reponses.
                Le test contient {TOTAL_QUESTION_COUNT} questions au total,
                incluant 1 question d'echauffement fixe et {RANDOM_QUESTION_COUNT} questions tirees au sort.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Base d'echantillonnage disponible pour le niveau {selected_level}: {eligible_count} questions"
        )

        can_start = bool(user_name and (not user_email or is_email_ok) and eligible_count >= RANDOM_QUESTION_COUNT)
        st.button(
            "Start / Commencer le QCM",
            type="primary",
            use_container_width=True,
            disabled=not can_start,
            key="start_quiz",
        )

        if st.session_state.start_quiz:
            eligible_df = filter_questions_by_level(df, selected_level)
            if len(eligible_df) < RANDOM_QUESTION_COUNT:
                st.error(
                    "Pas assez de questions pour ce niveau. "
                    f"Questions disponibles: {len(eligible_df)} / {RANDOM_QUESTION_COUNT} requises."
                )
                return

            quiz_df = build_quiz_dataframe(eligible_df)
            st.session_state.candidate_name = user_name.strip()
            st.session_state.candidate_email = user_email.strip().lower() if user_email else ""
            st.session_state.selected_level = selected_level
            st.session_state.quiz_df = quiz_df
            st.session_state.quiz_started = True
            st.session_state.quiz_finished = False
            st.session_state.current_question = 0
            st.session_state.question_start_ts = time.time()
            st.session_state.answers = {}
            st.session_state.shuffled_options = {}
            st.session_state.auto_assigned = []
            st.session_state.result_saved = False
            st.rerun()

        if not user_name:
            st.info("Saisissez votre nom pour activer le bouton Start.")
        elif user_email and not is_email_ok:
            st.info("Saisissez un email valide (exemple: nom@domaine.ext) pour activer le bouton Start.")
        elif eligible_count < RANDOM_QUESTION_COUNT:
            st.info(
                f"Pas assez de questions disponibles pour ce niveau (minimum {RANDOM_QUESTION_COUNT} requises)."
            )
        return

    quiz_df = st.session_state.quiz_df if st.session_state.quiz_df is not None else df

    if st.session_state.quiz_finished:
        score = 0.0
        total_points = len(quiz_df)
        for index, row in quiz_df.iterrows():
            correct_texts = get_correct_texts(row)
            selected_texts = st.session_state.answers.get(index, [])
            score += calculate_question_points(correct_texts, selected_texts)

        normalized_score = (score / total_points) * 100 if total_points else 0.0
        st.success(f"Termine ! Score normalise: {normalized_score:.2f}%")
        st.caption(f"Detail: {score:.2f} points sur {total_points}")
        if st.session_state.auto_assigned:
            st.info(
                f"Reponses attribuees aleatoirement (temps ecoule): "
                f"{len(st.session_state.auto_assigned)}"
            )

        # Verrou optimiste: on marque d'abord comme sauvegardé pour éviter les doublons en cas de rerun.
        if not st.session_state.result_saved:
            st.session_state.result_saved = True
            local_msg = save_result(
                st.session_state.candidate_name,
                st.session_state.candidate_email,
                score,
                total_points,
            )
            st.info(local_msg)

        if st.button("Recommencer le test", type="primary", use_container_width=True):
            reset_quiz_state()
            st.rerun()
        return

    # Auto-refresh uniquement pendant le quiz (évite des reruns inutiles sur l'écran final).
    if st_autorefresh is not None:
        st_autorefresh(interval=1000, key="quiz_autorefresh")

    index = st.session_state.current_question
    row = quiz_df.iloc[index]

    # Vérifier si on doit afficher la bonne réponse (phase 4-sec post-réponse)
    if st.session_state.showing_answer_for is not None:
        showing_idx = st.session_state.showing_answer_for
        elapsed_answer = int(time.time() - st.session_state.answer_display_start_time) if st.session_state.answer_display_start_time else 0
        
        showing_row = quiz_df.iloc[showing_idx]
        st.subheader(f"Question {showing_idx + 1} / {len(quiz_df)}")
        st.markdown(f"<div class='question-text'>{showing_row['question']}</div>", unsafe_allow_html=True)
        
        correct_texts = get_correct_texts(showing_row)
        st.success(f"✓ Bonne réponse: {', '.join(correct_texts)}")
        st.info(f"Passage à la question suivante dans {max(0, 4 - elapsed_answer)} secondes...")
        
        # Si 4 secondes sont écoulées, passer à la question suivante
        if elapsed_answer >= 4:
            st.session_state.showing_answer_for = None
            st.session_state.answer_display_start_time = None
            next_question(len(quiz_df))
        
        return

    if index not in st.session_state.shuffled_options:
        options = [
            row["option_a"],
            row["option_b"],
            row["option_c"],
            row["option_d"],
            row["option_e"],
        ]
        random.shuffle(options)
        st.session_state.shuffled_options[index] = options

    options = st.session_state.shuffled_options[index]

    current_time_limit = get_time_limit_for_level(st.session_state.selected_level)
    elapsed = int(time.time() - st.session_state.question_start_ts)
    remaining = max(0, current_time_limit - elapsed)

    st.subheader(f"Question {index + 1} / {len(quiz_df)}")
    st.caption(
        f"Categorie : {row['categorie']} | Difficulte : {row['difficulte']} | "
        f"Niveau choisi : {st.session_state.selected_level}"
    )
    st.markdown(f"<div class='question-text'>{row['question']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='timer-box'>Temps restant: {remaining} secondes</div>",
        unsafe_allow_html=True,
    )

    st.write("Choisissez 1 ou 2 réponses :")
    selected = []
    for opt_idx, option_text in enumerate(options):
        if st.checkbox(option_text, key=f"q_{index}_opt_{opt_idx}"):
            selected.append(option_text)

    if len(selected) > 2:
        st.warning("Vous pouvez cocher au maximum 2 réponses.")

    # Si le temps est ecoule, on attribue une reponse aleatoire et on affiche la bonne reponse
    if remaining == 0 and index not in st.session_state.answers:
        random_choice = random.choice(options)
        st.session_state.answers[index] = [random_choice]
        st.session_state.auto_assigned.append(index + 1)
        st.session_state.showing_answer_for = index
        st.session_state.answer_display_start_time = time.time()
        st.rerun()

    if st.button("Valider la reponse", key=f"validate_{index}"):
        if not selected:
            st.warning("Selectionnez au moins une reponse avant de valider.")
        elif len(selected) > 2:
            st.warning("Selectionnez au maximum 2 reponses avant de valider.")
        else:
            st.session_state.answers[index] = selected
            st.session_state.showing_answer_for = index
            st.session_state.answer_display_start_time = time.time()
            st.rerun()

if __name__ == "__main__":
    main()
