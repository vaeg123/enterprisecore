"""
EnterpriseCore — Module d'ingestion de données (réutilisable)
=============================================================

Contient toutes les fonctions d'ingestion extraites de scripts/ingest.py.
Peut être importé depuis Python (Flask, API, etc.) sans passer par la CLI.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from database.db_config import get_connection

try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    _openai_client = None

# ── Paramètres ────────────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
EMBED_MODEL   = "text-embedding-3-small"
SUPPORTED     = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".csv"}


# ── Domaines ──────────────────────────────────────────────────

def load_domains() -> dict:
    """Retourne {code: {id, label, poids_strategique}} depuis la DB."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, code, label, poids_strategique FROM knowledge_domains WHERE actif=1")
    rows   = cursor.fetchall()
    cursor.close()
    conn.close()
    return {row["code"].upper(): row for row in rows}


def guess_domain(filename: str, content_preview: str) -> str | None:
    """Devine le domaine depuis le nom de fichier et le début du contenu."""
    text = (filename + " " + content_preview[:500]).lower()
    rules = [
        (["rgpd", "gdpr", "cnil", "données personnelles", "dpo", "consentement", "dpia"], "RGPD"),
        (["contrat", "clause", "accord", "convention", "avenant", "cession"], "CONTRATS"),
        (["droit social", "travail", "salarié", "licenciement", "convention collective"], "SOCIAL"),
        (["fiscal", "impôt", "tva", "is ", "cfe", "cvae", "taxe"], "FISCAL"),
        (["bilan", "compte de résultat", "trésorerie", "cash", "ebitda"], "FINANCE"),
        (["budget", "prévisionnel", "contrôle de gestion", "écart", "reporting"], "COMPTABILITE"),
        (["brevet", "marque", "propriété intellectuelle", "copyright", "licence"], "PI"),
        (["rh", "recrutement", "formation", "paie", "fiche de poste"], "RH"),
        (["qualité", "iso", "certification", "audit", "non-conformité"], "QUALITE"),
        (["stratégie", "plan stratégique", "vision", "gouvernance", "comité"], "STRATEGIE"),
        (["commercial", "prospect", "client", "crm", "pipeline", "vente"], "COMMERCIAL"),
        (["marketing", "communication", "campagne", "seo", "social media"], "MARKETING"),
        (["numérique", "ia ", "intelligence artificielle", "cybersécurité"], "NUMERIQUE_IA"),
        (["contentieux", "procédure", "tribunal", "assignation", "litige"], "CONTENTIEUX"),
        (["assemblée", "statuts", "actionnaire", "capital", "ag ", "sas", "sarl"], "SOCIETES"),
    ]
    domains = load_domains()
    for keywords, code in rules:
        if any(kw in text for kw in keywords) and code in domains:
            return code
    return None


# ── Extraction texte ──────────────────────────────────────────

def extract_txt(path: Path) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def extract_pdf(path: Path) -> str:
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        return ""


def extract_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return ""


def extract_md(path: Path) -> str:
    text = extract_txt(path)
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text


def extract_csv(path: Path) -> str:
    import csv
    rows = []
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(" | ".join(row))
        return "\n".join(rows)
    except Exception:
        return ""


def extract_text(path: Path) -> str:
    """Extrait le texte depuis n'importe quel format supporté."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in (".docx", ".doc"):
        return extract_docx(path)
    elif ext in (".md", ".markdown"):
        return extract_md(path)
    elif ext == ".csv":
        return extract_csv(path)
    else:
        return extract_txt(path)


# ── Découpage en chunks ───────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    text   = clean_text(text)
    chunks = []
    start  = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        for sep in (".\n", ". ", "\n\n", "\n"):
            pos = text.rfind(sep, start + chunk_size // 2, end)
            if pos != -1:
                end = pos + len(sep)
                break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return [c for c in chunks if len(c) > 50]


# ── Embeddings ────────────────────────────────────────────────

def generate_embedding(text: str) -> list[float] | None:
    if not _openai_client:
        return None
    try:
        resp = _openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=text[:8000],
        )
        return resp.data[0].embedding
    except Exception:
        return None


# ── Persistance en base ───────────────────────────────────────

def get_or_create_document(conn, domain_id: int, title: str,
                           file_path: str, source_type: str) -> tuple:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM knowledge_documents WHERE file_path=%s", (file_path,))
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        return existing["id"], True
    cursor.execute(
        "INSERT INTO knowledge_documents (domain_id, title, file_path, source_type, actif) "
        "VALUES (%s, %s, %s, %s, 1)",
        (domain_id, title, file_path, source_type)
    )
    doc_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return doc_id, False


def save_chunk(conn, doc_id: int, content: str, idx: int) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO knowledge_chunks (document_id, content, chunk_index) VALUES (%s, %s, %s)",
        (doc_id, content, idx)
    )
    chunk_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return chunk_id


def save_embedding(conn, chunk_id: int, embedding: list[float]) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO knowledge_embeddings (chunk_id, embedding) VALUES (%s, %s)",
        (chunk_id, json.dumps(embedding))
    )
    conn.commit()
    cursor.close()


def delete_chunks_for_document(conn, doc_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "DELETE ke FROM knowledge_embeddings ke "
        "JOIN knowledge_chunks kc ON ke.chunk_id = kc.id "
        "WHERE kc.document_id = %s",
        (doc_id,)
    )
    cursor.execute("DELETE FROM knowledge_chunks WHERE document_id = %s", (doc_id,))
    conn.commit()
    cursor.close()


def delete_document(doc_id: int) -> None:
    """Supprime un document, ses chunks et ses embeddings."""
    conn = get_connection()
    delete_chunks_for_document(conn, doc_id)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_documents WHERE id=%s", (doc_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ── Ingestion principale ──────────────────────────────────────

def ingest_file(path: Path, domain_code: str | None = None,
                force: bool = False) -> dict:
    """
    Ingère un fichier dans la base de connaissances.
    Retourne un dict {file, domain, chunks, embeddings, doc_id, skipped, error}.
    """
    if path.suffix.lower() not in SUPPORTED:
        return {"skipped": True, "error": f"Format non supporté : {path.suffix}"}

    # 1. Extraction du texte
    text = extract_text(path)
    if not text or len(text) < 100:
        return {"skipped": True, "error": "Fichier vide ou illisible"}

    # 2. Domaine
    if not domain_code:
        domain_code = guess_domain(path.name, text)
    if not domain_code:
        return {"skipped": True, "error": "Domaine non déterminable — précisez domain_code"}

    domains = load_domains()
    if domain_code.upper() not in domains:
        return {"skipped": True, "error": f"Domaine inconnu : {domain_code}"}

    domain    = domains[domain_code.upper()]
    domain_id = domain["id"]

    # 3. Document en DB
    conn        = get_connection()
    file_path   = str(path.resolve())
    title       = path.stem.replace("_", " ").replace("-", " ").title()
    source_type = path.suffix.lstrip(".").upper()

    doc_id, already_exists = get_or_create_document(conn, domain_id, title, file_path, source_type)

    if already_exists:
        if not force:
            conn.close()
            return {"skipped": True, "already_exists": True,
                    "error": "Document déjà importé. Utilisez force=True pour ré-importer."}
        else:
            delete_chunks_for_document(conn, doc_id)

    # 4. Chunks
    chunks = chunk_text(text)

    # 5. Sauvegarde + embeddings
    embedded = 0
    for i, chunk in enumerate(chunks, 1):
        chunk_id  = save_chunk(conn, doc_id, chunk, i)
        embedding = generate_embedding(chunk)
        if embedding:
            save_embedding(conn, chunk_id, embedding)
            embedded += 1

    conn.close()

    return {
        "file":       path.name,
        "domain":     domain_code.upper(),
        "chunks":     len(chunks),
        "embeddings": embedded,
        "doc_id":     doc_id,
        "skipped":    False,
    }


def ingest_bytes(filename: str, file_bytes: bytes, domain_code: str | None = None,
                 force: bool = False) -> dict:
    """
    Ingère un fichier fourni en bytes (depuis un upload HTTP).
    Écrit dans un fichier temporaire, puis appelle ingest_file.
    """
    import tempfile
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        return {"skipped": True, "error": f"Format non supporté : {suffix}"}

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = ingest_file(tmp_path, domain_code, force)
        # Corriger le nom de fichier dans le résultat
        result["file"] = filename
        # Mettre à jour le titre dans la DB si non ignoré
        if not result.get("skipped") and result.get("doc_id"):
            title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
            conn   = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE knowledge_documents SET title=%s, file_path=%s WHERE id=%s",
                (title, filename, result["doc_id"])
            )
            conn.commit()
            cursor.close()
            conn.close()
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Statistiques ──────────────────────────────────────────────

def get_stats() -> dict:
    """Retourne les statistiques de la base de connaissances."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_documents WHERE actif=1")
    nb_docs = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_chunks")
    nb_chunks = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_embeddings")
    nb_emb = cursor.fetchone()["n"]

    cursor.close()
    conn.close()

    embed_pct = int(nb_emb / max(nb_chunks, 1) * 100)
    return {
        "docs":       nb_docs,
        "chunks":     nb_chunks,
        "embeddings": nb_emb,
        "coverage":   embed_pct,
    }


def list_documents() -> list:
    """Retourne la liste des documents avec leurs stats."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT kdoc.id, kdoc.title, kdoc.source_type, kdoc.created_at,
               kd.code AS domain_code, kd.label AS domain_label,
               COUNT(kc.id) AS nb_chunks
        FROM knowledge_documents kdoc
        LEFT JOIN knowledge_domains kd ON kdoc.domain_id = kd.id
        LEFT JOIN knowledge_chunks kc  ON kc.document_id = kdoc.id
        WHERE kdoc.actif = 1
        GROUP BY kdoc.id
        ORDER BY kdoc.created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r["created_at"] = str(r["created_at"])
    return rows
