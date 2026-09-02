import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from config import BrandConfig


def log(msg: str):
    print(f"[GoApp Downloader] {msg}", flush=True)


@dataclass
class DownloadedFiles:
    brand: str
    target_date: date
    list_path: Optional[Path] = None
    message_log_path: Optional[Path] = None
    sales_log_path: Optional[Path] = None


class GoAppDownloader:
    def __init__(self, data_dir: Path, logs_dir: Path, headless: bool = True):
        self.data_dir = data_dir
        self.logs_dir = logs_dir
        self.headless = headless
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    async def _login_brand(self, page: Page, brand: BrandConfig):
        """Navigates to GoApp login with specific brand workspace and performs authentication."""
        log(f"🔐 Logging into GoApp for brand [{brand.name}] (Business ID: {brand.business_id})...")
        
        await page.goto(
            brand.login_url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        await page.wait_for_selector('input[type="password"]', timeout=120000)
        await page.fill('input[type="password"]', brand.password)
        await page.click('button[type="submit"]')

        # Wait for redirect and session establishment
        await page.wait_for_timeout(8000)

        current_url = page.url.lower()
        log(f"🌐 Post-login URL: {current_url}")

        password_fields = await page.locator('input[type="password"]').count()
        if "login" in current_url and password_fields > 0:
            screenshot_path = self.logs_dir / f"login_failed_{brand.name.lower()}.png"
            await page.screenshot(path=str(screenshot_path))
            raise RuntimeError(f"Login failed for [{brand.name}]. Screenshot saved to {screenshot_path}")

        log(f"✅ Login successful for [{brand.name}]")

    async def _download_report(self, page: Page, url: str, target_path: Path, label: str) -> Path:
        """Navigates to GoApp report export URL, waits for Download Ready, and saves file."""
        log(f"📥 Downloading {label}...")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        log("⏳ Waiting for report generation ('Download Ready')...")
        
        try:
            await page.wait_for_selector("text=Download Ready", timeout=350000)
            
            async with page.expect_download(timeout=120000) as download_info:
                await page.click("text=Download Ready")
                
            download = await download_info.value
            target_path.parent.mkdir(parents=True, exist_ok=True)
            await download.save_as(str(target_path))
            
            log(f"✅ Saved {label} ({target_path.stat().st_size} bytes) to {target_path.name}")
            return target_path
        except PlaywrightTimeoutError:
            screenshot_path = self.logs_dir / f"timeout_{target_path.stem}.png"
            await page.screenshot(path=str(screenshot_path))
            raise TimeoutError(f"Timed out waiting for 'Download Ready' on {label}. Screenshot: {screenshot_path}")

    async def download_brand_reports(self, brand: BrandConfig, target_date: date) -> DownloadedFiles:
        """
        Downloads all 3 reports (List, Message Log, Sales Log) for a single brand.
        """
        date_str = target_date.strftime("%Y-%m-%d")
        brand_key = brand.name.lower()
        
        list_file = self.data_dir / f"{brand_key}_conversation_list_{date_str}.xlsx"
        message_log_file = self.data_dir / f"{brand_key}_conversation_message_log_{date_str}.xlsx"
        sales_log_file = self.data_dir / f"{brand_key}_sales_conversation_log_{date_str}.xlsx"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                # 1. Login session
                await self._login_brand(page, brand)

                # 2. Download Conversation List
                list_url = brand.get_list_url(target_date)
                await self._download_report(page, list_url, list_file, f"[{brand.name}] Conversation List")

                # 3. Download Message Log
                msg_log_url = brand.get_message_log_url(target_date)
                await self._download_report(page, msg_log_url, message_log_file, f"[{brand.name}] Message Log")

                # 4. Download Sales Conversation Log
                sales_log_url = brand.get_sales_log_url(target_date)
                await self._download_report(page, sales_log_url, sales_log_file, f"[{brand.name}] Sales Conversation Log")

                return DownloadedFiles(
                    brand=brand.name,
                    target_date=target_date,
                    list_path=list_file,
                    message_log_path=message_log_file,
                    sales_log_path=sales_log_file
                )
            finally:
                await context.close()
                await browser.close()
