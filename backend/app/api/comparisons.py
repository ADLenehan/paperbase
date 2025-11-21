"""
API endpoints for comparison and trend analysis.

Enables period-over-period, group-over-group, and trend analysis.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.settings import User
from app.services.comparison_service import ComparisonService

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


# Request/Response Models

class PeriodRange(BaseModel):
    """Time period range."""
    from_date: str = Field(..., alias="from", description="Start date (ISO format)")
    to_date: str = Field(..., alias="to", description="End date (ISO format)")

    class Config:
        populate_by_name = True


class ComparePeriodsRequest(BaseModel):
    """Request model for period-over-period comparison."""
    field: str = Field(..., description="Field to aggregate")
    aggregation_type: str = Field(..., description="Aggregation type (sum, avg, count, etc.)")
    period1: PeriodRange = Field(..., description="First period")
    period2: PeriodRange = Field(..., description="Second period")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    period1_name: Optional[str] = Field(None, description="Name for period 1 (e.g., 'Q4 2024')")
    period2_name: Optional[str] = Field(None, description="Name for period 2 (e.g., 'Q3 2024')")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "invoice_total",
                "aggregation_type": "sum",
                "period1": {"from": "2024-10-01", "to": "2024-12-31"},
                "period2": {"from": "2024-07-01", "to": "2024-09-30"},
                "period1_name": "Q4 2024",
                "period2_name": "Q3 2024"
            }
        }


class CompareGroupsRequest(BaseModel):
    """Request model for group-over-group comparison."""
    field: str = Field(..., description="Field to aggregate")
    aggregation_type: str = Field(..., description="Aggregation type (sum, avg, count, etc.)")
    group_field: str = Field(..., description="Field to group by")
    groups: List[str] = Field(..., description="List of group values to compare")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "invoice_total",
                "aggregation_type": "sum",
                "group_field": "template_name",
                "groups": ["Invoice", "Receipt", "Contract"]
            }
        }


class TrendRequest(BaseModel):
    """Request model for trend analysis."""
    field: str = Field(..., description="Field to aggregate")
    aggregation_type: str = Field(..., description="Aggregation type (sum, avg, count, etc.)")
    interval: str = Field("month", description="Time interval (day, week, month, quarter, year)")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "invoice_total",
                "aggregation_type": "sum",
                "interval": "month",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            }
        }


# Endpoints

@router.post("/periods")
async def compare_periods(
    request: ComparePeriodsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Compare aggregations across two time periods.

    Example use cases:
    - This quarter vs last quarter revenue
    - January vs February invoice count
    - 2024 vs 2023 total sales

    Returns:
        Comparison results with change metrics (absolute, percentage, trend)
    """
    service = ComparisonService(db)

    try:
        result = await service.compare_periods(
            field=request.field,
            agg_type=request.aggregation_type,
            period1={"from": request.period1.from_date, "to": request.period1.to_date},
            period2={"from": request.period2.from_date, "to": request.period2.to_date},
            filters=request.filters,
            period1_name=request.period1_name,
            period2_name=request.period2_name
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.post("/groups")
async def compare_groups(
    request: CompareGroupsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Compare aggregations across different groups.

    Example use cases:
    - Revenue by template type (Invoice vs Receipt vs Contract)
    - Invoice count by vendor
    - Average contract value by status

    Returns:
        Comparison results across groups with statistics
    """
    service = ComparisonService(db)

    try:
        result = await service.compare_groups(
            field=request.field,
            agg_type=request.aggregation_type,
            group_field=request.group_field,
            groups=request.groups,
            filters=request.filters
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Group comparison failed: {str(e)}")


@router.post("/trend")
async def get_trend(
    request: TrendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get trend data for a field over time.

    Example use cases:
    - Monthly revenue trend for 2024
    - Weekly invoice count
    - Quarterly sales growth

    Returns:
        Time-series data with trend statistics
    """
    service = ComparisonService(db)

    try:
        result = await service.get_trend(
            field=request.field,
            agg_type=request.aggregation_type,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            filters=request.filters
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trend analysis failed: {str(e)}")


@router.get("/quick/{comparison_type}")
async def quick_comparison(
    comparison_type: str,
    field: str,
    aggregation_type: str = "sum",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Quick comparisons with preset periods.

    Args:
        comparison_type: One of:
            - this_vs_last_quarter
            - this_vs_last_month
            - this_vs_last_year
            - ytd_vs_last_ytd (year-to-date comparison)
        field: Field to aggregate
        aggregation_type: Aggregation type (default: sum)

    Returns:
        Comparison results
    """
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta

    service = ComparisonService(db)
    now = datetime.utcnow()

    # Calculate periods based on comparison type
    if comparison_type == "this_vs_last_quarter":
        # Current quarter
        current_quarter = (now.month - 1) // 3
        period1_start = datetime(now.year, current_quarter * 3 + 1, 1)
        period1_end = period1_start + relativedelta(months=3)

        # Last quarter
        period2_start = period1_start - relativedelta(months=3)
        period2_end = period1_start

        period1_name = f"Q{current_quarter + 1} {now.year}"
        period2_name = f"Q{current_quarter} {now.year if current_quarter > 0 else now.year - 1}"

    elif comparison_type == "this_vs_last_month":
        # Current month
        period1_start = datetime(now.year, now.month, 1)
        period1_end = period1_start + relativedelta(months=1)

        # Last month
        period2_start = period1_start - relativedelta(months=1)
        period2_end = period1_start

        period1_name = period1_start.strftime("%B %Y")
        period2_name = period2_start.strftime("%B %Y")

    elif comparison_type == "this_vs_last_year":
        # Current year
        period1_start = datetime(now.year, 1, 1)
        period1_end = datetime(now.year + 1, 1, 1)

        # Last year
        period2_start = datetime(now.year - 1, 1, 1)
        period2_end = datetime(now.year, 1, 1)

        period1_name = str(now.year)
        period2_name = str(now.year - 1)

    elif comparison_type == "ytd_vs_last_ytd":
        # Year-to-date this year
        period1_start = datetime(now.year, 1, 1)
        period1_end = now

        # Year-to-date last year (same date range)
        period2_start = datetime(now.year - 1, 1, 1)
        period2_end = datetime(now.year - 1, now.month, now.day)

        period1_name = f"YTD {now.year}"
        period2_name = f"YTD {now.year - 1}"

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown comparison type: {comparison_type}. "
                   f"Valid options: this_vs_last_quarter, this_vs_last_month, "
                   f"this_vs_last_year, ytd_vs_last_ytd"
        )

    try:
        result = await service.compare_periods(
            field=field,
            agg_type=aggregation_type,
            period1={"from": period1_start.isoformat(), "to": period1_end.isoformat()},
            period2={"from": period2_start.isoformat(), "to": period2_end.isoformat()},
            period1_name=period1_name,
            period2_name=period2_name
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick comparison failed: {str(e)}")
