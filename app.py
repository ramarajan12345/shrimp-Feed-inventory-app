import os
from datetime import date
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
app.secret_key = "aquaculture_secret_key"

# Render-ல் ஓடும்போது /tmp/ ஐயும், லேப்டாப்பில் (Windows) ஓடும்போது லோக்கல் ஃபோல்டரையும் பயன்படுத்தும்
if os.environ.get("RENDER") or os.name != "nt":
    INVENTORY_FILE = "/tmp/store_feed_inventory.csv"
    REQUESTS_FILE = "/tmp/feed_requests_history.csv"
else:
    INVENTORY_FILE = "store_feed_inventory.csv"
    REQUESTS_FILE = "feed_requests_history.csv""

DEPARTMENTS = [
    "Maturation", "Hatchery", "Grow-out Pond", 
    "Block 1", "Block 2", "Block 3", "Nursery"
]

def init_inventory():
    if not os.path.exists(INVENTORY_FILE):
        default_data = pd.DataFrame([
            {"Feed_Name_Size": "Starter 0.5mm", "Total_Stock_Kg": 1000.0, "Store_Remarks": "Available - Normal Stock", "Last_Updated": str(date.today())},
            {"Feed_Name_Size": "Grower 1.2mm", "Total_Stock_Kg": 2500.0, "Store_Remarks": "Available - Normal Stock", "Last_Updated": str(date.today())},
            {"Feed_Name_Size": "Finisher 2.0mm", "Total_Stock_Kg": 1500.0, "Store_Remarks": "Available - Normal Stock", "Last_Updated": str(date.today())}
        ])
        default_data.to_csv(INVENTORY_FILE, index=False)

def init_requests():
    if not os.path.exists(REQUESTS_FILE):
        df = pd.DataFrame(columns=[
            "Request_ID", "Date", "Department", "Supervisor", "Feed_Name_Size", 
            "Quantity_Requested_Kg", "Status", "Store_Remarks"
        ])
        df.to_csv(REQUESTS_FILE, index=False)

init_inventory()
init_requests()

@app.route("/", methods=["GET", "POST"])
def index():
    inv_df = pd.read_csv(INVENTORY_FILE)
    req_df = pd.read_csv(REQUESTS_FILE)
    
    role = request.args.get("role", "Department Supervisor")
    store_pass = request.form.get("store_password", "")
    message = None
    msg_type = "success"

    if request.method == "POST":
        action_type = request.form.get("action_type")
        
        # 1. Supervisor Submit Request
        if action_type == "submit_request":
            dept = request.form.get("department")
            supervisor = request.form.get("supervisor")
            feed_type = request.form.get("feed_type")
            try:
                quantity = float(request.form.get("quantity", 0))
            except ValueError:
                quantity = 0.0
            req_date = request.form.get("req_date", str(date.today()))

            if not supervisor or not supervisor.strip():
                message = "தயவுசெய்து உங்கள் பெயரை உள்ளிடவும்!"
                msg_type = "danger"
            else:
                new_id = f"JR-{len(req_df) + 1001}"
                new_row = pd.DataFrame([{
                    "Request_ID": new_id, "Date": req_date, "Department": dept,
                    "Supervisor": supervisor, "Feed_Name_Size": feed_type,
                    "Quantity_Requested_Kg": quantity, "Status": "Pending",
                    "Store_Remarks": "Waiting for Store Approval"
                }])
                req_df = pd.concat([req_df, new_row], ignore_index=True)
                req_df.to_csv(REQUESTS_FILE, index=False)
                message = f"கோரிக்கை வெற்றிகரமாக அனுப்பப்பட்டது! ID: {new_id}"
                msg_type = "success"

        # 2. Store Keeper Add / Restock Feed
        elif action_type == "manage_inventory":
            feed_action = request.form.get("feed_action")
            feed_name = request.form.get("feed_name_input")
            existing_feed = request.form.get("existing_feed")
            try:
                stock_qty = float(request.form.get("stock_qty", 0))
            except ValueError:
                stock_qty = 0.0
            store_rem = request.form.get("store_rem", "")

            target_feed = feed_name.strip() if feed_action == "new" else existing_feed

            if feed_action == "new" and not target_feed:
                message = "தயவுசெய்து புதிய ஃபீட்டின் பெயரைக் குறிப்பிடவும்!"
                msg_type = "danger"
            else:
                if feed_action == "new":
                    if target_feed in inv_df["Feed_Name_Size"].values:
                        message = "இந்த ஃபீட் பெயர் ஏற்கனவே ஸ்டாக்கில் உள்ளது!"
                        msg_type = "warning"
                    else:
                        new_feed = pd.DataFrame([{
                            "Feed_Name_Size": target_feed, "Total_Stock_Kg": stock_qty,
                            "Store_Remarks": store_rem, "Last_Updated": str(date.today())
                        }])
                        inv_df = pd.concat([inv_df, new_feed], ignore_index=True)
                        inv_df.to_csv(INVENTORY_FILE, index=False)
                        message = f"புதிய ஃபீட் '{target_feed}' வெற்றிகரமாக சேர்க்கப்பட்டது!"
                        msg_type = "success"
                else:
                    inv_df.loc[inv_df["Feed_Name_Size"] == target_feed, "Total_Stock_Kg"] += stock_qty
                    inv_df.loc[inv_df["Feed_Name_Size"] == target_feed, "Store_Remarks"] = store_rem
                    inv_df.loc[inv_df["Feed_Name_Size"] == target_feed, "Last_Updated"] = str(date.today())
                    inv_df.to_csv(INVENTORY_FILE, index=False)
                    message = f"'{target_feed}' ஸ்டாக் வெற்றிகரமாக அப்டேட் செய்யப்பட்டது!"
                    msg_type = "success"

        # 3. Store Keeper Approve / Reject Request
        elif action_type == "process_request":
            req_id = request.form.get("req_id")
            decision = request.form.get("decision")
            rem = request.form.get("store_remark", "")

            req_row = req_df[req_df["Request_ID"] == req_id]
            if not req_row.empty:
                feed_name = req_row.iloc[0]["Feed_Name_Size"]
                req_qty = req_row.iloc[0]["Quantity_Requested_Kg"]
                
                current_stock = inv_df.loc[inv_df["Feed_Name_Size"] == feed_name, "Total_Stock_Kg"].values
                stock_avail = current_stock[0] if len(current_stock) > 0 else 0

                if decision == "approve":
                    if stock_avail >= req_qty:
                        inv_df.loc[inv_df["Feed_Name_Size"] == feed_name, "Total_Stock_Kg"] -= req_qty
                        inv_df.to_csv(INVENTORY_FILE, index=False)
                        
                        req_df.loc[req_df["Request_ID"] == req_id, "Status"] = "Approved & Issued"
                        req_df.loc[req_df["Request_ID"] == req_id, "Store_Remarks"] = rem
                        req_df.to_csv(REQUESTS_FILE, index=False)
                        message = f"Request {req_id} Approved & Issued!"
                        msg_type = "success"
                    else:
                        message = "ஸ்டோரில் போதுமான ஃபீட் இல்லை!"
                        msg_type = "danger"
                else:
                    req_df.loc[req_df["Request_ID"] == req_id, "Status"] = "Delayed / Out of Stock"
                    req_df.loc[req_df["Request_ID"] == req_id, "Store_Remarks"] = rem
                    req_df.to_csv(REQUESTS_FILE, index=False)
                    message = f"Request {req_id} marked as Out of Stock."
                    msg_type = "warning"

        inv_df = pd.read_csv(INVENTORY_FILE)
        req_df = pd.read_csv(REQUESTS_FILE)

    return render_template(
        "index.html",
        role=role,
        store_password=store_pass,
        inventory=inv_df.to_dict(orient="records"),
        requests=req_df.to_dict(orient="records"),
        departments=DEPARTMENTS,
        message=message,
        msg_type=msg_type
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
