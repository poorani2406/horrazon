CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE TABLE IF NOT EXISTS raw.ads(id BIGSERIAL PRIMARY KEY,run_id UUID,loaded_at TIMESTAMPTZ DEFAULT now(),payload JSONB);
CREATE TABLE IF NOT EXISTS raw.crm(id BIGSERIAL PRIMARY KEY,run_id UUID,loaded_at TIMESTAMPTZ DEFAULT now(),file_name TEXT,payload JSONB);
CREATE TABLE IF NOT EXISTS raw.orders(id BIGSERIAL PRIMARY KEY,run_id UUID,loaded_at TIMESTAMPTZ DEFAULT now(),payload JSONB);
CREATE TABLE IF NOT EXISTS staging.ads(campaign_id TEXT,campaign_name TEXT,platform TEXT,ad_date DATE,spend NUMERIC(14,2),impressions BIGINT,clicks BIGINT,updated_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS staging.leads(lead_id TEXT,phone TEXT,email TEXT,utm_campaign TEXT,created_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS staging.orders(order_id TEXT,phone TEXT,status TEXT,total NUMERIC(14,2),order_ts TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS mart.dim_campaign(campaign_id TEXT PRIMARY KEY,platform TEXT NOT NULL,campaign_name TEXT NOT NULL,campaign_key TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mart.dim_customer(customer_id BIGSERIAL PRIMARY KEY,phone TEXT UNIQUE CHECK(phone IS NULL OR phone ~ '^[0-9]{10}$'));
CREATE TABLE IF NOT EXISTS mart.fact_ad_spend_daily(campaign_id TEXT REFERENCES mart.dim_campaign,platform TEXT,ad_date DATE,spend NUMERIC(14,2) CHECK(spend>=0),impressions BIGINT CHECK(impressions>=0),clicks BIGINT CHECK(clicks>=0 AND clicks<=impressions),updated_at TIMESTAMPTZ,PRIMARY KEY(campaign_id,platform,ad_date));
CREATE TABLE IF NOT EXISTS mart.fact_leads(lead_id TEXT PRIMARY KEY,customer_id BIGINT REFERENCES mart.dim_customer,campaign_id TEXT REFERENCES mart.dim_campaign,lead_name TEXT,email TEXT,email_valid BOOLEAN,created_at TIMESTAMPTZ,campaign_matched BOOLEAN);
CREATE TABLE IF NOT EXISTS mart.fact_orders(order_id TEXT PRIMARY KEY,customer_id BIGINT REFERENCES mart.dim_customer,order_ts TIMESTAMPTZ,updated_at TIMESTAMPTZ,status TEXT CHECK(status IN('PLACED','PAID','SHIPPED','DELIVERED','CANCELLED','RETURNED')),payment_mode TEXT,total_amount NUMERIC(14,2),customer_matched BOOLEAN);
CREATE TABLE IF NOT EXISTS mart.fact_order_items(order_id TEXT REFERENCES mart.fact_orders ON DELETE CASCADE,line_no INT,sku TEXT,qty INT CHECK(qty>0),unit_price NUMERIC(14,2),PRIMARY KEY(order_id,line_no));
CREATE TABLE IF NOT EXISTS mart.rejected_rows(id BIGSERIAL PRIMARY KEY,run_id UUID,source TEXT,rule_name TEXT,reason TEXT,original_data JSONB, fingerprint TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS mart.pipeline_runs(
 run_id UUID PRIMARY KEY, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
 ads_read INT, ads_loaded INT, ads_rejected INT, ads_duplicates INT,
 crm_read INT, crm_loaded INT, crm_rejected INT, crm_duplicates INT,
 orders_read INT, orders_loaded INT, orders_rejected INT, orders_duplicates INT,
 status TEXT);
CREATE TABLE IF NOT EXISTS mart.processed_files(file_name TEXT PRIMARY KEY,processed_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE IF NOT EXISTS mart.watermarks(source_name TEXT PRIMARY KEY,last_updated_at TIMESTAMPTZ NOT NULL);
