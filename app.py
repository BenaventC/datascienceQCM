import streamlit as st
import pandas as pd
import os
import random
import re
import time
from datetime import datetime

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# Configuration de la page
st.set_page_config(page_title="Data Sciences Knowledge Test (DSKT)", page_icon="📊")

# Fichiers
QUESTIONS_FILE = "questions.csv"
RESULTS_FILE_NAME = "examen_resultat.csv"
DIFFICULTY_RANK = {
    "facile": 1,
    "intermédiaire": 2,
    "intermediaire": 2,
    "avancé": 3,
    "avance": 3,
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
    new_result = pd.DataFrame([{
        "Nom": name,
        "Email": email,
        "Score": score,
        "Total": total,
        "Taux_reussite_%": success_rate,
        "Date": date_str
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

    payload = {
        "Nom": name,
        "Email": email,
        "Score": score,
        "Total": total,
        "Taux_reussite_%": success_rate,
        "Date": date_str,
    }

    local_msg = f"Vos resultats ont ete enregistres dans '{results_file}'."
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


def validate_correct_options(df):
    invalid_rows = []
    for idx, row in df.iterrows():
        letters = parse_correct_letters(row["correct_option"])
        if not (1 <= len(letters) <= 2):
            invalid_rows.append(idx + 2)  # +2: en-tete CSV + index 1-based

    return invalid_rows


def normalize_difficulty(value):
    return str(value).strip().lower()


def validate_difficulty_values(df):
    invalid_rows = []
    for idx, row in df.iterrows():
        level = normalize_difficulty(row["difficulte"])
        if level not in DIFFICULTY_RANK:
            invalid_rows.append(idx + 2)
    return invalid_rows


def filter_questions_by_level(df, selected_level):
    selected_rank = DIFFICULTY_RANK[normalize_difficulty(selected_level)]

    def is_eligible(level):
        rank = DIFFICULTY_RANK.get(normalize_difficulty(level))
        return rank is not None and rank <= selected_rank

    return df[df["difficulte"].apply(is_eligible)]


def build_quiz_dataframe(eligible_df):
    sampled_df = eligible_df.sample(n=20).reset_index(drop=True)
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
    st.session_state.selected_level = "intermédiaire"
    st.session_state.quiz_df = None

def main():
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
            .stButton > button[kind="primary"] {
                background-color: #f28c28;
                border-color: #f28c28;
                color: white;
                font-weight: 600;
            }
            .stButton > button[kind="primary"]:hover {
                background-color: #e67e22;
                border-color: #e67e22;
                color: white;
            }
            .attention-box {
                background: #f8d7da;
                border-left: 6px solid #e5989b;
                color: #6d3b3f;
                padding: 0.75rem 0.9rem;
                border-radius: 0.35rem;
                margin: 0.45rem 0 0.6rem 0;
                font-size: 0.98rem;
            }
            .timer-box {
                background: #f6c5cc;
                border-left: 6px solid #e5989b;
                color: #6a2e36;
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
            }
            div[data-testid="stCheckbox"] label p {
                font-size: 1.08rem;
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
    user_name = st.text_input("Entrez votre nom complet :")
    user_email = st.text_input("Entrez votre adresse email (optionnel) :")
    is_email_ok = is_valid_dauphine_email(user_email)

    if user_email and not is_email_ok:
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
        st.session_state.selected_level = "intermédiaire"
        st.session_state.quiz_df = None

    if not st.session_state.quiz_started:
        selected_level = st.selectbox(
            "Choisissez votre niveau d'évaluation :",
            ["facile", "intermédiaire", "avancé"],
            index=1,
        )
        eligible_count = len(filter_questions_by_level(df, selected_level))

        st.markdown(
            """
            <div class="attention-box">
                Attention: vous aurez 15 secondes par question. Si vous ne validez pas votre reponse a temps,
                la machine choisira aleatoirement a votre place. Vous pouvez selectionner 1 ou 2 reponses.
                Le test contient 20 questions tirees au sort selon votre niveau,
                plus 1 question d'echauffement fixe.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Base d'echantillonnage disponible pour le niveau {selected_level}: {eligible_count} questions"
        )

        can_start = bool(user_name and (not user_email or is_email_ok) and eligible_count >= 20)
        st.button(
            "Start / Commencer le QCM",
            type="primary",
            use_container_width=True,
            disabled=not can_start,
            key="start_quiz",
        )

        if st.session_state.start_quiz:
            eligible_df = filter_questions_by_level(df, selected_level)
            if len(eligible_df) < 20:
                st.error(
                    "Pas assez de questions pour ce niveau. "
                    f"Questions disponibles: {len(eligible_df)} / 20 requises."
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
        elif eligible_count < 20:
            st.info("Pas assez de questions disponibles pour ce niveau (minimum 20 requises).")
        return

    quiz_df = st.session_state.quiz_df if st.session_state.quiz_df is not None else df

    # Auto-refresh stable (sans rechargement navigateur) pour piloter timer et transitions.
    if st_autorefresh is not None:
        st_autorefresh(interval=1000, key="quiz_autorefresh")

    if st.session_state.quiz_finished:
        score = 0.0
        total_points = len(quiz_df)
        for index, row in quiz_df.iterrows():
            correct_texts = get_correct_texts(row)
            selected_texts = st.session_state.answers.get(index, [])
            if correct_texts:
                # 1 bonne réponse -> 1 point; 2 bonnes réponses -> 0.5 point chacune.
                score += len(set(selected_texts) & set(correct_texts)) / len(correct_texts)

        normalized_score = (score / total_points) * 100 if total_points else 0.0
        st.success(f"Termine ! Score normalise: {normalized_score:.2f}%")
        st.caption(f"Detail: {score:.2f} points sur {total_points}")
        if st.session_state.auto_assigned:
            st.info(
                f"Reponses attribuees aleatoirement (temps ecoule): "
                f"{len(st.session_state.auto_assigned)}"
            )

        if not st.session_state.result_saved:
            local_msg = save_result(
                st.session_state.candidate_name,
                st.session_state.candidate_email,
                score,
                total_points,
            )
            st.session_state.result_saved = True
            st.info(local_msg)

        if st.button("Recommencer le test", type="primary", use_container_width=True):
            reset_quiz_state()
            st.rerun()
        return

    index = st.session_state.current_question
    row = quiz_df.iloc[index]

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

    elapsed = int(time.time() - st.session_state.question_start_ts)
    remaining = max(0, 15 - elapsed)

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

    # Si le temps est ecoule, on attribue une reponse aleatoire et on passe
    # directement a la question suivante.
    if remaining == 0 and index not in st.session_state.answers:
        random_choice = random.choice(options)
        st.session_state.answers[index] = [random_choice]
        st.session_state.auto_assigned.append(index + 1)
        next_question(len(quiz_df))

    if st.button("Valider la reponse", key=f"validate_{index}"):
        if not selected:
            st.warning("Selectionnez au moins une reponse avant de valider.")
        elif len(selected) > 2:
            st.warning("Selectionnez au maximum 2 reponses avant de valider.")
        else:
            st.session_state.answers[index] = selected
            next_question(len(quiz_df))

if __name__ == "__main__":
    main()
