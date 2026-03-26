from collections import Counter


class ConfidenceScorer:
    """
    Calcule un score de confiance multi-facteurs à partir des résultats du débat.

    Facteurs (pondérés) :
      40% — Consensus agents : tous d'accord → confiance max
      25% — Confiance moyenne déclarée par les agents
      20% — Richesse juridique : nombre d'articles distincts cités
      15% — Taux de parsing réussi (agents ayant retourné un JSON valide)
    """

    RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def compute(self, agents_results: list) -> dict:
        valid = [
            r for r in agents_results
            if r["analysis"].get("risk_level", "UNKNOWN") != "UNKNOWN"
        ]

        if not valid:
            return {"score": 0.0, "details": {"reason": "aucun agent n'a produit d'analyse valide"}}

        # ── Facteur 1 : consensus sur le niveau de risque ──────────────
        levels = [r["analysis"]["risk_level"] for r in valid]
        counts = Counter(levels)
        dominant_count = counts.most_common(1)[0][1]
        consensus = dominant_count / len(levels)          # 1.0 si unanimité

        # ── Facteur 2 : confiance moyenne déclarée ─────────────────────
        declared_confidences = [
            float(r["analysis"].get("confidence", 0.5))
            for r in valid
        ]
        avg_declared = sum(declared_confidences) / len(declared_confidences)

        # ── Facteur 3 : richesse juridique (articles cités) ────────────
        all_articles = []
        for r in valid:
            all_articles.extend(r["analysis"].get("articles_referenced", []))
        unique_articles = len(set(all_articles))
        article_score = min(1.0, unique_articles / 6)     # max score à 6 articles distincts

        # ── Facteur 4 : taux de parsing réussi ────────────────────────
        parse_rate = len(valid) / len(agents_results)

        # ── Score final pondéré ───────────────────────────────────────
        final = (
            consensus      * 0.40 +
            avg_declared   * 0.25 +
            article_score  * 0.20 +
            parse_rate     * 0.15
        )

        # ── Niveau de divergence ──────────────────────────────────────
        if len(counts) == 1:
            divergence = "none"
        elif len(counts) == 2:
            divergence = "minor"
        else:
            divergence = "significant"

        return {
            "score": round(final, 3),
            "details": {
                "consensus":        round(consensus, 2),
                "avg_declared":     round(avg_declared, 2),
                "unique_articles":  unique_articles,
                "article_score":    round(article_score, 2),
                "parse_rate":       round(parse_rate, 2),
                "divergence":       divergence,
                "risk_distribution": dict(counts),
            }
        }
