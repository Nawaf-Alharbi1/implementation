"""Small reusable coordinator for the existing three-agent pipeline."""


class NoEligibleOffers(RuntimeError):
    def __init__(self, provider_status):
        self.provider_status = provider_status
        super().__init__("لم نجد عروضاً مؤهلة لبياناتك الحالية. جرّب تعديل نوع التغطية أو بيانات الطلب.")


def coordinate_recommendation(agent1_output, recommender, explainer, rec_id=None):
    """Run the completed recommender and explainer against Agent 1's actual output."""
    profile = agent1_output["customer_profile"]
    step2 = recommender.run_from_agent1_output(agent1_output, priority=profile.get("priority"))
    if step2["selected"] is None:
        raise NoEligibleOffers(step2.get("provider_status") or agent1_output.get("provider_status", []))
    # V2 attaches score_breakdown and weighted_contributions to selected; Agent 3
    # consumes those fields directly to generate criterion-specific explanations.
    step3 = explainer.run(step2["selected"], step2["ranked"], rec_id=rec_id)
    return {
        "recommended_package": step2["selected"],
        "all_offers_ranked": step2["ranked"],
        "explanation": step3,
        "provider_status": step2.get("provider_status", agent1_output.get("provider_status", [])),
    }
