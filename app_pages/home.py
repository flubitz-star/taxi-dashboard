import streamlit as st


st.caption("Willkommen beim Taxi Dashboard. Wähle eine Auswertung über die Navigation.")
st.page_link(
    "app_pages/hourly_overview.py",
    label="Hourly Overview öffnen",
    icon=":material/bar_chart:",
    width="stretch",
)
