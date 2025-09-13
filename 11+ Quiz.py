import streamlit as st
import pandas as pd
import random
import time  # ← ADDED

# Initialize session state for Google Sheets data
if 'sheets_connected' not in st.session_state:
    st.session_state.sheets_connected = False
if 'df' not in st.session_state:
    st.session_state.df = None
if 'words' not in st.session_state:
    st.session_state.words = None
if 'sheet' not in st.session_state:
    st.session_state.sheet = None

# Google Sheets Setup - ONLY ONCE at start
if st.session_state.df is None:
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
        st.session_state.sheet = sheet

        # Load data into DataFrame ONCE
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        st.session_state.df = df
        st.session_state.sheets_connected = True
        st.success("✅ Connected to Google Sheets - Data loaded")

    except Exception as e:
        st.error(f"❌ Google Sheets connection failed: {str(e)[:100]}...")
        st.info("Using local data mode - scores won't be saved to Google Sheets")
        # Fallback: Create empty dataframe
        df = pd.DataFrame(columns=['Word', 'Polished Definition', 'Part of Speech', 'Synonyms', 'Antonyms', 'Repetition'])
        df['Repetition'] = df['Repetition'].fillna(0).astype(int)
        st.session_state.df = df
        st.session_state.sheets_connected = False

# Get data from session state
df = st.session_state.df
sheets_connected = st.session_state.sheets_connected
sheet = st.session_state.sheet if hasattr(st.session_state, 'sheet') else None

# Fill missing repetition values with 0
if 'Repetition' not in df.columns:
    df['Repetition'] = 0
else:
    df['Repetition'] = df['Repetition'].fillna(0).astype(int)

words = df.to_dict(orient="records")
st.session_state.words = words

# ======== UPDATED REPETITION SCORE FUNCTION ========
def update_repetition_score(word, increment=1):
    """Update repetition score LOCALLY ONLY during quiz"""
    try:
        # Update local DataFrame only (no API calls during quiz)
        df.loc[df['Word'] == word, 'Repetition'] += increment
        st.session_state.df = df  # Keep updated in session state
    except Exception as e:
        st.warning(f"Couldn't update score for '{word}'")

# ======== BULK UPLOAD FUNCTION ========
def upload_all_scores():
    """Upload ALL updated scores to Google Sheets at ONCE"""
    if sheets_connected and sheet is not None:
        try:
            # Convert updated DataFrame back to list of lists
            all_data = [df.columns.values.tolist()] + df.values.tolist()
            # Update entire sheet in ONE API call
            sheet.update(all_data)
            st.success("✅ All scores saved to Google Sheets!")
        except Exception as e:
            st.error(f"❌ Failed to save scores to Google Sheets: {str(e)[:100]}...")
# ======== END OF FUNCTIONS ========

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
            'user_answers': []
        }
        
        # Generate question types (10 defs, 7 syns, 3 ants)
        question_types = (['definition'] * 10) + (['synonym'] * 7) + (['antonym'] * 3)
        random.shuffle(question_types)
        st.session_state.quiz_data['question_types'] = question_types


        # Prepare all questions upfront
        used_words = set()  # Track words already used in this quiz
        
        # Get minimum repetition value in the entire dataset
        min_rep = min(word['Repetition'] for word in words)
        
        for q_type in question_types:
            # FIRST: Only use words with the current minimum repetition value
            eligible_words = [w for w in words if w['Repetition'] == min_rep]
            
            # SECOND: From eligible words, avoid duplicates within this quiz
            available_words = [w for w in eligible_words if w['Word'] not in used_words]
            
            # Fallback: If no unique words left at this repetition level, use any eligible words
            if not available_words:
                available_words = eligible_words
                
            word = random.choice(available_words)
            used_words.add(word['Word'])  # Mark this word as used
      
            
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
                # SMART FALLBACK: Use available options
                num_options = min(4, len(other_defs))
                quiz['options'] = random.sample(other_defs, num_options) + [current_q['correct']]
            
            elif current_q['type'] in ['synonym', 'antonym']:
                other_words = [w['Word'] for w in words 
                            if w['Part of Speech'] == current_q['pos']
                            and w['Word'] != current_q['word']]
                # SMART FALLBACK: Use available options
                num_options = min(4, len(other_words))
                quiz['options'] = random.sample(other_words, num_options) + [current_q['correct']]
            
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

        # Display each option as a clickable button (replaces radio buttons + submit button)
        st.write("**Choose your answer:**") 
        



            for option in quiz['options']:
                if st.button(option, key=f"opt_{option}", disabled=quiz['submitted'], use_container_width=True):
                    quiz['selected_option'] = option
                    quiz['submitted'] = True
                    
                    # PROCESS ANSWER IMMEDIATELY
                    is_correct = option == current_q['correct']
                    quiz['user_answers'].append({
                        'word': current_q['word'],
                        'correct': is_correct,
                        'user_choice': option,
                        'correct_answer': current_q['correct'],
                        'question_type': current_q['type']
                    })
                    
                    if is_correct:
                        st.success("✅ Correct!")
                        quiz['score'] += 1
                        update_repetition_score(current_q['word'], increment=1)
                    else:
                        st.error(f"❌ Wrong! The correct answer was: **{current_q['correct']}**")
                    
                    # Show explanation box
                    with st.expander("💡 Explanation", expanded=True):
                        word_info = next((w for w in words if w['Word'] == current_q['word']), None)
                        if word_info:
                            st.write(f"**Word:** {current_q['word']}")
                            st.write(f"**Part of Speech:** {word_info['Part of Speech']}")
                            st.write(f"**Definition:** {word_info['Polished Definition']}")
                            st.write(f"**Synonyms:** {word_info['Synonyms']}")
                            st.write(f"**Antonyms:** {word_info['Antonyms']}")
                    
                    # STORE the feedback in session state so it persists through rerun
                    st.session_state.feedback = {
                        'is_correct': is_correct,
                        'message': "✅ Correct!" if is_correct else f"❌ Wrong! The correct answer was: **{current_q['correct']}**",
                        'word_info': word_info,
                        'current_word': current_q['word']
                    }
                    
                    st.rerun()
            
            # AFTER the buttons, show persistent feedback if it exists
            if quiz['submitted'] and 'feedback' in st.session_state:
                feedback = st.session_state.feedback
                if feedback['is_correct']:
                    st.success(feedback['message'])
                else:
                    st.error(feedback['message'])
                
                # Show explanation box
                with st.expander("💡 Explanation", expanded=True):
                    if feedback['word_info']:
                        st.write(f"**Word:** {feedback['current_word']}")
                        st.write(f"**Part of Speech:** {feedback['word_info']['Part of Speech']}")
                        st.write(f"**Definition:** {feedback['word_info']['Polished Definition']}")
                        st.write(f"**Synonyms:** {feedback['word_info']['Synonyms']}")
                        st.write(f"**Antonyms:** {feedback['word_info']['Antonyms']}")
                
                # Countdown timer
                st.write("⏳ Moving to next question in 3 seconds...")
                time.sleep(3)
                
                # Clean up and move to next question
                del st.session_state.feedback  # Remove stored feedback
                quiz['current_question'] += 1
                quiz['selected_option'] = None
                quiz['submitted'] = False
                quiz.pop('options', None)
                st.rerun()
        
        
        # Automatic next question after 3 seconds ← REPLACED NEXT QUESTION BUTTON
        if quiz['submitted']:
            st.write("⏳ Moving to next question in 3 seconds...")
            
            # Add delay
            time.sleep(3)
            
            # Move to next question
            quiz['current_question'] += 1
            quiz['selected_option'] = None
            quiz['submitted'] = False
            quiz.pop('options', None)
            st.rerun()

    # Final score screen
    else:
        st.balloons()
        st.subheader(f"Quiz Complete! Score: {quiz['score']}/20")
        
        # UPLOAD ALL SCORES AT ONCE (Bulk API call)
        if sheets_connected:
            upload_all_scores()
        
        # Progress Report - Show repetition score distribution
        st.subheader("📊 Progress Report")
        st.write("Occasions correctly answered / number of words")
        
        # Get all repetition values and count distribution
        repetition_counts = df['Repetition'].value_counts().sort_index()
        
        # Display each repetition level
        for rep_value in sorted(df['Repetition'].unique()):
            count = repetition_counts.get(rep_value, 0)
            st.write(f"{rep_value} times correctly answered : {count} words")
        
        # Detailed Results Breakdown
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

