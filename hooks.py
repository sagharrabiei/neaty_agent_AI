from typing import Dict, Any, Optional
from validate_tool_call import validate_arguments, SecurityException


def security_before_tool_callback(
    tool: Any, args: Dict[str, Any], tool_context: Any
) -> Optional[Dict[str, Any]]:
    """
    ADK 2.0 Before Tool Callback for security enforcement.
    Intercepts every tool call and validates arguments for:
    1. Destructive commands (e.g., rm -rf).
    2. Prompt injection attempts.
    3. Redacts any PII (Email, Phone, SSN, Credit Cards) in place.

    If any high-risk violation is detected, blocks the tool call and returns an error response.
    """
    tool_name = getattr(tool, "name", "unknown_tool")
    print(f"\n[Security Interceptor] Checking tool call '{tool_name}'...")

    try:
        # Validate and mutate arguments (redacting PII in-place)
        validated_args = validate_arguments(args)

        # In-place modify the arguments passed to the tool
        args.clear()
        args.update(validated_args)

        print(f"[Security Interceptor] Tool '{tool_name}' arguments passed validation.")
        return None  # Return None to allow tool call to proceed with modified/cleaned arguments

    except SecurityException as e:
        error_msg = str(e)
        print(
            f"\n⚠️ [SECURITY BLOCK] Denied execution of tool '{tool_name}'! Reason: {error_msg}"
        )

        # By returning a dictionary, we prevent the actual tool from running and return this result instead.
        return {
            "status": "blocked",
            "error": f"Security Policy Violation: {error_msg}",
            "remedy": "Please refrain from passing destructive commands, personal data (PII), or instruction overrides.",
        }
