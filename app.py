# app.py
import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime, timedelta

# ---------------------------
# CONFIG + FOLDERS
# ---------------------------
st.set_page_config(page_title="Fleet Management", page_icon="🚚", layout="wide")

DATA_DIR = "data"
UPLOADS_DIR = "uploads"
MILEAGE_DIR = os.path.join(UPLOADS_DIR, "mileage")
RECEIPTS_DIR = os.path.join(UPLOADS_DIR, "receipts")

TRIPS_CSV = os.path.join(DATA_DIR, "trips.csv")
FUEL_CSV = os.path.join(DATA_DIR, "fuel_logs.csv")

for d in [DATA_DIR, UPLOADS_DIR, MILEAGE_DIR, RECEIPTS_DIR]:
    os.makedirs(d, exist_ok=True)

# ---------------------------
# SCHEMA / COLUMNS
# ---------------------------
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

# ---------------------------
# HELPERS
# ---------------------------
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
# STREAMLIT UI
# ---------------------------
st.title("🚚 Fleet Management System — Enhanced")

menu = st.sidebar.radio("Menu", ["Start Trip", "End Trip", "Log Refuel", "View Dashboard"])

# ---------- START TRIP ----------
if menu == "Start Trip":
    st.header("🛣 Start a Trip")
    st.info("You cannot start a new trip if there is already an open trip for the same driver+vehicle. Gate pass must be unique.")

    with st.form("start_trip_form", clear_on_submit=False):
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

# ---------- VIEW DASHBOARD ----------
elif menu == "View Dashboard":
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
    vehicle_type_filter = st.sidebar.multiselect("Vehicle Type", sorted(trips_df["VehicleType"].dropna().unique()), default=[])

    # Prepare filtered copies
    trips = trips_df.copy()
    fuel = fuel_df.copy()

    # Normalize datetimes and date columns for filtering & plotting
    trips["StartDateTime_dt"] = pd.to_datetime(trips["StartDateTime"], errors="coerce")
    trips["EndDateTime_dt"] = pd.to_datetime(trips["EndDateTime"], errors="coerce")
    trips["StartDate"] = trips["StartDateTime_dt"].dt.date
    trips["EndDate"] = trips["EndDateTime_dt"].dt.date

    fuel["DateTime_dt"] = pd.to_datetime(fuel["DateTime"], errors="coerce")
    fuel["Date"] = fuel["DateTime_dt"].dt.date

    # Apply filters
    if filter_by_date and start_date and end_date:
        trips = trips[( (trips["StartDate"].notna()) & (trips["StartDate"] >= start_date) & (trips["StartDate"] <= end_date) ) |
                      ( (trips["EndDate"].notna()) & (trips["EndDate"] >= start_date) & (trips["EndDate"] <= end_date) )]
        fuel = fuel[(fuel["Date"].notna()) & (fuel["Date"] >= start_date) & (fuel["Date"] <= end_date)]

    if vehicle_filter:
        trips = trips[trips["VehicleReg"].isin(vehicle_filter)]
        fuel = fuel[fuel["VehicleReg"].isin(vehicle_filter)]

    if driver_filter:
        trips = trips[trips["Driver"].isin(driver_filter)]
        fuel = fuel[fuel["Driver"].isin(driver_filter)]

    if vehicle_type_filter:
        trips = trips[trips["VehicleType"].isin(vehicle_type_filter)]

    # KPI Summary
    try:
        total_km = pd.to_numeric(trips[trips["Status"] == "closed"]["DistanceKM"], errors="coerce").fillna(0).sum()
        total_litres = pd.to_numeric(fuel["Litres"], errors="coerce").fillna(0).sum()
        total_fuel_cost = pd.to_numeric(fuel["Cost"], errors="coerce").fillna(0).sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Distance (KM)", f"{total_km:.2f}")
        col2.metric("Total Fuel (L)", f"{total_litres:.2f}")
        col3.metric("Total Fuel Cost", f"{total_fuel_cost:.2f}")
        # fuel cost per km
        if total_km > 0:
            st.sidebar.metric("Fuel cost / KM", f"{(total_fuel_cost/total_km):.3f}")
    except Exception:
        pass

    st.markdown("---")

    # Reports
    if report_type == "Trips Report":
        st.subheader("Trips Report")
        st.write("All trips (filtered):")
        st.dataframe(trips[TRIP_COLUMNS].sort_values(["StartDateTime"], ascending=False).reset_index(drop=True), height=300)

        # Trips per vehicle per day (closed trips)
        trips_closed = trips[trips["Status"] == "closed"].copy()
        if not trips_closed.empty:
            trips_closed["StartDate"] = pd.to_datetime(trips_closed["StartDate"], errors="coerce").dt.date
            trips_per_vehicle_day = trips_closed.groupby(["VehicleReg", "StartDate"]).size().reset_index(name="TotalTrips")
            trips_per_vehicle_day = trips_per_vehicle_day.sort_values(["VehicleReg", "StartDate"], ascending=[True, True])
            st.markdown("**Total trips per vehicle per day (closed trips)**")
            st.dataframe(trips_per_vehicle_day, height=300)

            # visualization: if a vehicle selected show its daily counts
            vehicles = sorted(trips_per_vehicle_day["VehicleReg"].unique())
            vehicle_choice = st.selectbox("Choose vehicle to chart daily trips", ["(All)"] + vehicles)
            if vehicle_choice != "(All)":
                df_v = trips_per_vehicle_day[trips_per_vehicle_day["VehicleReg"] == vehicle_choice].copy()
                df_v = df_v.set_index("StartDate")["TotalTrips"]
                st.line_chart(df_v)
            else:
                # total trips per day across fleet
                total_trips_day = trips_per_vehicle_day.groupby("StartDate")["TotalTrips"].sum().sort_index()
                st.bar_chart(total_trips_day)
        else:
            st.info("No closed trips in this filter to aggregate trips per vehicle per day.")

        # download filtered trips
        csv = trips[TRIP_COLUMNS].to_csv(index=False)
        st.download_button("Download Trips CSV (current filter)", csv, file_name="trips_filtered.csv", mime="text/csv")

    elif report_type == "Fuel Report":
        st.subheader("Fuel Report")
        st.write("Fuel logs (filtered):")
        st.dataframe(fuel[FUEL_COLUMNS].sort_values("DateTime", ascending=False).reset_index(drop=True), height=300)

        # Efficiency over time
        fuel_plot = fuel.copy()
        fuel_plot["EfficiencyKMperL"] = pd.to_numeric(fuel_plot["EfficiencyKMperL"], errors="coerce")
        fuel_plot = fuel_plot.dropna(subset=["DateTime_dt", "EfficiencyKMperL"])
        fuel_plot = fuel_plot.sort_values("DateTime_dt")
        if not fuel_plot.empty:
            eff_series = fuel_plot.set_index("DateTime_dt")["EfficiencyKMperL"]
            st.line_chart(eff_series)
            st.caption("Fuel efficiency (KM per L) over time.")
        else:
            st.info("No efficiency data yet for chart.")

        # Consumption trend (Litres)
        cons_plot = fuel.copy()
        cons_plot["Litres"] = pd.to_numeric(cons_plot["Litres"], errors="coerce").fillna(0)
        cons_plot = cons_plot.dropna(subset=["DateTime_dt"])
        cons_plot = cons_plot.sort_values("DateTime_dt")
        if not cons_plot.empty:
            litres_series = cons_plot.set_index("DateTime_dt")["Litres"]
            st.bar_chart(litres_series)
            st.caption("Fuel litres filled over time.")
        else:
            st.info("No consumption data yet for chart.")

        csv = fuel[FUEL_COLUMNS].to_csv(index=False)
        st.download_button("Download Fuel CSV (current filter)", csv, file_name="fuel_filtered.csv", mime="text/csv")

    elif report_type == "Allowances Report":
        st.subheader("Allowances Report")
        # ensure numeric allowance columns
        allowance_cols = ["DailyAllowance", "OffloadingPay", "LoaderAllowance", "SecurityFee", "ParkingFee", "NightOutAllowance"]
        allow_df = trips.copy()
        for col in allowance_cols:
            if col in allow_df.columns:
                allow_df[col] = pd.to_numeric(allow_df[col], errors="coerce").fillna(0.0)
            else:
                allow_df[col] = 0.0
        allow_df["TotalAllowance"] = allow_df[allowance_cols].sum(axis=1)

        # show table
        show_cols = ["TripID", "VehicleReg", "Driver", "StartDateTime", "EndDateTime", "Status"] + allowance_cols + ["TotalAllowance"]
        st.dataframe(allow_df[show_cols].sort_values("StartDateTime", ascending=False).reset_index(drop=True), height=350)

        # aggregated allowances by vehicle or by driver
        agg_by_vehicle = allow_df.groupby("VehicleReg")["TotalAllowance"].sum().reset_index().sort_values("TotalAllowance", ascending=False)
        st.markdown("**Total allowances by vehicle**")
        st.dataframe(agg_by_vehicle)
        st.bar_chart(agg_by_vehicle.set_index("VehicleReg")["TotalAllowance"])

        agg_by_driver = allow_df.groupby("Driver")["TotalAllowance"].sum().reset_index().sort_values("TotalAllowance", ascending=False)
        st.markdown("**Total allowances by driver**")
        st.dataframe(agg_by_driver.head(20))

        csv = allow_df[show_cols].to_csv(index=False)
        st.download_button("Download Allowances CSV (current filter)", csv, file_name="allowances_filtered.csv", mime="text/csv")

    elif report_type == "Summary KPIs":
        st.subheader("Summary KPIs & Insights")
        # Fuel cost per km
        total_km = pd.to_numeric(trips[trips["Status"] == "closed"]["DistanceKM"], errors="coerce").fillna(0).sum()
        total_fuel_cost = pd.to_numeric(fuel["Cost"], errors="coerce").fillna(0).sum()
        total_litres = pd.to_numeric(fuel["Litres"], errors="coerce").fillna(0).sum()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Closed trips", f"{len(trips[trips['Status']=='closed']):,}")
        col2.metric("Total distance (KM)", f"{total_km:.2f}")
        col3.metric("Total fuel (L)", f"{total_litres:.2f}")
        col4.metric("Total fuel cost", f"{total_fuel_cost:.2f}")
        if total_km > 0:
            st.write(f"**Fuel cost per KM:** {total_fuel_cost / total_km:.3f}")
        else:
            st.write("**Fuel cost per KM:** N/A (no closed trips)")

        # Top 10 vehicles by distance
        vehicle_km = trips[trips["Status"] == "closed"].groupby("VehicleReg")["DistanceKM"].sum().reset_index().sort_values("DistanceKM", ascending=False)
        st.markdown("**Top vehicles by distance (closed trips)**")
        st.dataframe(vehicle_km.head(10))

        # suggestions
        st.markdown("**Suggestions / Notes:**")
        st.write("- Encourage drivers to upload mileage photos at start and end consistently for accurate distance tracking.")
        st.write("- Use the Allowances report to reconcile cash disbursements monthly.")
        st.write("- Consider adding trip revenue or job ID to the trip data if you want trip-level profitability.")

    st.markdown("---")
    st.info("Tip: CSVs are in the 'data/' folder, images in 'uploads/'. Use the filters to refine the reports. You can download filtered reports for sharing or further analysis.")
