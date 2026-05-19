from __future__ import annotations


REPORT_FILTER_DEFAULTS = {
    "income_expense_report": {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": None,
        "overdue_date_field": None,
        "direction_field": "direction",
        "category_fields": ["category", "counterparty", "description"],
        "ranking_dimensions": {
            "category": {"group_by": ["category"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "counterparty": {"group_by": ["counterparty"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
        },
    },
    "cash_flow_report": {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": None,
        "overdue_date_field": None,
        "direction_field": "direction",
        "category_fields": ["category", "counterparty", "description", "source"],
        "ranking_dimensions": {
            "category": {"group_by": ["category"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "counterparty": {"group_by": ["counterparty"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
        },
    },
    "debt_receivable_report": {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": "payment_status",
        "overdue_date_field": "due_date",
        "direction_field": "direction",
        "category_fields": ["counterparty", "counterparty_type", "description", "invoice_no"],
        "ranking_dimensions": {
            "counterparty": {"group_by": ["counterparty"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "counterparty_type": {"group_by": ["counterparty_type"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "risk_score": {"group_by": ["counterparty"], "metric_field": "risk_score", "aggregate": "risk_score", "direction": "desc"},
        },
    },
    "sales_performance_report": {
        "primary_date_field": "date",
        "amount_field": "total_sales",
        "status_field": "return_status",
        "overdue_date_field": None,
        "direction_field": "transaction_type",
        "category_fields": ["product_name", "customer", "salesperson", "region", "counterparty"],
        "ranking_dimensions": {
            "customer": {"group_by": ["customer"], "metric_field": "total_sales", "aggregate": "sum", "direction": "desc"},
            "product_name": {"group_by": ["product_name"], "metric_field": "total_sales", "aggregate": "sum", "direction": "desc"},
            "salesperson": {"group_by": ["salesperson"], "metric_field": "total_sales", "aggregate": "sum", "direction": "desc"},
            "region": {"group_by": ["region"], "metric_field": "total_sales", "aggregate": "sum", "direction": "desc"},
        },
    },
    "personnel_expense_report": {
        "primary_date_field": "date",
        "amount_field": "total_employer_cost",
        "status_field": None,
        "overdue_date_field": None,
        "direction_field": None,
        "category_fields": ["department", "employee_name"],
        "ranking_dimensions": {
            "department": {"group_by": ["department"], "metric_field": "total_employer_cost", "aggregate": "sum", "direction": "desc"},
            "employee_name": {"group_by": ["employee_name"], "metric_field": "total_employer_cost", "aggregate": "sum", "direction": "desc"},
        },
    },
    "inventory_cost_report": {
        "primary_date_field": "date",
        "amount_field": "unit_cost",
        "status_field": "transaction_type",
        "overdue_date_field": None,
        "direction_field": "transaction_type",
        "category_fields": ["product_name", "product_code", "warehouse", "supplier", "product_category"],
        "ranking_dimensions": {
            "product_name": {"group_by": ["product_name"], "metric_field": "unit_cost", "aggregate": "sum", "direction": "desc"},
            "product_code": {"group_by": ["product_code"], "metric_field": "unit_cost", "aggregate": "sum", "direction": "desc"},
            "warehouse": {"group_by": ["warehouse"], "metric_field": "unit_cost", "aggregate": "sum", "direction": "desc"},
        },
    },
    "vat_summary_report": {
        "primary_date_field": "date",
        "amount_field": "total_amount",
        "status_field": "transaction_type",
        "overdue_date_field": None,
        "direction_field": "transaction_type",
        "category_fields": ["counterparty", "product_name", "description", "invoice_no"],
        "ranking_dimensions": {
            "counterparty": {"group_by": ["counterparty"], "metric_field": "tax_amount", "aggregate": "sum", "direction": "desc"},
            "product_name": {"group_by": ["product_name"], "metric_field": "tax_amount", "aggregate": "sum", "direction": "desc"},
        },
    },
    "tax_calculation_report": {
        "primary_date_field": "date",
        "amount_field": "tax_amount",
        "status_field": "transaction_type",
        "overdue_date_field": None,
        "direction_field": "transaction_type",
        "category_fields": ["tax_type", "transaction_type", "counterparty", "period"],
        "ranking_dimensions": {
            "tax_type": {"group_by": ["tax_type"], "metric_field": "tax_amount", "aggregate": "sum", "direction": "desc"},
            "counterparty": {"group_by": ["counterparty"], "metric_field": "tax_amount", "aggregate": "sum", "direction": "desc"},
            "period": {"group_by": ["period"], "metric_field": "tax_amount", "aggregate": "sum", "direction": "desc"},
        },
    },
    "profitability_report": {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": "direction",
        "overdue_date_field": None,
        "direction_field": "direction",
        "category_fields": ["category", "description"],
        "ranking_dimensions": {
            "category": {"group_by": ["category"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
        },
    },
    "current_account_report": {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": "payment_status",
        "overdue_date_field": "due_date",
        "direction_field": "transaction_direction",
        "category_fields": ["counterparty", "counterparty_type", "description", "invoice_no"],
        "ranking_dimensions": {
            "counterparty": {"group_by": ["counterparty"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "counterparty_type": {"group_by": ["counterparty_type"], "metric_field": "amount", "aggregate": "sum", "direction": "desc"},
            "risk_score": {"group_by": ["counterparty"], "metric_field": "risk_score", "aggregate": "risk_score", "direction": "desc"},
        },
    },
    "payroll_cost_report": {
        "primary_date_field": "date",
        "amount_field": "total_employer_cost",
        "status_field": None,
        "overdue_date_field": None,
        "direction_field": None,
        "category_fields": ["department", "employee_name"],
        "ranking_dimensions": {
            "department": {"group_by": ["department"], "metric_field": "total_employer_cost", "aggregate": "sum", "direction": "desc"},
            "employee_name": {"group_by": ["employee_name"], "metric_field": "total_employer_cost", "aggregate": "sum", "direction": "desc"},
        },
    },
}


def get_report_filter_defaults(report_type: str) -> dict:
    defaults = REPORT_FILTER_DEFAULTS.get(report_type)
    if defaults is not None:
        return defaults
    return {
        "primary_date_field": "date",
        "amount_field": "amount",
        "status_field": None,
        "overdue_date_field": None,
        "direction_field": None,
        "category_fields": [],
        "ranking_dimensions": {},
    }
