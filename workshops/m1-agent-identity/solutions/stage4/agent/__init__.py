"""Register Agent Identity Auth Manager as ADK's credential source.

This runs at import-time of the `agent` package. The runtime imports
`agent.tools` (via the pickled LlmAgent tool references), which imports
the `agent` package, which executes this __init__.py — so the
class-level registration is in place before any AuthenticatedFunctionTool
calls get_auth_credential.

If this registration is omitted, tool invocation fails at runtime with:
    ValueError: No auth provider registered for custom auth scheme
                'gcpAuthProviderScheme'.
"""

from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import GcpAuthProvider

CredentialManager.register_auth_provider(GcpAuthProvider())
