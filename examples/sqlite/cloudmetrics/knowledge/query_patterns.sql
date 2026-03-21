-- Pattern: Total MRR
-- Description: Shows current total monthly recurring revenue from active subscriptions
-- Keywords: mrr, revenue, recurring, total, current
SELECT SUM(mrr) AS total_mrr
FROM subscriptions
WHERE status = 'active';

-- Pattern: MRR by Plan
-- Description: Breaks down MRR by plan tier with subscription counts
-- Keywords: mrr, plan, breakdown, tier, revenue
SELECT p.plan_name,
       COUNT(*) AS active_subscriptions,
       SUM(s.mrr) AS total_mrr,
       ROUND(AVG(s.mrr), 2) AS avg_mrr
FROM subscriptions s
JOIN plans p ON s.plan_id = p.plan_id
WHERE s.status = 'active'
GROUP BY p.plan_name
ORDER BY total_mrr DESC;

-- Pattern: Monthly Revenue Trend
-- Description: Shows paid invoice revenue by month over time
-- Keywords: revenue, monthly, trend, time, paid, invoices
SELECT strftime('%Y-%m', invoice_date) AS month,
       SUM(amount) AS total_revenue,
       COUNT(*) AS invoice_count
FROM invoices
WHERE status = 'paid'
GROUP BY strftime('%Y-%m', invoice_date)
ORDER BY month;

-- Pattern: Customer Count by Industry
-- Description: Shows number of customers per industry vertical
-- Keywords: customers, industry, count, distribution, breakdown
SELECT industry,
       COUNT(*) AS customer_count
FROM customers
GROUP BY industry
ORDER BY customer_count DESC;

-- Pattern: Average Ticket Resolution Time by Priority
-- Description: Calculates average resolution time in hours grouped by priority
-- Keywords: ticket, resolution, time, priority, average, hours, support
SELECT priority,
       COUNT(*) AS ticket_count,
       ROUND(AVG((julianday(resolved_at) - julianday(created_at)) * 24), 1) AS avg_resolution_hours
FROM support_tickets
WHERE resolved_at IS NOT NULL
GROUP BY priority
ORDER BY CASE priority
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 4
END;

-- Pattern: Top Customers by Revenue
-- Description: Lists top N customers by total paid invoice amount
-- Keywords: top, customers, revenue, highest, biggest, best
SELECT c.company_name,
       c.industry,
       SUM(i.amount) AS total_revenue,
       COUNT(i.invoice_id) AS invoice_count
FROM customers c
JOIN invoices i ON c.customer_id = i.customer_id
WHERE i.status = 'paid'
GROUP BY c.customer_id, c.company_name, c.industry
ORDER BY total_revenue DESC
LIMIT 10;

-- Pattern: Subscription Status Distribution
-- Description: Shows count of subscriptions by current status
-- Keywords: subscription, status, active, churned, trial, paused, distribution
SELECT status,
       COUNT(*) AS subscription_count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM subscriptions), 1) AS percentage
FROM subscriptions
GROUP BY status
ORDER BY subscription_count DESC;

-- Pattern: Churn by Month
-- Description: Shows number of subscriptions that churned each month
-- Keywords: churn, churned, monthly, rate, loss, cancel
SELECT strftime('%Y-%m', end_date) AS churn_month,
       COUNT(*) AS churned_subscriptions
FROM subscriptions
WHERE status = 'churned' AND end_date IS NOT NULL
GROUP BY strftime('%Y-%m', end_date)
ORDER BY churn_month;
