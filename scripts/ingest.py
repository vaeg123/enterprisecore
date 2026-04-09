#!/usr/bin/env python3
"""
EnterpriseCore — Script d'ingestion de données entreprise
==========================================================

Importe vos fichiers (PDF, Word, TXT, Markdown) dans la base de connaissances
et génère automatiquement les embeddings pour la recherche sémantique (RAG).

USAGE :
    # Importer un seul fichier
    python3 scripts/ingest.py fichier.pdf

    # Importer un dossier entier
    python3 scripts/ingest.py /chemin/vers/dossier/

    # Choisir le domaine manuellement
    python3 scripts/ingest.py rapport.pdf --domaine RGPD

    # Lister les domaines disponibles
    python3 scripts/ingest.py --liste-domaines

    # Voir l'état de la base de connaissances
    python3 scripts/ingest.py --stats

FORMATS SUPPORTÉS : .pdf · .docx · .doc · .txt · .md · .csv
"""

import os
import sys
import json
import argparse
import textwrap
import re
from pathlib import Path
from datetime import datetime

# ── Ajouter la racine du projet au path ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from database.db_config import get_connection

try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    _openai_client = None


# ─────────────────────────────────────────────────────────────────────────────
# Paramètres
# ─────────────────────────────────────────────────────────────────────────────

CHUNK_SIZE    = 800    # caractères par chunk
CHUNK_OVERLAP = 150    # chevauchement entre chunks pour ne pas perdre le contexte
EMBED_MODEL   = "text-embedding-3-small"

# Extensions supportées
SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".csv"}

# Domaines disponibles (code → label)
DOMAINS_CACHE: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# Couleurs terminal
# ─────────────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}✅ {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}⚠️  {msg}{RESET}")
def err(msg):   print(f"{RED}❌ {msg}{RESET}")
def info(msg):  print(f"{BLUE}ℹ️  {msg}{RESET}")
def step(msg):  print(f"{BOLD}   {msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Lecture des domaines
# ─────────────────────────────────────────────────────────────────────────────

def load_domains() -> dict:
    """Retourne {code: (id, label, poids)} depuis la DB."""
    global DOMAINS_CACHE
    if DOMAINS_CACHE:
        return DOMAINS_CACHE
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, code, label, poids_strategique FROM knowledge_domains WHERE actif=1")
    for row in cursor.fetchall():
        DOMAINS_CACHE[row["code"].upper()] = row
    cursor.close()
    conn.close()
    return DOMAINS_CACHE


def list_domains():
    """Affiche la liste des domaines disponibles."""
    domains = load_domains()
    print(f"\n{BOLD}Domaines disponibles ({len(domains)}) :{RESET}\n")
    for code, d in sorted(domains.items(), key=lambda x: x[1]["id"]):
        print(f"  {BLUE}{code:<30}{RESET} {d['label']}  (poids: {d['poids_strategique']})")
    print()


def guess_domain(filename: str, content_preview: str) -> str | None:
    """Devine le domaine à partir du nom de fichier et du contenu."""
    text = (filename + " " + content_preview[:500]).lower()

    rules = [
        (["rgpd", "gdpr", "cnil", "données personnelles", "dpo", "consentement", "dpia", "aipd"], "RGPD"),
        (["contrat", "clause", "accord", "convention", "avenant", "cession"], "CONTRATS"),
        (["droit social", "travail", "salarié", "licenciement", "contrat de travail", "convention collective"], "SOCIAL"),
        (["fiscal", "impôt", "tva", "is ", "cfe", "cvae", "taxe"], "FISCAL"),
        (["bilan", "compte de résultat", "trésorerie", "cash", "ebita", "ebitda"], "FINANCE"),
        (["budget", "prévisionnel", "contrôle de gestion", "écart", "reporting"], "COMPTABILITE"),
        (["brevet", "marque", "propriété intellectuelle", "copyright", "licence"], "PI"),
        (["rh", "recrutement", "formation", "paie", "fiche de poste", "entretien annuel"], "RH"),
        (["qualité", "iso", "certification", "audit", "non-conformité", "procédure"], "QUALITE"),
        (["stratégie", "plan stratégique", "vision", "mission", "gouvernance", "comité"], "STRATEGIE"),
        (["commercial", "prospect", "client", "crm", "pipeline", "vente"], "COMMERCIAL"),
        (["marketing", "communication", "marque", "campagne", "seo", "social media"], "MARKETING"),
        (["numérique", "ia ", "intelligence artificielle", "données", "cybersécurité", "logiciel"], "NUMERIQUE_IA"),
        (["contentieux", "procédure", "tribunal", "assignation", "litige"], "CONTENTIEUX"),
        (["assemblée", "statuts", "actionnaire", "capital", "ag ", "sas", "sarl", "sas"], "SOCIETES"),
    ]

    for keywords, code in rules:
        if any(kw in text for kw in keywords):
            domains = load_domains()
            if code in domains:
                return code

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Extraction de texte
# ─────────────────────────────────────────────────────────────────────────────

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
        err(f"Erreur PDF {path.name} : {e}")
        return ""


def extract_docx(path: Path) -> str:
    try:
        import docx
        doc  = docx.Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        err(f"Erreur DOCX {path.name} : {e}")
        return ""


def extract_md(path: Path) -> str:
    text = extract_txt(path)
    # Retirer les balises Markdown pour ne garder que le texte
    text = re.sub(r"#{1,6}\s+", "", text)          # titres
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)  # gras/italique
    text = re.sub(r"`[^`]+`", "", text)             # code inline
    text = re.sub(r"```[\s\S]*?```", "", text)      # blocs code
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # liens
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
    except Exception as e:
        err(f"Erreur CSV {path.name} : {e}")
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
    else:  # .txt et autres
        return extract_txt(path)


# ─────────────────────────────────────────────────────────────────────────────
# Découpage en chunks
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Nettoie le texte brut extrait."""
    text = re.sub(r"\n{3,}", "\n\n", text)   # max 2 sauts de ligne
    text = re.sub(r" {2,}", " ", text)        # espaces multiples
    text = text.strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Découpe le texte en chunks avec chevauchement.
    Découpe de préférence sur des fins de phrases.
    """
    text   = clean_text(text)
    chunks = []
    start  = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Chercher une fin de phrase proche
        for sep in (".\n", ". ", "\n\n", "\n"):
            pos = text.rfind(sep, start + chunk_size // 2, end)
            if pos != -1:
                end = pos + len(sep)
                break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return [c for c in chunks if len(c) > 50]  # ignorer les chunks trop courts


# ─────────────────────────────────────────────────────────────────────────────
# Génération d'embeddings
# ─────────────────────────────────────────────────────────────────────────────

def generate_embedding(text: str) -> list[float] | None:
    """Génère un embedding via OpenAI text-embedding-3-small."""
    if not _openai_client:
        warn("OPENAI_API_KEY absent — embeddings ignorés (recherche RAG désactivée pour ce document)")
        return None
    try:
        resp = _openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=text[:8000],   # limite du modèle
        )
        return resp.data[0].embedding
    except Exception as e:
        warn(f"Embedding échoué : {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Persistance en base
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_document(conn, domain_id: int, title: str, file_path: str, source_type: str) -> int:
    """Retourne l'id du document (le crée si inexistant)."""
    cursor = conn.cursor(dictionary=True)

    # Vérifier si un document avec ce file_path existe déjà
    cursor.execute(
        "SELECT id FROM knowledge_documents WHERE file_path=%s",
        (file_path,)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        return existing["id"], True   # (id, already_exists)

    cursor.execute(
        """INSERT INTO knowledge_documents (domain_id, title, file_path, source_type, actif)
           VALUES (%s, %s, %s, %s, 1)""",
        (domain_id, title, file_path, source_type)
    )
    doc_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return doc_id, False


def save_chunk(conn, doc_id: int, content: str, idx: int) -> int:
    """Sauvegarde un chunk et retourne son id."""
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
    """Sauvegarde l'embedding d'un chunk."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO knowledge_embeddings (chunk_id, embedding) VALUES (%s, %s)",
        (chunk_id, json.dumps(embedding))
    )
    conn.commit()
    cursor.close()


def delete_chunks_for_document(conn, doc_id: int) -> None:
    """Supprime les chunks et embeddings existants d'un document (avant ré-import)."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion d'un fichier
# ─────────────────────────────────────────────────────────────────────────────

def ingest_file(path: Path, domain_code: str | None = None, force: bool = False) -> dict:
    """
    Ingère un fichier dans la base de connaissances.
    Retourne un dict avec les statistiques.
    """
    if path.suffix.lower() not in SUPPORTED:
        warn(f"Format non supporté : {path.suffix} ({path.name})")
        return {"skipped": True}

    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}Fichier  : {path.name}{RESET}")

    # 1. Extraction du texte
    step("Extraction du texte...")
    text = extract_text(path)
    if not text or len(text) < 100:
        warn(f"Fichier vide ou illisible : {path.name}")
        return {"skipped": True}

    print(f"   Texte extrait : {len(text):,} caractères")

    # 2. Détermination du domaine
    if not domain_code:
        domain_code = guess_domain(path.name, text)
        if domain_code:
            info(f"Domaine détecté automatiquement : {domain_code}")
        else:
            # Demander interactivement
            list_domains()
            domain_code = input("   Quel domaine pour ce fichier ? (code) : ").strip().upper()

    domains = load_domains()
    if domain_code.upper() not in domains:
        err(f"Domaine inconnu : {domain_code}")
        print("   Utilisez --liste-domaines pour voir les codes disponibles.")
        return {"skipped": True}

    domain     = domains[domain_code.upper()]
    domain_id  = domain["id"]
    print(f"   Domaine : {domain['label']} ({domain_code})")

    # 3. Création/récupération du document en DB
    conn        = get_connection()
    file_path   = str(path.resolve())
    title       = path.stem.replace("_", " ").replace("-", " ").title()
    source_type = path.suffix.lstrip(".").upper()

    doc_id, already_exists = get_or_create_document(conn, domain_id, title, file_path, source_type)

    if already_exists:
        if not force:
            warn(f"Document déjà importé (ID {doc_id}). Utilisez --force pour ré-importer.")
            conn.close()
            return {"skipped": True, "already_exists": True}
        else:
            step("Suppression des anciens chunks...")
            delete_chunks_for_document(conn, doc_id)
            info("Anciens chunks supprimés — ré-import en cours")

    # 4. Découpage en chunks
    step("Découpage en chunks...")
    chunks = chunk_text(text)
    print(f"   {len(chunks)} chunks créés (taille ≈ {CHUNK_SIZE} car, chevauchement {CHUNK_OVERLAP})")

    # 5. Sauvegarde + embeddings
    step("Génération des embeddings et sauvegarde...")
    embedded = 0
    for i, chunk in enumerate(chunks, 1):
        chunk_id  = save_chunk(conn, doc_id, chunk, i)
        embedding = generate_embedding(chunk)
        if embedding:
            save_embedding(conn, chunk_id, embedding)
            embedded += 1
        # Barre de progression simple
        print(f"   [{i:>3}/{len(chunks)}] chunk sauvegardé{'  + embedding' if embedding else ''}", end="\r")

    print()
    conn.close()

    ok(f"{path.name} importé → {len(chunks)} chunks, {embedded} embeddings")
    return {
        "file": path.name,
        "domain": domain_code,
        "chunks": len(chunks),
        "embeddings": embedded,
        "doc_id": doc_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Statistiques
# ─────────────────────────────────────────────────────────────────────────────

def show_stats():
    """Affiche l'état actuel de la base de connaissances."""
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_documents WHERE actif=1")
    nb_docs = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_chunks")
    nb_chunks = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM knowledge_embeddings")
    nb_emb = cursor.fetchone()["n"]

    cursor.execute("""
        SELECT kd.label, COUNT(DISTINCT kdoc.id) AS docs, COUNT(kc.id) AS chunks
        FROM knowledge_domains kd
        LEFT JOIN knowledge_documents kdoc ON kdoc.domain_id = kd.id AND kdoc.actif=1
        LEFT JOIN knowledge_chunks kc ON kc.document_id = kdoc.id
        GROUP BY kd.id, kd.label
        HAVING docs > 0
        ORDER BY chunks DESC
    """)
    by_domain = cursor.fetchall()

    cursor.execute("""
        SELECT title, source_type, created_at
        FROM knowledge_documents
        WHERE actif=1
        ORDER BY created_at DESC
        LIMIT 10
    """)
    recent_docs = cursor.fetchall()

    cursor.close()
    conn.close()

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}  BASE DE CONNAISSANCES ENTERPRISECORE{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")
    print(f"  Documents   : {GREEN}{nb_docs}{RESET}")
    print(f"  Chunks      : {GREEN}{nb_chunks}{RESET}")
    print(f"  Embeddings  : {GREEN}{nb_emb}{RESET}")
    embed_pct = int(nb_emb / max(nb_chunks, 1) * 100)
    print(f"  Couverture  : {GREEN}{embed_pct}%{RESET} des chunks ont un embedding RAG")

    if by_domain:
        print(f"\n{BOLD}  Par domaine :{RESET}")
        for d in by_domain:
            print(f"    {d['label']:<40} {d['docs']} doc(s)  {d['chunks']} chunk(s)")

    if recent_docs:
        print(f"\n{BOLD}  Documents récents :{RESET}")
        for d in recent_docs:
            date = str(d["created_at"])[:10]
            print(f"    [{date}] {d['title']} ({d['source_type']})")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Importer des données entreprise dans EnterpriseCore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exemples :
              python3 scripts/ingest.py contrat_fournisseur.pdf
              python3 scripts/ingest.py /Documents/Juridique/ --domaine CONTRATS
              python3 scripts/ingest.py politique_rgpd.pdf --domaine RGPD --force
              python3 scripts/ingest.py --liste-domaines
              python3 scripts/ingest.py --stats
        """)
    )
    parser.add_argument("source", nargs="?", help="Fichier ou dossier à importer")
    parser.add_argument("--domaine",        help="Code du domaine (ex: RGPD, CONTRATS, FINANCE)")
    parser.add_argument("--force",          action="store_true", help="Ré-importer si déjà présent")
    parser.add_argument("--liste-domaines", action="store_true", help="Lister les domaines disponibles")
    parser.add_argument("--stats",          action="store_true", help="Afficher l'état de la base")
    args = parser.parse_args()

    if args.liste_domaines:
        list_domains()
        return

    if args.stats:
        show_stats()
        return

    if not args.source:
        parser.print_help()
        return

    source = Path(args.source)
    if not source.exists():
        err(f"Chemin introuvable : {source}")
        sys.exit(1)

    results = []
    start   = datetime.now()

    if source.is_file():
        result = ingest_file(source, args.domaine, args.force)
        results.append(result)

    elif source.is_dir():
        files = sorted([
            f for f in source.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED
        ])
        if not files:
            warn(f"Aucun fichier supporté trouvé dans {source}")
            sys.exit(1)
        info(f"{len(files)} fichier(s) trouvé(s) dans {source}")
        for f in files:
            r = ingest_file(f, args.domaine, args.force)
            results.append(r)
    else:
        err(f"Source invalide : {source}")
        sys.exit(1)

    # Résumé final
    elapsed = (datetime.now() - start).total_seconds()
    done    = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}  RÉSUMÉ{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")
    print(f"  Importés  : {GREEN}{len(done)}{RESET}")
    print(f"  Ignorés   : {YELLOW}{len(skipped)}{RESET}")
    print(f"  Durée     : {elapsed:.1f}s")
    if done:
        total_chunks = sum(r.get("chunks", 0) for r in done)
        total_emb    = sum(r.get("embeddings", 0) for r in done)
        print(f"  Chunks    : {total_chunks}")
        print(f"  Embeddings: {total_emb}")
    print()
    print(f"  Les agents peuvent maintenant utiliser ces données dans leurs analyses.")
    print(f"  Vérifiez avec : python3 scripts/ingest.py --stats")
    print()


if __name__ == "__main__":
    main()
