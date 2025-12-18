#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------
# 1. Basic Configuration & Data Loading
# ------------------------------------------------------------
st.set_page_config(page_title="Olist Demand & GMV Dashboard", layout="wide")

@st.cache_data
def load_and_process_data():
    orders      = pd.read_csv("olist_orders_dataset.csv")
    order_items = pd.read_csv("olist_order_items_dataset.csv")
    products    = pd.read_csv("olist_products_dataset.csv")
    customers   = pd.read_csv("olist_customers_dataset.csv")

    # Time processing
    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
    orders = orders.dropna(subset=["order_purchase_timestamp"])

    # Filter orders
    invalid_status = ["canceled", "unavailable"]
    orders_valid = orders[~orders["order_status"].isin(invalid_status)].copy()

    # Merge
    df = order_items.merge(orders_valid[["order_id", "customer_id", "order_purchase_timestamp"]], on="order_id", how="inner")
    df = df.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    df = df.merge(customers[["customer_id", "customer_city", "customer_state"]], on="customer_id", how="left")

    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    df["order_date"] = df["order_purchase_timestamp"].dt.floor("D")
    return df

df = load_and_process_data()

# ------------------------------------------------------------
# 2. Sidebar navigation
# ------------------------------------------------------------
st.sidebar.title("Olist Analysis Panel")
tab_selection = st.sidebar.radio("Switch Dashboard", ["Demand Analysis", "GMV Analysis"])

# Get filtering options
category_options = sorted(df["product_category_name"].unique())
state_options    = sorted(df["customer_state"].unique())
top_cities       = df.groupby("customer_city")["order_id"].nunique().sort_values(ascending=False).head(10).index.tolist()

# ------------------------------------------------------------
# 3. Demand Analysis Tab
# ------------------------------------------------------------
if tab_selection == "Demand Analysis":
    st.title("📦 Demand Analysis")
    
    view_type = st.selectbox("Select Demand View", ["Overall Demand", "Category Demand", "State Demand", "City Demand"])
    
    if view_type == "Overall Demand":
        data = df.groupby("order_date")["order_id"].nunique().reset_index(name="demand")
        fig = px.line(data, x="order_date", y="demand", title="Overall Daily Demand (Unique Orders)")
        st.plotly_chart(fig, use_container_width=True)

    elif view_type == "Category Demand":
        cat = st.selectbox("Select Category", category_options)
        data = df[df["product_category_name"] == cat].groupby("order_date")["order_item_id"].count().reset_index(name="demand")
        st.plotly_chart(px.line(data, x="order_date", y="demand", title=f"Daily Item Demand: {cat}"), use_container_width=True)

    elif view_type == "State Demand":
        state = st.selectbox("Select State", state_options)
        data = df[df["customer_state"] == state].groupby("order_date")["order_item_id"].count().reset_index(name="demand")
        st.plotly_chart(px.line(data, x="order_date", y="demand", title=f"Daily Item Demand in {state}"), use_container_width=True)

    elif view_type == "City Demand":
        city = st.selectbox("Select City (Top 10)", top_cities)
        data = df[df["customer_city"] == city].groupby("order_date")["order_item_id"].count().reset_index(name="demand")
        st.plotly_chart(px.line(data, x="order_date", y="demand", title=f"Daily Item Demand in {city}"), use_container_width=True)

# ------------------------------------------------------------
# 4. GMV Analysis Tab
# ------------------------------------------------------------
else:
    st.title("💰 GMV Analysis")
    
    gmv_view = st.selectbox("Select GMV View", ["Overall", "Category", "State", "City"])
    
    # Filter data based on selection
    if gmv_view == "Category":
        selected = st.selectbox("Category Selector", category_options)
        filtered_df = df[df["product_category_name"] == selected]
    elif gmv_view == "State":
        selected = st.selectbox("State Selector", state_options)
        filtered_df = df[df["customer_state"] == selected]
    elif gmv_view == "City":
        selected = st.selectbox("City Selector", top_cities)
        filtered_df = df[df["customer_city"] == selected]
    else:
        filtered_df = df

    # Calculate Metrics
    ts_data = filtered_df.groupby("order_date").agg(
        gmv=("price", "sum"),
        orders=("order_id", "nunique"),
        items=("order_item_id", "count")
    ).reset_index()
    ts_data["aov"] = ts_data["gmv"] / ts_data["orders"].replace(0, np.nan)

    # Figure 1: GMV Time Series
    st.subheader("GMV Time Series")
    st.plotly_chart(px.line(ts_data, x="order_date", y="gmv", title="Daily GMV Trend"), use_container_width=True)

    # Figure 2: AOV
    st.subheader("Average Order Value (AOV)")
    st.plotly_chart(px.line(ts_data, x="order_date", y="aov", title="Daily AOV Trend"), use_container_width=True)

    # Figure 3: GMV Share (Bar Chart)
    st.subheader("GMV Share")
    if gmv_view in ["Overall", "Category"]:
        share_df = df.groupby("product_category_name")["price"].sum().reset_index().sort_values("price", ascending=False).head(20)
        fig_share = px.bar(share_df, x="product_category_name", y="price", title="Top 20 Categories by GMV")
    elif gmv_view == "State":
        share_df = df.groupby("customer_state")["price"].sum().reset_index().sort_values("price", ascending=False)
        fig_share = px.bar(share_df, x="customer_state", y="price", title="GMV by State")
    else:
        share_df = df[df["customer_city"].isin(top_cities)].groupby("customer_city")["price"].sum().reset_index()
        fig_share = px.bar(share_df, x="customer_city", y="price", title="GMV by Top 10 Cities")
    st.plotly_chart(fig_share, use_container_width=True)

    # Figure 4: Demand vs GMV Overlay (dual axis)
    st.subheader("Demand vs GMV Overlay")
    
    demand_col = "orders" if gmv_view == "Overall" else "items"
    demand_label = "Orders" if gmv_view == "Overall" else "Items Sold"

    fig_overlay = go.Figure()

    # left axis
    fig_overlay.add_trace(go.Scatter(
        x=ts_data["order_date"], 
        y=ts_data[demand_col], 
        name=f"Demand ({demand_label})", 
        line=dict(color="blue")
    ))

    # right axis
    fig_overlay.add_trace(go.Scatter(
        x=ts_data["order_date"], 
        y=ts_data["gmv"], 
        name="GMV ($)", 
        yaxis="y2", 
        line=dict(color="orange")
    ))

    # Use explicit update_layout
    fig_overlay.update_layout(
        title_text=f"Dual Axis: Demand vs GMV ({gmv_view})",
        xaxis_title_text="Date",
        yaxis=dict(
            title_text=f"Demand ({demand_label})",
            title_font=dict(color="blue"),
            tickfont=dict(color="blue")
        ),
        yaxis2=dict(
            title_text="GMV ($)",
            title_font=dict(color="orange"),
            tickfont=dict(color="orange"),
            overlaying="y",
            side="right",
            showgrid=False
        ),
        # Adjust the legend position
        legend=dict(
            orientation="h",      
            yanchor="bottom",     
            y=1.02,               
            xanchor="right",      
            x=1
        ),
        margin=dict(t=100)        
    )

    st.plotly_chart(fig_overlay, use_container_width=True)