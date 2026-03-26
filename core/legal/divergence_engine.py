class DivergenceEngine:
    """
    Compare deux analyses juridiques
    et calcule un score de divergence pondéré.
    """

    RISK_WEIGHTS = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3
    }

    def compute(self, analysis_a: dict, analysis_b: dict):

        if not analysis_a or not analysis_b:
            return {
                "divergence_score": 1.0,
                "risk_conflict": True,
                "article_conflict": True,
                "recommendation_conflict": True,
                "escalation_required": True
            }

        # 1️⃣ Risk divergence
        risk_a = analysis_a.get("risk_level")
        risk_b = analysis_b.get("risk_level")

        risk_conflict = risk_a != risk_b

        risk_distance = abs(
            self.RISK_WEIGHTS.get(risk_a, 0) -
            self.RISK_WEIGHTS.get(risk_b, 0)
        ) / 3

        # 2️⃣ Article divergence
        articles_a = set(analysis_a.get("articles_referenced", []))
        articles_b = set(analysis_b.get("articles_referenced", []))

        article_conflict = articles_a != articles_b

        union = articles_a.union(articles_b)
        intersection = articles_a.intersection(articles_b)

        article_distance = 1 - (len(intersection) / len(union)) if union else 0

        # 3️⃣ Recommendation divergence (simple heuristic)
        rec_a = analysis_a.get("recommendation", "")
        rec_b = analysis_b.get("recommendation", "")

        recommendation_conflict = rec_a.strip().lower() != rec_b.strip().lower()

        recommendation_distance = 1 if recommendation_conflict else 0

        # 4️⃣ Weighted divergence score
        divergence_score = (
            0.5 * risk_distance +
            0.3 * article_distance +
            0.2 * recommendation_distance
        )

        escalation_required = divergence_score > 0.4

        return {
            "divergence_score": round(divergence_score, 3),
            "risk_conflict": risk_conflict,
            "article_conflict": article_conflict,
            "recommendation_conflict": recommendation_conflict,
            "escalation_required": escalation_required
        }
