import re
from typing import Dict, Any, Tuple, Optional

# ==============================================================================
# THREAT MODEL & DESIGN RATIONALE: validate_tool_call.py
# ==============================================================================
# As an AI concierge managing files, Neaty is exposed to two primary threat vectors:
# 1. Prompt Injection (Indirect): Malicious instructions hidden inside raw text files
#    being scanned by the agent, attempting to hijack the LLM to run system commands.
# 2. Privacy Leakage (PII): Accidentally transmitting credit cards, phone numbers,
#    SSNs, or emails contained in filenames or snippets to the Gemini API.
#
# DESIGN PATTERN: Zero-Trust Input Interception
# To mitigate these threats, this module performs real-time, deterministic sanitization
# and validation of all tool arguments BEFORE they are processed or sent to the LLM.
# By combining strict regex filters with deep structure traversals, we establish a
# robust boundary between untrusted filesystem data and the reasoning agent.
# ==============================================================================

# Regex Patterns for Security Controls
# Block known destructive filesystem operations to prevent arbitrary command execution.
DESTRUCTIVE_COMMAND_PATTERN = re.compile(
    r"\b(rm|rf|rmdir|del|erase|shred|mkfs|format)\b", re.IGNORECASE
)

# Detect typical shell metacharacters used to concatenate or redirect terminal commands.
SHELL_INJECTION_PATTERN = re.compile(r"[|&;`$<>#\n\r]")

# Patterns for sensitive PII scanning. Matches standard Credit Card, SSN, US Phone, and Email formats.
PII_PATTERNS = {
    "Email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
    "Phone": re.compile(r"(?:\+?1[-. ]?)?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CreditCard": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

# Heuristics targeting common jailbreak or instructional override attacks.
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
    """
    Custom exception raised when a security control or guardrail policy is violated.
    Triggers an immediate halt of the tool execution thread to protect system integrity.
    """

    pass


def validate_command_safety(value: str) -> Tuple[bool, Optional[str]]:
    """
    BEHAVIOR:
    Evaluates file paths and parameter values for destructive CLI patterns or system commands.
    Returns a tuple (is_safe, error_reason) indicating whether the value is clean.

    DESIGN DECISION:
    To support deep folder traversal, we allow certain folder paths but block them if
    special terminal redirection symbols are coupled with system execution keywords.
    """
    if not isinstance(value, str):
        return True, None

    # Step 1: Search for banned destructive operations
    if DESTRUCTIVE_COMMAND_PATTERN.search(value):
        return False, "Destructive file command detected (e.g., rm -rf, del, rmdir)"

    # Step 2: Search for shell concatenation characters which might lead to shell piping/spawning
    if SHELL_INJECTION_PATTERN.search(value):
        # Allow paths containing special characters, but trigger a block if shell words are co-located
        lower_val = value.lower()
        if any(
            cmd in lower_val
            for cmd in ["rm", "rf", "sh", "bash", "cmd", "powershell", "exec"]
        ):
            return False, "Shell metacharacter injection attempt with commands detected"

    return True, None


def detect_and_redact_pii(value: str) -> Tuple[str, Dict[str, int]]:
    """
    BEHAVIOR:
    Performs high-speed scanning of a text parameter or content snippet.
    Replaces sensitive personal details in-place with standardized redacted tokens.

    DESIGN DECISION:
    Redaction is performed IN-PLACE before the agent executes tools. This ensures
    that even if file structures contain credit cards or phone numbers, only
    sanitized placeholders reach the model context window, satisfying strict privacy policies.
    """
    if not isinstance(value, str):
        return value, {}

    redacted_value = value
    redactions = {}

    # Iterate over all defined PII patterns and apply in-place replacements
    for name, pattern in PII_PATTERNS.items():
        matches = pattern.findall(redacted_value)
        if matches:
            redactions[name] = len(matches)
            redacted_value = pattern.sub(f"[{name.upper()}_REDACTED]", redacted_value)

    return redacted_value, redactions


def detect_prompt_injection(value: str) -> Tuple[bool, Optional[str]]:
    """
    BEHAVIOR:
    Inspects strings for common instruction override or LLM jailbreaking phrases.

    DESIGN DECISION:
    Prevents indirect prompt injections hidden inside raw scanned files. By screening
    the raw inputs at the tool level, we protect the agent's meta-instructions from
    being overridden by untrusted user documents.
    """
    if not isinstance(value, str):
        return True, None

    # Check the text against all known override patterns
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(value)
        if match:
            return False, f"Prompt injection pattern detected: '{match.group(0)}'"

    return True, None


def validate_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    BEHAVIOR:
    The central entry point for argument validation. Performs a deep recursive
    traversal of any incoming tool arguments (handling strings, nested dicts, and lists).

    DESIGN DECISION:
    Instead of performing a flat dictionary scan, this function recursively cleans
    nested payloads, making it compatible with complex ADK 2.0 object schemas.
    - Raises SecurityException immediately if destructive commands or prompt injections are found.
    - Mutates and redacts PII in-place for all other parameters.
    """
    validated_args = {}

    for key, val in args.items():
        if isinstance(val, str):
            # 1. Enforce strict CLI and shell command blocks
            is_safe_cmd, cmd_err = validate_command_safety(val)
            if not is_safe_cmd:
                raise SecurityException(
                    f"Security Policy Violation in '{key}': {cmd_err}"
                )

            # 2. Block instructional overrides / jailbreaks
            is_safe_prompt, injection_err = detect_prompt_injection(val)
            if not is_safe_prompt:
                raise SecurityException(
                    f"Security Policy Violation in '{key}': {injection_err}"
                )

            # 3. Apply real-time PII redactions
            redacted_val, redactions = detect_and_redact_pii(val)
            if redactions:
                print(
                    f"[Security Control] Redacted PII in argument '{key}': {redactions}"
                )
                validated_args[key] = redacted_val
            else:
                validated_args[key] = val
        elif isinstance(val, dict):
            # Recursively validate nested dictionary payloads
            validated_args[key] = validate_arguments(val)
        elif isinstance(val, list):
            # Traverse and sanitize lists of strings or dicts
            validated_list = []
            for item in val:
                if isinstance(item, dict):
                    validated_list.append(validate_arguments(item))
                elif isinstance(item, str):
                    # Validate list string items for command safety and prompt injection
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
            # Leave non-string primitives intact
            validated_args[key] = val

    return validated_args

