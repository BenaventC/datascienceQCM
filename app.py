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
st.set_page_config(page_title="QCM Data Science", page_icon="📊")

# Fichiers
QUESTIONS_FILE = "questions.csv"
RESULTS_FILE = "examen_resultat.csv"

def load_questions():
    if os.path.exists(QUESTIONS_FILE):
        return pd.read_csv(QUESTIONS_FILE)
    return pd.DataFrame()

def is_valid_dauphine_email(email):
    pattern = r"^[A-Za-z0-9._%+-]+@dauphine\.psl\.eu$"
    return re.match(pattern, email.strip()) is not None


def save_result(name, email, score, total):
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

    if not os.path.exists(RESULTS_FILE):
        new_result.to_csv(RESULTS_FILE, index=False)
    else:
        existing = pd.read_csv(RESULTS_FILE)
        if "Taux_reussite_%" not in existing.columns and {"Score", "Total"}.issubset(existing.columns):
            existing["Taux_reussite_%"] = (
                (existing["Score"] / existing["Total"].replace(0, pd.NA)) * 100
            ).round(2).fillna(0.0)
        combined = pd.concat([existing, new_result], ignore_index=True, sort=False)
        combined.to_csv(RESULTS_FILE, index=False)


def next_question(total_questions):
    st.session_state.current_question += 1
    st.session_state.question_start_ts = time.time()
    if st.session_state.current_question >= total_questions:
        st.session_state.quiz_finished = True
    st.rerun()

def main():
    st.title("🎓 QCM de Data Science")
    st.write("Répondez aux questions suivantes pour tester vos connaissances.")

    df = load_questions()

    if df.empty:
        st.error("Le fichier de questions est introuvable ou vide.")
        return

    required_columns = {
        "question",
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
            "question, option_a, option_b, option_c, option_d, option_e, correct_option."
        )
        return

    # Formulaire d'identification
    user_name = st.text_input("Entrez votre nom complet :")
    user_email = st.text_input("Entrez votre adresse email Dauphine :")
    is_email_ok = is_valid_dauphine_email(user_email) if user_email else False

    if user_email and not is_email_ok:
        st.warning("Utilisez une adresse valide au format @dauphine.psl.eu")

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

    if not st.session_state.quiz_started:
        st.warning(
            "Attention: vous aurez 15 secondes par question. "
            "Si vous ne validez pas votre reponse a temps, la machine choisira aleatoirement a votre place."
        )

        can_start = bool(user_name and is_email_ok)
        st.button(
            "Start / Commencer le QCM",
            type="primary",
            use_container_width=True,
            disabled=not can_start,
            key="start_quiz",
        )

        if st.session_state.start_quiz:
            st.session_state.candidate_name = user_name.strip()
            st.session_state.candidate_email = user_email.strip().lower()
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
        elif not is_email_ok:
            st.info("Saisissez un email valide @dauphine.psl.eu pour activer le bouton Start.")
        return

    # Auto-refresh stable (sans rechargement navigateur) pour piloter timer et transitions.
    if st_autorefresh is not None:
        st_autorefresh(interval=1000, key="quiz_autorefresh")

    if st.session_state.quiz_finished:
        score = 0
        for index, row in df.iterrows():
            letter_to_text = {
                "A": row["option_a"],
                "B": row["option_b"],
                "C": row["option_c"],
                "D": row["option_d"],
                "E": row["option_e"],
            }
            correct_text = letter_to_text.get(str(row["correct_option"]).strip().upper())
            if st.session_state.answers.get(index) == correct_text:
                score += 1

        st.success(f"Termine ! Votre score est de {score} / {len(df)}")
        if st.session_state.auto_assigned:
            st.info(
                f"Reponses attribuees aleatoirement (temps ecoule): "
                f"{len(st.session_state.auto_assigned)}"
            )

        if not st.session_state.result_saved:
            save_result(
                st.session_state.candidate_name,
                st.session_state.candidate_email,
                score,
                len(df),
            )
            st.session_state.result_saved = True
            st.info("Vos resultats ont ete enregistres dans 'examen_resultat.csv'.")
        return

    index = st.session_state.current_question
    row = df.iloc[index]

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

    st.subheader(f"Question {index + 1} / {len(df)}")
    st.write(row["question"])
    st.warning(f"Temps restant: {remaining} secondes")

    selected = st.radio(
        "Choisissez une reponse:",
        options,
        key=f"q_{index}",
        index=None,
    )

    # Si le temps est ecoule, on attribue une reponse aleatoire et on passe
    # directement a la question suivante.
    if remaining == 0 and index not in st.session_state.answers:
        random_choice = random.choice(options)
        st.session_state.answers[index] = random_choice
        st.session_state.auto_assigned.append(index + 1)
        next_question(len(df))

    if st.button("Valider la reponse", key=f"validate_{index}"):
        if selected is None:
            st.warning("Selectionnez une reponse avant de valider.")
        else:
            st.session_state.answers[index] = selected
            next_question(len(df))

if __name__ == "__main__":
    main()
