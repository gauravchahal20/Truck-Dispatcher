import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FleetSizeConfig(BaseModel):
    min: int = 2
    max: int = 10
    partial_min: int = 1
    partial_max: int = 20
    partial_multiplier: float = 0.5
    preferred_min: int = 2
    preferred_max: int = 10


class CarrierPrefilterConfig(BaseModel):
    enabled: bool = True
    exclude_household_goods: bool = False
    excluded_name_keywords: List[str] = [
        "wrecker", "towing", "tow", "auto sales", "auto repair", "dealership",
        "used cars", "landscaping", "landscape", "tree service", "tree care",
        "dumpster", "dumpsters", "waste", "trash", "junk", "scrap", "concrete",
        "paving", "roofing", "passenger", "limo", "limousine", "taxi", "bus",
        "charter", "ambulance", "medical transport"
    ]
    excluded_carrier_operations: List[str] = ["Passenger", "Migrant", "Government"]
    excluded_cargo_classifications: List[str] = [
        "Passengers", "Garbage/Refuse", "Driveaway/Towaway",
        "crgo_passengers", "crgo_garbage", "crgo_drivetow"
    ]


class ICPWideningOption(BaseModel):
    enabled: bool = False
    segment: str = "icp_edge"
    flag: str = "ICP edge"
    priority_weight: float = 0.6


class ICPWideningConfig(BaseModel):
    enabled: bool = False
    fleet_1_owner_operators: ICPWideningOption = Field(
        default_factory=lambda: ICPWideningOption(segment="owner_operator", flag="ICP edge", priority_weight=0.6)
    )
    fleet_11_15_mid_size: ICPWideningOption = Field(
        default_factory=lambda: ICPWideningOption(segment="mid_size_carrier", flag="ICP edge", priority_weight=0.7)
    )


class ICPConfig(BaseModel):
    target_country: str = "US"
    target_states: List[str] = ["TX", "CA", "GA", "IL", "OH", "PA", "FL", "NC", "IN", "MI"]
    fleet_size: FleetSizeConfig = Field(default_factory=FleetSizeConfig)
    icp_widening: ICPWideningConfig = Field(default_factory=ICPWideningConfig)
    equipment_types: List[str] = ["dry_van", "reefer", "flatbed", "drayage", "stepdeck", "power_only"]
    carrier_operations: List[str] = ["Interstate", "Intrastate Hazmat", "Intrastate Non-Hazmat"]
    authorized_only: bool = True
    min_verification_confidence: float = 0.70
    score_threshold_for_final: float = 5.0
    mcs150_min_date: str = "20241024"
    carrier_prefilter: CarrierPrefilterConfig = Field(default_factory=CarrierPrefilterConfig)



class ScoringWeights(BaseModel):
    target_fleet_size: float = 2.0
    verified_active_carrier: float = 2.0
    decision_maker_identified: float = 2.0
    equipment_verified: float = 1.0
    usable_contact: float = 1.0
    intent_signal_present: float = 1.0
    tech_or_business_event: float = 1.0


class ScoringThresholds(BaseModel):
    priority_a_min: float = 8.0
    priority_b_min: float = 6.0
    priority_c_min: float = 5.0
    reject_below: float = 5.0


class RoleAccountWeights(BaseModel):
    named_person: float = 1.0       # Full credit (+1.0)
    personal_webmail: float = 0.7   # Configurable credit (default 0.7) for free webmail with personal local part
    departmental: float = 0.5       # Medium credit (+0.5 for sales@, dispatch@, ops@)
    generic_inbox: float = 0.2      # Lowest credit (+0.2 for info@, admin@, support@)


class ScoringConfig(BaseModel):
    registered_officer_partial_credit: float = 0.5
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    priority_thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)
    role_account_weights: RoleAccountWeights = Field(default_factory=RoleAccountWeights)


class ResearchBudgetConfig(BaseModel):
    max_discovery_pages_per_source: int = 10
    max_verification_attempts: int = 3
    max_decision_maker_searches: int = 3
    max_intent_searches: int = 2
    max_website_pages_to_crawl: int = 6
    http_timeout_seconds: int = 15
    browser_timeout_seconds: int = 25
    delay_between_requests_ms: int = 1200


class SecurityConfig(BaseModel):
    strict_robots_respect: bool = True
    pause_on_captcha: bool = True
    max_redirects: int = 3
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 10.0
    response_size_cap_bytes: int = 2 * 1024 * 1024  # 2MB cap
    allowed_domains: List[str] = [
        "safer.fmcsa.dot.gov",
        "ai.fmcsa.dot.gov",
        "google.com",
        "www.google.com",
        "maps.google.com",
        "news.google.com",
        "linkedin.com",
        "www.linkedin.com",
        "indeed.com",
        "www.indeed.com",
        "bbb.org",
        "yellowpages.com"
    ]
    blocked_domains: List[str] = ["*.gov.ru", "*.cn"]


class GoogleSheetsConfig(BaseModel):
    enabled: bool = True
    spreadsheet_id: str = ""
    sheet_name: str = "TRUCKLEAD_AUTOPILOT_RESULTS"
    export_local_backup_csv: bool = True
    export_local_backup_xlsx: bool = True
    backup_dir: str = "./exports"
    tabs: Dict[str, str] = {
        "final_leads": "FINAL_LEADS",
        "research_queue": "RESEARCH_QUEUE",
        "rejected": "REJECTED",
        "source_log": "SOURCE_LOG",
        "run_report": "RUN_REPORT"
    }


class PipelineConfig(BaseModel):
    pause_shipper_discovery: bool = True
    benchmark_states: List[str] = ["TX", "GA", "OH"]
    sync_states: List[str] = ["TX", "GA", "FL", "NC", "TN"]


class ComplianceConfig(BaseModel):
    postal_address: Optional[str] = None
    sender_identity: Optional[str] = None
    sender_email: Optional[str] = "dispatch@trucklead-autopilot.internal"
    unsubscribe_url: str = "http://localhost:8000/api/compliance/opt-out"


class DailyCapacityConfig(BaseModel):
    calls_per_day: int = 30
    emails_per_day: int = 30


class OutreachConfig(BaseModel):
    physical_address: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = "dispatch@trucklead-autopilot.internal"
    enable_continuous_autopilot: bool = False
    daily_capacity: DailyCapacityConfig = Field(default_factory=DailyCapacityConfig)


class PhoneVerificationSettings(BaseModel):
    default_provider: str = "twilio"
    cost_cap_per_lead: float = 0.05
    cost_cap_per_run: float = 5.00
    cache_ttl_days: int = 30


class EmailVerificationSettings(BaseModel):
    verify_mx: bool = True
    disposable_domain_check: bool = True
    cost_cap_per_lead: float = 0.05
    cost_cap_per_run: float = 5.00


class ContactVerificationConfig(BaseModel):
    phone: PhoneVerificationSettings = Field(default_factory=PhoneVerificationSettings)
    email: EmailVerificationSettings = Field(default_factory=EmailVerificationSettings)


class AutopilotConfig(BaseModel):
    per_cycle_leads_cap: int = 50
    per_cycle_spend_cap: float = 2.00
    max_requests_per_host_per_min: int = 30


class SourceConfigItem(BaseModel):
    enabled: bool = True
    priority: int = 1
    timeout: int = 20


class SignalSyncCapsConfig(BaseModel):
    insurance_limit: int = 500
    authority_history_limit: int = 500
    new_applications_limit: int = 500
    sync_stored_carriers_first: bool = True


class SignalHalfLifeConfig(BaseModel):
    new_authority: float = 45.0
    insurance_cancel_pending: float = 15.0
    mcs150_recent_update: float = 60.0
    power_units_growth: float = 90.0
    generic_intent: float = 30.0
    pending_authority: float = 90.0
    clean_inspection: float = 90.0


class SignalWeightsConfig(BaseModel):
    new_authority: float = 2.0
    insurance_cancel_pending: float = 1.5
    mcs150_recent_update: float = 0.5
    power_units_growth: float = 1.5
    generic_intent: float = 1.0
    new_usdot_registration: float = 0.5
    pending_authority: float = 0.5
    clean_inspection: float = 0.5


class SignalWindowConfig(BaseModel):
    min_days: int = 30
    max_days: int = 120


class SignalEngineConfig(BaseModel):
    version: str = "2.0"
    max_intent_points: float = 3.0
    half_life_days: SignalHalfLifeConfig = Field(default_factory=SignalHalfLifeConfig)
    weights: SignalWeightsConfig = Field(default_factory=SignalWeightsConfig)
    new_authority_window: SignalWindowConfig = Field(default_factory=SignalWindowConfig)
    mcs150_window_days: int = 60


class CallQueueConfig(BaseModel):
    daily_cap: int = 30
    default_sort: str = "fit_score"


class SignalsConfig(BaseModel):
    sync_caps: SignalSyncCapsConfig = Field(default_factory=SignalSyncCapsConfig)
    engine: SignalEngineConfig = Field(default_factory=SignalEngineConfig)




PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class AppSettings(BaseSettings):
    app_name: str = "TRUCKLEAD AUTOPILOT"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "trucklead_dev_secret_key"
    database_url: str = "sqlite+aiosqlite:///./data/trucklead.db"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    google_application_credentials: Optional[str] = None
    google_service_account_json: Optional[str] = None
    google_spreadsheet_id: Optional[str] = None

    serper_api_key: Optional[str] = None
    google_custom_search_api_key: Optional[str] = None
    google_custom_search_engine_id: Optional[str] = None

    # Phone Verification API Keys (Twilio Lookup v2, Telnyx, NumVerify)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    telnyx_api_key: Optional[str] = None
    numverify_api_key: Optional[str] = None

    # Email Verification API Keys (ZeroBounce, Hunter, Anymail finder, Apollo)
    zerobounce_api_key: Optional[str] = None
    hunter_api_key: Optional[str] = None
    anymail_api_key: Optional[str] = None
    apollo_api_key: Optional[str] = None
    api_key: Optional[str] = None

    enable_continuous_autopilot: bool = False

    playwright_headless: bool = True
    browser_timeout_ms: int = 25000
    max_concurrent_workers: int = 4
    enable_captcha_auto_pause: bool = True

    model_config = SettingsConfigDict(
        env_file=[str(PROJECT_ROOT / ".env"), ".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore"
    )


def find_config_file_path(config_path: Optional[str] = None) -> Optional[Path]:
    search_paths = [
        config_path,
        os.getenv("TRUCKLEAD_CONFIG_PATH"),
        str(PROJECT_ROOT / "config" / "default_config.yaml"),
        "config/default_config.yaml",
        "../config/default_config.yaml"
    ]
    for path in search_paths:
        if path and Path(path).is_file():
            return Path(path).resolve()
    return None


def load_yaml_config(config_path: Optional[str] = None) -> tuple[Dict[str, Any], Optional[Path]]:
    """Loads configuration from YAML file with fallback to default paths."""
    resolved_path = find_config_file_path(config_path)
    if resolved_path:
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}, resolved_path
        except Exception as e:
            print(f"Warning: Failed to load config from {resolved_path}: {e}")
    return {}, resolved_path


class SystemConfig:
    """Singleton configuration manager combining YAML settings and Environment Variables."""
    _instance = None

    def __init__(self, config_file: Optional[str] = None):
        self._init_config(config_file)

    def _init_config(self, config_file: Optional[str] = None):
        self.raw_yaml, self.config_file_path = load_yaml_config(config_file)
        self.env = AppSettings()

        # Merge YAML into structured sections
        icp_data = self.raw_yaml.get("icp", {})
        self.icp = ICPConfig(**icp_data) if icp_data else ICPConfig()

        scoring_data = self.raw_yaml.get("scoring", {})
        self.scoring = ScoringConfig(**scoring_data) if scoring_data else ScoringConfig()

        budget_data = self.raw_yaml.get("research_budget", {})
        self.budget = ResearchBudgetConfig(**budget_data) if budget_data else ResearchBudgetConfig()

        sec_data = self.raw_yaml.get("security", {})
        self.security = SecurityConfig(**sec_data) if sec_data else SecurityConfig()

        sheets_data = self.raw_yaml.get("google_sheets", {})
        self.sheets = GoogleSheetsConfig(**sheets_data) if sheets_data else GoogleSheetsConfig()
        if self.env.google_spreadsheet_id:
            self.sheets.spreadsheet_id = self.env.google_spreadsheet_id

        self.sources: Dict[str, SourceConfigItem] = {}
        sources_data = self.raw_yaml.get("sources", {})
        for name, item in sources_data.items():
            if isinstance(item, dict):
                self.sources[name] = SourceConfigItem(**item)

        self.decision_makers: List[str] = self.raw_yaml.get("decision_makers", {}).get(
            "priority_order",
            ["Owner", "Founder", "President", "Fleet Manager", "Operations Manager", "Dispatch Manager"]
        )

        self.intent_keywords: Dict[str, List[str]] = self.raw_yaml.get("intent_signals", {}).get("keywords", {})

        pipeline_data = self.raw_yaml.get("pipeline", {})
        self.pipeline = PipelineConfig(**pipeline_data) if pipeline_data else PipelineConfig()

        compliance_data = self.raw_yaml.get("compliance", {})
        self.compliance = ComplianceConfig(**compliance_data) if compliance_data else ComplianceConfig()

        outreach_data = self.raw_yaml.get("outreach", {})
        self.outreach = OutreachConfig(**outreach_data) if outreach_data else OutreachConfig()

        cv_data = self.raw_yaml.get("contact_verification", {})
        self.contact_verification = ContactVerificationConfig(**cv_data) if cv_data else ContactVerificationConfig()

        autopilot_data = self.raw_yaml.get("autopilot", {})
        self.autopilot = AutopilotConfig(**autopilot_data) if autopilot_data else AutopilotConfig()

        signals_data = self.raw_yaml.get("signals", {})
        self.signals = SignalsConfig(**signals_data) if signals_data else SignalsConfig()

        call_queue_data = self.raw_yaml.get("call_queue", {})
        self.call_queue = CallQueueConfig(**call_queue_data) if call_queue_data else CallQueueConfig()



    def reload(self, config_file: Optional[str] = None):
        target_file = config_file or (str(self.config_file_path) if self.config_file_path else None)
        self._init_config(target_file)

    @classmethod
    def get_instance(cls, config_file: Optional[str] = None):
        if cls._instance is None:
            cls._instance = cls(config_file)
        return cls._instance


settings = AppSettings()
config = SystemConfig.get_instance()

