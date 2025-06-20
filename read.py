import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import os
import base64
import random
import edge_tts
import tempfile
import base64
import asyncio
from datetime import datetime, date
from typing import Optional
from PIL import Image
from openai import OpenAI, BadRequestError 
import pyttsx3
import tempfile

def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

image_base64 = get_base64_image("wave_blue.jpeg")  # Update with correct path

# ─────────────────────────────────────────────────────────────────────────────
# SETUP OPENAI CLIENT
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Streamlit page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Trade Analysis Dashboard")

# ─────────────────────────────────────────────────────────────
# GPT conversation memory (seed + reset)
# ─────────────────────────────────────────────────────────────
# GPT conversation memory
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "system",
            "content": (
                "You are **Optimus**, a smart financial assistant. You always introduce yourself as Optimus. Your responses are based strictly on the user's uploaded transaction data and documents (CSV, Excel, PDF, DOCX, or TXT). Each row represents a trade, excluding headers or summary lines.\n\n"
"You must:\n"
"- Always offer to show results in **tabular format** unless the user specifies otherwise.\n"
"- Always **include open transactions** when calculating earnings or premiums.\n"
"- Fully **study the data upfront** to detect patterns, quantities, premiums, symbols, and statuses.\n"
"- Ask for clarification if the user mentions a **month present across multiple years** (e.g. 'January') and proceed only after disambiguating the year.\n\n"
"You can create Excel summaries or PDFs if requested. You do not go online to retrieve info. If asked your name, respond that you are Optimus, a financial trading assistant. You can answer basic options-related concepts only if taught through uploaded material."
            )
        }
    ]

def reset_gpt_session():
    st.session_state.chat_history = [
        {
            "role": "system",
            "content": (
                "You are **Optimus**, a smart financial assistant. "
                "You always introduce yourself as Optimus. "
                "You answer using the user's transaction data which is either csv or excel and uploaded documents only which can be pdf or text or word documents. "
                "Every row in the data is a trade transaction (counting each line that represents a trade/transaction and excluding only the header and the TOTAL summary row). "
                "Keep your answers short (≤300 words). "
                "You can educate the user about concepts on things like Options and Options trading if they share the material with you. You are not to go online and gather that data"
                "If asked your name, respond that you are Optimus, a financial trading assistant. "
                "You will create a PDF report if asked, or output Excel summaries if asked. "
                "You are allowed to train on options concepts at a high level, but no detailed textbook explanations. "
                "You must ask the user if they want the results in a table format"
                "You must also accept uploaded PDF statement files, which can contain account history such as Securities Held in Account, Sym/Cusip, Account Type, Qty, Price, Market Value, Estimated Dividend Yield, and % of Total Portfolio. "
                "You must be able to answer based on this information too."
            )
        }
    ]
    st.session_state["gpt_response"] = ""
    st.session_state["user_input"] = ""
    st.session_state["gpt4_api_key"] = ""  # (✅ Clear key when resetting)

# ─────────────────────────────────────────────────────────────
# One-time voice + avatar initialisation
# ─────────────────────────────────────────────────────────────
def init_voice_and_avatar() -> None:
    """Pick a random voice/avatar once per session and set up a placeholder."""
    if "voice" in st.session_state:        # already initialised
        return

    gender         = random.choice(["male", "female"])
    voice, imgfile = (
        ("en-US-GuyNeural",   "optimm.jpeg")   if gender == "male"
        else ("en-US-JennyNeural", "optimf.jpeg")
    )

    st.session_state.update({
        "voice": voice,
        "image_file": imgfile,
        "gender": gender,          # placeholder – draw later
        "avatar_shown": False,
    })

init_voice_and_avatar()   # ← call once, before any TTS

# ─────────────────────────────────────────────────────────────
# Helper: speak via Edge TTS & keep avatar in sync
# ─────────────────────────────────────────────────────────────
async def speak_edge_tts(text: str, voice: Optional[str] = None) -> None:
    """Generate speech and ensure the correct avatar is displayed."""
    voice = voice or st.session_state["voice"]

    # ── make sure the placeholder exists ───────────────────────────
    if "avatar_slot" not in st.session_state:          # NEW
        st.session_state.avatar_slot = st.empty()      # NEW

    # show / update avatar if needed


         # ── show / update avatar if needed ───────────────────────────────
    expected_img = "optimm.jpeg" if "Guy" in voice else "optimf.jpeg"

    if (
        not st.session_state.get("avatar_shown", False)
        or expected_img != st.session_state.get("image_file")
    ):
        # center-aligned avatar
        b64 = base64.b64encode(open(expected_img, "rb").read()).decode()
        st.session_state.avatar_slot.markdown(
            f"""
             <div style="text-align:center;">
                 <img src="data:image/jpeg;base64,{b64}" style="width:280px;">
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.session_state.update(
            {"image_file": expected_img, "avatar_shown": True}
        )

    # synthesize speech
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            out_path = fp.name

        await edge_tts.Communicate(text, voice).save(out_path)

        audio_bytes = open(out_path, "rb").read()
        st.markdown(
            f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{base64.b64encode(audio_bytes).decode()}"
                        type="audio/mp3">
            </audio>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Edge TTS playback failed: {e}")

def init_voice_and_avatar():
    """Choose voice/avatar once per session and create an empty display slot."""
    if "voice" in st.session_state:
        return                                   # already set

    gender = random.choice(["male", "female"])
    voice, img_file = (
        ("en-US-GuyNeural",   "optimm.jpeg") if gender == "male"
        else ("en-US-JennyNeural", "optimf.jpeg")
    )

    st.session_state.update({
        "voice": voice,
        "image_file": img_file,
        "gender": gender,
        "avatar_slot": st.empty(),               # placeholder only – no image yet
        "avatar_shown": False,
    })

init_voice_and_avatar()  # ← call once

# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {background-color:#FFFFFF;}
        [data-testid="stSidebar"] .block-container {font-size:14px;}
        .block-container {font-size:16px;}
        .stDownloadButton > button,
        .stButton > button {
            background-color:#0A57C1 !important;
            color:white !important;
            border:none !important;
            padding:10px 20px !important;
            border-radius:8px !important;
            font-size:16px !important;
            font-weight:bold !important;
            box-shadow:0 4px 6px rgba(0,0,0,0.2);
            transition:background-color .3s ease;
            margin-top:10px !important;
        }
        .stDownloadButton > button:hover,
        .stButton > button:hover {background-color:#388E3C !important;}
    </style>
    """,
    unsafe_allow_html=True,
)
# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
def img_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# Move final2.jpeg to the sidebar
try:
    final_img = Image.open('final2.jpeg')
    final_b64 = img_to_b64(final_img)
    st.sidebar.markdown(
        f"""
        <div style='text-align:center; margin-bottom:10px;margin-top:-60px'>
            <img src='data:image/png;base64,{final_b64}' style='max-width:100%; border-radius:8px;'>
        </div>
        """,
        unsafe_allow_html=True,
    )
except FileNotFoundError:
    st.sidebar.warning("final2.jpeg missing.")



st.sidebar.subheader("Navigation")
page_selection = st.sidebar.radio("Select Page", ("Dashboard", "FAQ"))

# ─────────────────────────────────────────────────────────────
# 📥 Unified Upload Section – Trades and Knowledge Documents
# ─────────────────────────────────────────────────────────────
#st.sidebar.markdown("## 📥 Upload Your Files (Trades + Docs)")

uploaded_files = st.sidebar.file_uploader(
    "",
    type=["csv", "xlsx", "pdf", "docx", "txt"],
    accept_multiple_files=True,
    key="unified_uploader"
)

# Separate into two lists
uploaded_trade_files = []
uploaded_knowledge_files = []

if uploaded_files:
    for f in uploaded_files:
        ext = f.name.lower().split(".")[-1]
        if ext in ["csv", "xlsx"]:
            uploaded_trade_files.append(f)  # ✅ Parse later
        elif ext in ["pdf", "docx", "txt"]:
            uploaded_knowledge_files.append(f)  # ✅ Store for GPT later

# Save parsed files separately
if uploaded_trade_files:
    st.session_state["uploaded_trade_files"] = uploaded_trade_files

if uploaded_knowledge_files:
    st.session_state["knowledge_files_pending_upload"] = uploaded_knowledge_files

# ─────────────────────────────────────────────────────────────
# 🧹 Sort Transactions Section
# ─────────────────────────────────────────────────────────────
st.sidebar.subheader("Sort Transactions")
sort_columns = st.sidebar.multiselect(
    "Sort by (in priority order)",
    ["Activity Date", "Instrument", "Option Type", "Status", "Premium($)", "Broker"],
    default=["Activity Date"],
    key="sort_columns"
)
sort_direction = st.sidebar.radio("Sort order", ["Ascending", "Descending"], key="sort_direction")

st.sidebar.markdown("<div style='margin-bottom:-50px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 🔑 OpenAI API Key Input
# ─────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🔑 OpenAI API Key")
user_api_key = st.sidebar.text_input(
    "Enter your OpenAI API key:",
    type="password",
    key="api_key_input"
)

if user_api_key:
    st.session_state["gpt4_api_key"] = user_api_key
    st.sidebar.success("✅ API Key saved successfully!")

# 🔥 Always check whether the user has an API key
has_api_key = bool(st.session_state.get("gpt4_api_key"))

# ─────────────────────────────────────────────────────────────
# 🔄 Reset Session Button
# ─────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset Chat Session", key="reset_btn_sidebar"):
    reset_gpt_session()
    st.session_state.pop("gpt4_api_key", None)
    st.session_state.pop("assistant_id", None)
    st.session_state.pop("thread_id", None)
    st.session_state.pop("gpt_file_ids", None)
    st.session_state.pop("gpt_knowledge_file_ids", None)
    st.success("🔄 Chat session and API key have been reset.")


# 🛡 Reminder if API Key is missing
if not has_api_key:
    st.sidebar.warning(
        "Optimu$ chatbot requires an OpenAI API Key to work.\n\n"
        "Get yours here: [https://platform.openai.com/account/api-keys](https://platform.openai.com/account/api-keys)",
        icon="🚨"
    )
# ─────────────────────────────
# Renaming logic + display
# ─────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# FAQ (early exit)
# ─────────────────────────────────────────────────────────────────────────────
if page_selection == "FAQ":
    st.title("FAQ - Application Usage")
    st.markdown(
        """
        <div style="font-size:20px;">
            <strong>What does this app do?</strong><br>
            Upload brokerage trade files, then explore summaries, charts and full transaction details.<br><br>
            <strong>Filters & Options</strong><br>
            Use sidebar filters to slice data by broker, month, instrument, status and more.<br><br>
            <strong>Monthly Summary</strong><br>
            Net premiums with tax adjustments and grand totals.<br><br>
            <strong>Charts</strong><br>
            • Monthly Net Premium bar chart<br>
            • Three pie charts (open positions, closed/expired premium, calls vs puts)<br><br>
            <strong>Detailed Transactions</strong><br>
            Line‑item table of every trade with download button.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# GPT‑4 CHAT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def query_gpt4_conversational(prompt: str) -> str:
    try:
        client = OpenAI(api_key=st.session_state["gpt4_api_key"])

        # 1. Create/reuse Assistant
        if "assistant_id" not in st.session_state:
            assistant = client.beta.assistants.create(
                name="Optimu$ Doc-Aware",
                model="gpt-4o-mini",
                instructions="Answer strictly using the user's uploaded trades and documents. No assumptions.",
                tools=[{"type": "file_search"}]
            )
            st.session_state["assistant_id"] = assistant.id

        # 2. Create/reuse Thread
        if "thread_id" not in st.session_state:
            thread = client.beta.threads.create()
            st.session_state["thread_id"] = thread.id

        # 3. Combine all file attachments
        trade_files = st.session_state.get("gpt_file_ids", [])
        knowledge_files = st.session_state.get("gpt_knowledge_file_ids", [])
        all_files = trade_files + knowledge_files

        attachments = [{"file_id": fid, "tools": [{"type": "file_search"}]} for fid in all_files]

        # 4. Send user message with all attachments
        client.beta.threads.messages.create(
            thread_id=st.session_state["thread_id"],
            role="user",
            content=prompt,
            attachments=attachments
        )

        # 5. Run Assistant
        run = client.beta.threads.runs.create(
            thread_id=st.session_state["thread_id"],
            assistant_id=st.session_state["assistant_id"],
        )

        while run.status not in ("completed", "failed", "cancelled"):
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state["thread_id"],
                run_id=run.id
            )

        # 6. Return the final reply
        messages = client.beta.threads.messages.list(
            thread_id=st.session_state["thread_id"],
            limit=1
        )
        reply = messages.data[0].content[0].text.value

        return reply

    except Exception as e:
        return f"⚠️ GPT-4 connection failed: {e}"
# ─────────────────────────────────────────────────────────────
# Utility: convert an image file to base-64 (for HTML embed)
# ─────────────────────────────────────────────────────────────
import base64
def img_to_b64(pil_img):
    from io import BytesIO
    buf = BytesIO()
    pil_img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

# ─────────────────────────────────────────────────────────────
# Main Streamlit chat handler
# ─────────────────────────────────────────────────────────────
def run_gpt4_chat():
    tx_df = st.session_state.get("full_transactions_df")
    st.session_state.avatar_slot = st.empty()

    # Show Optimus Avatar
    img_path = st.session_state.get("image_file")
    if img_path:
        b64_img = base64.b64encode(open(img_path, "rb").read()).decode()
        st.session_state.avatar_slot.markdown(
            f"<div style='text-align:center;'><img src='data:image/jpeg;base64,{b64_img}' style='width:160px;'></div>",
            unsafe_allow_html=True,
        )

    # One-time greeting
    if "played_greeting" not in st.session_state:
        greeting = "Hi, I’m Optimus! I analyze your trades based on the data you share. Click ‘Ask Optimus’ to get started. For anything else, try searching outside the app. I also have the most common question prompt shortcuts you can use instead of having to type them"
        asyncio.run(speak_edge_tts(greeting))
        st.session_state.played_greeting = True

    # Style: larger checkbox + text input
    st.markdown("""
    <style>
        div[data-testid="stCheckbox"] input[type="checkbox"] {
            width: 28px; height: 28px; transform: scale(1.5); margin-right:10px;
        }
        div[data-testid="stCheckbox"] label {
            font-size: 30px !important;
            font-weight: 900 !important;
            color: #0A57C1 !important;
            padding-top: 12px;
            padding-bottom: 12px;
        }
        div[data-baseweb="input"] input {
            font-size: 24px !important;
            padding: 14px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Checkbox: Ask Optimus
    ask_optimus = st.checkbox(
        "Ask Optimus?",
        key="ask_optimus_checkbox",
        help="Enable Optimus chatbot with your data."
    )

    if ask_optimus:
        if not st.session_state.get("gpt4_api_key"):
            st.error("🚨 Please enter a valid OpenAi API Key first.")
            return

        # Upload knowledge files (only once)
        if st.session_state.get("knowledge_files_pending_upload"):
            client = OpenAI(api_key=st.session_state["gpt4_api_key"])
            st.session_state.setdefault("gpt_knowledge_file_ids", [])
            for f in st.session_state["knowledge_files_pending_upload"]:
                f.seek(0)
                upload = client.files.create(file=f, purpose="assistants")
                st.session_state["gpt_knowledge_file_ids"].append(upload.id)
            st.session_state["knowledge_files_pending_upload"] = []


        # Suggested Prompts for Quick Access
        # Suggested Quick Prompts
        st.markdown("<div style='font-size:26px; font-weight:bold; margin-top:20px;'>Ask Optimu$:</div>", unsafe_allow_html=True)

        example_prompts = [
            "Show me my top 5 premium-generating stocks YTD, including open trades.",
            "Summarize all option trades expiring this month and how much premium I’ve collected from them.",
            "List all open put options with strike prices below current stock prices and their premiums.",
            "Compare premium earnings month-over-month for the past 12 months in a table.",
            "How much net premium did I earn from rolled trades, and which ones are still open?"
        ]

        for i, prompt in enumerate(example_prompts):
            if st.button(f"🔹 {prompt}", key=f"quick_prompt_{i}"):
                st.session_state["selected_quick_prompt"] = prompt
                st.session_state["trigger_quick_prompt"] = True

        # Text input AFTER buttons so state can still be updated
        st.text_input(
            label="",
            key="optimus_question_input",
            placeholder="Type your trading question here...",
            on_change=process_query
        )

                # Show response if available
        if "gpt_response" in st.session_state:
            st.markdown("<div style='font-size:24px; font-weight:bold; margin-top:20px;'>Optimu$ Response:</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='font-size:22px; background-color:#f9f9f9; padding:18px; border-radius:10px; border:1px solid #ccc;'>{st.session_state['gpt_response']}</div>",
                unsafe_allow_html=True
            )


def process_query(prompt_override=None):
    user_question = prompt_override or st.session_state.get("optimus_question_input", "").strip()
    if not user_question:
        return
    

    ask_optimus = st.session_state.get("ask_optimus_checkbox", False)
    if not ask_optimus:
        return

    tx_df = st.session_state.get("full_transactions_df", pd.DataFrame())
    if tx_df.empty:
        st.error("No transaction data found.")
        return

    drop_cols = ["BTC Price", "STO Price", "Collateral", "Strike Price", "BTC Date", "STO Date"]
    df_short = tx_df.drop(columns=drop_cols, errors="ignore")

    chunk_size = 233
    chunks = [df_short.iloc[i:i + chunk_size] for i in range(0, len(df_short), chunk_size)]


    current_month = datetime.now().strftime("%Y-%m")

    if prompt_override:
        user_question = prompt_override

    final_answer = ""
    for i, chunk in enumerate(chunks):
        csv_chunk = chunk.to_csv(index=False)
        prompt = (
            "You are Optimus, a smart trading assistant. Use the data below to answer.\n"
            "Always:\n"
            "- Show results in table format unless told otherwise.\n"
            "- Include open transactions in any earnings or premium calculations.\n"
            "- Clarify if the user asks about a month that appears in multiple years (e.g., Jan 2023 and Jan 2024).\n"
            "- Study all available patterns before responding.\n\n"
            f"Chunk {i+1} of {len(chunks)}:\n{csv_chunk}\n\n"
            f"User's Question: {user_question}"
            f"You are Optimus, a trading assistant. Use the transaction data below to answer the user's question.\n"
            f"The current month is {current_month}. If the user says 'this month', interpret it as '{current_month}'.\n\n"
            f"Chunk {i+1} of {len(chunks)}:\n{csv_chunk}\n\n"
            f"User's Question: {user_question}"

        )
        
        response = query_gpt4_conversational(prompt)
        final_answer += f"{response}"

    st.session_state["gpt_response"] = final_answer
    # 🔧 Moved outside so input box always shows
    #st.markdown("<div style='font-size:24px; font-weight:bold; margin-top:10px;'>Ask Optimu$:</div>", unsafe_allow_html=True)
    st.markdown("""
        <style>
        div[data-baseweb="input"] input {
            font-size: 22px !important;
            padding: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (parsing, tagging, etc.)
# ─────────────────────────────────────────────────────────────────────────────
def parse_amount(amt):
    if pd.isna(amt):
        return 0.0
    txt = (
        str(amt).replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    )
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?", txt)
    return sum(float(n) for n in nums) if nums else 0.0


def fallback_extract_expiry_date(desc):
    if pd.isna(desc):
        return None
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", str(desc))
    if m:
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y")
        except ValueError:
            return None
    return None


def symbol_extract_expiry_strike_option(text):
    if not text or pd.isna(text):
        return (None, 0.0, None)
    dt_m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    expiry_dt = (
        datetime.strptime(dt_m.group(1), "%m/%d/%Y").date() if dt_m else None
    )
    sc_m = re.search(r"\s(\d+(?:\.\d+))\s([PC])\b", text)
    if sc_m:
        strike = float(sc_m.group(1))
        opt_type = "Put" if sc_m.group(2).upper() == "P" else "Call"
    else:
        strike, opt_type = 0.0, None
    return (expiry_dt, strike, opt_type)


def parse_schwab_to_robinhood(file_like):
    df = pd.read_csv(file_like)
    df = df[df["Action"].isin(["Sell to Open", "Buy to Close"])].copy()
    df["Instrument"] = df["Symbol"].str.split().str[0]
    df["Trans Code"] = np.where(df["Action"] == "Sell to Open", "STO", "BTC")

    def clean_dt(d):
        if pd.isna(d):
            return None
        m = re.search(r"as of (\d{2}/\d{2}/\d{4})", str(d))
        if m:
            try:
                return datetime.strptime(m.group(1), "%m/%d/%Y").date()
            except ValueError:
                return None
        try:
            return datetime.strptime(str(d), "%m/%d/%Y").date()
        except ValueError:
            return None

    df["Activity Date"] = df["Date"].apply(clean_dt)
    df["Price"] = df["Price"].apply(parse_amount)
    df["Amount"] = df["Amount"].apply(parse_amount)

    parsed = df["Symbol"].apply(symbol_extract_expiry_strike_option)
    df["Parsed Expiry"] = parsed.apply(lambda x: x[0])
    df["Parsed Strike"] = parsed.apply(lambda x: x[1])
    df["Parsed Type"] = parsed.apply(lambda x: x[2])

    if df["Parsed Expiry"].notna().sum() == 0:
        df["Parsed Expiry"] = df["Description"].apply(fallback_extract_expiry_date)

    df["Expiry Date"] = df["Parsed Expiry"]
    df["Strike Price"] = df["Parsed Strike"]
    df["Option Type"] = df["Parsed Type"]

    def seg_amt(a):
        if pd.isna(a):
            return (None, None)
        if a > 0:
            return (a, None)
        if a < 0:
            return (None, a)
        return (None, None)

    df[["STO($)", "BTC($)"]] = df["Amount"].apply(lambda x: pd.Series(seg_amt(x)))

    keep = [
        "Activity Date",
        "Instrument",
        "Description",
        "Trans Code",
        "Price",
        "Amount",
        "Expiry Date",
        "Strike Price",
        "Option Type",
        "STO($)",
        "BTC($)",
    ]
    return df[keep].copy()


def parse_description_for_option(desc):
    if not desc or pd.isna(desc):
        return (None, 0.0, None)
    dt_m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", str(desc))
    expiry = datetime.strptime(dt_m.group(1), "%m/%d/%Y").date() if dt_m else None
    type_m = re.search(r"\b(put|call)\b", str(desc), re.IGNORECASE)
    opt_type = type_m.group(1).capitalize() if type_m else None
    strike_m = re.search(r"\$(\d+(?:\.\d+)?)", str(desc))
    strike = float(strike_m.group(1)) if strike_m else 0.0
    return (expiry, strike, opt_type)


def parse_robinhood_file(file_like):
    fname = file_like.name.lower()
    data = pd.read_csv(file_like, on_bad_lines="skip") if fname.endswith(".csv") else pd.read_excel(file_like)
    data.columns = data.columns.str.strip()

    if "Description" in data.columns:
        ext = data["Description"].apply(parse_description_for_option)
        data["Expiry Date"] = ext.apply(lambda x: x[0])
        data["Strike Price"] = ext.apply(lambda x: x[1])
        data["Option Type"] = ext.apply(lambda x: x[2])
    else:
        st.warning("Robinhood CSV has no 'Description' column – option fields empty.")

    if {"Trans Code", "Amount"}.issubset(data.columns):
        data["STO($)"] = np.where(data["Trans Code"] == "STO", data["Amount"], 0)
        data["BTC($)"] = np.where(data["Trans Code"] == "BTC", data["Amount"], 0)

    for c in ["Amount", "Price", "Quantity"]:
        if c in data.columns:
            data[c] = data[c].apply(parse_amount)
    return data


def upload_to_openai(sf_file):
    sf_file.seek(0)                                   # ← NEW: rewind
    up = client.files.create(file=sf_file, purpose="assistants")
    return up.id



def _read_as_text(file_obj) -> str:
    """
    Streamlit gives an `UploadedFile` whose .read()/.getvalue() is *bytes*.
    This helper makes sure we always get plain *str*.
    """
    raw = file_obj.getvalue() if hasattr(file_obj, "getvalue") else file_obj.read()
    return raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else raw

def parse_fidelity_file(file_like):
    import pandas as pd
    import re
    import io

    # Step 1: Read and clean disclaimer lines
    content = file_like.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    clean_lines = [
        line for line in content.splitlines()
        if "Date downloaded" not in line and "provided to you solely for your use" not in line
    ]
    df = pd.read_csv(io.StringIO("\n".join(clean_lines)))

    # Step 2: Strip whitespace from column names and strings
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Step 3: Parse fields
    df["Activity Date"] = pd.to_datetime(df["Run Date"], errors="coerce")
    df["Trans Code"] = df["Action"].str.extract(r"YOU\s+(\w+)", expand=False).str.upper()
    df["Trans Code"] = df["Trans Code"].replace({"SOLD": "STO", "BOUGHT": "BTC"})
    df["Instrument"] = df["Description"].str.extract(r"\((\w+)\)")

    def extract_option_fields(desc):
        if pd.isna(desc):
            return (None, 0.0, None)
        desc = str(desc)
        expiry = re.search(r"([A-Z]{3,9}\s\d{1,2}\s\d{2,4})", desc)
        strike = re.search(r"\$(\d+(?:\.\d+)?)", desc)
        opt_type = "Put" if "put" in desc.lower() else ("Call" if "call" in desc.lower() else None)
        return (
            pd.to_datetime(expiry.group(1), errors="coerce").date() if expiry else None,
            float(strike.group(1)) if strike else 0.0,
            opt_type
        )

    parsed = df["Description"].apply(extract_option_fields)
    df["Expiry Date"] = parsed.apply(lambda x: x[0])
    df["Strike Price"] = parsed.apply(lambda x: x[1])
    df["Option Type"] = parsed.apply(lambda x: x[2])

    def parse_amount(val):
        if pd.isna(val):
            return 0.0
        txt = str(val).replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
        nums = re.findall(r"[+-]?\d+(?:\.\d+)?", txt)
        return sum(float(n) for n in nums) if nums else 0.0

    df["Price"] = df["Price ($)"].apply(parse_amount)
    df["Amount"] = df["Amount ($)"].apply(parse_amount)
    df[["STO($)", "BTC($)"]] = df["Amount"].apply(lambda x: pd.Series((x, 0) if x > 0 else (0, x)))

    # Step 4: Remove blank rows (missing Description usually means blank row)
    df = df[df["Description"].notna()].copy()

    # Step 5: Final columns
    keep = [
        "Activity Date", "Instrument", "Description", "Trans Code",
        "Price", "Amount", "Expiry Date", "Strike Price", "Option Type",
        "STO($)", "BTC($)"
    ]
    return df[keep].copy()

def tag_transactions(mg):
    def status_row(r):
        today = date.today()
        exp_val = r.get("Expiry Date")
        exp_dt = None
        if pd.notna(exp_val):
            if isinstance(exp_val, (pd.Timestamp, datetime)):
                exp_dt = exp_val.date()
            elif isinstance(exp_val, date):
                exp_dt = exp_val
            else:
                try:
                    exp_dt = datetime.strptime(str(exp_val), "%m/%d/%Y").date()
                except ValueError:
                    pass
        if pd.notna(r.get("STO Date")) and pd.isna(r.get("BTC Date")) and exp_dt and exp_dt > today:
            return "Open"
        if pd.isna(r.get("BTC Date")) and exp_dt and exp_dt < today:
            return "Expired"
        if pd.notna(r.get("BTC Date")) and abs(r.get("BTC Price", 0)) <= 2:
            return "Closed"
        if pd.notna(r.get("BTC Date")) and abs(r.get("BTC Price", 0)) > 2:
            return "Rolled"
        return "Open"

    mg["Status"] = mg.apply(status_row, axis=1)
    return mg


def compute_qty(r):
    if r.get("STO($)", 0) != 0:
        amt, price = r["STO($)"], r["STO Price"]
    elif r.get("BTC($)", 0) != 0:
        amt, price = r["BTC($)"], r["BTC Price"]
    else:
        return 0
    return 0 if pd.isna(price) or price == 0 else amt / (price * 100)


def calc_premium(r):
    return r.get("STO($)", 0) - abs(r.get("BTC($)", 0))


# ─────────────────────────────────────────────────────────────────────────────
# HEADER IMAGES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
    <div style="
        background-image: url('data:image/png;base64,{image_base64}');
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center;
        padding: 80px 20px;
        border-radius: 20px;
        margin-top: -50px;
        margin-bottom: 40px;
        text-align: center;">
        
    </div>
""", unsafe_allow_html=True)



# MAIN LOGIC – FILE UPLOAD
# ─────────────────────────────────────────────────────────────────────────────
# File uploader (isolated)
# Custom display of renamed files (prevents pagination)
# MAIN LOGIC – FILE UPLOAD
if uploaded_trade_files:  # ✅ only trade files, NOT knowledge docs
    data_frames = []
    for f in uploaded_trade_files:
        try:
            if f.name.startswith("Designated"):
                df_parsed = parse_schwab_to_robinhood(f)
                df_parsed["Broker"] = "Schwab"
            elif f.name.startswith("History"):
                text = _read_as_text(f)
                filtered_text = "\n".join([
                    ln for ln in text.splitlines()
                    if "date downloaded" not in ln.lower() and "provided to you solely for your use" not in ln.lower()
                ])
                from io import StringIO
                temp_buf = StringIO(filtered_text)
                df_parsed = parse_fidelity_file(temp_buf)
                df_parsed["Broker"] = "Fidelity"
            else:
                df_parsed = parse_robinhood_file(f)
                df_parsed["Broker"] = "Hood"

            if not df_parsed.empty:
                data_frames.append(df_parsed)

        except Exception as e:
            st.error(f"Error parsing '{f.name}': {e}")

    if not data_frames:
        st.error("No valid data from uploaded files.")
        st.stop()

    # ── 3. Standardize and combine ──────────────────────────
    def standardize_common_columns(df):
        for col in ["Activity Date", "Process Date", "Settle Date", "Expiry Date", "STO Date", "BTC Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        if "Option Type" in df.columns:
            df["Option Type"] = df["Option Type"].fillna("Other").astype(str)
        return df

    data_frames = [standardize_common_columns(df) for df in data_frames if not df.empty]
    data = pd.concat(data_frames, ignore_index=True)

    if "Option Type" in data.columns:
        data["Option Type"] = data["Option Type"].astype(str)

    if "BTC Date" in data.columns:
        data["BTC Date"] = pd.to_datetime(
            data["BTC Date"].replace("", pd.NA),
            format="%m/%d/%Y",
            errors="coerce",
        )

    for col in ["Amount", "Price", "Quantity"]:
        if col in data.columns:
            data[col] = data[col].apply(parse_amount)

    if "Expiry Date" not in data.columns:
        data["Expiry Date"] = data["Description"].apply(fallback_extract_expiry_date)

    if "Strike Price" not in data.columns:
        data["Strike Price"] = data["Description"].apply(
            lambda x: float(re.search(r"\$(\d+(\.\d+)?)", str(x)).group(1))
            if re.search(r"\$(\d+(\.\d+)?)", str(x))
            else 0.0
        )

    if "Option Type" not in data.columns:
        data["Option Type"] = data["Description"].apply(
            lambda x: (
                "Call"
                if "call" in str(x).lower()
                else ("Put" if "put" in str(x).lower() else "Other")
            )
        )


    if "BTC Date" in data.columns:
        data["BTC Date"] = pd.to_datetime(
            data["BTC Date"].replace("", pd.NA),
            format="%m/%d/%Y",
            errors="coerce",
        )

    for col in ["Amount", "Price", "Quantity"]:
        if col in data.columns:
            data[col] = data[col].apply(parse_amount)

    if "Expiry Date" not in data.columns:
        data["Expiry Date"] = data["Description"].apply(fallback_extract_expiry_date)

    if "Strike Price" not in data.columns:
        data["Strike Price"] = data["Description"].apply(
            lambda x: float(re.search(r"\$(\d+(\.\d+)?)", str(x)).group(1))
            if re.search(r"\$(\d+(\.\d+)?)", str(x))
            else 0.0
        )

    if "Option Type" not in data.columns:
        data["Option Type"] = data["Description"].apply(
            lambda x: (
                "Call"
                if "call" in str(x).lower()
                else ("Put" if "put" in str(x).lower() else "Other")
            )
        )

    # Consolidate STO/BTC lines into single rows
    group_cols = ["Instrument", "Trans Code", "Activity Date", "Description", "Broker"]
    agg_dict = {
        "Amount": "sum",
        "Price": "mean",
        "Option Type": "first",
        "Strike Price": "first",
        "Expiry Date": "first",
        "Quantity": "sum"
    }

    data_cons = (
        data.groupby(group_cols, dropna=False, as_index=False)
        .agg(agg_dict)
        .dropna(subset=["Activity Date", "Instrument", "Trans Code"])
    )

    # split STO/BTC
    sto = data_cons[data_cons["Trans Code"] == "STO"]
    btc = data_cons[data_cons["Trans Code"] == "BTC"]

    sto["Quantity"] = sto.apply(compute_qty, axis=1)
    btc["Quantity"] = btc.apply(compute_qty, axis=1)

    sto_grp = (
        sto.groupby(["Description", "Instrument", "Broker"], dropna=False)
        .agg(
            {
                "Amount": "sum",
                "Price": "mean",
                "Activity Date": "min",
                "Option Type": "first",
                "Strike Price": "first",
                "Expiry Date": "first",
                "Quantity": "sum"
            }
        )
        .reset_index()
        .rename(
            columns={
                "Amount": "STO($)",
                "Price": "STO Price",
                "Activity Date": "STO Date",
            }
        )
    )

    btc_grp = (
        btc.groupby(["Description", "Instrument", "Broker"], dropna=False)
        .agg({"Amount": "sum", "Price": "mean", "Activity Date": "max"})
        .reset_index()
        .rename(
            columns={
                "Amount": "BTC($)",
                "Price": "BTC Price",
                "Activity Date": "BTC Date",
            }
        )
    )

    merged = pd.merge(
        sto_grp,
        btc_grp,
        on=["Description", "Instrument", "Broker"],
        how="outer",
    )

    for col in ["Activity Date", "Expiry Date", "STO Date", "BTC Date"]:
        if col in merged.columns:
            merged[col] = pd.to_datetime(merged[col], errors="coerce")

    merged[["STO($)", "BTC($)", "STO Price", "BTC Price"]] = merged[
        ["STO($)", "BTC($)", "STO Price", "BTC Price"]
    ].fillna(0)

    merged["Activity Date"] = pd.to_datetime(
        merged[["STO Date", "BTC Date"]]
        .apply(
            lambda r: min([d for d in r if pd.notna(d)])
            if any(pd.notna(r)) else pd.NaT,
            axis=1,
        ),
        errors="coerce",
    )
    merged["Amount"]         = merged["STO($)"] + merged["BTC($)"]
    merged["Activity Month"] = merged["Activity Date"].dt.strftime("%Y-%m")
    merged["Expiry Month"]   = (
        pd.to_datetime(merged["Expiry Date"], errors="coerce").dt.strftime("%Y-%m")
    )
    merged["Quantity"]       = merged.apply(compute_qty, axis=1).round(0).astype(int)
    merged["Premium($)"]     = merged.apply(calc_premium, axis=1)
    merged                    = tag_transactions(merged)

    data = merged.copy()

    # ───────────────────────────────────────────────────────────────
    #  Premium header  (values independent of tax_rate)
    # ───────────────────────────────────────────────────────────────
    tot_prem  = data["Premium($)"].sum()
    yr        = datetime.now().year
    prev_yr   = yr - 1
    prem_ytd  = data[data["Activity Month"].str.startswith(str(yr))]["Premium($)"].sum()
    prem_prev = data[data["Activity Month"].str.startswith(str(prev_yr))]["Premium($)"].sum()
    yoy_pct   = ((prem_ytd - prem_prev) / prem_prev * 100) if prem_prev else 0

    # Top‑earning stock (by total premium)
    top_row   = (
        data.groupby("Instrument")["Premium($)"].sum().sort_values(ascending=False).head(1)
    )
    top_stock = top_row.index[0]
    top_value = top_row.iat[0]

    # Average premium per calendar month
    avg_prem_month = (
        data.groupby("Activity Month")["Premium($)"].sum().mean()
        if not data.empty
        else 0
    )

    

    label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
    #value_css = f"font-size:22px;margin-top:2px;text-align:center;"


    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;margin-top:2px;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>Total Premium</p>
                <p style='{value_css}'>${tot_prem:,.2f}</p>
            </div>
        """, unsafe_allow_html=True)


    with col2:
        value_color = "#2ECC40" if yoy_pct >= 0 else "#FF4136"
        label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;color:{value_color};font-weight:bold;margin-top:2px;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>Y-O-Y %</p>
                <p style='{value_css}'>{yoy_pct:,.2f}%</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        
        #label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;margin-top:2px;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>{yr} YTD Premium</p>
                <p style='{value_css}'>${prem_ytd:,.2f}</p>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        
        #label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;margin-top:2px;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>{prev_yr} Total Premium</p>
                <p style='{value_css}'>${prem_prev:,.2f}</p>
            </div>
        """, unsafe_allow_html=True)

    with col5:
        
        #label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;margin-top:2px;font-weight:bold;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>Top‑Earning Stock</p>
                <p style='{value_css}'>{top_stock}: ${top_value:,.2f}</p>
            </div>
        """, unsafe_allow_html=True)

    with col6:
        
        #label_css = "font-size:24px;font-weight:bold;margin-bottom:10px;margin-top:-40px;text-align:center;"
        value_css = f"font-size:22px;margin-top:2px;text-align:center;"
        st.markdown(f"""
            <div style='border:0.5px solid #0A57C1; border-radius:20px; padding:-5px 2px;'>
                <p style='{label_css}'>Avg Premium / Month</p>
                <p style='{value_css}'>${avg_prem_month:,.2f}</p>
            </div>
        """, unsafe_allow_html=True)

    # ───────────────────────────────────────────────────────────────
    #  Tax‑rate slider (immediately after header)
    # ───────────────────────────────────────────────────────────────
    txA, txSpacer, txB = st.columns([0.2, 0.2, 0.3])

    with txA:
        st.markdown(
            "<h2 style='font-size:28px;margin-top:40px;text-align:center;'>Net Premium</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='font-size:20px;margin-top:-10px;text-align:center;'>Use the slider to select your Tax Bracket</p>",
            unsafe_allow_html=True,
        )

    #with txB:
        tax_rate = st.select_slider(
            "",
            options=[0, 0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
            format_func=lambda x: f"{int(x*100)}%",
        )

    # now show the chosen rate in column 5
    with col5:
        placeholder_after_tax = st.empty()

   # ───────────────────────────────────────────────────────────────
   #  Update column 5 with Net Premium After Tax (using chosen rate)
   # ───────────────────────────────────────────────────────────────
    #net_after_tax_total = tot_prem * (1 - tax_rate)
    #placeholder_after_tax.markdown(
    #    f"**Net Premium After Tax ({int(tax_rate*100)}%)**<br>"
    #    f"${net_after_tax_total:,.2f}",
    #    unsafe_allow_html=True,
  #)

    # ───────────────────────────────────────────────────────────────
    #  Monthly Summary  (depends on tax_rate)
    # ───────────────────────────────────────────────────────────────
    if not data.empty:
        monthly = (
            data.groupby("Activity Month")["Premium($)"]
            .sum()
            .reset_index()
            .rename(columns={"Premium($)": "Net Premium"})
            .sort_values("Activity Month")
        )
        monthly["Net After Tax"] = monthly["Net Premium"] * (1 - tax_rate)

        grand = pd.DataFrame(
            {
                "Activity Month": ["Grand Total"],
                "Net Premium": [monthly["Net Premium"].sum()],
                "Net After Tax": [monthly["Net After Tax"].sum()],
            }
        )
        monthly = pd.concat([monthly, grand], ignore_index=True)
    else:
        monthly = pd.DataFrame()

    sumA, _, sumC = st.columns([0.3, 0.05, 0.65])

    with sumA:
        st.markdown(
            "<p style='font-size:28px;margin-bottom:5px;text-align:center;font-weight:bold;'>Monthly Summary</p>",
            unsafe_allow_html=True,
        )

        if not monthly.empty:
            styled = (
                monthly.style.format(
                    {"Net Premium": "${:,.2f}", "Net After Tax": "${:,.2f}"}
                )
                .set_properties(**{"font-size": "18px", "text-align": "center"})
                .apply(
                    lambda r: (
                        ["background-color:aliceblue;font-weight:bold;text-align:center"]
                        * len(r)
                        if r["Activity Month"] == "Grand Total"
                        else [""]
                        * len(r)
                    ),
                    axis=1,
                )
                .set_table_styles(
                    [
                        {
                            "selector": "thead th",
                            "props": [
                                ("background-color", "aliceblue"),
                                ("border", "1px solid #CCC"),
                                ("padding", "10px"),
                            ],
                        },
                        {
                            "selector": "tbody td",
                            "props": [
                                ("padding", "10px"),
                                ("border", "1px solid #CCC"),
                            ],
                        },
                        {
                            "selector": "table",
                            "props": [
                                ("width", "100%"),
                                ("margin", "0 auto"),
                                ("border-collapse", "collapse"),
                            ],
                        },
                    ]
                )
            )

            st.write(styled.to_html(), unsafe_allow_html=True)
            st.download_button(
                "Download Monthly Summary CSV",
                monthly.to_csv(index=False),
                "monthly_summary.csv",
                "text/csv",
            )
        else:
            st.write("No monthly summary to display.")

    # Monthly Net Premium bar chart
    def plot_monthly(mdf):
        import plotly.express as px

        dat = mdf[mdf["Activity Month"] != "Grand Total"]
        if dat.empty:
            return
        fig = px.bar(
            dat,
            x="Activity Month",
            y=["Net Premium", "Net After Tax"],
            labels={"value": "Net ($)", "Activity Month": "Month"},
            barmode="group",
            text_auto=".2s",
            height=600,
            width=900,
        )
        fig.update_layout(font=dict(size=12), legend=dict(font=dict(size=12)), xaxis_tickangle=-45)
        mn = min(dat["Net Premium"].min(), dat["Net After Tax"].min())
        mx = max(dat["Net Premium"].max(), dat["Net After Tax"].max())
        fig.update_yaxes(range=[mn * 1.2 if mn < 0 else 0, mx * 1.2])
        st.plotly_chart(fig, use_container_width=True)

    with sumC:
        st.markdown(
            "<p style='font-size:28px;margin-bottom:5px;text-align:center;font-weight:bold;'>Monthly Net Premium</p>",
            unsafe_allow_html=True,
        )
        if not monthly.empty:
            plot_monthly(monthly)

    # ─────────────────────────────────────────────────────────────────────
    # FILTERS
    # ─────────────────────────────────────────────────────────────────────
    if data.empty:
        st.warning("No data left after filters."); st.stop()

    selA, selB, selC, selD, selE, selF = st.columns(6)
    with selA:
        act_choice = st.selectbox("Activity Month", ["All"] + sorted(data["Activity Month"].dropna().unique(), reverse=True))
    with selB:
        exp_choice = st.selectbox("Expiry Month", ["All"] + sorted(data["Expiry Month"].dropna().unique(), reverse=True))
    with selC:
        brk_choice = st.selectbox("Broker", ["All"] + sorted(data["Broker"].unique()))
    with selD:
        inst_choice = st.selectbox("Instrument", ["All"] + sorted(data["Instrument"].unique()))
    with selE:
        stat_choice = st.selectbox("Status", ["All"] + sorted(data["Status"].unique()))
    with selF:
        type_choice = st.selectbox(
            "Type",
            ["All"] + sorted(str(x) for x in data["Option Type"].dropna().unique())
        )

    filt = data.copy()
    if act_choice != "All":
        filt = filt[filt["Activity Month"] == act_choice]
    if exp_choice != "All":
        filt = filt[filt["Expiry Month"] == exp_choice]
    if brk_choice != "All":
        filt = filt[filt["Broker"] == brk_choice]
    if inst_choice != "All":
        filt = filt[filt["Instrument"] == inst_choice]
    if stat_choice != "All":
        filt = filt[filt["Status"] == stat_choice]
    if type_choice != "All":
        filt = filt[filt["Option Type"] == type_choice]

    # ─────────────────────────────────────────────────────────────────────
    # PIE CHARTS (OPEN, CLOSED/EXPIRED, CALLS vs PUTS)
    # ─────────────────────────────────────────────────────────────────────
    def generate_pie_charts(filt):
        import plotly.express as px
        pc1, pc2, pc3 = st.columns(3)
        color_seq = ['#008CEE', '#000080', '#A80000', '#107C10',
                 '#094782', '#6495ED', '#5F9EA0', '#2E8B57']

        # 1) Open positions by Instrument
        with pc1:
            open_df = filt[filt["Status"] == "Open"]
            if not open_df.empty and open_df["Quantity"].sum() > 0:
                grp = open_df.groupby("Instrument")["Quantity"].sum().reset_index()
                import plotly.express as px
                fig1 = px.pie(
                    grp, names="Instrument", values="Quantity", hole=0.3,
                    title="Open Positions", color="Instrument",
                    color_discrete_sequence=color_seq[:len(grp)]
                )
                fig1.update_traces(textinfo="percent+label", textfont=dict(size=14))
                fig1.update_layout(
                    title_font_size=18,
                    legend=dict(font=dict(size=12), orientation="h", x=0.5, xanchor="center", y=-0.1),
                    margin=dict(l=10, r=10, t=60, b=40)
                )
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.write("No open positions for current filters.")

        # 2) Closed / Expired premium by Instrument
        with pc2:
            cx_df = filt[filt["Status"].isin(["Closed", "Expired"])]
            if not cx_df.empty:
                col_p = "Premium($)" if "Premium($)" in cx_df.columns else "Amount"
                agg_p = cx_df.groupby("Instrument")[col_p].sum().reset_index()
                if not agg_p.empty:
                    fig2 = px.pie(
                        agg_p, names="Instrument", values=col_p, hole=0.3,
                        title="Closed / Expired Premium",
                        color="Instrument", color_discrete_sequence=color_seq[:len(agg_p)]
                    )
                    fig2.update_traces(textinfo="percent+label", textfont=dict(size=14))
                    fig2.update_layout(
                        title_font_size=18,
                        legend=dict(font=dict(size=12), orientation="h", x=0.5, xanchor="center", y=-0.1),
                        margin=dict(l=10, r=10, t=60, b=40)
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.write("No closed / expired premium for current filters.")
            else:
                st.write("No closed / expired transactions for current filters.")

        # 3) Calls vs Puts
        with pc3:
            if "Option Type" in filt.columns:
                dist = filt["Option Type"].value_counts().reset_index()
                dist.columns = ["Option Type", "Count"]
                if not dist.empty and dist["Count"].sum() > 0:
                    fig3 = px.pie(
                        dist, names="Option Type", values="Count", hole=0.3,
                        title="Calls vs Puts Distribution",
                        color="Option Type", color_discrete_sequence=color_seq[:len(dist)]
                    )
                    fig3.update_traces(textinfo="percent+label", textfont=dict(size=14))
                    fig3.update_layout(
                        title_font_size=18,
                        legend=dict(font=dict(size=12), orientation="h", x=0.5, xanchor="center", y=-0.1),
                        margin=dict(l=10, r=10, t=60, b=40)
                    )
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.write("No option‑type data for current filters.")
            else:
                st.write("No 'Option Type' column found.")

    # ────  spacer row so column layout from pie‑charts ends cleanly  ────
    _ = st.columns(1)          #  << this single empty row fixes the jump

    # ────   EXCLUDE INSTRUMENTS (moved here, right above detailed table)  ────
    st.markdown("### Exclude Stocks")
    all_instr = sorted(filt["Instrument"].unique())
    if all_instr:
        ex_toggle = st.checkbox("Click here if you want to Exclude any stocks?")
        if ex_toggle:
            excl = st.multiselect("Select instruments to exclude", all_instr, [])
            if excl: filt = filt[~filt["Instrument"].isin(excl)]  

    # ─────────────────────────────────────────────────────────────────────
    # DETAILED TRANSACTIONS
    # ─────────────────────────────────────────────────────────────────────
    if not filt.empty and "Activity Date" in filt.columns:
        ddf = filt.copy()
        ddf["Collateral"] = ddf["Strike Price"] * ddf["Quantity"] * 100
        ddf.loc[ddf["Option Type"].str.lower() == "call", "Collateral"] = np.nan
        desired = [
            "Activity Date", "Instrument", "Option Type", "Quantity",
            "Strike Price", "Expiry Date", "STO($)", "BTC($)", "STO Price",
            "BTC Price", "STO Date", "BTC Date", "Status", "Premium($)",
            "Collateral", "Broker"
        ]
        dt = ddf[[c for c in desired if c in ddf.columns]].copy()
        for dc in ["Activity Date", "STO Date", "BTC Date", "Expiry Date"]:
            if dc in dt.columns:
                dt[dc] = pd.to_datetime(dt[dc], errors="coerce")
        dt = dt.sort_values("Activity Date", ascending=False)

        totals = dt[["STO($)", "BTC($)", "Premium($)", "Collateral"]].apply(
            lambda x: pd.to_numeric(x, errors="coerce")
        ).sum()
        total_row = {col: (totals[col] if col in totals else ("TOTAL" if col == "Instrument" else "")) for col in dt.columns}
        dt_total = pd.concat([dt, pd.DataFrame([total_row])], ignore_index=True)

        def highlight_total(r):
            return ["font-weight:bold"] * len(r) if str(r.get("Instrument", "")).upper() == "TOTAL" else [""] * len(r)

        numeric_cols = ["STO($)", "BTC($)", "Premium($)", "STO Price", "BTC Price", "Strike Price", "Collateral"]
        for n in numeric_cols:
            if n in dt_total.columns:
                dt_total[n] = pd.to_numeric(dt_total[n], errors="coerce").fillna(0.0)

        def fmt_date(v):
            return "" if pd.isna(v) else v.strftime("%Y-%m-%d") if isinstance(v, (pd.Timestamp, datetime, date)) else str(v)

        styled_tx = (
            dt_total.style.format(
                {
                    "STO($)": "${:,.2f}", "BTC($)": "${:,.2f}", "Premium($)": "${:,.2f}",
                    "STO Price": "${:,.2f}", "BTC Price": "${:,.2f}",
                    "Strike Price": "${:,.2f}", "Collateral": "${:,.2f}",
                    "Activity Date": fmt_date, "STO Date": fmt_date,
                    "BTC Date": fmt_date, "Expiry Date": fmt_date
                }
            )
            .set_properties(**{"font-size": "15px", "text-align": "center"})
            .apply(highlight_total, axis=1)
            .set_table_styles(
                [
                    {"selector": "thead th", "props": [("background-color", "aliceblue"), ("border", "1px solid #CCC"), ("padding", "10px")]},
                    {"selector": "tbody td", "props": [("padding", "10px"), ("border", "1px solid #CCC")]},
                    {"selector": "table", "props": [("width", "100%"), ("margin", "0 auto"), ("border-collapse", "collapse")]},
                ]
            )
        )

        st.session_state["full_transactions_df"] = data.copy()  # store full data for chat use

        if has_api_key:
            with st.expander("Pie Charts & Detailed Transactions", expanded=False):
                generate_pie_charts(filt)
                st.write(styled_tx.to_html(), unsafe_allow_html=True)
                st.download_button("Download Detailed Transactions", dt_total.to_csv(index=False), "detailed_transactions.csv", "text/csv")
        else:
            st.markdown("### Detailed Transactions")
            st.write(styled_tx.to_html(), unsafe_allow_html=True)
            st.download_button("Download Detailed Transactions", dt_total.to_csv(index=False), "detailed_transactions.csv", "text/csv")


    # GPT‑4 chat
    if has_api_key:
       run_gpt4_chat()
        # 🔁 Process selected quick prompt AFTER UI is rendered
       if st.session_state.get("trigger_quick_prompt", False):
          st.session_state["trigger_quick_prompt"] = False
          selected_prompt = st.session_state.get("selected_quick_prompt", "")
          if selected_prompt:
              process_query(prompt_override=selected_prompt)


else:
    cf_left, cf_center, cf_right = st.columns([0.2, 0.6, 0.2])
    with cf_center:
        st.markdown(
        """
        <div style="#background:linear-gradient(45deg,#f8fbff,#cce6ff,#f8fbff);
                    background-size:400% 400%;
                    animation:subtleColorfulGradient 15s ease infinite;
                    padding:20px;border-radius:10px;box-shadow:0 0px 8px rgba(0,0,0,0.1); text-align:center;">
            <p style="font-size:22px;margin:0;color:navy;animation:flash 1s infinite alternate;">
                Please upload one or more CSV/XLSX files to get started.
            </p>
        </div>
        <style>
        @keyframes subtleColorfulGradient {
            0% {background-position:0% 50%;}
            50% {background-position:100% 50%;}
            100% {background-position:0% 50%;}
        }
        @keyframes flash {
            0% {color:#1E90FF;}
            50% {color:navy;}
            100% {color:#1E90FF;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )