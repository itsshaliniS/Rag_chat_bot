import os
import uuid
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
import re

import config
from services import document_processor, gemini_client, vector_store, auth, chat_store

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE_BYTES
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.DB_FOLDER, exist_ok=True)

GREETING_PATTERN = re.compile(
    r"^(hi+|hello+|hey+|hola|yo|howdy|greetings|good\s+(morning|afternoon|evening|night))[\s!.,]*$",
    re.IGNORECASE,
)


def is_greeting(text):
    return bool(GREETING_PATTERN.match(text.strip()))


def get_owner_id():
    return session.get("username", "guest")


def get_current_session_id():
    owner_id = get_owner_id()
    session_id = session.get("current_session_id")

    if not session_id or chat_store.get_session(owner_id, session_id) is None:
        session_id = chat_store.create_session(owner_id)
        session["current_session_id"] = session_id

    return session_id


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def extract_used_sources(raw_answer, sources):
    if "USED_SOURCES:" not in raw_answer:
        return raw_answer.strip(), sources

    answer_part, _, used_part = raw_answer.partition("USED_SOURCES:")
    answer = answer_part.strip()
    used_part = used_part.strip().lower()

    if used_part == "none":
        return answer, []

    # parse source numbers with standard loop
    used_numbers = set()
    for n in used_part.split(","):
        val = n.strip()
        if val.isdigit():
            used_numbers.add(int(val))

    # filter with standard loop
    filtered = []
    for idx, s in enumerate(sources, start=1):
        if idx in used_numbers:
            filtered.append(s)

    return answer, filtered



@app.route("/")
def index():
    if not session.get("username"):
        return redirect(url_for("login"))

    owner_id = get_owner_id()
    current_session_id = get_current_session_id()
    current_messages = chat_store.get_session(owner_id, current_session_id) or []
    history_list = chat_store.list_sessions(owner_id)
    documents = vector_store.list_user_documents(owner_id)

    return render_template(
        "index.html",
        username=session.get("username"),
        current_messages=current_messages,
        history_list=history_list,
        current_session_id=current_session_id,
        documents=documents,
    )


@app.route("/history/new", methods=["POST"])
def new_chat():
    if not session.get("username"):
        return redirect(url_for("login"))
    owner_id = get_owner_id()
    session["current_session_id"] = chat_store.create_session(owner_id)
    return redirect(url_for("index"))


@app.route("/history/<session_id>/open")
def open_chat(session_id):
    if not session.get("username"):
        return redirect(url_for("login"))
    owner_id = get_owner_id()
    if chat_store.get_session(owner_id, session_id) is not None:
        session["current_session_id"] = session_id
    return redirect(url_for("index"))



@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"):
        return redirect(url_for("index"))

    if request.method == "GET":
        return render_template("login.html", error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    print(f"login request received for username: '{username}'")


    if auth.verify_login(username, password):
        session["username"] = username
        return redirect(url_for("index"))

    return render_template("login.html", error="Invalid username or password.")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("username"):
        return redirect(url_for("index"))

    if request.method == "GET":
        return render_template("signup.html", error=None)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    success, error = auth.create_user(username, password, name, email)

    if not success:
        return render_template("signup.html", error=error)

    session["username"] = username
    return redirect(url_for("index"))



@app.route("/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    if request.is_json:
        return jsonify({"message": "Logged out."})
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/upload", methods=["POST"])
@auth.login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file was sent."}), 400

    file = request.files["file"]
    print("Received upload request for file:", file.filename)


    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and TXT files are allowed."}), 400

    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    file_path = os.path.join(config.UPLOAD_FOLDER, filename)
    file.save(file_path)

    try:
        raw_text = document_processor.extract_text(file_path, extension)
        cleaned = document_processor.clean_text(raw_text)

        if not cleaned:
            return jsonify({"error": "This document appears to be empty."}), 400

        chunks = document_processor.chunk_text(cleaned, filename)

        embeddings = []
        for chunk in chunks:
            try:
                embeddings.append(gemini_client.embed_text(chunk["text"]))
            except Exception:
                return jsonify({"error": "Failed to generate embeddings. Check your API key."}), 500

        username = session.get("username")
        # delete old chunks of this file if re-uploading to avoid duplicates
        vector_store.delete_document(username, filename)
        vector_store.add_chunks(chunks, embeddings, username)


        return jsonify({
            "message": f"'{filename}' processed successfully.",
            "chunks_created": len(chunks),
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Something went wrong while processing this document."}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.route("/documents", methods=["GET"])
@auth.login_required
def get_documents():
    username = session.get("username")
    docs = vector_store.list_user_documents(username)
    return jsonify({"documents": docs})


@app.route("/documents/<path:filename>", methods=["DELETE"])
@auth.login_required
def delete_document(filename):
    username = session.get("username")
    vector_store.delete_document(username, filename)
    return jsonify({"message": f"Document '{filename}' deleted successfully."})



@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("username"):
        return jsonify({"error": "Please log in first."}), 401

    data = request.get_json()
    question = (data or {}).get("message", "").strip()
    print(f"received user message: '{question}'")


    if not question:
        return jsonify({"error": "Please type a question."}), 400

    owner_id = get_owner_id()
    session_id = get_current_session_id()

    if is_greeting(question):
        if vector_store.has_documents(owner_id):
            answer = "Hi there! Ask me anything about your uploaded document."
        else:
            answer = "Hello! Upload a PDF or TXT using the paperclip icon, then ask me anything about it."

        timestamp = datetime.now().strftime("%H:%M")
        chat_store.append_message(owner_id, session_id, "user", question, timestamp)
        chat_store.append_message(owner_id, session_id, "assistant", answer, timestamp)
        return jsonify({"answer": answer, "sources": [], "timestamp": timestamp})

    if not vector_store.has_documents(owner_id):
        return jsonify({"error": "Please upload a document first."}), 400

    try:
        query_embedding = gemini_client.embed_text(question, task_type="RETRIEVAL_QUERY")
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Could not generate an embedding for your question."}), 500

    sources = vector_store.query(query_embedding, username=owner_id, top_k=config.TOP_K_RESULTS)

    if not sources:
        answer = "I couldn't find this information in the uploaded document."
    else:
        # combine the retrieved chunk texts into a single context block for gemini
        context = "\n\n".join(
            f"[Source {i+1}] ({s['filename']}, chunk {s['chunk_number']})\n{s['text']}"
            for i, s in enumerate(sources)
        )

        # get last 4 messages from session to build chat memory history
        current_messages = chat_store.get_session(owner_id, session_id) or []
        history_context = ""
        for msg in current_messages[-4:]:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_context += f"{role_label}: {msg['text']}\n"


        prompt = (
            "You are a helpful assistant.\n"
            "Answer ONLY from the provided context.\n"
            "Do not use any markdown formatting (such as bold asterisks **, bullet lists, or headers). "
            "Respond in simple, clear, conversational plain text. "
            "If the answer is unavailable in the context, reply exactly: "
            "\"I couldn't find this information in the uploaded document.\"\n\n"
            f"Conversation History:\n{history_context}\n"
            f"Context:\n{context}\n\n"
            f"Question:\n{question}\n\n"
            "After your answer, add a new line starting with 'USED_SOURCES:' "
            "followed by the numbers of the sources you actually used, "
            "comma separated (e.g. USED_SOURCES: 1,3). "
            "If you used none, write USED_SOURCES: none"
        )

        try:
            raw_answer = gemini_client.generate_answer(prompt)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 429
        except Exception as e:
            print("GEMINI ERROR:", repr(e))
            return jsonify({"error": "Gemini failed to generate an answer. Try again."}), 500

        answer, sources = extract_used_sources(raw_answer, sources)

    timestamp = datetime.now().strftime("%H:%M")

    chat_store.append_message(owner_id, session_id, "user", question, timestamp)
    chat_store.append_message(owner_id, session_id, "assistant", answer, timestamp, sources)

    return jsonify({
        "answer": answer,
        "sources": sources,
        "timestamp": timestamp,
    })



if __name__ == "__main__":
    app.run(debug=True)