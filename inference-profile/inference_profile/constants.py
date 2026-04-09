OPT_MODEL_IDS = (
    "facebook/opt-125m",
    "facebook/opt-350m",
    "facebook/opt-1.3b",
    "facebook/opt-2.7b",
    "facebook/opt-6.7b",
)
SUPPORTED_MODEL_IDS = OPT_MODEL_IDS

PREFILL_CHUNK_SIZES = (64, 128, 256, 512, 1024)
CHUNK_SIZES = PREFILL_CHUNK_SIZES

DECODE_SEQUENCE_LENGTHS = (1024, 2048, 4096, 8192)
SEQUENCE_LENGTHS = DECODE_SEQUENCE_LENGTHS

REMOTE_HOST = "netsys@192.168.1.20"
REMOTE_PROJECT_ROOT = "/home/netsys/dheeraj/inference-profile"
REMOTE_ROOT = REMOTE_PROJECT_ROOT

LOCAL_FETCH_ROOT = "/mnt/data/dheeraj/dicertation/inference-profile/runs"
SSHPASS_FILE = "/mnt/data/dheeraj/dicertation/.ssh_pass"

REMOTE_LDPC_TRACE = (
    "/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/"
    "e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv"
)
REMOTE_RAN_CTRL_TRACE = (
    "/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/"
    "e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv"
)
