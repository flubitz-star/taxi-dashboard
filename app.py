"""Streamlit entry point: configures the app and registers all dashboard pages."""

import streamlit as st


st.set_page_config(page_title="Taxi Dashboard", page_icon="🚕", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Taxi Dashboard", icon=":material/home:"),
        st.Page(
            "app_pages/hourly_overview.py",
            title="Hourly Overview",
            icon=":material/bar_chart:",
        ),
        st.Page(
            "app_pages/weather_comparison.py",
            title="Wetter & Mobilität",
            icon=":material/thunderstorm:",
        ),
        st.Page(
            "app_pages/revenue_analysis.py",
            title="Umsatz nach Pickup-Zone",
            icon=":material/attach_money:",
        ),
    ],
    position="top",
)

# Shared page title; the pages themselves do not render their own title.
st.title(page.title, icon=page.icon)
page.run()
