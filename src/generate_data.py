from pathlib import Path
import csv, json
ROOT=Path(__file__).resolve().parents[1]
(ROOT/"sources/crm").mkdir(parents=True,exist_ok=True)
(ROOT/"sources/store").mkdir(parents=True,exist_ok=True)
ads=[
 {"campaign_id":"C1","campaign_name":"Summer Shirts","platform":"Meta","date":"2026-08-01","spend":"₹1,250.50","impressions":10000,"clicks":250,"updated_at":"2026-08-02T02:00:00+00:00"},
 {"campaign_id":"C2","campaign_name":"Festive Search ","platform":"Google","date":"01/08/2026","spend":"900.00","impressions":8000,"clicks":190,"updated_at":"2026-08-02T02:00:00+00:00"},
 {"campaign_id":"C1","campaign_name":" summer shirts ","platform":"Meta","date":"2026-08-01","spend":"1300.00","impressions":10000,"clicks":250,"updated_at":"2026-08-03T02:00:00+00:00"},
 {"campaign_id":"C3","campaign_name":"Bad Clicks","platform":"Meta","date":"2026-08-01","spend":"100","impressions":100,"clicks":150,"updated_at":"2026-08-02T02:00:00+00:00"}]
(ROOT/"sources/ads.json").write_text(json.dumps(ads,ensure_ascii=False,indent=2),encoding="utf-8")
with (ROOT/"sources/crm/leads_20260801.csv").open("w",newline="",encoding="utf-8-sig") as f:
 w=csv.DictWriter(f,fieldnames=["lead_id","name","phone","email","utm_campaign","created_at"]);w.writeheader()
 w.writerow(dict(lead_id="L1",name="Ananya",phone="+91 98765 43210",email="ANANYA@example.com",utm_campaign="Summer Shirts",created_at="2026-08-01 10:30:00"))
 w.writerow(dict(lead_id="L2",name="അനു",phone="09876543211",email="bad-email",utm_campaign="festive search",created_at="2026-08-01 11:00:00"))
 w.writerow(dict(lead_id="L1",name="Ananya",phone="+91 98765 43210",email="ANANYA@example.com",utm_campaign="Summer Shirts",created_at="2026-08-01 10:30:00"))
orders=[
 {"order_id":"O1","customer_phone":"+91 98765 43210","order_ts":"2026-08-02T10:00:00+05:30","updated_at":"2026-08-02T11:00:00+05:30","status":"PAID","payment_mode":"UPI","total_amount":"1299.00","items":[{"sku":"SHIRT1","qty":"1","unit_price":"1299.00"}]},
 {"order_id":"O2","phone_number":"09876543211","order_ts":"2026-08-02T05:30:00Z","updated_at":"2026-08-02T06:00:00Z","status":"CANCELED","payment_mode":"CARD","total_amount":"129900","items":[{"sku":"TOP1","qty":"1","unit_price":"1299.00"}]},
 {"order_id":"O1","customer_phone":"+91 98765 43210","order_ts":"2026-08-02T10:00:00+05:30","updated_at":"2026-08-04T10:00:00+05:30","status":"SHIPPED","payment_mode":"UPI","total_amount":"1299.00","items":[{"sku":"SHIRT1","qty":"1","unit_price":"1299.00"}]}]
(ROOT/"sources/store/orders.json").write_text(json.dumps(orders,ensure_ascii=False,indent=2),encoding="utf-8")
print("Sample data generated.")
