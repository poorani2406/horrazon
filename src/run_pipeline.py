import os, csv, json, time, uuid, hashlib
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import requests, psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv
from src.cleaning import clean_phone,money,day,timestamp,campaign_key,status,email_valid

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/".env")
DB=os.getenv("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/meridian")
API=os.getenv("ADS_API_URL","http://127.0.0.1:8000/ads")

def get_ads(updated_after=None):
    page=1; result=[]; delay=.5
    while True:
        for attempt in range(5):
            try:
                response=requests.get(API,params={"page":page,"page_size":100,"updated_after":updated_after},timeout=15)
                response.raise_for_status(); body=response.json(); break
            except requests.RequestException:
                if attempt==4: raise
                time.sleep(delay); delay*=2
        result.extend(body["data"])
        if not body["has_next"]: return result
        page+=1

def main():
    run_id=uuid.uuid4(); started=datetime.now(timezone.utc)
    with psycopg.connect(DB) as conn:
        conn.execute((ROOT/"sql/schema.sql").read_text(encoding="utf-8"))
        wm=conn.execute("SELECT last_updated_at FROM mart.watermarks WHERE source_name='ads'").fetchone()
        ads_raw=get_ads(wm[0].isoformat() if wm else None)
        crm_raw=[]
        for path in sorted((ROOT/"sources/crm").glob("leads_*.csv")):
            if conn.execute("SELECT 1 FROM mart.processed_files WHERE file_name=%s",(path.name,)).fetchone(): continue
            with path.open(encoding="utf-8-sig",newline="") as f:
                for r in csv.DictReader(f):
                    r["_file"]=path.name; crm_raw.append(r)
        store_path=ROOT/"sources/store/orders.json"
        orders_raw=json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else []

        # RAW: retain original records before cleaning.
        for r in ads_raw: conn.execute("INSERT INTO raw.ads(run_id,payload) VALUES(%s,%s)",(run_id,Jsonb(r)))
        for r in crm_raw: conn.execute("INSERT INTO raw.crm(run_id,file_name,payload) VALUES(%s,%s,%s)",(run_id,r["_file"],Jsonb(r)))
        for r in orders_raw: conn.execute("INSERT INTO raw.orders(run_id,payload) VALUES(%s,%s)",(run_id,Jsonb(r)))

        rejected={"ads":[],"crm":[],"store":[]}; dups={"ads":0,"crm":0,"store":0}
        # Clean and deduplicate ads: latest updated_at for campaign/platform/day wins.
        ad_map={}
        for r in ads_raw:
            try:
                spend=money(r["spend"]); ad_day=day(r["date"]); imp=int(r["impressions"]); clicks=int(r["clicks"]); upd=timestamp(r["updated_at"])
                if spend<0: raise ValueError("negative_spend")
                if imp<0: raise ValueError("negative_impressions")
                if clicks<0 or clicks>imp: raise ValueError("clicks_exceed_impressions")
                key=(r["campaign_id"],r["platform"],ad_day)
                clean={**r,"spend":spend,"ad_day":ad_day,"impressions":imp,"clicks":clicks,"updated":upd,"key":campaign_key(r["campaign_name"])}
                if key in ad_map:
                    dups["ads"]+=1
                    if upd>ad_map[key]["updated"]: ad_map[key]=clean
                else: ad_map[key]=clean
            except Exception as e: rejected["ads"].append((r,str(e)))
        ads=list(ad_map.values())

        # CRM: lead_id is unique; first valid occurrence is retained.
        lead_map={}
        for r in crm_raw:
            try:
                lid=str(r["lead_id"]).strip()
                if not lid: raise ValueError("missing_lead_id")
                clean={**r,"lead_id":lid,"phone":clean_phone(r.get("phone")),"email":(r.get("email") or "").strip().lower(),
                       "email_ok":email_valid(r.get("email")),"created":timestamp(r["created_at"]),"utm_key":campaign_key(r.get("utm_campaign"))}
                if lid in lead_map: dups["crm"]+=1
                else: lead_map[lid]=clean
            except Exception as e: rejected["crm"].append((r,str(e)))
        leads=list(lead_map.values())

        # Orders: latest updated_at per order_id wins.
        order_map={}
        for r in orders_raw:
            try:
                oid=str(r["order_id"]).strip()
                phone=clean_phone(r.get("customer_phone") or r.get("phone_number"))
                order_ts=timestamp(r["order_ts"]); upd=timestamp(r.get("updated_at") or r["order_ts"])
                st=status(r["status"]); total=money(r["total_amount"],paise=True)
                items=[]; item_sum=Decimal("0.00")
                for item in r.get("items",[]):
                    qty=int(item["qty"]); price=money(item["unit_price"])
                    if qty<=0: raise ValueError("quantity_not_positive")
                    if price<0: raise ValueError("negative_unit_price")
                    items.append((item.get("sku","UNKNOWN"),qty,price)); item_sum+=qty*price
                if not items: raise ValueError("no_order_items")
                if abs(total-item_sum)>Decimal("1.00"): raise ValueError("order_total_item_mismatch")
                clean={**r,"order_id":oid,"phone":phone,"order_time":order_ts,"updated":upd,"status_clean":st,"total":total,"clean_items":items}
                if oid in order_map:
                    dups["store"]+=1
                    if upd>order_map[oid]["updated"]: order_map[oid]=clean
                else: order_map[oid]=clean
            except Exception as e: rejected["store"].append((r,str(e)))
        orders=list(order_map.values())

        # STAGING contains typed cleaned rows; refreshed each run.
        conn.execute("TRUNCATE staging.ads,staging.leads,staging.orders")
        for r in ads:
            conn.execute("INSERT INTO staging.ads VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(r["campaign_id"],r["campaign_name"],r["platform"],r["ad_day"],r["spend"],r["impressions"],r["clicks"],r["updated"]))
        for r in leads:
            conn.execute("INSERT INTO staging.leads VALUES(%s,%s,%s,%s,%s)",(r["lead_id"],r["phone"],r["email"],r.get("utm_campaign"),r["created"]))
        for r in orders:
            conn.execute("INSERT INTO staging.orders VALUES(%s,%s,%s,%s,%s)",(r["order_id"],r["phone"],r["status_clean"],r["total"],r["order_time"]))

        # Rejections retain the original row and validation reason.
        for source, bad_rows in rejected.items():
            for original, reason in bad_rows:
                fingerprint=hashlib.sha256((source+json.dumps(original,sort_keys=True,ensure_ascii=False)+reason).encode("utf-8")).hexdigest()
                conn.execute("INSERT INTO mart.rejected_rows(run_id,source,rule_name,reason,original_data,fingerprint) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(fingerprint) DO NOTHING",
                             (run_id,source,source+"_validation",reason,Jsonb(original),fingerprint))

        # FINAL: dimensions and facts with natural keys and upserts.
        for r in ads:
            conn.execute("""INSERT INTO mart.dim_campaign VALUES(%s,%s,%s,%s)
              ON CONFLICT(campaign_id) DO UPDATE SET platform=EXCLUDED.platform,campaign_name=EXCLUDED.campaign_name,campaign_key=EXCLUDED.campaign_key""",
              (r["campaign_id"],r["platform"],r["campaign_name"].strip().title(),r["key"]))
            conn.execute("""INSERT INTO mart.fact_ad_spend_daily VALUES(%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(campaign_id,platform,ad_date) DO UPDATE SET spend=EXCLUDED.spend,impressions=EXCLUDED.impressions,clicks=EXCLUDED.clicks,updated_at=EXCLUDED.updated_at
              WHERE EXCLUDED.updated_at>mart.fact_ad_spend_daily.updated_at""",
              (r["campaign_id"],r["platform"],r["ad_day"],r["spend"],r["impressions"],r["clicks"],r["updated"]))

        campaign_lookup={k:v for v,k in conn.execute("SELECT campaign_id,campaign_key FROM mart.dim_campaign").fetchall()}
        def customer_id(phone):
            if not phone: return None
            return conn.execute("""INSERT INTO mart.dim_customer(phone) VALUES(%s)
              ON CONFLICT(phone) DO UPDATE SET phone=EXCLUDED.phone RETURNING customer_id""",(phone,)).fetchone()[0]

        for r in leads:
            cid=customer_id(r["phone"]); camp=campaign_lookup.get(r["utm_key"])
            conn.execute("""INSERT INTO mart.fact_leads VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(lead_id) DO UPDATE SET customer_id=EXCLUDED.customer_id,campaign_id=EXCLUDED.campaign_id,
              lead_name=EXCLUDED.lead_name,email=EXCLUDED.email,email_valid=EXCLUDED.email_valid,created_at=EXCLUDED.created_at,campaign_matched=EXCLUDED.campaign_matched""",
              (r["lead_id"],cid,camp,r.get("name"),r["email"],r["email_ok"],r["created"],camp is not None))

        for r in orders:
            cid=customer_id(r["phone"])
            conn.execute("""INSERT INTO mart.fact_orders VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(order_id) DO UPDATE SET customer_id=EXCLUDED.customer_id,order_ts=EXCLUDED.order_ts,
              updated_at=EXCLUDED.updated_at,status=EXCLUDED.status,payment_mode=EXCLUDED.payment_mode,
              total_amount=EXCLUDED.total_amount,customer_matched=EXCLUDED.customer_matched
              WHERE EXCLUDED.updated_at>mart.fact_orders.updated_at""",
              (r["order_id"],cid,r["order_time"],r["updated"],r["status_clean"],r.get("payment_mode","UNKNOWN"),r["total"],cid is not None))
            conn.execute("DELETE FROM mart.fact_order_items WHERE order_id=%s",(r["order_id"],))
            for n,(sku,qty,price) in enumerate(r["clean_items"],1):
                conn.execute("INSERT INTO mart.fact_order_items VALUES(%s,%s,%s,%s,%s)",(r["order_id"],n,sku,qty,price))

        # Mark CRM files processed only after all their rows were handled.
        for r in crm_raw:
            conn.execute("INSERT INTO mart.processed_files(file_name) VALUES(%s) ON CONFLICT DO NOTHING",(r["_file"],))
        for p in (ROOT/"sources/crm").glob("leads_*.csv"):
            conn.execute("INSERT INTO mart.processed_files(file_name) VALUES(%s) ON CONFLICT DO NOTHING",(p.name,))

        # Persist Ads watermark only after all transformations and loads have succeeded.
        if ads:
            latest=max(r["updated"] for r in ads)
            conn.execute("""INSERT INTO mart.watermarks(source_name,last_updated_at) VALUES('ads',%s)
              ON CONFLICT(source_name) DO UPDATE SET last_updated_at=GREATEST(mart.watermarks.last_updated_at,EXCLUDED.last_updated_at)""",(latest,))
        conn.execute("""INSERT INTO mart.pipeline_runs
          (run_id,started_at,ended_at,ads_read,ads_loaded,ads_rejected,ads_duplicates,
           crm_read,crm_loaded,crm_rejected,crm_duplicates,orders_read,orders_loaded,orders_rejected,orders_duplicates,status)
          VALUES(%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'SUCCESS')""",
          (run_id,started,len(ads_raw),len(ads),len(rejected["ads"]),dups["ads"],
           len(crm_raw),len(leads),len(rejected["crm"]),dups["crm"],
           len(orders_raw),len(orders),len(rejected["store"]),dups["store"]))
        for source, raw_count, good_count in [
            ("ads",len(ads_raw),len(ads)),("crm",len(crm_raw),len(leads)),("store",len(orders_raw),len(orders))]:
            print(f"{source.upper()}: read={raw_count}, valid_after_dedupe={good_count}, rejected={len(rejected[source])}, duplicates_removed={dups[source]}")
        print("\nFINAL TABLE COUNTS")
        for table in ["dim_campaign","dim_customer","fact_ad_spend_daily","fact_leads","fact_orders","fact_order_items","rejected_rows"]:
            print(table,conn.execute(f"SELECT COUNT(*) FROM mart.{table}").fetchone()[0])
        final_spend=conn.execute("SELECT COALESCE(SUM(spend),0) FROM mart.fact_ad_spend_daily").fetchone()[0]
        final_net_orders=conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM mart.fact_orders WHERE status NOT IN ('CANCELLED','RETURNED')").fetchone()[0]
        raw_spend=Decimal("0.00")
        for row in ads_raw:
            try: raw_spend += money(row["spend"])
            except Exception: pass
        dedup_spend=sum((r["spend"] for r in ads),Decimal("0.00"))
        raw_order_value=Decimal("0.00")
        for row in orders_raw:
            try: raw_order_value += money(row["total_amount"],paise=True)
            except Exception: pass
        accepted_order_value=sum((r["total"] for r in orders),Decimal("0.00"))
        print("CONTROL TOTALS (this run; source raw vs valid after dedupe)")
        print("Ads spend:",raw_spend,"->",dedup_spend,"| final mart spend:",final_spend)
        print("Order value:",raw_order_value,"->",accepted_order_value,"| final eligible order value:",final_net_orders)
        conn.commit()

if __name__=="__main__":
    main()
