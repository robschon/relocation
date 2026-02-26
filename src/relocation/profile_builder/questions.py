from dataclasses import dataclass


@dataclass
class ProfileQuestion:
    key: str
    section: str
    question: str
    hint: str = ""
    multiline: bool = False


QUESTIONS = [
    # Demographics
    ProfileQuestion("ages", "Demographics", "What are your ages?", hint="e.g., 62 and 64"),
    ProfileQuestion("health_status", "Demographics", "Describe your general health and any ongoing medical needs.", multiline=True),
    ProfileQuestion("pets", "Demographics", "Do you have pets? If so, what kind and how many?"),

    # Financial
    ProfileQuestion("budget_monthly", "Financial", "What is your target monthly budget for living expenses (excluding housing)?"),
    ProfileQuestion("budget_housing", "Financial", "What is your housing budget (rent or purchase)?"),
    ProfileQuestion("income_sources", "Financial", "Describe your income sources (pensions, Social Security, investments, remote work, etc.).", multiline=True),
    ProfileQuestion("tax_situation", "Financial", "Any specific tax considerations? (US citizenship obligations, state tax residency, etc.)", multiline=True),

    # Languages & Culture
    ProfileQuestion("languages", "Languages & Culture", "What languages do you speak? At what proficiency levels?"),
    ProfileQuestion("cultural_preferences", "Languages & Culture", "What cultural environment appeals to you? (cosmopolitan, quiet town, artsy, etc.)"),
    ProfileQuestion("prior_international", "Languages & Culture", "Describe any prior international living or extended travel experience.", multiline=True),

    # Lifestyle
    ProfileQuestion("interests_hobbies", "Lifestyle", "What are your primary hobbies and interests?", multiline=True),
    ProfileQuestion("daily_routine", "Lifestyle", "Describe your ideal daily routine.", multiline=True),
    ProfileQuestion("food_preferences", "Lifestyle", "Any dietary preferences or food requirements?"),
    ProfileQuestion("exercise_activity", "Lifestyle", "What physical activities are important to you?"),

    # Requirements
    ProfileQuestion("must_haves", "Requirements", "What are your absolute must-haves in a location?", multiline=True),
    ProfileQuestion("deal_breakers", "Requirements", "What are your deal-breakers?", multiline=True),
    ProfileQuestion("climate_preference", "Requirements", "Describe your ideal climate."),
    ProfileQuestion("healthcare_needs", "Requirements", "Any specific healthcare requirements (specialists, medications, etc.)?"),

    # Connections
    ProfileQuestion("family_locations", "Connections", "Where do your closest family members live?", multiline=True),
    ProfileQuestion("friend_locations", "Connections", "Where do your closest friends live?", multiline=True),
    ProfileQuestion("visit_frequency", "Connections", "How often do you want to visit or be visited by family/friends?"),
    ProfileQuestion("remote_work_needs", "Connections", "Any remote work requirements (reliable internet, time zone constraints)?"),

    # Other
    ProfileQuestion("timeline", "Other", "What is your target timeline for relocation?"),
    ProfileQuestion("trial_period", "Other", "Are you open to trial periods before committing?"),
    ProfileQuestion("additional_notes", "Other", "Anything else that should inform location recommendations?", multiline=True),
]
