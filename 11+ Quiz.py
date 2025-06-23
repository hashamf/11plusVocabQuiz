import streamlit as st
import pandas as pd
import random

# Load Excel
df = pd.read_excel("WordBank.xlsx")
words = df.to_dict(orient="records")

# Initialize session state
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = {
        'questions': [],
        'current_question': 0,
        'score': 0,
        'selected_option': None,
        'submitted': False,
        'question_types': []
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
            if selected == current_q['correct']:
                st.success("Correct! ✅")
                quiz['score'] += 1
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
    if st.button("Restart Quiz"):
        st.session_state.clear()
        st.rerun()