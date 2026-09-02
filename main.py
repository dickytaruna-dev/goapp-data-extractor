import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from typing import List

from config import AppConfig, load_app_config, resolve_default_target_date
from data_converter import build_brand_bundle_json, build_report_json, save_json_file
from api_dispatcher import APIDispatcher, DispatchResult
from goapp_downloader import GoAppDownloader, DownloadedFiles


def log(msg: str):
    print(f"[Main Orchestrator] {msg}", flush=True)


async def process_brand(
    brand_name: str,
    target_date: date,
    config: AppConfig,
    downloader: GoAppDownloader,
    dispatcher: APIDispatcher,
    dry_run: bool = False,
    save_json: bool = True
) -> bool:
    brand_cfg = config.brands.get(brand_name.upper())
    if not brand_cfg:
        log(f"❌ Brand [{brand_name}] is not configured in AppConfig.")
        return False

    log(f"============================================================")
    log(f"🚀 Starting extraction for Brand: [{brand_cfg.name}] | Date: {target_date}")
    log(f"============================================================")

    # 1. Download reports via Playwright
    try:
        downloaded = await downloader.download_brand_reports(brand_cfg, target_date)
    except Exception as exc:
        log(f"❌ Download failed for [{brand_cfg.name}]: {exc}")
        return False

    # 2. Convert to JSON Bundle
    bundle_json = build_brand_bundle_json(
        brand_name=brand_cfg.name,
        target_date=target_date,
        list_path=downloaded.list_path,
        message_log_path=downloaded.message_log_path,
        sales_log_path=downloaded.sales_log_path
    )

    # Optionally save JSON files locally
    if save_json:
        json_path = config.data_dir / f"{brand_cfg.name.lower()}_data_{target_date.strftime('%Y-%m-%d')}.json"
        save_json_file(bundle_json, json_path)
        log(f"💾 JSON payload saved to {json_path}")

    # 3. Dispatch to API with JWT
    if dry_run:
        log(f"🔍 [DRY-RUN] Skipped API dispatch for [{brand_cfg.name}].")
        return True

    log(f"📡 Sending JSON payload for [{brand_cfg.name}] to API endpoint: {config.api.endpoint_url}")
    result: DispatchResult = dispatcher.send_json(bundle_json)

    if result.success:
        log(f"✅ API Dispatch SUCCESS for [{brand_cfg.name}]! HTTP Status: {result.status_code}")
        return True
    else:
        log(f"❌ API Dispatch FAILED for [{brand_cfg.name}]: {result.error_message}")
        return False


async def run_pipeline(
    target_date: date,
    brands: List[str],
    dry_run: bool = False,
    save_json: bool = True
) -> int:
    config = load_app_config()
    downloader = GoAppDownloader(
        data_dir=config.data_dir,
        logs_dir=config.logs_dir,
        headless=config.headless
    )
    dispatcher = APIDispatcher(
        api_config=config.api,
        jwt_config=config.jwt
    )

    success_count = 0
    total_count = len(brands)

    for brand_name in brands:
        ok = await process_brand(
            brand_name=brand_name,
            target_date=target_date,
            config=config,
            downloader=downloader,
            dispatcher=dispatcher,
            dry_run=dry_run,
            save_json=save_json
        )
        if ok:
            success_count += 1

    log("============================================================")
    log(f"📊 SUMMARY: {success_count}/{total_count} brands processed successfully.")
    log("============================================================")

    # Cleanup local raw files if configured
    if not config.keep_local_files and not dry_run:
        log("🧹 Cleaning up temporary Excel files...")
        for excel_file in config.data_dir.glob("*.xlsx"):
            try:
                excel_file.unlink()
            except Exception:
                pass

    return 0 if success_count == total_count else 1


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="GoApp Data Extractor & JWT API Dispatcher for IKONS, MODULO, and ZBOM."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date for extraction in YYYY-MM-DD format (defaults to yesterday)."
    )
    parser.add_argument(
        "--brands",
        type=str,
        default=os.getenv("ACTIVE_BRANDS", "IKONS,MODULO,ZBOM"),
        help="Comma-separated list of brands to process (e.g. IKONS,MODULO,ZBOM)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform download and conversion without sending to the target API."
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        default=True,
        help="Save converted JSON locally in data/ directory."
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    target_date = resolve_default_target_date(args.date)
    brands = [b.strip().upper() for b in args.brands.split(",") if b.strip()]

    log(f"🌟 Starting GoApp Data Extractor")
    log(f"📅 Target Date: {target_date}")
    log(f"🏷️  Target Brands: {', '.join(brands)}")
    log(f"⚙️  Dry-run mode: {args.dry_run}")

    exit_code = asyncio.run(run_pipeline(
        target_date=target_date,
        brands=brands,
        dry_run=args.dry_run,
        save_json=args.save_json
    ))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
