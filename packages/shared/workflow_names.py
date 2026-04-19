"""Workflow, Signal, Query, and Queue name constants.

See TRD Section 4.6 for full specifications.
"""

# Workflow type names
VAULT_MANAGER_WORKFLOW = "VaultManagerWorkflow"
COPILOT_SESSION_WORKFLOW = "CopilotSessionWorkflow"
NIGHT_WATCHMAN_WORKFLOW = "NightWatchmanWorkflow"
FILER_INGESTION_WORKFLOW = "FilerIngestionWorkflow"
READ_VAULT_WORKFLOW = "ReadVaultWorkflow"
WRITE_VAULT_WORKFLOW = "WriteVaultWorkflow"

# Well-known workflow IDs (for addressing long-running singletons)
VAULT_MANAGER_ID = "vault-manager"

# Signal names
SIG_RECEIVE_MESSAGE = "receive_message"
SIG_CANCEL_SESSION = "cancel_session"
SIG_APPROVE = "approve"
SIG_REJECT = "reject"
SIG_ENSURE_SYNCED = "ensure_synced"
SIG_SYNC_ACK = "sync_ack"

# Query names
QRY_GET_HISTORY = "get_history"
QRY_GET_STATUS = "get_status"
QRY_GET_SYNC_STATUS = "get_sync_status"
QRY_GET_DRAFT_PROPOSAL = "get_draft_proposal"
QRY_GET_PROGRESS = "get_progress"

# Task Queue names
QUEUE_DEFAULT = "vault-default"
QUEUE_MUTATION = "vault-mutation-queue"

# Set of all workflow type names for validation
WORKFLOW_NAMES: set[str] = {
    VAULT_MANAGER_WORKFLOW,
    COPILOT_SESSION_WORKFLOW,
    NIGHT_WATCHMAN_WORKFLOW,
    FILER_INGESTION_WORKFLOW,
    READ_VAULT_WORKFLOW,
    WRITE_VAULT_WORKFLOW,
}