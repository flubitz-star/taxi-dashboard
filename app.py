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
    ],
    position="top",
)

st.title(page.title, icon=page.icon)
page.run()
