import streamlit as st
import pandas as pd
from lightweight_charts.widgets import StreamlitChart
from src_client.workspace.level2 import get_market_depth  # Import the function to get market depth
import time

# Sample OHLC data (just for demo — replace with real df in production)
sample_ohlc = pd.DataFrame({
    "timestamp": pd.date_range("2025-05-13 18:00", periods=10, freq="1min"),
    "open": [5890 + i for i in range(10)],
    "high": [5890.5 + i for i in range(10)],
    "low": [5889.5 + i for i in range(10)],
    "close": [5890.25 + i for i in range(10)],
})
sample_ohlc.set_index("timestamp", inplace=True)

# Sample level 2 data
# sample_bids = [(5890.25 - i * 0.25, 10 * (i + 1)) for i in range(10)]
# sample_asks = [(5890.50 + i * 0.25, 10 * (i + 1)) for i in range(10)]

# def start_streamlit_chart(df, bids, asks):
def start_streamlit_chart(df):
    st.set_page_config(page_title="Chart + Level 2", layout="wide")
    st.title("Chart & Level 2")

    # Add auto-refresh
    st.empty()
    placeholder = st.empty()

    while True:
        with placeholder.container():
            # Layout
            col1, col2, col3 = st.columns([3, 1, 1])  # Changed to three columns

            with col1:
                chart = StreamlitChart(height=700, width=1400)
                chart.set(df)

            with col2:
                # Get real-time market depth data
                bids, asks = get_market_depth()
                
                # Create order book display
                st.subheader("Order Book")
                
                # Convert to DataFrames
                bids_df = pd.DataFrame(bids, columns=["Price", "Size"])
                asks_df = pd.DataFrame(asks, columns=["Price", "Size"])
                
                # Sort bids in descending order and asks in descending order (flipped)
                bids_df = bids_df.sort_values("Price", ascending=False)
                asks_df = asks_df.sort_values("Price", ascending=False)
                
                # Create a container for the order book
                order_book = st.container()
                
                # Custom CSS for better formatting
                st.markdown("""
                    <style>
                    .order-book {
                        font-family: 'Courier New', monospace;
                        font-size: 14px;
                        border: 1px solid #e0e0e0;
                        border-radius: 4px;
                        overflow: hidden;
                    }
                    .order-row {
                        display: flex;
                        justify-content: space-between;
                        padding: 8px 12px;
                        border-bottom: 1px solid #e0e0e0;
                    }
                    .order-row:last-child {
                        border-bottom: none;
                    }
                    .price {
                        text-align: right;
                        width: 100px;
                        font-weight: 500;
                    }
                    .size {
                        text-align: right;
                        width: 100px;
                    }
                    .best-ask {
                        background-color: rgba(255,75,75,0.1);
                        font-weight: bold;
                    }
                    .best-bid {
                        background-color: rgba(0,172,181,0.1);
                        font-weight: bold;
                    }
                    .bar-container {
                        width: 100px;
                        height: 20px;
                        background-color: #f0f0f0;
                        border-radius: 2px;
                        overflow: hidden;
                    }
                    .bar {
                        height: 100%;
                        background-color: #666;
                        transition: width 0.3s ease;
                    }
                    .ask-bar {
                        background-color: rgba(255,75,75,0.3);
                    }
                    .bid-bar {
                        background-color: rgba(0,172,181,0.3);
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                # Calculate max size for bar scaling
                max_size = max(
                    asks_df["Size"].max() if not asks_df.empty else 0,
                    bids_df["Size"].max() if not bids_df.empty else 0
                )
                
                # Display asks (top)
                st.markdown('<div class="order-book">', unsafe_allow_html=True)
                for _, row in asks_df.iterrows():
                    price = row["Price"]
                    size = row["Size"]
                    # Calculate bar width percentage
                    bar_width = (size / max_size * 100) if max_size > 0 else 0
                    # Highlight best ask (lowest price)
                    is_best_ask = price == asks_df.iloc[-1]["Price"]
                    row_class = "best-ask" if is_best_ask else ""
                    st.markdown(
                        f'<div class="order-row {row_class}">'
                        f'<span class="price">{price:.2f}</span>'
                        f'<span class="size">{size:,.0f}</span>'
                        f'<div class="bar-container"><div class="bar ask-bar" style="width: {bar_width}%"></div></div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                
                # Add a divider
                st.markdown('<div style="border-top: 1px solid #666; margin: 5px 0;"></div>', unsafe_allow_html=True)
                
                # Display bids (bottom)
                for _, row in bids_df.iterrows():
                    price = row["Price"]
                    size = row["Size"]
                    # Calculate bar width percentage
                    bar_width = (size / max_size * 100) if max_size > 0 else 0
                    # Highlight best bid (highest price)
                    is_best_bid = price == bids_df.iloc[0]["Price"]
                    row_class = "best-bid" if is_best_bid else ""
                    st.markdown(
                        f'<div class="order-row {row_class}">'
                        f'<span class="price">{price:.2f}</span>'
                        f'<span class="size">{size:,.0f}</span>'
                        f'<div class="bar-container"><div class="bar bid-bar" style="width: {bar_width}%"></div></div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                st.markdown('</div>', unsafe_allow_html=True)

            with col3:
                st.subheader("Depth Visualization")
                # Create a container for the depth chart
                depth_chart = st.container()
                
                # Create a simple bar chart using Streamlit's native chart
                if not asks_df.empty and not bids_df.empty:
                    # Combine asks and bids for visualization
                    depth_data = pd.concat([
                        asks_df.assign(side='Ask'),
                        bids_df.assign(side='Bid')
                    ])
                    
                    # Create a bar chart
                    st.bar_chart(
                        depth_data.set_index('Price')['Size'],
                        use_container_width=True
                    )

        time.sleep(1)  # Update every second

if __name__ == "__main__":
    start_streamlit_chart(sample_ohlc)

#cd .\src_client\workspace\ 
#streamlit run streamlitapp.py
# http://localhost:8501/