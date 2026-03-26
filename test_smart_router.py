from providers.role_router import RoleBasedRouter

router = RoleBasedRouter()

# FinanceAgent
finance_id = "bb100af1-9617-4192-9a0b-eb98ef1222a0"

result = router.route(
    agent_id=finance_id,
    role="finance",
    domain_code="FINANCE",
    prompt="Explain financial risk management in enterprise context."
)

print("Provider:", result.metadata)
print("Confidence:", result.confidence)
print("Output preview:", result.content[:300])
