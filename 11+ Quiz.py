import streamlit as st
import pandas as pd
import random

# Google Sheets Setup with error handling
try:
    import gspread
    from google.oauth2.service_account import Credentials

    # Authenticate with Google Sheets
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]
    CREDS = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPE)
    CLIENT = gspread.authorize(CREDS)

    # Open your Google Sheet
    SHEET_ID = st.secrets["sheets"]["sheet_id"]
    sheet = CLIENT.open_by_key(SHEET_ID).sheet1

    # Load data into DataFrame
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    st.success("✅ Connected to Google Sheets")

except Exception as e:
    st.error(f"❌ Google Sheets connection failed: {str(e)[:100]}...")
    st.info("Using local data mode - scores won't be saved to Google Sheets")
    
    # Fallback: Create empty dataframe with required columns
    df = pd.DataFrame(columns=['Word', 'Polished Definition', 'Part of Speech', 'Synonyms', 'Antonyms', 'Repetition'])
    df['Repetition'] = df['Repetition'].fillna(0).astype(int)
    
    # Set a flag to disable Google Sheets updates
    sheets_connected = False
else:
    sheets_connected = True

# Fill missing repetition values with 0
if 'Repetition' not in df.columns:
    df['Repetition'] = 0
else:
    df['Repetition'] = df['Repetition'].fillna(0).astype(int)

words = df.to_dict(orient="records")

# ======== REPETITION SCORE FUNCTION ========
def update_repetition_score(word, increment=1):
    """Update repetition score with connection check"""
    try:
        # Update local DataFrame first (always works)
        df.loc[df['Word'] == word, 'Repetition'] += increment
        
        # Only try Google Sheets if connected
        if sheets_connected:
            try:
                cell = sheet.find(word)
                repetition_col = df.columns.get_loc('Repetition') + 1
                current_value = int(sheet.cell(cell.row, repetition_col).value or 0)
                new_value = current_value + increment
                sheet.update_cell(cell.row, repetition_col, new_value)
            except Exception as sheet_error:
                st.warning(f"Couldn't update Google Sheets, but local score saved")
                
    except Exception as e:
        st.warning(f"Couldn't update score for '{word}'")
# ======== END OF FUNCTION ========

# Initialize session state
if 'quiz_started' not in st.session_state:
    st.session_state.quiz_started = False

# Start screen
if not st.session_state.quiz_started:
    st.title("11+ Vocabulary Quiz")
    st.write("Click below to start the quiz!")
    if st.button("Start Quiz"):
        st.session_state.quiz_started = True
        st.rerun()
else:
    
    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = {
            'questions': [],
            'current_question': 0,
            'score': 0,
            'selected_option': None,
            'submitted': False,
            'question_types': [],
            'user_answers': []  # ← ADDED: Track all user answers
        }
        
        # Generate question types (10 defs, 7 syns, 3 ants)
        question_types = (['definition'] * 10) + (['synonym'] * 7) + (['antonym'] * 3)
        random.shuffle(question_types)
        st.session_state.quiz_data['question_types'] = question_types
        
        # Prepare all questions upfront
        for q_type in question_types:
            word = random.choice(words)
            st.session_state.quiz_data['questions'].append({
                'word': word['Word'],
                'type': q_type,
                'correct': word['Polished Definition'] if q_type == 'definition' 
                        else random.choice(word['Synonyms'].split(', ')) if q_type == 'synonym'
                        else random.choice(word['Antonyms'].split(', ')),
                'pos': word['Part of Speech']
            })

    # Get current question data
    quiz = st.session_state.quiz_data
    if quiz['current_question'] < 20:  # Only proceed if questions remain
        current_q = quiz['questions'][quiz['current_question']]
        
        # Generate options (only once per question)
        if 'options' not in quiz:
            if current_q['type'] == 'definition':
                other_defs = [w['Polished Definition'] for w in words 
                            if w['Part of Speech'] == current_q['pos'] 
                            and w['Polished Definition'] != current_q['correct']]
                quiz['options'] = random.sample(other_defs, 4) + [current_q['correct']]
            
            elif current_q['type'] in ['synonym', 'antonym']:
                other_words = [w['Word'] for w in words 
                            if w['Part of Speech'] == current_q['pos']
                            and w['Word'] != current_q['word']]
                quiz['options'] = random.sample(other_words, 4) + [current_q['correct']]
            
            random.shuffle(quiz['options'])

        # Display question
        st.title("11+ Vocabulary Quiz")
        st.subheader(f"Question {quiz['current_question'] + 1}/20")
        
        if current_q['type'] == 'definition':
            st.subheader(f"What does {current_q['word']} mean?")
        elif current_q['type'] == 'synonym':
            st.subheader(f"Which word is a synonym of {current_q['word']}?")
        else:
            st.subheader(f"Which word is an antonym of {current_q['word']}?")

        # Radio buttons - disabled after submission
        selected = st.radio(
            "Choose:",
            quiz['options'],
            index=quiz['options'].index(quiz['selected_option']) if quiz['selected_option'] in quiz['options'] else None,
            disabled=quiz['submitted']
        )

        # Store selection
        if not quiz['submitted']:
            quiz['selected_option'] = selected

        # Submit button - only enabled when an option is selected
        if not quiz['submitted']:
            if st.button("Submit", disabled=selected is None):
                quiz['submitted'] = True
                is_correct = selected == current_q['correct']
                
                # RECORD USER ANSWER ← ADDED
                quiz['user_answers'].append({
                    'word': current_q['word'],
                    'correct': is_correct,
                    'user_choice': selected,
                    'correct_answer': current_q['correct'],
                    'question_type': current_q['type']
                })
                
                if is_correct:
                    st.success("Correct! ✅")
                    quiz['score'] += 1
                    update_repetition_score(current_q['word'], increment=1)
                else:
                    st.error(f"Wrong! The answer is: {current_q['correct']}")
        
        # Next question button - only shows after submission
        if quiz['submitted']:
            if st.button("Next Question"):
                quiz['current_question'] += 1
                quiz['selected_option'] = None
                quiz['submitted'] = False
                quiz.pop('options', None)
                st.rerun()

    # Final score screen
    else:
        st.balloons()
        st.subheader(f"Quiz Complete! Score: {quiz['score']}/20")
        
        # Progress Report - Show repetition score distribution
        st.subheader("📊 Progress Report")
        st.write("Occasions correctly answered / number of words")
        
        # Get all repetition values and count distribution
        repetition_counts = df['Repetition'].value_counts().sort_index()
        
        # Display each repetition level
        for rep_value in sorted(df['Repetition'].unique()):
            count = repetition_counts.get(rep_value, 0)
            st.write(f"{rep_value} times correctly answered : {count} words")
        
        # Detailed Results Breakdown ← ADDED
        st.subheader("📝 Detailed Results")
        
        # Separate correct and incorrect answers
        correct_words = []
        incorrect_words = []
        
        for answer in quiz['user_answers']:
            word_info = next((w for w in words if w['Word'] == answer['word']), None)
            if word_info:
                result_item = {
                    'Word': answer['word'],
                    'Part of Speech': word_info['Part of Speech'],
                    'Definition': word_info['Polished Definition'],
                    'Synonyms': word_info['Synonyms'],
                    'Antonyms': word_info['Antonyms'],
                    'Your Answer': answer['user_choice'],
                    'Correct Answer': answer['correct_answer'],
                    'Question Type': answer['question_type']
                }
                
                if answer['correct']:
                    correct_words.append(result_item)
                else:
                    incorrect_words.append(result_item)
        
        # Display results in expandable sections
        with st.expander(f"✅ Words You Got Right ({len(correct_words)})", expanded=True):
            if correct_words:
                st.dataframe(pd.DataFrame(correct_words), hide_index=True, use_container_width=True)
            else:
                st.write("No words answered correctly")
        
        with st.expander(f"❌ Words You Got Wrong ({len(incorrect_words)})", expanded=True):
            if incorrect_words:
                st.dataframe(pd.DataFrame(incorrect_words), hide_index=True, use_container_width=True)
            else:
                st.write("All words answered correctly! 🎉")
        
        if st.button("Restart Quiz"):
            st.session_state.clear()
            st.rerun()
