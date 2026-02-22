import re

from .models import UserAgentBotRule, UserAgentFalsePositive


MAX_USER_AGENT_LENGTH = 512


def validate_bot_pattern(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(str(exc)) from exc


def evaluate_user_agent_against_pattern(pattern: str, user_agent: str) -> bool:
    if not pattern or not user_agent:
        return False
    return bool(re.search(pattern, user_agent[:MAX_USER_AGENT_LENGTH]))


def should_flag_user_agent(user_agent: str):
    if not user_agent:
        return False, None
    rule = UserAgentBotRule.get_current()
    if not rule.enabled or not rule.pattern:
        return False, None
    if UserAgentFalsePositive.objects.filter(user_agent=user_agent).exists():
        return False, None
    try:
        matched = evaluate_user_agent_against_pattern(rule.pattern, user_agent)
    except re.error:
        return False, None
    if not matched:
        return False, None
    return True, rule.version
