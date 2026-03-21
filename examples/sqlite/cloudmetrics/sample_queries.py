"""Sample queries for the CloudMetrics Data Agent demo."""

SAMPLE_QUERIES = [
    # Simple (single table)
    "How many customers do we have?",
    "What are our plan names and prices?",

    # Medium (joins, filters, grouping)
    "What is our total MRR right now?",
    "Show me the number of customers by industry",
    "Which plan has the most active subscriptions?",

    # Advanced (multi-join, date logic)
    "What is the monthly revenue trend for the last 12 months?",
    "Which industry has the highest average MRR per customer?",
    "What is the average support ticket resolution time in hours, broken down by priority?",

    # Complex (multi-table, subqueries)
    "Show me the top 5 customers by total revenue who have also filed more than 3 support tickets",
    "What is the monthly churn rate over the past 6 months?",
]

FOLLOW_UP_SEQUENCE = [
    "What is our total MRR?",
    "Break that down by plan",
    "Now show only annual billing",
]
