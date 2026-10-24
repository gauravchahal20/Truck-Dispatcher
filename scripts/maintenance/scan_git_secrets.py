import subprocess
import re

PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API key
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),   # OpenAI / Stripe secret key
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),   # GitHub PAT
    re.compile(r"SG\.[a-zA-Z0-9-_]{22}\.[a-zA-Z0-9-_]{43}"), # SendGrid
    re.compile(r"AC[a-f0-9]{32}"),         # Twilio SID
]

KEY_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|password)\s*[:=]\s*['\"]([^'\"]+)['\"]"
)

ALLOWED_VALUES = {
    "", "your_key_here", "test_key", "trucklead_dev_secret_key", "development",
    "<SET>", "<NOT SET>", "test", "your_secret_key_here", "your_google_places_api_key_here",
    "your_twilio_account_sid_here", "your_twilio_auth_token_here", "your_telnyx_api_key_here",
    "your_numverify_api_key_here", "your_zerobounce_api_key_here", "your_hunter_api_key_here",
    "your_anymail_api_key_here", "your_apollo_api_key_here", "your_serper_api_key_here",
    "your_google_custom_search_api_key_here", "your_google_cse_id_here", "your_google_spreadsheet_id_here",
    "your_socrata_app_token_here", "your_qcmobile_webkey_here"
}

def scan_git_history():
    print("Scanning full git history for secrets and .env files...")
    # 1. Check all committed file paths in history
    all_files = subprocess.check_output(
        ["git", "log", "--all", "--pretty=format:", "--name-only"],
        text=True, encoding="utf-8", errors="ignore"
    ).splitlines()
    
    env_files = [f.strip() for f in all_files if f.strip().endswith(".env") or f.strip() == ".env"]
    if env_files:
        print(f"ALERT: Found committed .env files: {set(env_files)}")
    else:
        print("OK: No actual .env files ever committed in git history.")
        
    # 2. Check git log -p for leaked secret patterns
    diff_output = subprocess.check_output(
        ["git", "log", "-p", "--all"],
        text=True, encoding="utf-8", errors="ignore"
    )
    
    leaks = []
    for line in diff_output.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added = line[1:].strip()
            # Test known high-entropy token patterns
            for pat in PATTERNS:
                m = pat.search(added)
                if m:
                    leaks.append((pat.pattern, m.group(0)))
            
            # Test key assignment
            m2 = KEY_ASSIGNMENT.search(added)
            if m2:
                key_name, val = m2.group(1), m2.group(2)
                if val.lower() not in ALLOWED_VALUES and len(val) > 15:
                    leaks.append((key_name, val[:4] + "..." + val[-4:]))
                    
    if leaks:
        print(f"ALERT: Potential secret leaks detected in history ({len(leaks)} found):")
        for p, sample in leaks:
            print(f"  Pattern: {p} => {sample}")
    else:
        print("OK: 0 secret leaks found across all commits in git history.")

if __name__ == "__main__":
    scan_git_history()
