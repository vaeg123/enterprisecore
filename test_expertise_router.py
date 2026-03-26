from core.intelligence.expertise_router import ExpertiseRouter

router = ExpertiseRouter()

finance_id = "bb100af1-9617-4192-9a0b-eb98ef1222a0"

level = router.get_agent_expertise(finance_id, "FINANCE")

print("Expertise level:", level)

print("Provider category:", router.select_provider(level))
