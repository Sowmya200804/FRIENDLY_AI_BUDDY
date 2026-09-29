import streamlit as st
import ollama
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Optional document readers
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    import pandas as pd
except ImportError:
    pd = None

st.set_page_config(
    page_title="StudyBuddy AI 🤖📚",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CSS ----------
def load_css():
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True
        )

load_css()

# ---------- Local storage ----------
DATA_DIR = Path(__file__).parent / "study_data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "chat_history.json"
NOTES_FILE = DATA_DIR / "saved_notes.json"

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

if "messages" not in st.session_state:
    st.session_state.messages = load_json(HISTORY_FILE, [])

if "document_text" not in st.session_state:
    st.session_state.document_text = ""

if "document_name" not in st.session_state:
    st.session_state.document_name = ""

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

# ---------- File reading ----------
def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()

    if name.endswith(".txt") or name.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")

    if name.endswith(".pdf"):
        if PyPDF2 is None:
            return "PDF_READER_MISSING"
        reader = PyPDF2.PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)

    if name.endswith(".docx"):
        if Document is None:
            return "DOCX_READER_MISSING"
        doc = Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs)

    if name.endswith(".csv"):
        if pd is None:
            return "CSV_READER_MISSING"
        df = pd.read_csv(uploaded_file)
        return df.to_string(index=False)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        if pd is None:
            return "XLSX_READER_MISSING"
        sheets = pd.read_excel(uploaded_file, sheet_name=None)
        chunks = []
        for sheet, df in sheets.items():
            chunks.append(f"Sheet: {sheet}\n{df.to_string(index=False)}")
        return "\n\n".join(chunks)

    return "UNSUPPORTED_FILE"

# ---------- AI ----------
def ask_ollama(question, mode, context=""):
    mode_instructions = {
        "💬 Friendly Tutor": "Teach clearly using simple language, examples, and encouragement.",
        "📝 Exam Prep": "Focus on exam-ready explanations, key points, likely questions, and concise revision.",
        "🧩 Quiz Master": "Create a quiz. Ask one question at a time unless the student requests a full quiz.",
        "🧠 Explain Simply": "Explain the topic as if teaching a beginner. Use analogies and simple examples.",
        "⚡ Quick Revision": "Give a compact revision sheet with definitions, formulas, facts, and memory tricks.",
        "🎯 Study Planner": "Help organize a realistic study plan with priorities, breaks, and achievable tasks.",
        "💡 Doubt Solver": "Solve the student's doubt step by step and point out common mistakes."
    }

    system_prompt = f"""
You are StudyBuddy AI 🤖📚, a friendly, patient study assistant for students.

Current study mode: {mode}
Mode instructions: {mode_instructions.get(mode, mode_instructions["💬 Friendly Tutor"])}

Rules:
- Be encouraging but never pretend to know something you do not know.
- Explain difficult concepts in simple language.
- Use headings, bullets, examples, and step-by-step reasoning when useful.
- For mathematics/science, show the important steps and formulas.
- For exam preparation, distinguish important facts from optional detail.
- If a question is based on uploaded material, use that material first.
- Do not invent information that is not supported by the uploaded material when the user asks specifically about it.
- If the uploaded document does not contain the answer, clearly say so and then provide general knowledge if appropriate.
- Keep answers student-friendly and readable.

Uploaded study material:
{context[:30000]}
"""

    response = ollama.chat(
        model="llama3.2",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )
    return response["message"]["content"]

# ---------- Header ----------
st.markdown("""
<div class="top-glow"></div>
<div class="hero">
    <div class="robot">🤖</div>
    <div class="eyebrow">✦ AI-POWERED STUDY SPACE ✦</div>
    <h1>Study<span>Buddy</span> AI</h1>
    <p>Your friendly learning companion for doubts, notes, exams & everything in between. 📚✨</p>
    <div class="emoji-row">🧠 ✨ 📖 🎯 💡 🚀</div>
</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🧭 Study Hub")
    mode = st.selectbox(
        "Choose your study mode",
        [
            "💬 Friendly Tutor",
            "📝 Exam Prep",
            "🧩 Quiz Master",
            "🧠 Explain Simply",
            "⚡ Quick Revision",
            "🎯 Study Planner",
            "💡 Doubt Solver"
        ]
    )

    st.markdown("---")
    st.markdown("### 📂 Study Material")
    uploaded = st.file_uploader(
        "Upload your notes or files",
        type=["pdf", "txt", "md", "docx", "csv", "xlsx", "xls"],
        help="Upload notes, PDFs, Word documents, CSVs or Excel files."
    )

    if uploaded:
        file_hash = hashlib.md5(uploaded.getvalue()).hexdigest()
        previous_hash = st.session_state.get("file_hash")

        if file_hash != previous_hash:
            with st.spinner("📖 Reading your study material..."):
                text = read_uploaded_file(uploaded)
                st.session_state.file_hash = file_hash
                st.session_state.document_name = uploaded.name

                if text == "PDF_READER_MISSING":
                    st.error("Install PyPDF2 to read PDFs.")
                elif text == "DOCX_READER_MISSING":
                    st.error("Install python-docx to read Word files.")
                elif text.endswith("_READER_MISSING"):
                    st.error("Install the required package.")
                elif text == "UNSUPPORTED_FILE":
                    st.error("This file type is not supported.")
                else:
                    st.session_state.document_text = text
                    st.success(f"✅ Loaded: {uploaded.name}")

    if st.session_state.document_text:
        st.markdown(
            f'<div class="file-pill">📄 {st.session_state.document_name}</div>',
            unsafe_allow_html=True
        )
        if st.button("🗑️ Remove file", use_container_width=True):
            st.session_state.document_text = ""
            st.session_state.document_name = ""
            st.session_state.file_hash = None
            st.rerun()

    st.markdown("---")
    st.markdown("### 💾 Your Study Data")

    if st.button("🧹 Clear chat", use_container_width=True):
        st.session_state.messages = []
        save_json(HISTORY_FILE, [])
        st.rerun()

    saved_notes = load_json(NOTES_FILE, {})
    st.caption(f"🗃️ Saved notes: {len(saved_notes)}")

# ---------- Quick tools ----------
st.markdown("### ⚡ Quick Study Tools")

q1, q2, q3, q4 = st.columns(4)

quick_prompts = {
    "📌 Summarize": "Summarize my uploaded study material into clear exam-ready notes.",
    "❓ Make Quiz": "Create 10 useful quiz questions from my uploaded study material. Include answers after the questions.",
    "🧠 Flashcards": "Turn my uploaded study material into concise question-and-answer flashcards.",
    "🔑 Key Points": "Extract the most important definitions, formulas, facts, and concepts from my uploaded study material."
}

for col, label in zip([q1, q2, q3, q4], quick_prompts):
    if col.button(label, use_container_width=True):
        if not st.session_state.document_text:
            st.warning("📂 Upload study material first!")
        else:
            prompt = quick_prompts[label]
            with st.spinner("🤖 Creating your study material..."):
                answer = ask_ollama(prompt, mode, st.session_state.document_text)
                st.session_state.last_answer = answer
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_json(HISTORY_FILE, st.session_state.messages)

# ---------- Chat history ----------
if st.session_state.messages:
    st.markdown("### 💬 Study Conversation")
    for msg in st.session_state.messages[-12:]:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-bubble">🧑‍🎓 <b>You</b><br>{msg["content"]}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="ai-bubble">🤖 <b>StudyBuddy</b><br>{msg["content"]}</div>',
                unsafe_allow_html=True
            )

# ---------- Question ----------
st.markdown("### 💭 Ask your study question")

question = st.text_area(
    "Your question",
    placeholder="Example: Explain photosynthesis in simple words 🌱\n\nOr ask: What are the key points from my uploaded PDF? 📖",
    height=120,
    label_visibility="collapsed"
)

c1, c2 = st.columns([4, 1])

with c1:
    ask = st.button("🚀 ASK STUDYBUDDY", use_container_width=True)

with c2:
    if st.button("🎲 Surprise Me", use_container_width=True):
        question = "Give me one interesting study fact related to my uploaded material."

if ask:
    if not question.strip():
        st.warning("💡 Type a question first!")
    else:
        with st.spinner("🤖 Thinking... preparing your study magic ✨"):
            try:
                answer = ask_ollama(
                    question,
                    mode,
                    st.session_state.document_text
                )

                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.messages.append({
                    "role": "user",
                    "content": question,
                    "time": now
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "time": now
                })
                st.session_state.last_answer = answer

                save_json(HISTORY_FILE, st.session_state.messages)

                st.markdown("### 🌟 StudyBuddy's Answer")
                st.markdown(
                    f'<div class="answer-card">{answer}</div>',
                    unsafe_allow_html=True
                )

            except Exception as e:
                st.error(
                    "⚠️ I couldn't connect to Ollama. "
                    "Make sure Ollama is running and `llama3.2` is installed."
                )

# ---------- Save notes ----------
st.markdown("### 📝 Save a Study Note")

note_title = st.text_input(
    "Note title",
    placeholder="e.g. Important Biology Definitions",
    label_visibility="collapsed"
)

note_content = st.text_area(
    "Note content",
    value=st.session_state.last_answer,
    placeholder="Write or paste something you want to remember...",
    height=130,
    label_visibility="collapsed"
)

if st.button("💾 SAVE NOTE", use_container_width=True):
    if note_title.strip() and note_content.strip():
        notes = load_json(NOTES_FILE, {})
        notes[note_title.strip()] = {
            "content": note_content,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_json(NOTES_FILE, notes)
        st.success("✅ Note saved locally!")
    else:
        st.warning("Please enter a title and note.")

# ---------- Saved notes ----------
notes = load_json(NOTES_FILE, {})
if notes:
    st.markdown("### 📚 My Saved Notes")
    for title, item in reversed(list(notes.items())):
        with st.expander(f"📌 {title}"):
            st.write(item["content"])
            st.caption(f"Saved: {item['saved_at']}")

# ---------- Footer ----------
st.markdown("""
<div class="footer">
    <div>🤖 StudyBuddy AI</div>
    <div>Built with Python • Streamlit • Ollama • 💜</div>
    <div>Keep learning. Keep growing. 🚀</div>
</div>
""", unsafe_allow_html=True)