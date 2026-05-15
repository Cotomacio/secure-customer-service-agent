"""Register Agent Identity Auth Manager as ADK's credential source.

Runs at import-time of the `agent` package. The runtime imports
`agent.tools` (via pickled LlmAgent tool references), which imports the
`agent` package, which executes this __init__.py — so the class-level
registration is in place before AuthenticatedFunctionTool fires.
"""

from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import GcpAuthProvider

CredentialManager.register_auth_provider(GcpAuthProvider())
