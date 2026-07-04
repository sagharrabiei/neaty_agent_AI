import re
from typing import Dict, Any, Tuple, Optional

# Regex Patterns for Security Controls
DESTRUCTIVE_COMMAND_PATTERN = re.compile(
    r"\b(rm|rf|rmdir|del|erase|shred|mkfs|format)\b", re.IGNORECASE
)

SHELL_INJECTION_PATTERN = re.compile(r"[|&;`$<>#\n\r]")

PII_PATTERNS = {
    "Email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
    "Phone": re.compile(r"(?:\+?1[-. ]?)?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CreditCard": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(?:all\s+)?above\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+v2", re.IGNORECASE),
]


class SecurityException(Exception):
    """Raised when a security guardrail is violated."""

    pass


def validate_command_safety(value: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if a string contains shell commands or destructive operations like rm -rf.
    Returns: (is_safe, error_reason)
    """
    if not isinstance(value, str):
        return True, None

    # Check for destructive commands
    if DESTRUCTIVE_COMMAND_PATTERN.search(value):
        return False, "Destructive file command detected (e.g., rm -rf, del, rmdir)"

    # Check for shell metacharacters that could enable command execution or piping
    if SHELL_INJECTION_PATTERN.search(value):
        # We allow standard paths, but raise a flag if shell characters are used alongside command terms
        # Let's check for command injection keywords
        lower_val = value.lower()
        if any(
            cmd in lower_val
            for cmd in ["rm", "rf", "sh", "bash", "cmd", "powershell", "exec"]
        ):
            return False, "Shell metacharacter injection attempt with commands detected"

    return True, None


def detect_and_redact_pii(value: str) -> Tuple[str, Dict[str, int]]:
    """
    Scans a string for PII patterns and redacts them in-place.
    Returns: (redacted_string, dictionary_of_redactions_count)
    """
    if not isinstance(value, str):
        return value, {}

    redacted_value = value
    redactions = {}

    for name, pattern in PII_PATTERNS.items():
        matches = pattern.findall(redacted_value)
        if matches:
            redactions[name] = len(matches)
            redacted_value = pattern.sub(f"[{name.upper()}_REDACTED]", redacted_value)

    return redacted_value, redactions


def detect_prompt_injection(value: str) -> Tuple[bool, Optional[str]]:
    """
    Scans a string for typical LLM prompt injection and override phrases.
    Returns: (is_safe, detected_phrase)
    """
    if not isinstance(value, str):
        return True, None

    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(value)
        if match:
            return False, f"Prompt injection pattern detected: '{match.group(0)}'"

    return True, None


def validate_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates tool arguments for security violations.
    - Prevents destructive commands (raises SecurityException).
    - Prevents prompt injection (raises SecurityException).
    - Redacts PII in-place.
    """
    validated_args = {}

    for key, val in args.items():
        if isinstance(val, str):
            # 1. Destructive Commands Check
            is_safe_cmd, cmd_err = validate_command_safety(val)
            if not is_safe_cmd:
                raise SecurityException(
                    f"Security Policy Violation in '{key}': {cmd_err}"
                )

            # 2. Prompt Injection Check
            is_safe_prompt, injection_err = detect_prompt_injection(val)
            if not is_safe_prompt:
                raise SecurityException(
                    f"Security Policy Violation in '{key}': {injection_err}"
                )

            # 3. PII Redaction
            redacted_val, redactions = detect_and_redact_pii(val)
            if redactions:
                print(
                    f"[Security Control] Redacted PII in argument '{key}': {redactions}"
                )
                validated_args[key] = redacted_val
            else:
                validated_args[key] = val
        elif isinstance(val, dict):
            # Recursively validate dictionary structures
            validated_args[key] = validate_arguments(val)
        elif isinstance(val, list):
            # Recursively validate list items
            validated_list = []
            for item in val:
                if isinstance(item, dict):
                    validated_list.append(validate_arguments(item))
                elif isinstance(item, str):
                    is_safe_cmd, cmd_err = validate_command_safety(item)
                    if not is_safe_cmd:
                        raise SecurityException(
                            f"Security Policy Violation in list: {cmd_err}"
                        )
                    is_safe_prompt, injection_err = detect_prompt_injection(item)
                    if not is_safe_prompt:
                        raise SecurityException(
                            f"Security Policy Violation in list: {injection_err}"
                        )
                    redacted_item, _ = detect_and_redact_pii(item)
                    validated_list.append(redacted_item)
                else:
                    validated_list.append(item)
            validated_args[key] = validated_list
        else:
            validated_args[key] = val

    return validated_args
