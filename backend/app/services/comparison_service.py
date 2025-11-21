"""
Comparison service for period-over-period and group-over-group analysis.

Enables queries like:
- "This quarter vs last quarter revenue"
- "Q1 2024 vs Q1 2023 sales"
- "This month vs last month invoice count"
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.postgres_service import PostgresService

logger = logging.getLogger(__name__)


class ComparisonService:
    """Service for comparing aggregations across time periods or groups."""

    def __init__(self, db: Session):
        self.db = db
        self.postgres = PostgresService(db)

    async def compare_periods(
        self,
        field: str,
        agg_type: str,
        period1: Dict[str, str],
        period2: Dict[str, str],
        filters: Optional[Dict[str, Any]] = None,
        period1_name: Optional[str] = None,
        period2_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare aggregations across two time periods.

        Args:
            field: Field to aggregate
            agg_type: Aggregation type (sum, avg, count, etc.)
            period1: First period {"from": "2024-10-01", "to": "2024-12-31"}
            period2: Second period {"from": "2024-07-01", "to": "2024-09-30"}
            filters: Additional filters to apply to both periods
            period1_name: Human-readable name for period 1 (e.g., "Q4 2024")
            period2_name: Human-readable name for period 2 (e.g., "Q3 2024")

        Returns:
            Comparison results with change metrics
        """
        # Build filters for each period
        filters1 = self._merge_filters(filters, {"date_range": period1})
        filters2 = self._merge_filters(filters, {"date_range": period2})

        # Execute aggregations for both periods
        result1 = await self.postgres.get_aggregations(
            field=field,
            agg_type=agg_type,
            filters=filters1
        )

        result2 = await self.postgres.get_aggregations(
            field=field,
            agg_type=agg_type,
            filters=filters2
        )

        # Extract values based on aggregation type
        agg_name = f"{field}_{agg_type}"

        if agg_type in ["sum", "avg", "min", "max"]:
            value1 = result1.get(agg_name, {}).get(agg_type, 0)
            value2 = result2.get(agg_name, {}).get(agg_type, 0)
            count1 = result1.get(agg_name, {}).get("count", 0)
            count2 = result2.get(agg_name, {}).get("count", 0)

        elif agg_type == "count":
            value1 = result1.get(agg_name, {}).get("count", 0)
            value2 = result2.get(agg_name, {}).get("count", 0)
            count1 = value1
            count2 = value2

        elif agg_type == "cardinality":
            value1 = result1.get(agg_name, {}).get("value", 0)
            value2 = result2.get(agg_name, {}).get("value", 0)
            count1 = value1
            count2 = value2

        else:
            # For complex aggregations, return raw results
            return {
                "period1": {
                    "name": period1_name or self._format_period_name(period1),
                    "range": period1,
                    "result": result1
                },
                "period2": {
                    "name": period2_name or self._format_period_name(period2),
                    "range": period2,
                    "result": result2
                },
                "comparison_type": "complex"
            }

        # Calculate comparison metrics
        change = value1 - value2
        change_pct = (change / value2 * 100) if value2 != 0 else float('inf')
        trend = "up" if change > 0 else ("down" if change < 0 else "flat")

        return {
            "period1": {
                "name": period1_name or self._format_period_name(period1),
                "range": period1,
                "value": float(value1) if value1 is not None else 0.0,
                "count": count1
            },
            "period2": {
                "name": period2_name or self._format_period_name(period2),
                "range": period2,
                "value": float(value2) if value2 is not None else 0.0,
                "count": count2
            },
            "change": {
                "absolute": float(change),
                "percentage": round(change_pct, 2) if change_pct != float('inf') else None,
                "trend": trend
            },
            "field": field,
            "aggregation_type": agg_type
        }

    async def compare_groups(
        self,
        field: str,
        agg_type: str,
        group_field: str,
        groups: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compare aggregations across different groups.

        Example: Compare revenue by template type (Invoice vs Receipt vs Contract)

        Args:
            field: Field to aggregate
            agg_type: Aggregation type (sum, avg, count, etc.)
            group_field: Field to group by (e.g., "template_name")
            groups: List of group values to compare
            filters: Additional filters

        Returns:
            Comparison results across groups
        """
        results = {}

        for group_value in groups:
            # Add group filter
            group_filters = self._merge_filters(
                filters,
                {group_field: group_value}
            )

            # Execute aggregation
            result = await self.postgres.get_aggregations(
                field=field,
                agg_type=agg_type,
                filters=group_filters
            )

            agg_name = f"{field}_{agg_type}"

            if agg_type in ["sum", "avg", "min", "max"]:
                value = result.get(agg_name, {}).get(agg_type, 0)
                count = result.get(agg_name, {}).get("count", 0)
            elif agg_type == "count":
                value = result.get(agg_name, {}).get("count", 0)
                count = value
            elif agg_type == "cardinality":
                value = result.get(agg_name, {}).get("value", 0)
                count = value
            else:
                value = result
                count = 0

            results[group_value] = {
                "value": float(value) if isinstance(value, (int, float)) else value,
                "count": count
            }

        # Calculate comparisons
        values = [r["value"] for r in results.values() if isinstance(r["value"], (int, float))]

        if values:
            total = sum(values)
            max_value = max(values)
            min_value = min(values)
            avg_value = total / len(values) if values else 0

            # Find top and bottom groups
            sorted_groups = sorted(
                results.items(),
                key=lambda x: x[1]["value"] if isinstance(x[1]["value"], (int, float)) else 0,
                reverse=True
            )

            top_group = sorted_groups[0] if sorted_groups else (None, None)
            bottom_group = sorted_groups[-1] if sorted_groups else (None, None)

            comparison_stats = {
                "total": total,
                "max": max_value,
                "min": min_value,
                "avg": avg_value,
                "top_group": {
                    "name": top_group[0],
                    "value": top_group[1]["value"],
                    "count": top_group[1]["count"]
                } if top_group[0] else None,
                "bottom_group": {
                    "name": bottom_group[0],
                    "value": bottom_group[1]["value"],
                    "count": bottom_group[1]["count"]
                } if bottom_group[0] else None
            }
        else:
            comparison_stats = None

        return {
            "groups": results,
            "group_field": group_field,
            "field": field,
            "aggregation_type": agg_type,
            "comparison_stats": comparison_stats
        }

    def _merge_filters(
        self,
        base_filters: Optional[Dict[str, Any]],
        additional_filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two filter dictionaries."""
        if not base_filters:
            return additional_filters

        merged = base_filters.copy()
        merged.update(additional_filters)
        return merged

    def _format_period_name(self, period: Dict[str, str]) -> str:
        """Generate human-readable period name from date range."""
        from_date = period.get("from", "")
        to_date = period.get("to", "")

        if not from_date or not to_date:
            return "Unknown period"

        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))

            # Check if it's a quarter
            if self._is_quarter(from_dt, to_dt):
                quarter = (from_dt.month - 1) // 3 + 1
                return f"Q{quarter} {from_dt.year}"

            # Check if it's a full month
            if self._is_month(from_dt, to_dt):
                return from_dt.strftime("%B %Y")

            # Check if it's a full year
            if self._is_year(from_dt, to_dt):
                return str(from_dt.year)

            # Default to date range
            return f"{from_dt.strftime('%Y-%m-%d')} to {to_dt.strftime('%Y-%m-%d')}"

        except Exception:
            return f"{from_date} to {to_date}"

    def _is_quarter(self, from_dt: datetime, to_dt: datetime) -> bool:
        """Check if date range represents a full quarter."""
        # Quarter start months: 1, 4, 7, 10
        if from_dt.month not in [1, 4, 7, 10] or from_dt.day != 1:
            return False

        # Calculate expected end date (3 months later, last day of month)
        if from_dt.month in [1, 4, 7]:
            expected_end_month = from_dt.month + 3
            expected_end_year = from_dt.year
        else:  # month == 10
            expected_end_month = 1
            expected_end_year = from_dt.year + 1

        # Check if to_dt is approximately 3 months later
        return abs((to_dt - from_dt).days - 90) < 5

    def _is_month(self, from_dt: datetime, to_dt: datetime) -> bool:
        """Check if date range represents a full month."""
        if from_dt.day != 1:
            return False

        # Check if to_dt is approximately 1 month later
        return abs((to_dt - from_dt).days - 30) < 5

    def _is_year(self, from_dt: datetime, to_dt: datetime) -> bool:
        """Check if date range represents a full year."""
        if from_dt.month != 1 or from_dt.day != 1:
            return False

        # Check if to_dt is approximately 1 year later
        return abs((to_dt - from_dt).days - 365) < 5

    async def get_trend(
        self,
        field: str,
        agg_type: str,
        interval: str = "month",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get trend data for a field over time.

        Args:
            field: Field to aggregate
            agg_type: Aggregation type (sum, avg, count, etc.)
            interval: Time interval (day, week, month, quarter, year)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            filters: Additional filters

        Returns:
            Time-series data with trend analysis
        """
        # Use date_histogram aggregation
        date_field = filters.get("date_field", "date") if filters else "date"

        # Build filters with date range
        agg_filters = filters.copy() if filters else {}
        if start_date and end_date:
            agg_filters["date_range"] = {"from": start_date, "to": end_date}

        # Execute date_histogram aggregation
        result = await self.postgres.get_aggregations(
            field=date_field,
            agg_type="date_histogram",
            agg_config={"interval": interval},
            filters=agg_filters
        )

        agg_name = f"{date_field}_date_histogram"
        buckets = result.get(agg_name, {}).get("buckets", [])

        # For each bucket, calculate the metric
        trend_data = []

        for bucket in buckets:
            bucket_date = bucket["key"]
            doc_count = bucket["doc_count"]

            # Get aggregation for this specific time bucket
            bucket_filters = agg_filters.copy()
            bucket_filters["date_range"] = {"from": bucket_date, "to": bucket_date}

            bucket_result = await self.postgres.get_aggregations(
                field=field,
                agg_type=agg_type,
                filters=bucket_filters
            )

            metric_name = f"{field}_{agg_type}"

            if agg_type in ["sum", "avg", "min", "max"]:
                value = bucket_result.get(metric_name, {}).get(agg_type, 0)
            elif agg_type == "count":
                value = bucket_result.get(metric_name, {}).get("count", 0)
            elif agg_type == "cardinality":
                value = bucket_result.get(metric_name, {}).get("value", 0)
            else:
                value = 0

            trend_data.append({
                "date": bucket_date,
                "value": float(value) if value else 0.0,
                "count": doc_count
            })

        # Calculate trend statistics
        values = [d["value"] for d in trend_data]

        if len(values) >= 2:
            # Calculate simple trend (first vs last)
            first_value = values[0]
            last_value = values[-1]
            trend_change = last_value - first_value
            trend_pct = (trend_change / first_value * 100) if first_value != 0 else float('inf')
            trend_direction = "up" if trend_change > 0 else ("down" if trend_change < 0 else "flat")

            trend_stats = {
                "direction": trend_direction,
                "change": trend_change,
                "change_percentage": round(trend_pct, 2) if trend_pct != float('inf') else None,
                "average": sum(values) / len(values),
                "max": max(values),
                "min": min(values)
            }
        else:
            trend_stats = None

        return {
            "data": trend_data,
            "field": field,
            "aggregation_type": agg_type,
            "interval": interval,
            "trend_stats": trend_stats
        }
