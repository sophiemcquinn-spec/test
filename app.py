
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import duckdb
import os
st.cache_data.clear()

# Set page config
st.set_page_config(page_title="Campaign Finance Flow", layout="wide")

# Title
st.title("Campaign Finance Sankey Diagram")
st.markdown("Visualize the flow of campaign contributions by entity type")

# Load your data
@st.cache_data
def load_data():
    # Use the hardcoded token (moved inside function to avoid secrets lookup)
    MOTHERDUCK_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImNzZTYyNDJwcm9qZWN0MDFAZ21haWwuY29tIiwibWRSZWdpb24iOiJhd3MtdXMtZWFzdC0xIiwic2Vzc2lvbiI6ImNzZTYyNDJwcm9qZWN0MDEuZ21haWwuY29tIiwicGF0IjoibUc3ZXZDN1NnTDhGUF9zanhDekM1Y1RZMExPNGJoSlNWWFZWZFpxVS1nSSIsInVzZXJJZCI6ImY3ZDFkMTdiLTY2OWQtNGZhZi1hNDA4LTMzZmY1Njk2MDdhZiIsImlzcyI6Im1kX3BhdCIsInJlYWRPbmx5IjpmYWxzZSwidG9rZW5UeXBlIjoicmVhZF93cml0ZSIsImlhdCI6MTc3NDE2MDI1Nn0.FrW64qodVuTG8zkeDmUWqGmj6ZzvasM93JUt3GBrTsg'
    
    con = duckdb.connect(f"md:?motherduck_token={MOTHERDUCK_TOKEN}")
    df = con.execute("""
        SELECT *
        FROM cse6242group144.sankey_data_cand
        limit 1000
    """).df()

    return df 

# Load data
df = load_data()

# Clean candidate names
def clean_name(name):
    if pd.isna(name):
        return "Unknown"
    parts = str(name).split(', ')
    if len(parts) == 2:
        last = parts[0].title()
        first_parts = parts[1].split()
        first = first_parts[0].title() if first_parts else ""
        return f"{first} {last}"
    return str(name).title()

df['CAND_NAME_CLEAN'] = df['CAND_NAME'].apply(clean_name)
df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')

# Map entity types
entity_map = {
    'ORG': 'Organizations',
    'IND': 'Individuals',
    'COM': 'Committees',
    'PAC': 'Political Action Committees'
}
df['ENTITY_LABEL'] = df['ENTITY_TP'].map(entity_map).fillna('Other')

#affiliated party map
party_map = {
    'DEM': 'Democratic Party',
    'GRE': 'Green Party',
    'IAP': 'Independent American Party',
    'NULL': 'N/A',
    'NPA': 'No Party Affiliation',
    'CON': 'Constitution Party',
    'REP': 'Republican Party',
    'UN': 'Unaffiliated',
    'AIP': 'American Independent Party',
    'IDP': 'Independence Party',
    'IND': 'Independent',
    'DFL': 'Democratic-Farmer-Labor',
    'LIB': 'Libertarian Party',
    'W': 'Write-In',
    'OTH': 'Other'    
}
df['PARTY'] = df['CAND_PTY_AFFILIATION'].map(party_map).fillna('Other')

# Sidebar for filters
st.sidebar.header("Filters")

# Candidate selection
candidates = sorted(df['CAND_NAME_CLEAN'].unique())
selected_candidate = st.sidebar.selectbox(
    "Select Candidate",
    candidates,
    index=0
)

# Year selection
years = sorted(df['RPT_YR'].unique(), reverse=True)
selected_year = st.sidebar.selectbox(
    "Select Year",
    years,
    index=0
)

# Minimum amount filter
min_amount = st.sidebar.number_input(
    "Minimum Transaction Amount ($)",
    min_value=0.0,
    max_value=float(df['AMOUNT'].max()),
    value=0.0,
    step=100.0
)

# Filter data based on selections
filtered_df = df[
    (df['CAND_NAME_CLEAN'] == selected_candidate) &
    (df['RPT_YR'] == selected_year) &
    (df['AMOUNT'] >= min_amount)
].copy()

#filter out contributions vs expenditures
contributions_df = filtered_df[filtered_df['contribution_type'].isin(['committee_transaction', 'individual_contributions', 'committee_to_candidate'])]
expenditures_df = filtered_df[filtered_df['contribution_type'] == 'expenditure']

# Display summary statistics
col1, col2, col3, col4 = st.columns(4)
with col1:
    total = contributions_df['AMOUNT'].sum()
    st.metric("Total Contributions", f"${total:,.0f}")
with col2:
    totalex = expenditures_df['AMOUNT'].sum()
    st.metric("Total Expenditures", f"${totalex:,.0f}")

#with col3:
#    avg = filtered_df['AMOUNT'].mean() if len(filtered_df) > 0 else 0
#    st.metric("Average Transaction", f"${avg:,.0f}")

with col3:
    state = filtered_df['CAND_OFFICE_ST'].dropna().iloc[0] if len(filtered_df) > 0 else "N/A"
    st.metric("Candidate State", state)
#with col4:
#    max_val = filtered_df['AMOUNT'].max() if len(filtered_df) > 0 else 0
#    st.metric("Largest Transaction", f"${max_val:,.0f}")

with col4:
    party = filtered_df['PARTY'].dropna().iloc[0] if len(filtered_df) > 0 else "N/A"
    st.metric("Party Affiliation", party)
    
# Create Sankey diagram
if len(filtered_df) > 0:
    # Aggregate by entity type
    sankey_data = filtered_df.groupby('ENTITY_LABEL')['AMOUNT'].sum().reset_index()
    sankey_data.columns = ['source', 'value']
    sankey_data['target'] = selected_candidate
    
    # Remove zero or negative values
    sankey_data = sankey_data[sankey_data['value'] > 0]
    
    if len(sankey_data) > 0:
        # Create nodes (unique sources and targets)
        all_nodes = list(sankey_data['source'].unique()) + [selected_candidate]
        node_dict = {node: idx for idx, node in enumerate(all_nodes)}
        
        # Map sources and targets to indices
        sankey_data['source_idx'] = sankey_data['source'].map(node_dict)
        sankey_data['target_idx'] = sankey_data['target'].map(node_dict)
        
        # Color mapping for entity types
        color_map = {
            'Organizations': '#1f77b4',      # Blue
            'Individuals': '#2ca02c',        # Green
            'Committees': '#ff7f0e',         # Orange
            'Political Action Committees': '#d62728',  # Red
            'Other': '#7f7f7f'               # Gray
        }
        
        # Assign colors to nodes
        node_colors = []
        for node in all_nodes:
            if node in color_map:
                node_colors.append(color_map[node])
            else:
                node_colors.append('#9467bd')  # Purple for candidate
        
        # Assign colors to links (match source color)
        link_colors = [color_map.get(source, '#9467bd') for source in sankey_data['source']]
        
        # Create custom data for nodes
        node_customdata = []
        for node in all_nodes:
            if node == selected_candidate:
                total_val = sankey_data['value'].sum()
                node_customdata.append(f"${total_val:,.0f}")
            else:
                node_val = sankey_data[sankey_data['source'] == node]['value'].sum()
                node_customdata.append(f"${node_val:,.0f}")
        
        # Create Sankey diagram
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=all_nodes,
                color=node_colors,
                customdata=node_customdata,
                hovertemplate='%{label}<br>Total: %{customdata}<extra></extra>'
            ),
            link=dict(
                source=sankey_data['source_idx'].tolist(),
                target=sankey_data['target_idx'].tolist(),
                value=sankey_data['value'].tolist(),
                color=link_colors,
                customdata=sankey_data['source'].tolist(),
                hovertemplate='%{customdata} → ' + selected_candidate + '<br>Amount: $%{value:,.0f}<extra></extra>'
            )
        )])
        
        fig.update_layout(
            title=f"Campaign Contributions to {selected_candidate} ({selected_year})",
            font=dict(size=12),
            height=600,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show detailed breakdown table
        st.subheader("Detailed Breakdown by Entity Type")
        summary_table = filtered_df.groupby('ENTITY_LABEL').agg({
            'AMOUNT': ['sum', 'count', 'mean', 'max']
        }).round(2)
        summary_table.columns = ['Total Amount', 'Count', 'Average', 'Maximum']
        summary_table['Total Amount'] = summary_table['Total Amount'].apply(lambda x: f"${x:,.0f}")
        summary_table['Average'] = summary_table['Average'].apply(lambda x: f"${x:,.0f}")
        summary_table['Maximum'] = summary_table['Maximum'].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(summary_table, use_container_width=True)
        
        # Show raw data (optional)
        with st.expander("View Raw Transaction Data"):
            display_df = filtered_df[['ENTITY_LABEL', 'AMOUNT', 'TRANSACTION_TP', 'CMTE_ID']].copy()
            display_df['AMOUNT'] = display_df['AMOUNT'].apply(lambda x: f"${x:,.2f}")
            display_df.columns = ['Entity Type', 'Amount', 'Transaction Type', 'Committee ID']
            st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("No valid transactions to display after filtering.")
else:
    st.warning(f"No data found for {selected_candidate} in {selected_year} with transactions >= ${min_amount:,.0f}")

# Footer with data info
st.markdown("---")
st.markdown(f"**Data Source:** Federal Election Commission | **Total Records:** {len(df):,}")
