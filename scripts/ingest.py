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

import sys
import argparse
import textwrap
from pathlib import Path
from datetime import datetime

# ── Ajouter la racine du projet au path ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Importer depuis le module réutilisable
from core.knowledge.ingestor import (
    ingest_file, load_domains, get_stats, list_documents, SUPPORTED
)


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


# ─────────────────────────────────────────────────────────────────────────────
# Commandes CLI
# ─────────────────────────────────────────────────────────────────────────────

def list_domains_cli():
    domains = load_domains()
    print(f"\n{BOLD}Domaines disponibles ({len(domains)}) :{RESET}\n")
    for code, d in sorted(domains.items(), key=lambda x: x[1]["id"]):
        print(f"  {BLUE}{code:<30}{RESET} {d['label']}  (poids: {d['poids_strategique']})")
    print()


def show_stats():
    stats = get_stats()
    docs  = list_documents()

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}  BASE DE CONNAISSANCES ENTERPRISECORE{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")
    print(f"  Documents   : {GREEN}{stats['docs']}{RESET}")
    print(f"  Chunks      : {GREEN}{stats['chunks']}{RESET}")
    print(f"  Embeddings  : {GREEN}{stats['embeddings']}{RESET}")
    print(f"  Couverture  : {GREEN}{stats['coverage']}%{RESET} des chunks ont un embedding RAG")

    if docs:
        print(f"\n{BOLD}  Documents récents :{RESET}")
        for d in docs[:10]:
            date = str(d["created_at"])[:10]
            print(f"    [{date}] {d['title']} ({d['source_type']}) — {d['nb_chunks']} chunks")
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
        list_domains_cli()
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
        print(f"\n{BOLD}Fichier : {source.name}{RESET}")
        result = ingest_file(source, args.domaine, args.force)
        results.append(result)
        if result.get("skipped"):
            warn(result.get("error", "Ignoré"))
        else:
            ok(f"{result['file']} → {result['chunks']} chunks, {result['embeddings']} embeddings")

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
            print(f"\n{BOLD}{'─'*60}{RESET}")
            print(f"{BOLD}Fichier : {f.name}{RESET}")
            r = ingest_file(f, args.domaine, args.force)
            results.append(r)
            if r.get("skipped"):
                warn(r.get("error", "Ignoré"))
            else:
                ok(f"{r['file']} → {r['chunks']} chunks, {r['embeddings']} embeddings")
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
    print(f"  Vérifiez avec : python3 scripts/ingest.py --stats")
    print()


if __name__ == "__main__":
    main()
