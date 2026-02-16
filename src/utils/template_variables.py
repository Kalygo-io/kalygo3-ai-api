import re
from datetime import datetime, timezone

SUPPORTED_VARIABLES = {
    "current_time",
    "current_date",
    "current_datetime",
    "current_day_of_week",
    "agent_name",
}

TEMPLATE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def build_variable_context(agent_name: str = "") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "current_time": now.strftime("%H:%M UTC"),
        "current_date": now.strftime("%Y-%m-%d"),
        "current_datetime": now.isoformat(),
        "current_day_of_week": now.strftime("%A"),
        "agent_name": agent_name,
    }


def resolve_template_variables(template: str, context: dict) -> str:
    """Replace whitelisted {{ variable }} placeholders with their runtime values.

    Only variables in SUPPORTED_VARIABLES are substituted.
    Unrecognized variables are left as-is so the subsequent LangChain
    curly-brace escaping renders them harmlessly as literal text.
    """

    def replacer(match):
        var_name = match.group(1)
        if var_name in SUPPORTED_VARIABLES and var_name in context:
            return str(context[var_name])
        return match.group(0)

    return TEMPLATE_PATTERN.sub(replacer, template)
