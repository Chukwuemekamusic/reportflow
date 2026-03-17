# backend/app/workers/tasks/__init__.py
from app.workers.tasks.sales_summary import run_sales_summary
from app.workers.tasks.csv_export import run_csv_export
from app.workers.tasks.pdf_report import run_pdf_report

TASK_MAP = {
    "sales_summary": run_sales_summary,
    "csv_export":    run_csv_export,
    "pdf_report":    run_pdf_report,
}