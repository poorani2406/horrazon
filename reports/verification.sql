SELECT 'campaigns' AS table_name,COUNT(*) FROM mart.dim_campaign
UNION ALL SELECT 'customers',COUNT(*) FROM mart.dim_customer
UNION ALL SELECT 'ad_rows',COUNT(*) FROM mart.fact_ad_spend_daily
UNION ALL SELECT 'leads',COUNT(*) FROM mart.fact_leads
UNION ALL SELECT 'orders',COUNT(*) FROM mart.fact_orders
UNION ALL SELECT 'items',COUNT(*) FROM mart.fact_order_items;
SELECT SUM(spend) AS total_spend FROM mart.fact_ad_spend_daily;
SELECT status,SUM(total_amount) FROM mart.fact_orders GROUP BY status;
SELECT COUNT(*) AS unmatched_leads FROM mart.fact_leads WHERE campaign_id IS NULL;
SELECT COUNT(*) AS unmatched_orders FROM mart.fact_orders WHERE customer_id IS NULL;
