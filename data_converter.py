import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd


def clean_cell_value(val: Any) -> Any:
    """Converts Pandas/NumPy types, NaNs, and datetimes into standard JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.isoformat()
    if pd.isna(val):
        return None
    if isinstance(val, str):
        cleaned = val.strip()
        if cleaned.lower() in ["nan", "none", "null", "<na>"]:
            return None
        return cleaned
    if isinstance(val, (int, bool)):
        return val
    return str(val)


def excel_file_to_records(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Reads an Excel file and converts all rows into a list of dictionaries with clean JSON types.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File Excel tidak ditemukan: {path}")

    # Read as object/string to preserve phone numbers, IDs, and raw text
    df = pd.read_excel(path, dtype=object)
    
    if df.empty:
        return []

    # Clean column headers
    cleaned_columns = [str(col).strip() for col in df.columns]
    df.columns = cleaned_columns

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        record = {}
        for col in cleaned_columns:
            record[col] = clean_cell_value(row[col])
        records.append(record)

    return records


def build_report_json(
    file_path: Union[str, Path],
    brand_name: str,
    report_type: str,
    target_date: date
) -> Dict[str, Any]:
    """
    Converts an Excel report file into a standardized JSON payload with metadata.
    """
    path = Path(file_path)
    records = excel_file_to_records(path)
    
    return {
        "metadata": {
            "source": "goapp-data-extractor",
            "brand": brand_name.upper(),
            "report_type": report_type,
            "target_date": target_date.strftime("%Y-%m-%d"),
            "extracted_at": datetime.now().astimezone().isoformat(),
            "source_filename": path.name,
            "row_count": len(records)
        },
        "records": records
    }


def build_brand_bundle_json(
    brand_name: str,
    target_date: date,
    list_path: Optional[Union[str, Path]] = None,
    message_log_path: Optional[Union[str, Path]] = None,
    sales_log_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Bundles all 3 reports of a brand into a single unified JSON payload.
    """
    reports: Dict[str, Any] = {}
    
    if list_path and Path(list_path).exists():
        records = excel_file_to_records(list_path)
        reports["conversation_list"] = {
            "source_filename": Path(list_path).name,
            "row_count": len(records),
            "records": records
        }
        
    if message_log_path and Path(message_log_path).exists():
        records = excel_file_to_records(message_log_path)
        reports["conversation_message_log"] = {
            "source_filename": Path(message_log_path).name,
            "row_count": len(records),
            "records": records
        }
        
    if sales_log_path and Path(sales_log_path).exists():
        records = excel_file_to_records(sales_log_path)
        reports["sales_conversation_log"] = {
            "source_filename": Path(sales_log_path).name,
            "row_count": len(records),
            "records": records
        }

    return {
        "metadata": {
            "source": "goapp-data-extractor",
            "brand": brand_name.upper(),
            "target_date": target_date.strftime("%Y-%m-%d"),
            "extracted_at": datetime.now().astimezone().isoformat(),
            "total_reports": len(reports)
        },
        "reports": reports
    }


def save_json_file(data: Dict[str, Any], output_path: Union[str, Path]) -> Path:
    """Saves dictionary data as formatted JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path
