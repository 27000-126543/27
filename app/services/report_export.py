import os
import io
from datetime import datetime, date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from app.models import (
    CommissionRecord, RebateRecord, SalesOrder, Salesperson, ChannelPartner,
    Report, PaymentInstruction, User, ApprovalRecord, ProductCategory,
    CustomerLevel
)
import json


plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class ReportExportService:
    """报表与导出系统 - 每月5号自动报告、PDF/Excel导出、图表"""

    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = "./reports"
        os.makedirs(self.reports_dir, exist_ok=True)
        self._init_pdf_font()

    def _init_pdf_font(self):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        except:
            pass

    def _generate_filename(self, report_type: str, period: str, ext: str) -> str:
        return f"{report_type}_{period}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"

    def generate_monthly_report(self, year: int, month: int,
                                 user_id: int = None, auto: bool = False) -> Report:
        """生成月度佣金与返利分析报告"""
        period_str = f"{year}-{month:02d}"
        report_code = f"RPT{year}{month:02d}{datetime.now().strftime('%H%M%S')}"

        data = self._collect_report_data(year, month)

        excel_path = None
        pdf_path = None
        try:
            excel_path = self._generate_excel_report(year, month, data)
        except Exception as e:
            print(f"Excel生成失败: {e}")
        try:
            pdf_path = self._generate_pdf_report(year, month, data)
        except Exception as e:
            print(f"PDF生成失败: {e}")

        report = Report(
            report_code=report_code,
            report_type="monthly_commission_rebate",
            period_year=year,
            period_month=month,
            title=f"{period_str} 月度佣金与返利分析报告",
            summary=json.dumps(data.get("summary", {}), ensure_ascii=False),
            file_path_pdf=pdf_path,
            file_path_excel=excel_path,
            generated_by=user_id,
            is_auto_generated=auto
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _collect_report_data(self, year: int, month: int) -> Dict:
        commissions = self.db.query(CommissionRecord).filter(
            CommissionRecord.period_year == year,
            CommissionRecord.period_month == month
        ).all()

        import math
        q = math.ceil(month / 3)
        rebates = self.db.query(RebateRecord).filter(
            RebateRecord.period_year == year,
            RebateRecord.period_quarter == q
        ).all()

        total_commission = sum(c.total_commission for c in commissions)
        by_salesperson: Dict[int, float] = {}
        by_category: Dict[str, float] = {}
        by_customer_level: Dict[str, float] = {}

        for c in commissions:
            by_salesperson[c.salesperson_id] = by_salesperson.get(c.salesperson_id, 0) + c.total_commission
            cat = c.product_category.value if c.product_category else "OTHER"
            by_category[cat] = by_category.get(cat, 0) + c.total_commission
            lvl = c.customer_level.value if c.customer_level else "NORMAL"
            by_customer_level[lvl] = by_customer_level.get(lvl, 0) + c.total_commission

        salesperson_count = len(by_salesperson)
        avg_commission = total_commission / salesperson_count if salesperson_count else 0

        total_rebate = sum(r.total_rebate for r in rebates)
        by_partner: Dict[int, float] = {}
        for r in rebates:
            by_partner[r.channel_partner_id] = by_partner.get(r.channel_partner_id, 0) + r.total_rebate
        partner_count = len(by_partner)
        avg_rebate = total_rebate / partner_count if partner_count else 0

        frozen_rebates = [r for r in rebates if r.is_frozen]
        frozen_amount = sum(r.total_rebate for r in frozen_rebates)

        cost_trend = self._get_cost_trend(year, month)

        top_salespersons = sorted(by_salesperson.items(), key=lambda x: x[1], reverse=True)[:10]
        top_partners = sorted(by_partner.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "summary": {
                "period": f"{year}-{month:02d}",
                "total_commission": round(total_commission, 2),
                "total_rebate": round(total_rebate, 2),
                "salesperson_count": salesperson_count,
                "avg_commission_per_person": round(avg_commission, 2),
                "partner_count": partner_count,
                "avg_rebate_per_partner": round(avg_rebate, 2),
                "commission_record_count": len(commissions),
                "rebate_record_count": len(rebates),
                "frozen_rebate_count": len(frozen_rebates),
                "frozen_rebate_amount": round(frozen_amount, 2),
                "total_cost": round(total_commission + total_rebate, 2)
            },
            "by_category": by_category,
            "by_customer_level": by_customer_level,
            "top_salespersons": top_salespersons,
            "top_partners": top_partners,
            "cost_trend": cost_trend
        }

    def _get_cost_trend(self, year: int, month: int, months: int = 6) -> List[Dict]:
        trend = []
        for i in range(months - 1, -1, -1):
            m = month - i
            y = year
            if m <= 0:
                m += 12
                y -= 1
            comms = self.db.query(CommissionRecord).filter(
                CommissionRecord.period_year == y,
                CommissionRecord.period_month == m
            ).all()
            total = sum(c.total_commission for c in comms)
            trend.append({"period": f"{y}-{m:02d}", "commission": round(total, 2)})
        return trend

    def _generate_excel_report(self, year: int, month: int, data: Dict) -> str:
        filename = self._generate_filename("monthly_report", f"{year}-{month:02d}", "xlsx")
        filepath = os.path.join(self.reports_dir, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            summary_df = pd.DataFrame([data["summary"]])
            summary_df.to_excel(writer, sheet_name="摘要", index=False)

            cat_df = pd.DataFrame(
                [(k, v) for k, v in data["by_category"].items()],
                columns=["产品类别", "佣金金额"]
            )
            cat_df.to_excel(writer, sheet_name="产品类别分析", index=False)

            lvl_df = pd.DataFrame(
                [(k, v) for k, v in data["by_customer_level"].items()],
                columns=["客户等级", "佣金金额"]
            )
            lvl_df.to_excel(writer, sheet_name="客户等级分析", index=False)

            trend_df = pd.DataFrame(data["cost_trend"])
            trend_df.to_excel(writer, sheet_name="成本趋势", index=False)

            top_sp = []
            for sp_id, amount in data["top_salespersons"]:
                sp = self.db.query(Salesperson).filter(Salesperson.id == sp_id).first()
                name = sp.user.full_name if sp and sp.user else f"ID:{sp_id}"
                top_sp.append({"排名": len(top_sp) + 1, "销售人员": name, "佣金金额": round(amount, 2)})
            pd.DataFrame(top_sp).to_excel(writer, sheet_name="Top销售人员", index=False)

            top_pt = []
            for pt_id, amount in data["top_partners"]:
                pt = self.db.query(ChannelPartner).filter(ChannelPartner.id == pt_id).first()
                name = pt.partner_name if pt else f"ID:{pt_id}"
                top_pt.append({"排名": len(top_pt) + 1, "渠道商": name, "返利金额": round(amount, 2)})
            pd.DataFrame(top_pt).to_excel(writer, sheet_name="Top渠道商", index=False)

        return filepath

    def _generate_pdf_report(self, year: int, month: int, data: Dict) -> str:
        filename = self._generate_filename("monthly_report", f"{year}-{month:02d}", "pdf")
        filepath = os.path.join(self.reports_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                rightMargin=2 * cm, leftMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, spaceAfter=20, alignment=1)
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=10)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10, leading=14)
        try:
            title_style.fontName = 'STSong-Light'
            heading_style.fontName = 'STSong-Light'
            normal_style.fontName = 'STSong-Light'
        except:
            pass

        story = []
        story.append(Paragraph(f"{year}-{month:02d} 月度佣金与返利分析报告", title_style))
        story.append(Spacer(1, 0.5 * cm))

        s = data["summary"]
        story.append(Paragraph("一、报告摘要", heading_style))
        summary_data = [
            ["指标", "数值"],
            ["佣金总金额", f"¥ {s['total_commission']:,.2f}"],
            ["返利总金额", f"¥ {s['total_rebate']:,.2f}"],
            ["总成本", f"¥ {s['total_cost']:,.2f}"],
            ["销售人员数", str(s['salesperson_count'])],
            ["人均佣金", f"¥ {s['avg_commission_per_person']:,.2f}"],
            ["渠道商数", str(s['partner_count'])],
            ["平均返利", f"¥ {s['avg_rebate_per_partner']:,.2f}"],
            ["冻结返利金额", f"¥ {s['frozen_rebate_amount']:,.2f}"],
        ]
        t = Table(summary_data, colWidths=[8 * cm, 6 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

        trend_img = self._generate_trend_chart(data["cost_trend"], year, month)
        if trend_img:
            story.append(Paragraph("二、成本趋势图", heading_style))
            story.append(Image(trend_img, width=16 * cm, height=8 * cm))
            story.append(PageBreak())

        story.append(Paragraph("三、产品类别佣金分布", heading_style))
        cat_data = [["产品类别", "佣金金额", "占比"]]
        total_cat = sum(data["by_category"].values()) or 1
        for k, v in sorted(data["by_category"].items(), key=lambda x: x[1], reverse=True):
            cat_data.append([k, f"¥ {v:,.2f}", f"{v / total_cat * 100:.1f}%"])
        t2 = Table(cat_data, colWidths=[6 * cm, 5 * cm, 4 * cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("四、Top 10 销售人员", heading_style))
        sp_data = [["排名", "销售人员", "佣金金额"]]
        for i, (sp_id, amt) in enumerate(data["top_salespersons"], 1):
            sp = self.db.query(Salesperson).filter(Salesperson.id == sp_id).first()
            name = sp.user.full_name if sp and sp.user else f"ID:{sp_id}"
            sp_data.append([str(i), name, f"¥ {amt:,.2f}"])
        t3 = Table(sp_data, colWidths=[3 * cm, 8 * cm, 5 * cm])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t3)

        doc.build(story)
        return filepath

    def _generate_trend_chart(self, trend: List[Dict], year: int, month: int) -> Optional[str]:
        try:
            fig, ax = plt.subplots(figsize=(10, 5))
            periods = [t["period"] for t in trend]
            amounts = [t["commission"] for t in trend]
            ax.plot(periods, amounts, marker='o', linewidth=2, markersize=6, color='#2563eb')
            ax.fill_between(periods, amounts, alpha=0.1, color='#2563eb')
            ax.set_title(f"佣金成本趋势 (近{len(trend)}个月)", fontsize=14, fontweight='bold')
            ax.set_xlabel("月份")
            ax.set_ylabel("佣金金额 (元)")
            ax.grid(True, alpha=0.3)
            for i, (p, a) in enumerate(zip(periods, amounts)):
                ax.annotate(f"{a:,.0f}", (p, a), textcoords="offset points",
                            xytext=(0, 10), ha='center', fontsize=9)
            plt.tight_layout()
            img_path = os.path.join(self.reports_dir, f"trend_{year}{month:02d}.png")
            fig.savefig(img_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            return img_path
        except Exception as e:
            print(f"图表生成失败: {e}")
            return None

    def export_commissions_excel(self, records: List[CommissionRecord]) -> bytes:
        """批量导出佣金明细为Excel"""
        data = []
        for r in records:
            data.append({
                "记录编号": r.record_code,
                "周期": f"{r.period_year}-{r.period_month:02d}",
                "销售人员": r.salesperson.user.full_name if r.salesperson and r.salesperson.user else "",
                "订单号": r.order.order_number if r.order else "",
                "产品类别": r.product_category.value if r.product_category else "",
                "客户等级": r.customer_level.value if r.customer_level else "",
                "计算基数": r.base_amount,
                "佣金率": f"{r.commission_rate * 100:.2f}%",
                "基础佣金": r.base_commission,
                "奖励金额": r.bonus_amount,
                "总佣金": r.total_commission,
                "审批状态": r.approval_status.value,
                "是否已付": "是" if r.is_paid else "否",
                "创建时间": r.created_at.isoformat() if r.created_at else ""
            })
        output = io.BytesIO()
        df = pd.DataFrame(data)
        df.to_excel(output, index=False, engine='openpyxl')
        return output.getvalue()

    def export_rebates_excel(self, records: List[RebateRecord]) -> bytes:
        """批量导出返利明细为Excel"""
        data = []
        for r in records:
            data.append({
                "记录编号": r.record_code,
                "周期": f"{r.period_year} Q{r.period_quarter}",
                "渠道商": r.channel_partner.partner_name if r.channel_partner else "",
                "累计销售额": r.total_sales,
                "合同比例": f"{r.contract_ratio * 100:.0f}%",
                "调整后销售额": r.adjusted_sales,
                "返利率": f"{r.rebate_rate * 100:.2f}%",
                "基础返利": r.base_rebate,
                "奖励返利": r.bonus_rebate,
                "总返利": r.total_rebate,
                "预算金额": r.budget_amount,
                "预算利用率": f"{r.budget_utilization:.1f}%",
                "状态": r.status.value,
                "是否冻结": "是" if r.is_frozen else "否",
                "创建时间": r.created_at.isoformat() if r.created_at else ""
            })
        output = io.BytesIO()
        df = pd.DataFrame(data)
        df.to_excel(output, index=False, engine='openpyxl')
        return output.getvalue()
