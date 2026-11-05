from pydantic import BaseModel, ConfigDict

class PlanOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    description: str
    monthly_price_cents: int
    currency: str
    user_limit: int
    features: list[str]
    is_demo: bool

class SubscriptionOutput(BaseModel):
    company_id: str
    plan_code: str
    plan_name: str
    current_plan: PlanOutput | None
    status: str
    trial_started_at: int | None
    trial_ends_at: int | None
    trial_days_remaining: int | None
    total_users: int
    active_users: int
    billing_enabled: bool = False
    available_plans: list[PlanOutput]
