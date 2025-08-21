import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime, timedelta

# -----------------------
# CONFIG + FOLDERS (moved to top)
# -----------------------
st.set_page_config(page_title="Fleet Management", page_icon="🚚", layout="wide")

DATA_DIR = "data"
UPLOADS_DIR = "uploads"
MILEAGE_DIR = os.path.join(UPLOADS_DIR, "mileage")
RECEIPTS_DIR = os.path.join(UPLOADS_DIR, "receipts")
TRIPS_CSV = os.path.join(DATA_DIR, "trips.csv")
FUEL_CSV = os.path.join(DATA_DIR, "fuel_logs.csv")

for d in [DATA_DIR, UPLOADS_DIR, MILEAGE_DIR, RECEIPTS_DIR]:
    os.makedirs(d, exist_ok=True)

# -----------------------
# Vehicle list
# -----------------------
VEHICLES = [
    "KCA 940V", "KCB 621S", "KCA 936V", "KCA 938V", "KCB 622S", "KCA 937V", "KCA 942V",
    "KDE 018Q", "KDE 017Q", "KCA 138W", "KCA 935V", "KCA 941V", "KDE 153W", "KDM 357K",
    "KDR 654R", "KDG 438Z", "KDR 657H", "KDB 225R", "KDR 919A", "KDD 382W", "KDD 901K",
    "KDD 985W", "KDP 568N", "KDE 206Q", "KDD 359U", "KCX 106R", "KDE 211K", "KDE 262L",
    "KDE 309L", "KDE 098L", "KDK 139R", "KCX 712N", "KDC 563J", "KDD 113R", "KDE 177K",
    "KDE 225L", "KDE 454K", "KDR 819B", "KCX 718N", "KDR 462A", "KDQ 896V", "KDM 724U",
    "KBT 673G", "KDB 266R", "KDR 695S", "KCZ 218P", "KDB 971R", "KDE 199K", "KDE 188K",
    "KCX 995J", "KCZ 722M", "KDB 548V", "KDC 945F", "KDE 144K", "Executive"
]

# Admin credentials file
ADMIN_CREDS_FILE = os.path.join(DATA_DIR, "admin_creds.csv")

# Default admin credentials (used only if no admin exists)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin@1"

def validate_password(password):
    """Validate password: 6+ chars, 1 uppercase, 1 special character"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"

def load_admin_creds():
    """Load admin credentials from file, create default if not exists"""
    if os.path.exists(ADMIN_CREDS_FILE):
        df = pd.read_csv(ADMIN_CREDS_FILE)
        if not df.empty:
            return df.iloc[0]["username"], df.iloc[0]["password"]
    
    # Create default admin
    df = pd.DataFrame({
        "username": [DEFAULT_ADMIN_USERNAME],
        "password": [DEFAULT_ADMIN_PASSWORD]
    })
    df.to_csv(ADMIN_CREDS_FILE, index=False)
    return DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD

def save_admin_creds(username, password):
    """Save admin credentials to file"""
    df = pd.DataFrame({
        "username": [username],
        "password": [password]
    })
    df.to_csv(ADMIN_CREDS_FILE, index=False)

def verify_admin_login(username, password):
    """Verify admin login credentials"""
    stored_username, stored_password = load_admin_creds()
    return username == stored_username and password == stored_password

# -----------------------
# Session init
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.vehicle = None
    st.session_state.admin_username = None

# -----------------------
# Login page
# -----------------------
if not st.session_state.logged_in:
    st.title("🚚 Fleet Management Login")
    
    # Login tabs
    login_tab, admin_tab = st.tabs(["Driver Login", "Admin Login"])
    
    with login_tab:
        st.markdown("### Driver Login")
        st.info("Enter your vehicle registration number")
        
        with st.form("driver_login_form"):
            vehicle_number = st.text_input("Vehicle Registration Number:").strip()
            driver_login_submitted = st.form_submit_button("Login as Driver")
        
        if driver_login_submitted:
            if vehicle_number in VEHICLES:
                st.session_state.logged_in = True
                st.session_state.role = "driver"
                st.session_state.vehicle = vehicle_number
                st.success(f"Logged in as driver for {vehicle_number}")
                st.rerun()
            else:
                st.error("Invalid vehicle number. Please check and try again.")
    
    with admin_tab:
        st.markdown("### Administrator Login")
        st.info("Enter your admin username and password")
        
        with st.form("admin_login_form"):
            admin_username = st.text_input("Username:").strip()
            admin_password = st.text_input("Password:", type="password")
            admin_login_submitted = st.form_submit_button("Login as Admin")
        
        if admin_login_submitted:
            if verify_admin_login(admin_username, admin_password):
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.vehicle = None
                st.session_state.admin_username = admin_username
                st.success(f"Logged in as Administrator ({admin_username})")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    
    # Stop execution here if not logged in
    st.stop()

# -----------------------
# SCHEMA / COLUMNS
# -----------------------
TRIP_COLUMNS = [
    "TripID", "VehicleReg", "Driver", "DriverContact", "VehicleType",
    "StartDateTime", "EndDateTime",
    "Origin", "Destination", "Purpose", "PurposeCategory",
    "GatePassNumber",
    "StartMileage", "StartMileagePhoto", "EndMileage", "EndMileagePhoto",
    "DistanceKM",
    # Allowances
    "DailyAllowance", "OffloadingPay", "LoaderAllowance",
    "SecurityFee", "ParkingFee", "NightOutAllowance",
    "Status"
]

FUEL_COLUMNS = [
    "FuelID", "VehicleReg", "Driver", "DateTime", "Litres", "Cost",
    "MileagePhoto", "ReceiptPhoto", "DistanceSinceLastRefuelKM", "EfficiencyKMperL"
]

TRIP_DTYPES = {
    "TripID": "object", "VehicleReg": "object", "Driver": "object", "DriverContact": "object",
    "VehicleType": "object", "StartDateTime": "object", "EndDateTime": "object",
    "Origin": "object", "Destination": "object", "Purpose": "object", "PurposeCategory": "object",
    "GatePassNumber": "object",
    "StartMileage": "float64", "StartMileagePhoto": "object", "EndMileage": "float64", "EndMileagePhoto": "object",
    "DistanceKM": "float64",
    "DailyAllowance": "float64", "OffloadingPay": "float64", "LoaderAllowance": "float64",
    "SecurityFee": "float64", "ParkingFee": "float64", "NightOutAllowance": "float64",
    "Status": "object"
}

FUEL_DTYPES = {
    "FuelID": "object", "VehicleReg": "object", "Driver": "object",
    "DateTime": "object", "Litres": "float64", "Cost": "float64",
    "MileagePhoto": "object", "ReceiptPhoto": "object",
    "DistanceSinceLastRefuelKM": "float64", "EfficiencyKMperL": "float64"
}

# -----------------------
# HELPERS
# -----------------------
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_upload(uploaded_file, folder, prefix):
    """Save an uploaded image to disk and return its relative path (or None)."""
    if uploaded_file is None:
        return None
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    unique = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    path = os.path.join(folder, unique)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

def create_empty_df(columns, dtypes_map):
    data = {}
    for col in columns:
        dt = dtypes_map.get(col, "object")
        data[col] = pd.Series(dtype=dt)
    return pd.DataFrame(data, columns=columns)

def load_csv_with_schema(path, columns, dtypes_map):
    """Load CSV and coerce to schema; create empty file if missing. Ensures missing columns are added."""
    if os.path.exists(path):
        df = pd.read_csv(path, dtype="object")
        # ensure all columns exist
        for c in columns:
            if c not in df.columns:
                df[c] = pd.NA
        # coerce numeric columns carefully
        for col, dtype in dtypes_map.items():
            if dtype in ("float64", "int64"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                # cast object-like to string/object
                df[col] = df[col].astype("object")
        # keep column order
        df = df[columns]
    else:
        df = create_empty_df(columns, dtypes_map)
        df.to_csv(path, index=False)
    return df

def save_csv(path, df):
    df.to_csv(path, index=False)

def get_open_trip_for_driver(trips_df, driver, vehicle_reg=None):
    """Return the most recent open trip row (as DataFrame) for a driver (and optional vehicle), or empty df."""
    mask = (trips_df["Driver"] == driver) & (trips_df["Status"] == "open")
    if vehicle_reg:
        mask &= (trips_df["VehicleReg"] == vehicle_reg)
    open_trips = trips_df[mask]
    if open_trips.empty:
        return pd.DataFrame()
    open_trips = open_trips.sort_values("StartDateTime", ascending=False)
    return open_trips.head(1)

def distance_since_last_refuel_km(trips_df, fuel_df, driver, vehicle_reg, this_refuel_time_iso):
    """Sum distance of closed trips that ended after the last refuel and up to this refuel time for driver+vehicle."""
    trips = trips_df.copy()
    fuel = fuel_df.copy()
    if trips.empty:
        return 0.0
    trips = trips[(trips["Driver"] == driver) & (trips["VehicleReg"] == vehicle_reg) & (trips["Status"] == "closed")]
    if trips.empty:
        return 0.0

    trips["EndDateTime_dt"] = pd.to_datetime(trips["EndDateTime"], errors="coerce")
    this_refuel_dt = pd.to_datetime(this_refuel_time_iso, errors="coerce")

    last_refuel_dt = None
    if not fuel.empty:
        fuel_d = fuel[(fuel["Driver"] == driver) & (fuel["VehicleReg"] == vehicle_reg)].copy()
        if not fuel_d.empty:
            fuel_d["DateTime_dt"] = pd.to_datetime(fuel_d["DateTime"], errors="coerce")
            if not fuel_d.empty:
                last_refuel_dt = fuel_d["DateTime_dt"].max()

    if last_refuel_dt is not None:
        between = trips[(trips["EndDateTime_dt"] > last_refuel_dt) & (trips["EndDateTime_dt"] <= this_refuel_dt)]
    else:
        between = trips[trips["EndDateTime_dt"] <= this_refuel_dt]

    if between.empty:
        return 0.0

    between["DistanceKM"] = pd.to_numeric(between["DistanceKM"], errors="coerce").fillna(0.0)
    return float(between["DistanceKM"].sum())

# ---------------------------
# LOAD DATA (schema enforced)
# ---------------------------
trips_df = load_csv_with_schema(TRIPS_CSV, TRIP_COLUMNS, TRIP_DTYPES)
fuel_df = load_csv_with_schema(FUEL_CSV, FUEL_COLUMNS, FUEL_DTYPES)

# ---------------------------
# MAIN APPLICATION (only accessible after login)
# ---------------------------

# Header with user info and logout
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("🚚 Fleet Management System — Enhanced")
with col2:
    if st.session_state.role == "driver":
        st.info(f"Driver: {st.session_state.vehicle}")
    else:
        st.info(f"Admin: {st.session_state.admin_username}")
with col3:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.vehicle = None
        st.session_state.admin_username = None
        st.rerun()

# Create sidebar menu based on role
if st.session_state.role == "driver":
    menu = st.sidebar.radio("Menu", ["Start Trip", "End Trip", "Log Refuel"])
else:  # admin
    menu = st.sidebar.radio("Menu", ["Start Trip", "End Trip", "Log Refuel", "View Dashboard", "Admin Settings", "Delete Records"])

# ---------- START TRIP ----------
if menu == "Start Trip":
    st.header("🛣 Start a Trip")
    st.info("You cannot start a new trip if there is already an open trip for the same driver+vehicle. Gate pass must be unique.")

    with st.form("start_trip_form", clear_on_submit=False):
        # Pre-fill vehicle registration for drivers
        if st.session_state.role == "driver":
            vehicle_reg = st.text_input("Vehicle Registration", value=st.session_state.vehicle, disabled=True)
        else:
            vehicle_reg = st.text_input("Vehicle Registration (e.g., KAA 123A) *").strip()
        
        driver = st.text_input("Driver Name *").strip()
        driver_contact = st.text_input("Driver Contact (optional)").strip()
        vehicle_type = st.selectbox("Vehicle Type", ["Truck", "Trailer", "Pickup", "Van", "Other"])
        purpose = st.text_area("Purpose of Trip")
        purpose_category = st.selectbox("Purpose Category", ["Delivery", "Pickup", "Maintenance", "Transfer", "Other"])
        origin = st.text_input("Origin")
        destination = st.text_input("Destination")
        gate_pass_number = st.text_input("Gate Pass Number *").strip()
        start_mileage = st.number_input("Start Mileage (KM) *", min_value=0.0, step=0.1, format="%.1f")
        start_photo = st.file_uploader("Upload START mileage photo *", type=["jpg", "jpeg", "png"])
        start_btn = st.form_submit_button("Start Trip")

    if start_btn:
        if not vehicle_reg:
            st.error("Please enter Vehicle Registration.")
        elif not driver:
            st.error("Please enter Driver Name.")
        elif not gate_pass_number:
            st.error("Gate Pass Number is required.")
        elif start_photo is None:
            st.error("Please upload the START mileage photo.")
        else:
            # Gate pass uniqueness check (global across trips)
            existing_gates = trips_df["GatePassNumber"].fillna("").astype(str).str.strip().unique()
            if gate_pass_number in existing_gates and gate_pass_number != "":
                st.error("This Gate Pass Number is already used. Gate Pass numbers must be unique.")
            else:
                # check driver open trip
                open_trip = get_open_trip_for_driver(trips_df, driver, vehicle_reg)
                if not open_trip.empty:
                    st.warning("You already have an open trip for this driver & vehicle. End it before starting another.")
                else:
                    start_photo_path = save_upload(start_photo, MILEAGE_DIR, "start")
                    trip_id = f"TRIP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
                    new_trip = {
                        "TripID": trip_id,
                        "VehicleReg": vehicle_reg,
                        "Driver": driver,
                        "DriverContact": driver_contact if driver_contact else pd.NA,
                        "VehicleType": vehicle_type,
                        "StartDateTime": now_iso(),
                        "EndDateTime": "",
                        "Origin": origin,
                        "Destination": destination,
                        "Purpose": purpose,
                        "PurposeCategory": purpose_category,
                        "GatePassNumber": gate_pass_number,
                        "StartMileage": float(start_mileage),
                        "StartMileagePhoto": start_photo_path,
                        "EndMileage": pd.NA,
                        "EndMileagePhoto": pd.NA,
                        "DistanceKM": pd.NA,
                        "DailyAllowance": pd.NA,
                        "OffloadingPay": pd.NA,
                        "LoaderAllowance": pd.NA,
                        "SecurityFee": pd.NA,
                        "ParkingFee": pd.NA,
                        "NightOutAllowance": pd.NA,
                        "Status": "open"
                    }
                    new_df = pd.DataFrame([new_trip], columns=trips_df.columns)
                    # coerce numeric columns
                    for col in ["StartMileage", "EndMileage", "DistanceKM",
                                "DailyAllowance", "OffloadingPay", "LoaderAllowance",
                                "SecurityFee", "ParkingFee", "NightOutAllowance"]:
                        if col in new_df.columns:
                            new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
                    trips_df = pd.concat([trips_df, new_df], ignore_index=True, sort=False)
                    save_csv(TRIPS_CSV, trips_df)
                    st.success(f"Trip started for {driver} ({vehicle_reg}). Trip ID: {trip_id}")
                    st.balloons()

# ---------- END TRIP ----------
elif menu == "End Trip":
    st.header("🏁 End a Trip")
    st.info("Find and close your open trip by entering Driver and Vehicle Registration. When closing, request allowances if applicable.")

    # Pre-fill vehicle registration for drivers
    if st.session_state.role == "driver":
        vehicle_reg = st.text_input("Vehicle Registration", value=st.session_state.vehicle, disabled=True)
    else:
        vehicle_reg = st.text_input("Vehicle Registration *").strip()
    
    driver = st.text_input("Driver Name *").strip()

    if st.button("Find My Open Trip"):
        if not vehicle_reg or not driver:
            st.error("Please enter both Vehicle Registration and Driver Name.")
        else:
            open_trip = get_open_trip_for_driver(trips_df, driver, vehicle_reg)
            if open_trip.empty:
                st.warning("No open trip found for this driver & vehicle.")
            else:
                st.session_state["open_trip_for_driver"] = open_trip.to_dict(orient="records")[0]
                st.success("Open trip found. Scroll down to end it.")

    if "open_trip_for_driver" in st.session_state:
        t = st.session_state["open_trip_for_driver"]
        st.write(f"**Trip ID:** {t.get('TripID', '')}")
        st.write(f"**Origin → Destination:** {t.get('Origin','')} → {t.get('Destination','')}")
        st.write(f"**Start Mileage:** {t.get('StartMileage','')}")

        end_mileage = st.number_input("End Mileage (KM) *", min_value=0.0, step=0.1, format="%.1f")
        end_photo = st.file_uploader("Upload END mileage photo *", type=["jpg", "jpeg", "png"])

        st.markdown("### Allowances (enter amounts if applicable)")
        daily_allowance = st.number_input("Daily Allowance", min_value=0.0, step=0.1, format="%.2f")
        offloading_pay = st.number_input("Offloading Pay", min_value=0.0, step=0.1, format="%.2f")
        loader_allowance = st.number_input("Loader Allowance", min_value=0.0, step=0.1, format="%.2f")
        security_fee = st.number_input("Security Fee", min_value=0.0, step=0.1, format="%.2f")
        parking_fee = st.number_input("Parking Fee", min_value=0.0, step=0.1, format="%.2f")
        night_out_allowance = st.number_input("Night Out Allowance", min_value=0.0, step=0.1, format="%.2f")

        if st.button("Submit End Trip"):
            if end_photo is None:
                st.error("Please upload the END mileage photo.")
            else:
                try:
                    start_m = float(t["StartMileage"]) if pd.notna(t["StartMileage"]) else 0.0
                    if end_mileage < start_m:
                        st.error("End mileage cannot be less than start mileage.")
                    else:
                        end_photo_path = save_upload(end_photo, MILEAGE_DIR, "end")
                        distance_km = round(float(end_mileage) - float(start_m), 2)

                        trip_id = t["TripID"]
                        idx = trips_df[trips_df["TripID"] == trip_id].index
                        if len(idx) == 1:
                            i = idx[0]
                            trips_df.at[i, "EndDateTime"] = now_iso()
                            trips_df.at[i, "EndMileage"] = float(end_mileage)
                            trips_df.at[i, "EndMileagePhoto"] = end_photo_path
                            trips_df.at[i, "DistanceKM"] = float(distance_km)
                            trips_df.at[i, "Status"] = "closed"
                            # allowances
                            trips_df.at[i, "DailyAllowance"] = float(daily_allowance) if daily_allowance else 0.0
                            trips_df.at[i, "OffloadingPay"] = float(offloading_pay) if offloading_pay else 0.0
                            trips_df.at[i, "LoaderAllowance"] = float(loader_allowance) if loader_allowance else 0.0
                            trips_df.at[i, "SecurityFee"] = float(security_fee) if security_fee else 0.0
                            trips_df.at[i, "ParkingFee"] = float(parking_fee) if parking_fee else 0.0
                            trips_df.at[i, "NightOutAllowance"] = float(night_out_allowance) if night_out_allowance else 0.0

                            save_csv(TRIPS_CSV, trips_df)
                            st.success(f"Trip ended. Distance: {distance_km:.2f} KM.")
                            st.session_state.pop("open_trip_for_driver", None)
                        else:
                            st.error("Could not locate the open trip record.")
                except Exception as e:
                    st.error(f"Error: {e}")

# ---------- LOG REFUEL ----------
elif menu == "Log Refuel":
    st.header("⛽ Log Refuel")
    st.info("Efficiency = distance since last refuel ÷ litres on this refuel. Receipt attachment is required.")

    # Pre-fill vehicle registration for drivers
    if st.session_state.role == "driver":
        vehicle_reg = st.text_input("Vehicle Registration", value=st.session_state.vehicle, disabled=True)
    else:
        vehicle_reg = st.text_input("Vehicle Registration (match vehicle on trip) *").strip()
    
    driver = st.text_input("Driver Name *").strip()
    litres = st.number_input("Fuelled Litres *", min_value=0.0, step=0.1, format="%.2f")
    cost = st.number_input("Cost (optional)", min_value=0.0, step=0.1, format="%.2f")
    mileage_photo = st.file_uploader("Upload mileage reading photo (optional)", type=["jpg", "jpeg", "png"])
    receipt_photo = st.file_uploader("Upload receipt photo (REQUIRED) *", type=["jpg", "jpeg", "png"])

    if st.button("Submit Refuel"):
        if not vehicle_reg:
            st.error("Please enter Vehicle Registration.")
        elif not driver:
            st.error("Please enter Driver Name.")
        elif litres <= 0:
            st.error("Litres must be greater than 0.")
        elif receipt_photo is None:
            st.error("Receipt photo is required for fuel submission.")
        else:
            when = now_iso()
            mileage_path = save_upload(mileage_photo, MILEAGE_DIR, "refuel_mileage") if mileage_photo else pd.NA
            receipt_path = save_upload(receipt_photo, RECEIPTS_DIR, "receipt") if receipt_photo else pd.NA

            dist_km = distance_since_last_refuel_km(trips_df, fuel_df, driver, vehicle_reg, when)
            efficiency = (dist_km / litres) if litres > 0 else None

            fuel_id = f"FUEL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
            new_fuel = {
                "FuelID": fuel_id,
                "VehicleReg": vehicle_reg,
                "Driver": driver,
                "DateTime": when,
                "Litres": float(litres),
                "Cost": float(cost) if cost else pd.NA,
                "MileagePhoto": mileage_path if mileage_path else pd.NA,
                "ReceiptPhoto": receipt_path,
                "DistanceSinceLastRefuelKM": float(round(dist_km, 2)),
                "EfficiencyKMperL": float(round(efficiency, 2)) if efficiency is not None else pd.NA
            }

            new_df = pd.DataFrame([new_fuel], columns=fuel_df.columns)
            for col in ["Litres", "Cost", "DistanceSinceLastRefuelKM", "EfficiencyKMperL"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_numeric(new_df[col], errors="coerce")

            fuel_df = pd.concat([fuel_df, new_df], ignore_index=True, sort=False)
            save_csv(FUEL_CSV, fuel_df)

            eff_text = f"{(dist_km/litres):.2f} KM/L" if efficiency is not None else "N/A"
            st.success(f"Refuel logged. Distance since last refuel: {dist_km:.2f} KM | Efficiency: {eff_text}")
            st.balloons()

# ---------- VIEW DASHBOARD (Admin only) ----------
elif menu == "View Dashboard" and st.session_state.role == "admin":
    st.header("📊 Dashboard")
    st.markdown("Use the controls to filter the period, vehicle, driver or report type.")

    # Filters
    st.sidebar.header("Dashboard Filters")
    report_type = st.sidebar.selectbox("Report Type", ["Trips Report", "Fuel Report", "Allowances Report", "Summary KPIs"])
    filter_by_date = st.sidebar.checkbox("Filter by date range", value=False)
    if filter_by_date:
        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=30)
        start_date = st.sidebar.date_input("Start date", default_start)
        end_date = st.sidebar.date_input("End date", default_end)
    else:
        start_date = None
        end_date = None

    vehicle_filter = st.sidebar.multiselect("Vehicle (filter)", sorted(trips_df["VehicleReg"].dropna().unique()), default=[])
    driver_filter = st.sidebar.multiselect("Driver (filter)", sorted(trips_df["Driver"].dropna().unique()), default=[])

    # Apply filters
    filtered_trips = trips_df.copy()
    filtered_fuel = fuel_df.copy()

    if filter_by_date and start_date and end_date:
        # Convert to datetime for filtering
        filtered_trips["StartDateTime_dt"] = pd.to_datetime(filtered_trips["StartDateTime"], errors="coerce")
        filtered_fuel["DateTime_dt"] = pd.to_datetime(filtered_fuel["DateTime"], errors="coerce")
        
        filtered_trips = filtered_trips[
            (filtered_trips["StartDateTime_dt"].dt.date >= start_date) & 
            (filtered_trips["StartDateTime_dt"].dt.date <= end_date)
        ]
        filtered_fuel = filtered_fuel[
            (filtered_fuel["DateTime_dt"].dt.date >= start_date) & 
            (filtered_fuel["DateTime_dt"].dt.date <= end_date)
        ]

    if vehicle_filter:
        filtered_trips = filtered_trips[filtered_trips["VehicleReg"].isin(vehicle_filter)]
        filtered_fuel = filtered_fuel[filtered_fuel["VehicleReg"].isin(vehicle_filter)]

    if driver_filter:
        filtered_trips = filtered_trips[filtered_trips["Driver"].isin(driver_filter)]
        filtered_fuel = filtered_fuel[filtered_fuel["Driver"].isin(driver_filter)]

    # Display reports based on selection
    if report_type == "Trips Report":
        st.subheader("📝 Trips Report")
        if filtered_trips.empty:
            st.warning("No trips found for the selected filters.")
        else:
            st.dataframe(filtered_trips, use_container_width=True)
            st.download_button(
                "Download Trips CSV",
                filtered_trips.to_csv(index=False),
                "trips_report.csv",
                "text/csv"
            )

    elif report_type == "Fuel Report":
        st.subheader("⛽ Fuel Report")
        if filtered_fuel.empty:
            st.warning("No fuel records found for the selected filters.")
        else:
            st.dataframe(filtered_fuel, use_container_width=True)
            st.download_button(
                "Download Fuel CSV",
                filtered_fuel.to_csv(index=False),
                "fuel_report.csv",
                "text/csv"
            )

    elif report_type == "Allowances Report":
        st.subheader("💰 Allowances Report")
        if filtered_trips.empty:
            st.warning("No trips found for the selected filters.")
        else:
            allowance_cols = ["TripID", "VehicleReg", "Driver", "StartDateTime", "EndDateTime",
                            "DailyAllowance", "OffloadingPay", "LoaderAllowance", 
                            "SecurityFee", "ParkingFee", "NightOutAllowance"]
            allowance_data = filtered_trips[allowance_cols].copy()
            # Calculate total allowances
            allowance_data["TotalAllowances"] = (
                allowance_data[["DailyAllowance", "OffloadingPay", "LoaderAllowance", 
                               "SecurityFee", "ParkingFee", "NightOutAllowance"]]
                .fillna(0).sum(axis=1)
            )
            st.dataframe(allowance_data, use_container_width=True)
            
            # Summary statistics
            total_allowances = allowance_data["TotalAllowances"].sum()
            st.metric("Total Allowances", f"KSh {total_allowances:,.2f}")
            
            st.download_button(
                "Download Allowances CSV",
                allowance_data.to_csv(index=False),
                "allowances_report.csv",
                "text/csv"
            )

    elif report_type == "Summary KPIs":
        st.subheader("📊 Key Performance Indicators")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_trips = len(filtered_trips)
            open_trips = len(filtered_trips[filtered_trips["Status"] == "open"])
            st.metric("Total Trips", total_trips, delta=f"{open_trips} open")
        
        with col2:
            total_distance = filtered_trips["DistanceKM"].fillna(0).sum()
            st.metric("Total Distance", f"{total_distance:,.0f} KM")
        
        with col3:
            total_fuel = filtered_fuel["Litres"].fillna(0).sum()
            st.metric("Total Fuel", f"{total_fuel:,.1f} L")
        
        with col4:
            if total_fuel > 0:
                avg_efficiency = total_distance / total_fuel
                st.metric("Avg Efficiency", f"{avg_efficiency:.2f} KM/L")
            else:
                st.metric("Avg Efficiency", "N/A")
        
        # Charts
        if not filtered_trips.empty:
            st.subheader("Trip Status Distribution")
            status_counts = filtered_trips["Status"].value_counts()
            st.bar_chart(status_counts)
            
            st.subheader("Trips by Vehicle Type")
            vehicle_type_counts = filtered_trips["VehicleType"].value_counts()
            st.bar_chart(vehicle_type_counts)
        
        if not filtered_fuel.empty:
            st.subheader("Fuel Efficiency by Vehicle")
            fuel_by_vehicle = (
                filtered_fuel.groupby("VehicleReg")["EfficiencyKMperL"]
                .mean()
                .dropna()
                .sort_values(ascending=False)
            )
            if not fuel_by_vehicle.empty:
                st.bar_chart(fuel_by_vehicle)

# Add session state cleanup on logout
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ---------- ADMIN SETTINGS ----------
elif menu == "Admin Settings" and st.session_state.role == "admin":
    st.header("⚙️ Admin Settings")
    st.markdown("Change admin username and password")
    
    current_username, current_password = load_admin_creds()
    
    with st.form("change_admin_creds"):
        st.subheader("Change Admin Credentials")
        new_username = st.text_input("New Username:", value=current_username)
        new_password = st.text_input("New Password:", type="password")
        confirm_password = st.text_input("Confirm New Password:", type="password")
        
        st.info("Password requirements: At least 6 characters, 1 uppercase letter, 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)")
        
        change_creds_btn = st.form_submit_button("Update Credentials")
    
    if change_creds_btn:
        if not new_username.strip():
            st.error("Username cannot be empty")
        elif new_password != confirm_password:
            st.error("Passwords do not match")
        else:
            is_valid, message = validate_password(new_password)
            if is_valid:
                save_admin_creds(new_username.strip(), new_password)
                st.session_state.admin_username = new_username.strip()
                st.success("Admin credentials updated successfully!")
                st.balloons()
            else:
                st.error(message)

# ---------- DELETE RECORDS ----------
elif menu == "Delete Records" and st.session_state.role == "admin":
    st.header("🗑️ Delete Records")
    st.warning("⚠️ This action cannot be undone. Please be careful when deleting records.")
    
    delete_type = st.selectbox("Select Record Type to Delete", ["Trip Records", "Fuel Records"])
    
    if delete_type == "Trip Records":
        st.subheader("Delete Trip Records")
        
        if trips_df.empty:
            st.info("No trip records found.")
        else:
            # Show trips with selection
            st.write("Select trips to delete:")
            
            # Create display dataframe with key columns
            display_cols = ["TripID", "VehicleReg", "Driver", "StartDateTime", "EndDateTime", "Status", "DistanceKM"]
            display_df = trips_df[display_cols].copy()
            
            # Add selection checkboxes
            selected_trips = []
            for idx, row in display_df.iterrows():
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox("", key=f"trip_{idx}"):
                        selected_trips.append(idx)
                with col2:
                    st.write(f"**{row['TripID']}** | {row['VehicleReg']} | {row['Driver']} | {row['StartDateTime']} | Status: {row['Status']}")
            
            if selected_trips:
                st.write(f"**{len(selected_trips)} trips selected for deletion**")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("🗑️ Delete Selected Trips", type="primary"):
                        # Remove selected trips
                        trips_df_updated = trips_df.drop(selected_trips).reset_index(drop=True)
                        save_csv(TRIPS_CSV, trips_df_updated)
                        st.success(f"Successfully deleted {len(selected_trips)} trip records!")
                        st.rerun()
                
                with col2:
                    if st.button("Select All"):
                        st.rerun()
    
    elif delete_type == "Fuel Records":
        st.subheader("Delete Fuel Records")
        
        if fuel_df.empty:
            st.info("No fuel records found.")
        else:
            # Show fuel records with selection
            st.write("Select fuel records to delete:")
            
            # Create display dataframe with key columns
            display_cols = ["FuelID", "VehicleReg", "Driver", "DateTime", "Litres", "Cost"]
            display_df = fuel_df[display_cols].copy()
            
            # Add selection checkboxes
            selected_fuel = []
            for idx, row in display_df.iterrows():
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox("", key=f"fuel_{idx}"):
                        selected_fuel.append(idx)
                with col2:
                    cost_text = f"KSh {row['Cost']:.2f}" if pd.notna(row['Cost']) else "N/A"
                    st.write(f"**{row['FuelID']}** | {row['VehicleReg']} | {row['Driver']} | {row['DateTime']} | {row['Litres']}L | {cost_text}")
            
            if selected_fuel:
                st.write(f"**{len(selected_fuel)} fuel records selected for deletion**")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("🗑️ Delete Selected Fuel Records", type="primary"):
                        # Remove selected fuel records
                        fuel_df_updated = fuel_df.drop(selected_fuel).reset_index(drop=True)
                        save_csv(FUEL_CSV, fuel_df_updated)
                        st.success(f"Successfully deleted {len(selected_fuel)} fuel records!")
                        st.rerun()
                
                with col2:
                    if st.button("Select All"):
                        st.rerun()