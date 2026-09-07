import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


def get_today_jakarta() -> datetime:
    """Returns the current datetime in Asia/Jakarta timezone."""
    return datetime.now(JAKARTA_TZ)


def resolve_default_target_date(custom_date_str: Optional[str] = None) -> date:
    """
    Returns the target date for daily extraction.
    Defaults to yesterday (Jakarta time) unless overridden.
    """
    if custom_date_str and custom_date_str.strip():
        return datetime.strptime(custom_date_str.strip(), "%Y-%m-%d").date()
    
    # Check env override
    env_date = os.getenv("TARGET_DATE", "").strip()
    if env_date:
        return datetime.strptime(env_date, "%Y-%m-%d").date()
        
    return get_today_jakarta().date() - timedelta(days=1)


@dataclass
class BrandConfig:
    name: str
    email: str
    password: str
    business_id: str
    report_id: str = "211"
    
    @property
    def login_url(self) -> str:
        return f"https://my.goapp.co.id/account/login/?email={self.email}&business={self.business_id}"

    
    def get_list_url(self, target_date: date) -> str:
        date_str = target_date.strftime("%Y-%m-%d")
        return (
            f"https://my.goapp.co.id/conversation/views/report/conversation-list/"
            f"?start_date={date_str}&end_date={date_str}&report={self.report_id}&format=xlsx"
        )
    
    def get_message_log_url(self, target_date: date) -> str:
        date_str = target_date.strftime("%Y-%m-%d")
        return (
            f"https://my.goapp.co.id/conversation/views/conversation-log/"
            f"?start_date={date_str}&end_date={date_str}&format=xlsx&table=conversation_message&task_id="
        )
    
    def get_sales_log_url(self, target_date: date) -> str:
        date_str = target_date.strftime("%Y-%m-%d")
        return (
            f"https://my.goapp.co.id/conversation/views/conversation-log/"
            f"?start_date={date_str}&end_date={date_str}&format=xlsx&table=conversation&task_id="
        )


def get_env_or_default(key: str, default: str) -> str:
    """Returns the environment variable value, or default if not set or empty."""
    val = os.getenv(key, "").strip()
    return val if val else default


@dataclass
class JWTConfig:
    secret: str = field(default_factory=lambda: get_env_or_default("JWT_SECRET", "default_secret_key_change_me"))
    algorithm: str = field(default_factory=lambda: get_env_or_default("JWT_ALGORITHM", "HS256"))
    expiry_seconds: int = field(default_factory=lambda: int(get_env_or_default("JWT_EXPIRY_SECONDS", "3600")))
    issuer: str = field(default_factory=lambda: get_env_or_default("JWT_ISSUER", "goapp-data-extractor"))
    audience: Optional[str] = field(default_factory=lambda: os.getenv("JWT_AUDIENCE", "").strip() or None)
    static_token: Optional[str] = field(default_factory=lambda: os.getenv("STATIC_BEARER_TOKEN", "").strip() or None)


@dataclass
class APIConfig:
    endpoint_url: str = field(default_factory=lambda: get_env_or_default("API_ENDPOINT_URL", "https://httpbin.org/post"))
    timeout_seconds: int = field(default_factory=lambda: int(get_env_or_default("API_TIMEOUT_SECONDS", "60")))
    max_retries: int = field(default_factory=lambda: int(get_env_or_default("API_MAX_RETRIES", "3")))


@dataclass
class AppConfig:
    brands: Dict[str, BrandConfig]
    jwt: JWTConfig
    api: APIConfig
    data_dir: Path = DATA_DIR
    logs_dir: Path = LOGS_DIR
    headless: bool = True
    keep_local_files: bool = False


def load_app_config(custom_date: Optional[str] = None) -> AppConfig:
    """Constructs AppConfig from environment variables and defaults."""
    default_email = get_env_or_default("GOAPP_EMAIL", "cs2@ikonsfurniture.com")
    default_password = os.getenv("GOAPP_PASSWORD", "").strip()
    
    # 1. IKONS
    ikons_config = BrandConfig(
        name="IKONS",
        email=get_env_or_default("IKONS_GOAPP_EMAIL", default_email),
        password=get_env_or_default("IKONS_GOAPP_PASSWORD", default_password),
        business_id=get_env_or_default("IKONS_BUSINESS_ID", "136404588220488"),
        report_id=get_env_or_default("IKONS_REPORT_ID", "199")
    )
    
    # 2. MODULO
    modulo_config = BrandConfig(
        name="MODULO",
        email=get_env_or_default("MODULO_GOAPP_EMAIL", default_email),
        password=get_env_or_default("MODULO_GOAPP_PASSWORD", default_password),
        business_id=get_env_or_default("MODULO_BUSINESS_ID", "136046770557000"),
        report_id=get_env_or_default("MODULO_REPORT_ID", "211")
    )
    
    # 3. ZBOM
    zbom_config = BrandConfig(
        name="ZBOM",
        email=get_env_or_default("ZBOM_GOAPP_EMAIL", default_email),
        password=get_env_or_default("ZBOM_GOAPP_PASSWORD", default_password),
        business_id=get_env_or_default("ZBOM_BUSINESS_ID", "136046770557000"),
        report_id=get_env_or_default("ZBOM_REPORT_ID", "211")
    )

    
    brands_map = {
        "IKONS": ikons_config,
        "MODULO": modulo_config,
        "ZBOM": zbom_config
    }
    
    headless_str = os.getenv("HEADLESS", "true").strip().lower()
    headless = headless_str in ["1", "true", "yes", "t"]
    
    keep_files_str = os.getenv("KEEP_LOCAL_FILES", "false").strip().lower()
    keep_local_files = keep_files_str in ["1", "true", "yes", "t"]
    
    return AppConfig(
        brands=brands_map,
        jwt=JWTConfig(),
        api=APIConfig(),
        headless=headless,
        keep_local_files=keep_local_files
    )
