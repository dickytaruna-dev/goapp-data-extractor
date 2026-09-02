import json
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pandas as pd

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api_dispatcher import APIDispatcher
from config import APIConfig, BrandConfig, JWTConfig, load_app_config, resolve_default_target_date
from data_converter import (
    build_brand_bundle_json,
    build_report_json,
    clean_cell_value,
    excel_file_to_records,
    save_json_file
)


class TestConfig(unittest.TestCase):
    def test_brand_urls(self):
        brand = BrandConfig(
            name="IKONS",
            email="cs2@ikonsfurniture.com",
            password="pass",
            business_id="136404588220488",
            report_id="199"
        )
        self.assertIn("cs2%40ikonsfurniture.com", brand.login_url)
        self.assertIn("136404588220488", brand.login_url)
        
        target = date(2026, 8, 31)
        list_url = brand.get_list_url(target)
        self.assertIn("report=199", list_url)
        self.assertIn("start_date=2026-08-31", list_url)
        
        msg_url = brand.get_message_log_url(target)
        self.assertIn("table=conversation_message", msg_url)
        
        sales_url = brand.get_sales_log_url(target)
        self.assertIn("table=conversation&task_id=", sales_url)

    def test_target_date_resolution(self):
        custom_date = resolve_default_target_date("2026-07-15")
        self.assertEqual(custom_date, date(2026, 7, 15))


class TestDataConverter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(__file__).parent / "test_data"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.test_excel = self.test_dir / "sample_report.xlsx"

        # Create a mock Excel file with tricky edge cases (NaN, datetime, formulas, numbers)
        df = pd.DataFrame([
            {
                "Contact Name": "Alice ",
                "Phone": "08123456789",
                "EmptyCol": float("nan"),
                "NullStr": "nan",
                "Created Date": datetime(2026, 8, 31, 10, 30, 0),
                "Active": True,
                "Count": 42
            },
            {
                "Contact Name": "Bob",
                "Phone": "08987654321",
                "EmptyCol": None,
                "NullStr": "NULL",
                "Created Date": datetime(2026, 8, 31, 11, 0, 0),
                "Active": False,
                "Count": 0
            }
        ])
        df.to_excel(self.test_excel, index=False)

    def tearDown(self):
        if self.test_excel.exists():
            self.test_excel.unlink()
        if self.test_dir.exists():
            try:
                self.test_dir.rmdir()
            except Exception:
                pass

    def test_clean_cell_value(self):
        self.assertIsNone(clean_cell_value(float("nan")))
        self.assertIsNone(clean_cell_value("nan"))
        self.assertIsNone(clean_cell_value("null"))
        self.assertEqual(clean_cell_value("  Hello  "), "Hello")
        self.assertEqual(clean_cell_value(42), 42)
        self.assertEqual(clean_cell_value(True), True)

    def test_excel_to_records(self):
        records = excel_file_to_records(self.test_excel)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["Contact Name"], "Alice")
        self.assertIsNone(records[0]["EmptyCol"])
        self.assertIsNone(records[0]["NullStr"])
        self.assertEqual(records[0]["Count"], 42)
        self.assertTrue(records[0]["Active"])
        self.assertIn("2026-08-31", str(records[0]["Created Date"]))

    def test_build_brand_bundle(self):
        target = date(2026, 8, 31)
        bundle = build_brand_bundle_json(
            brand_name="MODULO",
            target_date=target,
            list_path=self.test_excel,
            message_log_path=self.test_excel,
            sales_log_path=self.test_excel
        )
        self.assertEqual(bundle["metadata"]["brand"], "MODULO")
        self.assertEqual(bundle["metadata"]["target_date"], "2026-08-31")
        self.assertEqual(len(bundle["reports"]), 3)
        self.assertIn("conversation_list", bundle["reports"])
        self.assertIn("conversation_message_log", bundle["reports"])
        self.assertIn("sales_conversation_log", bundle["reports"])
        
        # Ensure it is JSON serializable
        json_str = json.dumps(bundle)
        self.assertIsInstance(json_str, str)


class TestAPIDispatcher(unittest.TestCase):
    def setUp(self):
        self.api_config = APIConfig(
            endpoint_url="https://httpbin.org/post",
            timeout_seconds=10,
            max_retries=1
        )
        self.jwt_config = JWTConfig(
            secret="test_secret_key_1234567890",
            algorithm="HS256",
            expiry_seconds=1800,
            issuer="test-suite",
            audience="test-aud"
        )
        self.dispatcher = APIDispatcher(self.api_config, self.jwt_config)

    def test_generate_jwt_token(self):
        token = self.dispatcher.generate_jwt_token(subject="IKONS")
        self.assertIsInstance(token, str)

        # Decode and verify token
        decoded = jwt.decode(
            token,
            self.jwt_config.secret,
            algorithms=["HS256"],
            audience="test-aud",
            issuer="test-suite"
        )
        self.assertEqual(decoded["sub"], "IKONS")
        self.assertEqual(decoded["iss"], "test-suite")
        self.assertEqual(decoded["aud"], "test-aud")
        self.assertGreater(decoded["exp"], decoded["iat"])

    @patch("requests.Session.post")
    def test_send_json_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "received"}'
        mock_post.return_value = mock_response

        payload = {"metadata": {"brand": "IKONS"}, "data": [1, 2, 3]}
        result = self.dispatcher.send_json(payload)

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIn("received", result.response_body)

        # Verify Authorization header was sent
        args, kwargs = mock_post.call_args
        self.assertIn("Authorization", kwargs["headers"])
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer ey"))


if __name__ == "__main__":
    unittest.main()
