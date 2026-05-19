from __future__ import annotations

from schemas.analysis_models import AnalysisDefinition
from schemas.chart_models import ChartDefinition


CHART_DEFINITIONS = {
    "income_expense_pie_chart": ChartDefinition(
        artifact_id="income_expense_pie_chart",
        display_name="Gelir-Gider Pasta Grafiği",
        supported_input=["excel", "prompt"],
        source_report_type="income_expense_report",
        required_fields=["amount", "direction"],
    ),
    "monthly_expense_trend_chart": ChartDefinition(
        artifact_id="monthly_expense_trend_chart",
        display_name="Aylık Harcama Trend Grafiği",
        supported_input=["excel", "prompt"],
        source_report_type="income_expense_report",
        required_fields=["date", "amount", "direction"],
    ),
    "cashflow_bar_chart": ChartDefinition(
        artifact_id="cashflow_bar_chart",
        display_name="Nakit Akış Bar Grafiği",
        supported_input=["excel", "prompt"],
        source_report_type="cash_flow_report",
        required_fields=["date", "amount", "direction"],
    ),
    "top_expenses_chart": ChartDefinition(
        artifact_id="top_expenses_chart",
        display_name="En Büyük Giderler Grafiği",
        supported_input=["excel"],
        source_report_type="income_expense_report",
        required_fields=["amount", "direction"],
    ),
    "daily_balance_change_chart": ChartDefinition(
        artifact_id="daily_balance_change_chart",
        display_name="Günlük Bakiye Değişim Grafiği",
        supported_input=["excel"],
        source_report_type="cash_flow_report",
        required_fields=["date"],
    ),
    "debt_receivable_distribution_chart": ChartDefinition(
        artifact_id="debt_receivable_distribution_chart",
        display_name="Borç-Alacak Dağılım Grafiği",
        supported_input=["excel"],
        source_report_type="debt_receivable_report",
        required_fields=["counterparty", "amount", "direction"],
    ),
    "sales_performance_chart": ChartDefinition(
        artifact_id="sales_performance_chart",
        display_name="Satış Performans Grafiği",
        supported_input=["excel"],
        source_report_type="sales_performance_report",
        required_fields=["customer", "amount"],
    ),
    "tax_distribution_chart": ChartDefinition(
        artifact_id="tax_distribution_chart",
        display_name="Vergi Dağılım Grafiği",
        supported_input=["excel"],
        source_report_type="tax_calculation_report",
        required_fields=["tax_type", "tax_amount"],
    ),
}


ANALYSIS_DEFINITIONS = {
    "financial_risk_analysis": AnalysisDefinition(
        artifact_id="financial_risk_analysis",
        display_name="Finansal Risk Analizi",
        source_report_type="income_expense_report",
        required_fields=["date", "amount", "direction"],
    ),
    "cash_runway_analysis": AnalysisDefinition(
        artifact_id="cash_runway_analysis",
        display_name="Nakit Tükenme Riski Analizi",
        source_report_type="cash_flow_report",
        required_fields=["date", "amount", "direction"],
    ),
    "anomaly_spending_analysis": AnalysisDefinition(
        artifact_id="anomaly_spending_analysis",
        display_name="Anormal Harcama Analizi",
        source_report_type="income_expense_report",
        required_fields=["date", "amount", "direction"],
    ),
    "expense_optimization_analysis": AnalysisDefinition(
        artifact_id="expense_optimization_analysis",
        display_name="Gider Optimizasyon Analizi",
        source_report_type="income_expense_report",
        required_fields=["amount", "direction"],
    ),
    "profitability_analysis": AnalysisDefinition(
        artifact_id="profitability_analysis",
        display_name="Kârlılık Analizi",
        source_report_type="profitability_report",
        required_fields=["date", "amount", "direction"],
    ),
    "receivable_debt_risk_analysis": AnalysisDefinition(
        artifact_id="receivable_debt_risk_analysis",
        display_name="Borç-Alacak Risk Analizi",
        source_report_type="debt_receivable_report",
        required_fields=["amount", "direction"],
    ),
    "sales_risk_analysis": AnalysisDefinition(
        artifact_id="sales_risk_analysis",
        display_name="Satış Risk ve Performans Analizi",
        source_report_type="sales_performance_report",
        required_fields=["amount"],
    ),
    "tax_risk_analysis": AnalysisDefinition(
        artifact_id="tax_risk_analysis",
        display_name="Vergi Risk Analizi",
        source_report_type="tax_calculation_report",
        required_fields=["tax_amount"],
    ),
}
