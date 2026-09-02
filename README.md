# GoApp Data Extractor & JWT API Dispatcher

A robust, automated daily data extraction engine designed to fetch raw customer conversation reports across multiple brand workspaces (**IKONS**, **MODULO**, and **ZBOM**) from [GoApp](https://my.goapp.co.id), convert them into structured JSON records, and securely dispatch them to an external backend API using JSON Web Token (JWT) authentication.

---

## 🌟 Key Features

1. **Automated Session Handling:** Headless browser authentication via Playwright, overcoming GoApp's session-based report generation.
2. **Multi-Brand Support:** Seamlessly downloads reports for **IKONS**, **MODULO**, and **ZBOM** across their respective GoApp Business IDs.
3. **Three Core Datasets per Brand:**
   - **Sales Conversation List** (New/updated customer conversations)
   - **Conversation Message Log** (Granular chat message history and transcripts)
   - **Sales Conversation Log** (Lead agent assignment and activity logs)
4. **Structured JSON Converter:** Cleans up Excel artifacts, normalizes timestamps, cleans `NaN`/`null` values, and packages records into clean JSON.
5. **Secure JWT API Dispatcher:** Generates cryptographically signed JWT tokens (`HS256`/`RS256`) or passes Bearer tokens with exponential retry logic.
6. **Public Repository Ready:** **Zero hardcoded credentials**. All secrets and configurations are strictly loaded via `.env` or GitHub Secrets.

---

## 📁 Project Structure

```text
goapp-data-extractor/
├── .github/
│   └── workflows/
│       └── daily-data-extractor.yml    # GitHub Actions cron & manual workflow
├── .env.example                        # Safe template for environment variables
├── .gitignore                          # Excludes secrets, Excel/JSON dumps, and caches
├── requirements.txt                    # Python dependencies
├── config.py                           # Strongly typed configurations
├── goapp_downloader.py                 # Playwright session login & report fetcher
├── data_converter.py                   # Excel-to-JSON normalization engine
├── api_dispatcher.py                   # JWT generator & HTTP client with retries
├── main.py                             # Main CLI orchestrator
└── README.md                           # Documentation
```

---

## 🚀 Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.11 or 3.12
- Node.js / Playwright browser support

### 2. Clone & Install Dependencies
```bash
# Navigate to project directory
cd goapp-data-extractor

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install Python requirements
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Setup Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```ini
GOAPP_EMAIL=cs2@ikonsfurniture.com
GOAPP_PASSWORD=your_secure_password

API_ENDPOINT_URL=https://api.yourdomain.com/v1/goapp/ingest
JWT_SECRET=your_secret_jwt_key_here
```

### 4. Running the Script

#### Extract yesterday's data for all brands (Default):
```bash
python main.py
```

#### Extract specific date:
```bash
python main.py --date 2026-08-31
```

#### Extract specific brand only:
```bash
python main.py --brands IKONS
```

#### Dry-run mode (Download & convert to JSON locally without sending to API):
```bash
python main.py --dry-run
```

---

## 🔐 Environment Variables & GitHub Secrets Reference

| Variable Name | Required | Default | Description |
|---|---|---|---|
| `GOAPP_EMAIL` | **Yes** | - | GoApp account email |
| `GOAPP_PASSWORD` | **Yes** | - | GoApp account password |
| `API_ENDPOINT_URL` | **Yes** | - | Target API URL to receive the JSON data |
| `JWT_SECRET` | **Yes** | - | Secret key used to sign JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm (`HS256`, `HS384`, `HS512`, `RS256`) |
| `JWT_EXPIRY_SECONDS`| No | `3600` | Token lifespan in seconds (1 hour) |
| `JWT_ISSUER` | No | `goapp-data-extractor` | `iss` claim in JWT payload |
| `JWT_AUDIENCE` | No | `None` | `aud` claim in JWT payload |
| `STATIC_BEARER_TOKEN` | No | `None` | Optional static token override (if dynamic JWT is not used) |
| `IKONS_BUSINESS_ID` | No | `136404588220488` | GoApp business ID for IKONS |
| `IKONS_REPORT_ID` | No | `199` | Conversation list report ID for IKONS |
| `MODULO_BUSINESS_ID`| No | `136046770557000` | GoApp business ID for MODULO |
| `MODULO_REPORT_ID` | No | `211` | Conversation list report ID for MODULO |
| `ZBOM_BUSINESS_ID` | No | `136046770557000` | GoApp business ID for ZBOM |
| `ZBOM_REPORT_ID` | No | `211` | Conversation list report ID for ZBOM |

---

## 📡 JSON Payload Specification

The script sends an HTTP `POST` request to `API_ENDPOINT_URL` with the header:
```http
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

### Sample Payload Format (Brand Bundle):
```json
{
  "metadata": {
    "source": "goapp-data-extractor",
    "brand": "IKONS",
    "target_date": "2026-08-31",
    "extracted_at": "2026-09-01T04:45:00+07:00",
    "total_reports": 3
  },
  "reports": {
    "conversation_list": {
      "source_filename": "ikons_conversation_list_2026-08-31.xlsx",
      "row_count": 25,
      "records": [
        {
          "Date": "2026-08-31",
          "Time": "09:15",
          "Contact Name": "Budi Santoso",
          "No. Phone": "6281234567890",
          "Channel": "Ikons Furniture",
          "Inbox": "Sales Team",
          "Queue": "IKONS CS Queue",
          "Assigned To": "Sales Admin"
        }
      ]
    },
    "conversation_message_log": {
      "source_filename": "ikons_conversation_message_log_2026-08-31.xlsx",
      "row_count": 80,
      "records": [
        {
          "conversation_uid": "conv-12345",
          "sender_type": "contact",
          "text": "Halo, saya tertarik dengan katalog kursi resto Ikons.",
          "created_at": "2026-08-31 09:15:20"
        }
      ]
    },
    "sales_conversation_log": {
      "source_filename": "ikons_sales_conversation_log_2026-08-31.xlsx",
      "row_count": 15,
      "records": [
        {
          "id": "conv-12345",
          "contact": "Budi Santoso",
          "answered_at": "2026-08-31 09:18:00",
          "status": "closed"
        }
      ]
    }
  }
}
```

---

## ⚙️ GitHub Actions Setup

1. In your GitHub repository, navigate to **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret** and add:
   - `GOAPP_EMAIL`
   - `GOAPP_PASSWORD`
   - `API_ENDPOINT_URL`
   - `JWT_SECRET`
3. The workflow in `.github/workflows/daily-data-extractor.yml` will automatically run every day at **00:00 WIB** (17:00 UTC) and can also be triggered manually under the **Actions** tab.
