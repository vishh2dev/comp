import streamlit as st
import pandas as pd
import numpy as np
from groq import Groq
import plotly.express as px
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import json
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from xgboost import XGBRegressor
import joblib
import os
import pandas as pd
import plotly.express as px
import datetime

# Configure page settings
st.set_page_config(page_title="Product Analysis Dashboard", layout="wide")

# Initialize Groq client
groq_client = Groq(
    api_key=st.secrets["GROQ_API_KEY"]
)

# Load and prepare data
@st.cache_data
def load_data():
    clean_data = pd.read_csv("Final_Cleaned_and_Structured_Dataset.csv")
    full_data = pd.read_csv("product_data_with_details.csv")
    # Add index column to clean_data to match with full_data
    clean_data['product_index'] = range(len(clean_data))
    return clean_data, full_data


@st.cache_resource
def train_or_load_model(data):
    """Train or load the XGBoost model for demand prediction."""
    # Features for training
    training_columns = ['price', 'review_growth_rate', 'Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']
    target_column = 'reviews'  # Target variable

    # Define input features and target variable
    X = data[training_columns]
    y = data[target_column]

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Check for an existing model
    model_path = "xgboost_demand_model.joblib"
    if os.path.exists(model_path):
        # Load the existing model
        model = joblib.load(model_path)
    else:
        # Train the model
        model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
        model.fit(X_train, y_train)

        # Save the trained model for future use
        joblib.dump(model, model_path)

    return model, X_test, y_test

def generate_predictions(model, clean_data, days_ahead=30):
    """Generate predictions for the clean_data with future dates."""
    # Generate a DataFrame for future prediction
    future_data = generate_future_data(clean_data, days_ahead)
    
    # Make predictions
    future_data["predicted_reviews"] = model.predict(
        future_data[["price", "review_growth_rate", "Cotton", "Polyester", "Round Neck", "Polo Neck", "Short Sleeve", "Long Sleeve"]]
    )
    
    # Add product_id for grouping trends
    if "product_index" in clean_data.columns:
        # Repeat product_index to match the future_data length
        num_products = len(clean_data)
        repeat_factor = len(future_data) // num_products  # How many times to repeat each product
        remainder = len(future_data) % num_products      # Handle cases where it's not an exact multiple

        # Repeat product indices and handle remainder
        product_ids = list(clean_data["product_index"]) * repeat_factor + list(clean_data["product_index"][:remainder])
        future_data["product_id"] = product_ids
    
    return future_data


def generate_future_data(clean_data, days_ahead=30):
    """Generate future data for prediction."""
    future_dates = [datetime.date.today() + datetime.timedelta(days=i) for i in range(days_ahead)]
    future_data = []

    # Use sample products from clean_data for prediction
    for _, product in clean_data.sample(n=10, random_state=42).iterrows():  # Adjust n as needed
        for date in future_dates:
            future_data.append({
                'date': date,
                'price': product['price'],  # Use existing product price
                'review_growth_rate': product['review_growth_rate'],  # Use existing growth rate
                'Cotton': product['Cotton'],
                'Polyester': product['Polyester'],
                'Round Neck': product['Round Neck'],
                'Polo Neck': product['Polo Neck'],
                'Short Sleeve': product['Short Sleeve'],
                'Long Sleeve': product['Long Sleeve']
            })

    return pd.DataFrame(future_data)



def visualize_trends(clean_data, predictions_df):
    st.header("Consumer Behavior Trends")

    # Add tabs for Emerging Trends and Top Trending Products
    tab1, tab2 = st.tabs(["Emerging Trends & Recommendations", "Top Trending Products"])

    # Emerging Trends & Recommendations
    with tab1:
        st.subheader("Emerging Trends & Recommendations")
        
        # Analyze trends for features like materials, neck types, etc.
        feature_trends = predictions_df.copy()
        feature_trends["material"] = feature_trends["Cotton"].apply(lambda x: "Cotton" if x == 1 else "Polyester")
        feature_trends["neck_type"] = feature_trends["Round Neck"].apply(lambda x: "Round Neck" if x == 1 else "Polo Neck")
        feature_trends["sleeve_type"] = feature_trends["Short Sleeve"].apply(lambda x: "Short Sleeve" if x == 1 else "Long Sleeve")
        
        # Aggregate feature trends over time
        feature_demand = feature_trends.groupby(["date", "material", "neck_type", "sleeve_type"])["predicted_reviews"].sum().reset_index()
        
        # Visualize feature trends over time
        fig_features = px.line(
            feature_demand,
            x="date",
            y="predicted_reviews",
            color="material",
            line_group="neck_type",
            facet_col="sleeve_type",
            title="Emerging Feature Trends Over Time",
            labels={"predicted_reviews": "Predicted Reviews"}
        )
        st.plotly_chart(fig_features)

        # Insights & Recommendations
        st.subheader("Actionable Recommendations")
        
        # Identify emerging trends
        emerging_material = feature_demand.groupby("material")["predicted_reviews"].mean().idxmax()
        emerging_neck_type = feature_demand.groupby("neck_type")["predicted_reviews"].mean().idxmax()
        emerging_sleeve_type = feature_demand.groupby("sleeve_type")["predicted_reviews"].mean().idxmax()

        st.write("### Key Insights")
        st.markdown(f"1. **Emerging Material Preference**: Consumers are showing a preference for **{emerging_material}** products.")
        st.markdown(f"2. **Popular Neck Type**: **{emerging_neck_type}** products are seeing the highest growth in demand.")
        st.markdown(f"3. **Trending Sleeve Type**: Products with **{emerging_sleeve_type}** are gaining traction.")

        st.write("### Recommendations")
        st.markdown(
            f"- **Focus on Material**: Expand the product line for **{emerging_material}** to align with growing consumer preferences.\n"
            f"- **Feature Optimization**: Prioritize **{emerging_neck_type}** neck designs to capture higher market demand.\n"
            f"- **Sleeve Preferences**: Adjust the product line to include more **{emerging_sleeve_type}** options."
        )

    # Top Trending Products
    with tab2:
        st.subheader("Top Trending Products")
        
        # Identify the top trending products
        top_trending_products = (
            predictions_df.groupby("product_id")["predicted_reviews"].sum()
            .sort_values(ascending=False)
            .head(5)  # Top 5 products
        )
        
        # Extract product details
        trending_products_details = clean_data[clean_data['product_index'].isin(top_trending_products.index)]
        trending_products_details['total_predicted_reviews'] = top_trending_products.values

        # Display as a table without Product ID
        st.write("### Top 5 Trending Products")
        st.table(trending_products_details[[
            'price', 'rating', 'reviews', 'total_predicted_reviews'
        ]].rename(columns={
            'price': 'Price (₹)',
            'rating': 'Rating',
            'reviews': 'Reviews (Current)',
            'total_predicted_reviews': 'Predicted Reviews (Trending)'
        }))
        
        # Highlight the top trending product
        top_product = trending_products_details.iloc[0]
        st.write("#### 🚀 Most Trending Product")
        st.write(f"**Price:** ₹{top_product['price']}")
        st.write(f"**Rating:** {top_product['rating']}⭐")
        st.write(f"**Current Reviews:** {int(top_product['reviews']):,}")
        st.write(f"**Predicted Reviews:** {int(top_product['total_predicted_reviews']):,}")

def feature_importance_analysis(model, data):
    st.header("Feature Importance Analysis")

    # Extract feature importance from the model
    feature_importances = pd.DataFrame({
        "Feature": model.get_booster().feature_names,
        "Importance": model.feature_importances_
    }).sort_values(by="Importance", ascending=False)

    # Highlight the top 3 features
    top_features = feature_importances.head(3)
    feature_importances["Color"] = feature_importances["Feature"].apply(
        lambda x: "Top Feature" if x in top_features["Feature"].values else "Other"
    )

    # Create the bar chart with enhanced labels and colors
    fig_importance = px.bar(
        feature_importances,
        x="Importance",
        y="Feature",
        color="Color",
        color_discrete_map={"Top Feature": "blue", "Other": "lightblue"},
        orientation='h',
        title="Feature Importance: Impact on Demand Prediction",
        labels={"Importance": "Impact on Demand Prediction", "Feature": "Feature"}
    )
    st.plotly_chart(fig_importance)

    st.subheader("Behavioral Insights")
    st.write("**How different product features perform based on average reviews:**")
    
    # Features for behavioral insights
    features = ['Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']
    
    for feature in features:
        # Avoid calculating metrics for missing data
        if feature in data.columns:
            avg_reviews = data[data[feature] == 1]['reviews'].mean()
            if not pd.isna(avg_reviews):
                st.metric(feature, f"Average Reviews: {avg_reviews:.2f}")
            else:
                st.metric(feature, "No Data Available")
        else:
            st.metric(feature, "Feature Missing")

    # Add a call-to-action or recommendation
    st.write("### Recommendations:")
    st.write("- Focus on optimizing **Cotton**, **Price**, and **Review Growth Rate** to drive demand.")
    st.write("- Promote **Short Sleeve** and **Round Neck** designs for better consumer engagement.")
    st.write("- Avoid features with minimal importance like **Long Sleeve** unless targeting niche markets.")



def forecast_future_demand(model, data):
    st.header("Product Strategy Tool")

    # Step 1: Collect User Inputs
    st.subheader("Product Configuration")
    price = st.number_input("Enter Product Price", min_value=0, max_value=2000, value=500, key="strategy_price")
    review_growth_rate = st.slider("Expected Review Growth Rate", min_value=0.0, max_value=0.5, value=0.1, key="strategy_review_growth")
    material = st.selectbox("Select Material", ["Cotton", "Polyester"], key="strategy_material")
    neck_type = st.selectbox("Select Neck Type", ["Round Neck", "Polo Neck"], key="strategy_neck")
    sleeve_type = st.selectbox("Select Sleeve Type", ["Short Sleeve", "Long Sleeve"], key="strategy_sleeve")

    # Create DataFrame for the user's input
    user_product = pd.DataFrame({
        'price': [price],
        'review_growth_rate': [review_growth_rate],
        'Cotton': [1 if material == "Cotton" else 0],
        'Polyester': [1 if material == "Polyester" else 0],
        'Round Neck': [1 if neck_type == "Round Neck" else 0],
        'Polo Neck': [1 if neck_type == "Polo Neck" else 0],
        'Short Sleeve': [1 if sleeve_type == "Short Sleeve" else 0],
        'Long Sleeve': [1 if sleeve_type == "Long Sleeve" else 0]
    })

    # Step 2: Predict Demand
    predicted_demand = model.predict(user_product)[0]
    st.metric("Predicted Demand (Reviews)", f"{int(predicted_demand):,}")

    # Step 3: Analyze Data for Recommendations
    st.subheader("Recommendations and Insights")

    # Price Optimization
    st.markdown("### Price Optimization")
    # data['price_segment'] = pd.cut(data['price'], bins=5, labels=["Budget", "Economy", "Mid-Range", "Premium", "Luxury"])
    price_segments = pd.cut(
        data['price'],
        bins=5,
        labels=["Budget", "Economy", "Mid-Range", "Premium", "Luxury"]
    )
    # Convert categories to strings for proper display
    data['price_segment'] = price_segments.astype(str)

    segment_performance = data.groupby('price_segment').agg({'price': 'mean', 'reviews': 'mean', 'rating': 'mean'}).round(2)
    user_segment = pd.cut([price], bins=5, labels=["Budget", "Economy", "Mid-Range", "Premium", "Luxury"])[0]

    st.write(f"Your product falls under the **{user_segment}** segment.")
    st.dataframe(segment_performance)

    # Feature Prioritization
    st.markdown("### Feature Prioritization")
    feature_performance = []
    features = ['Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']
    for feature in features:
        if data[feature].sum() > 0:  # Avoid division by zero
            feature_demand = data[data[feature] == 1]['reviews'].mean()
            feature_popularity = (data[feature].sum() / len(data)) * 100
        else:
            feature_demand = "Insufficient Data"
            feature_popularity = "Insufficient Data"
        
        feature_performance.append({
            "Feature": feature,
            "Avg Demand": feature_demand if feature_demand != "Insufficient Data" else None,
            "Popularity": feature_popularity if feature_popularity != "Insufficient Data" else 0
        })

    feature_df = pd.DataFrame(feature_performance).sort_values(by="Avg Demand", ascending=False, na_position='last')
    st.dataframe(feature_df)

    # Suggested Adjustments
    st.markdown("### Suggested Adjustments")
    if predicted_demand < data['reviews'].mean():
        st.write("1. **Price Optimization**: Consider adjusting the price to align with high-demand products.")
        st.write("2. **Feature Adjustment**: Consider adding high-demand features such as:")
        for _, row in feature_df.iterrows():
            if row["Avg Demand"] is not None:
                st.write(f"- **{row['Feature']}**: Avg Demand = {row['Avg Demand']:.1f}, Popularity = {row['Popularity']:.1f}%")
    else:
        st.write("Your product is already well-aligned with the market demand.")




def convert_numpy_types(obj):
    """Recursively convert numpy types to Python native types"""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def display_demand_prediction_tab(clean_data, user_product):
    st.header("Demand Prediction")

    # Train or load the model
    model, X_test, y_test = train_or_load_model(clean_data)

    # Predict demand for the user product
    prediction = model.predict(user_product)[0]
    st.subheader("Predicted Demand")
    st.metric("Estimated Reviews (Demand Proxy)", f"{int(prediction):,}")

    # Display model performance metrics
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    st.subheader("Model Performance")
    st.metric("Mean Squared Error", f"{mse:.2f}")
    st.metric("R-squared", f"{r2:.2f}")

    # Display feature importance
    st.subheader("Feature Importance")
    feature_importances = pd.DataFrame({
        "Feature": model.get_booster().feature_names,
        "Importance": model.feature_importances_
    }).sort_values(by="Importance", ascending=False)

    fig_importance = px.bar(feature_importances, x="Importance", y="Feature", orientation='h',
                            title="Feature Importance for Demand Prediction")
    st.plotly_chart(fig_importance)

def get_market_insights(data):
    """Generate market insights using Groq LLM"""
    market_summary = {
        "avg_price": data['price'].mean(),
        "avg_rating": data['rating'].mean(),
        "price_range": {
            "min": data['price'].min(),
            "max": data['price'].max(),
            "median": data['price'].median()
        },
        "popular_features": {
            "Cotton": data['Cotton'].sum(),
            "Polyester": data['Polyester'].sum(),
            "Round_Neck": data['Round Neck'].sum(),
            "Polo_Neck": data['Polo Neck'].sum(),
            "Short_Sleeve": data['Short Sleeve'].sum(),
            "Long_Sleeve": data['Long Sleeve'].sum()
        },
        "review_stats": {
            "avg_reviews": data['reviews'].mean(),
            "max_reviews": data['reviews'].max(),
            "avg_growth": data['review_growth_rate'].mean()
        }
    }
    
    # Convert all numpy types to Python native types
    market_summary = convert_numpy_types(market_summary)
    
    prompt = f"""
    As a market analysis expert, provide detailed insights about the apparel market based on the following data:
    {json.dumps(market_summary, indent=2)}
    
    Please analyze:
    1. Overall market positioning and pricing strategy
    2. Consumer preferences based on features
    3. Market engagement trends based on reviews
    4. Key recommendations for new entrants
    
    Format your response in clear sections with bullet points where appropriate.
    Be specific and provide actionable insights based on the numbers .And use ₹ (INR)
    """
    response = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a market analysis expert specializing in e-commerce and apparel."},
            {"role": "user", "content": prompt}
        ],
        model="mixtral-8x7b-32768",
        temperature=0.5,
    )
    return response.choices[0].message.content

def get_competitive_analysis(similar_products_data, user_product):
    """Generate competitive analysis using Groq LLM"""
    prompt = f"""
    As a product strategy expert, analyze these competing products against the user's product:
    
    User Product:
    {json.dumps(user_product, indent=2)}
    
    Competing Products:
    {json.dumps(similar_products_data, indent=2)}
    
    Provide a detailed competitive analysis including:
    1. Price Positioning Analysis
    - How does the user's product price compare to competitors?
    - What's the optimal price point based on the market?
    
    2. Product Feature Analysis
    - What features are common among successful competitors?
    - What unique features could differentiate the user's product?
    
    3. Market Performance Indicators
    - Analysis of ratings and reviews compared to competitors
    - Identify what drives higher ratings in this category
    
    4. Specific Recommendations
    - Clear, actionable steps to improve competitiveness
    - Potential areas for differentiation
    
    Format your response in clear sections. Be specific and data-driven in your analysis.And use ₹ (INR), and make it so it looks like you are talking to the client.
    """
    
    response = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a product strategy expert specializing in competitive analysis."},
            {"role": "user", "content": prompt}
        ],
        model="mixtral-8x7b-32768",
        temperature=0.5,
    )
    return response.choices[0].message.content


def calculate_similarity(user_product, products_df):
    """Calculate similarity between user product and existing products"""
    features = ['price', 'Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']
    scaler = StandardScaler()
    
    # Convert user_product to DataFrame if it's not already
    if not isinstance(user_product, pd.DataFrame):
        user_product = pd.DataFrame(user_product, columns=features)
    
    products_features = scaler.fit_transform(products_df[features])
    user_features = scaler.transform(user_product[features])
    
    similarities = cosine_similarity(user_features, products_features)
    return similarities[0]

def main():
    st.title("Product Analysis and Insights Dashboard")
    
    clean_data, full_data = load_data()
    
    # Sidebar for user input
    st.sidebar.header("Enter Your Product Details")
    
    price = st.sidebar.number_input("Price", min_value=0, max_value=2000, value=500)
    material = st.sidebar.selectbox("Material", ["Cotton", "Polyester"])
    neck_type = st.sidebar.selectbox("Neck Type", ["Round Neck", "Polo Neck"])
    sleeve_type = st.sidebar.selectbox("Sleeve Type", ["Short Sleeve", "Long Sleeve"])
    

    user_product = pd.DataFrame({
    'price': [price],
    'review_growth_rate': [0],
    'Cotton': [1 if material == "Cotton" else 0],
    'Polyester': [1 if material == "Polyester" else 0],
    'Round Neck': [1 if neck_type == "Round Neck" else 0],
    'Polo Neck': [1 if neck_type == "Polo Neck" else 0],
    'Short Sleeve': [1 if sleeve_type == "Short Sleeve" else 0],
    'Long Sleeve': [1 if sleeve_type == "Long Sleeve" else 0]
    })

    
    tab1, tab2, tab3, tab4 = st.tabs(["Market Overview", "Competitive Analysis", "Product Insights","Demand Prediction"])
      
    with tab1:
        st.header("Market Overview")
        
        # Market Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Average Price", f"₹{clean_data['price'].mean():.2f}")
        with col2:
            st.metric("Average Rating", f"{clean_data['rating'].mean():.1f}⭐")
        with col3:
            st.metric("Total Products", len(clean_data))
        with col4:
            st.metric("Avg Review Growth", f"{clean_data['review_growth_rate'].mean():.2%}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Price Distribution with Market Segments
            fig_price = px.histogram(clean_data, x='price', 
                                   nbins=30,
                                   title='Price Distribution with Market Segments',
                                   labels={'price': 'Price', 'count': 'Number of Products'})
            
            # Add vertical lines for market segments
            fig_price.add_vline(x=clean_data['price'].quantile(0.33), 
                              line_dash="dash", 
                              annotation_text="Budget Segment")
            fig_price.add_vline(x=clean_data['price'].quantile(0.66), 
                              line_dash="dash", 
                              annotation_text="Premium Segment")
            st.plotly_chart(fig_price)
            
        with col2:
            # Rating vs Price with Review Volume
            fig_rating = px.scatter(clean_data, 
                                  x='price', 
                                  y='rating',
                                  size='reviews',
                                  title='Price vs Rating (size = number of reviews)',
                                  labels={'price': 'Price', 
                                        'rating': 'Rating',
                                        'reviews': 'Number of Reviews'})
            st.plotly_chart(fig_rating)
        
        # Feature Popularity
        fig_features = go.Figure()
        features = ['Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']
        for feature in features:
            success_rate = clean_data[clean_data[feature] == 1]['rating'].mean()
            count = clean_data[feature].sum()
            fig_features.add_trace(go.Bar(
                name=feature,
                x=[feature],
                y=[count],
                text=f"Avg Rating: {success_rate:.1f}⭐",
                textposition='auto',
            ))
        
        fig_features.update_layout(
            title='Feature Popularity and Success Rate',
            showlegend=False
        )
        st.plotly_chart(fig_features)
        
        # Market Insights from LLM
        st.subheader("Market Insights")
        market_insights = get_market_insights(clean_data)
        st.markdown(market_insights)
        
    with tab2:
        st.header("Competitive Analysis")
        
        # Calculate similarities and get similar products
        similarities = calculate_similarity(user_product, clean_data)
        similar_indices = np.argsort(similarities)[::-1][:5]
        
        # Get detailed product information
        similar_products_detailed = []
        for idx in similar_indices:
            clean_product = clean_data.iloc[idx]
            full_product = full_data.iloc[idx]
            
            product_info = {
                "title": full_product['title'],
                "price": clean_product['price'],
                "rating": clean_product['rating'],
                "reviews": clean_product['reviews'],
                "product_link": full_product['product_link'],
                "source": full_product['source'],
                "product_details": full_product['product_details'],
                "additional_features": full_product['additional_features'],
                "features": {
                    "material": "Cotton" if clean_product['Cotton'] else "Polyester",
                    "neck_type": "Round Neck" if clean_product['Round Neck'] else "Polo Neck",
                    "sleeve_type": "Short Sleeve" if clean_product['Short Sleeve'] else "Long Sleeve"
                },
                "similarity_score": similarities[idx]
            }
            similar_products_detailed.append(product_info)
        
        # Create a row with heading and sort button
        col1, col2, col3 = st.columns([0.4, 0.5, 0.1])
        with col1:
            st.subheader("Similar Products in Market")
        with col3:
            sort_option = st.selectbox(
                "",
                ["Similarity", "Reviews", "Rating", "Price"],
                key="sort_similar_products",
                label_visibility="collapsed",
                help="Sort products by different metrics"
            )
            
        # Add some space after the header
        st.write("")
        
        # Sort the products based on selected option
        if sort_option == "Similarity":
            similar_products_detailed.sort(key=lambda x: x['similarity_score'], reverse=True)
        elif sort_option == "Reviews":
            similar_products_detailed.sort(key=lambda x: x['reviews'], reverse=True)
        elif sort_option == "Rating":
            similar_products_detailed.sort(key=lambda x: x['rating'], reverse=True)
        elif sort_option == "Price":
            similar_products_detailed.sort(key=lambda x: x['price'])
        
        # Display sorted similar products
        for i, product in enumerate(similar_products_detailed, 1):
            with st.expander(
                f"#{i} - {product['title']} "
                f"(Similarity: {product['similarity_score']:.2%}, "
                f"Reviews: {int(product['reviews']):,}, "
                f"Rating: {product['rating']:.1f}⭐)"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Price:** ₹{:,.0f}".format(product['price']))
                    st.write("**Rating:** {:.1f}⭐".format(product['rating']))
                    st.write("**Reviews:** {:,.0f}".format(product['reviews']))
                    st.write("**Source:** ", product['source'])
                with col2:
                    st.write("**Material:** ", product['features']['material'])
                    st.write("**Neck Type:** ", product['features']['neck_type'])
                    st.write("**Sleeve Type:** ", product['features']['sleeve_type'])
                
                # Additional Information Section
                st.write("---")
                
                # Product details and additional features side by side
                details_col1, details_col2 = st.columns(2)
                
                with details_col1:
                    st.write("**📋 Product Details:**")
                    if product['product_details'] and pd.notna(product['product_details']):
                        st.write(product['product_details'])
                    else:
                        st.write("*No product details available*")
                        
                with details_col2:
                    st.write("**🔍 Additional Features:**")
                    if product['additional_features'] and pd.notna(product['additional_features']):
                        st.write(product['additional_features'])
                    else:
                        st.write("*No additional features available*")
                
                # Product link at the bottom
                st.write("**🔗 Product Link:**", product['product_link'])
        
        # Get competitive analysis from LLM
        st.subheader("Competitive Analysis")
        competitive_insights = get_competitive_analysis(similar_products_detailed, user_product.to_dict())
        st.markdown(competitive_insights)
        
    with tab3:
        st.header("Product Insights")
        
        # Price Optimization
        st.subheader("Price Optimization Analysis")
        
        # Create price ranges and analyze performance
        price_ranges = pd.cut(clean_data['price'], bins=5, duplicates='drop')
        price_analysis = clean_data.groupby(price_ranges).agg({
            'rating': 'mean',
            'reviews': 'mean',
            'review_growth_rate': 'mean'
        }).round(2)
        
        fig_price_analysis = go.Figure()
        fig_price_analysis.add_trace(go.Bar(
            name='Average Rating',
            x=[f"₹{int(i.left)}-{int(i.right)}" for i in price_analysis.index],
            y=price_analysis['rating'],
            yaxis='y1'
        ))
        fig_price_analysis.add_trace(go.Scatter(
            name='Review Growth Rate',
            x=[f"₹{int(i.left)}-{int(i.right)}" for i in price_analysis.index],
            y=price_analysis['review_growth_rate'],
            yaxis='y2'
        ))
        
        fig_price_analysis.update_layout(
            title='Price Range Performance Analysis',
            yaxis=dict(title='Average Rating'),
            yaxis2=dict(title='Review Growth Rate', overlaying='y', side='right')
        )
        st.plotly_chart(fig_price_analysis)
        
        # Feature Performance Analysis
        st.subheader("Feature Performance Analysis")
        
        feature_performance = pd.DataFrame()
        for feature in ['Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 'Short Sleeve', 'Long Sleeve']:
            performance = clean_data.groupby(feature).agg({
                'rating': 'mean',
                'reviews': 'mean',
                'review_growth_rate': 'mean',
                'price': 'mean'
            }).round(2)
            
            # Check if 1 exists in the index before accessing it
            if 1 in performance.index:
                feature_performance[feature] = performance.loc[1]
            else:
                # Handle the case where the feature value 1 doesn't exist
                feature_performance[feature] = pd.Series({
                    'rating': 0,
                    'reviews': 0,
                    'review_growth_rate': 0,
                    'price': 0
                })
        
        fig_feature_performance = px.parallel_coordinates(
            feature_performance.T,
            title='Feature Performance Comparison',
            labels={
                "rating": "Avg Rating",
                "reviews": "Avg Reviews",
                "review_growth_rate": "Review Growth",
                "price": "Avg Price"
            }
        )
        st.plotly_chart(fig_feature_performance)
        
        # Product Recommendations
        st.subheader("Product Recommendations")
        
        # Calculate optimal price range
        user_price = user_product['price'].values[0]
        price_segment = pd.cut(clean_data['price'], bins=5, labels=['Budget', 'Economy', 'Mid-Range', 'Premium', 'Luxury'], duplicates='drop')
        user_segment = pd.cut([user_price], bins=5, labels=['Budget', 'Economy', 'Mid-Range', 'Premium', 'Luxury'])[0]
        
        segment_performance = clean_data.groupby(price_segment).agg({
            'rating': 'mean',
            'reviews': 'mean',
            'review_growth_rate': 'mean'
        }).round(2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"Your product is in the **{user_segment}** segment")
            st.write("Segment Performance:")
            st.dataframe(segment_performance)
            
        with col2:
            # Feature recommendations based on segment
            segment_features = clean_data[clean_data['price'].between(
                clean_data['price'].quantile(0.2 * (price_segment.cat.categories.tolist().index(user_segment))),
                clean_data['price'].quantile(0.2 * (price_segment.cat.categories.tolist().index(user_segment) + 1))
            )]
            
            best_features = pd.DataFrame({
                'feature': features,
                'success_rate': [
                    segment_features[segment_features[f] == 1]['rating'].mean() 
                    for f in features
                ],
                'popularity': [
                    segment_features[f].sum() / len(segment_features) * 100 
                    for f in features
                ],
                'avg_price': [
                    segment_features[segment_features[f] == 1]['price'].mean() 
                    for f in features
                ],
                'review_engagement': [
                    segment_features[segment_features[f] == 1]['reviews'].mean() 
                    for f in features
                ],
                'growth_potential': [
                    segment_features[segment_features[f] == 1]['review_growth_rate'].mean() 
                    for f in features
                ]
            }).sort_values('success_rate', ascending=False)

            # Feature recommendations visualization
            fig_recommendations = px.bar(
                best_features,
                x='feature',
                y=['success_rate', 'popularity'],
                title='Feature Performance in Your Segment',
                barmode='group'
            )
            st.plotly_chart(fig_recommendations)

            # Display detailed recommendations
            st.write("### Feature Recommendations")
            for _, row in best_features.iterrows():
                with st.expander(f"{row['feature']} Analysis"):
                    cols = st.columns(4)
                    cols[0].metric("Success Rate", f"{row['success_rate']:.1f}⭐")
                    cols[1].metric("Popularity", f"{row['popularity']:.1f}%")
                    cols[2].metric("Avg Price", f"₹{row['avg_price']:.0f}")
                    cols[3].metric("Growth Potential", f"{row['growth_potential']:.1%}")

            # Add competitiveness score
            user_features = set([
                col for col in ['Cotton', 'Polyester', 'Round Neck', 'Polo Neck', 
                              'Short Sleeve', 'Long Sleeve'] 
                if user_product[col].values[0] == 1
            ])
            
            top_features = set(
                best_features.nlargest(3, 'success_rate')['feature'].values
            )
            
            competitiveness_score = len(user_features.intersection(top_features)) / 3 * 100
            
            st.write("### Competitiveness Analysis")
            st.metric(
                "Product Competitiveness Score", 
                f"{competitiveness_score:.1f}%",
                help="Based on alignment with top-performing features in your segment"
            )

            # Price optimization recommendations
            st.write("### Price Optimization")
            optimal_price_range = segment_features[
                segment_features['rating'] >= segment_features['rating'].quantile(0.75)
            ]['price'].agg(['mean', 'min', 'max'])

            price_cols = st.columns(3)
            price_cols[0].metric("Recommended Price", f"₹{optimal_price_range['mean']:.0f}")
            price_cols[1].metric("Min Profitable", f"₹{optimal_price_range['min']:.0f}")
            price_cols[2].metric("Max Profitable", f"₹{optimal_price_range['max']:.0f}")

            # Demand prediction
            st.write("### Demand Prediction")
            
            # Calculate demand score based on feature popularity and review growth
            demand_factors = {
                'feature_alignment': competitiveness_score / 100,
                'price_optimization': 1 - abs(user_product['price'].values[0] - optimal_price_range['mean']) / optimal_price_range['mean'],
                'market_growth': segment_features['review_growth_rate'].mean()
            }
            
            demand_score = (
                demand_factors['feature_alignment'] * 0.4 +
                demand_factors['price_optimization'] * 0.3 +
                demand_factors['market_growth'] * 0.3
            ) * 100

            st.metric(
                "Predicted Demand Score", 
                f"{demand_score:.1f}%",
                help="Based on feature alignment, price optimization, and market growth"
            )

            # Show demand factors
            st.write("#### Demand Factors")
            for factor, value in demand_factors.items():
                # Clamp the value between 0 and 1
                clamped_value = max(0, min(1, value))
                st.progress(clamped_value)
                st.caption(factor.replace('_', ' ').title())
  
    # with tab4:
    #     display_demand_prediction_tab(clean_data, user_product)
    with tab4:
        st.header("Demand & Trend Forecasting")
        
        model, X_test, y_test = train_or_load_model(clean_data)
        predictions_df = generate_predictions(model, clean_data, days_ahead=30)
        # Visualize consumer behavior trends
     
        forecast_future_demand(model,clean_data)
        visualize_trends(clean_data, predictions_df)
        
        # Analyze feature importance
        
        feature_importance_analysis(model, clean_data)
        
        



def create_market_analysis_prompt(market_summary):
    # Convert all numpy types to Python native types
    market_summary = convert_numpy_types(market_summary)
    return f"""
    Analyze the following apparel market data and provide strategic insights:
    {json.dumps(market_summary, indent=2)}
    
    Focus on:
    1. Market positioning analysis
    - Price point optimization
    - Competition intensity
    - Market share opportunities
    
    2. Feature analysis
    - Most successful feature combinations
    - Underserved feature segments
    - Feature pricing premiums
    
    3. Growth opportunities
    - High-growth segments
    - Emerging trends
    - Market gaps
    
    4. Specific recommendations
    - Pricing strategy
    - Feature selection
    - Market positioning
    
    Provide data-driven insights and actionable recommendations.
    """

def create_competitive_analysis_prompt(similar_products_data, user_product):
    # Convert all numpy types to Python native types
    user_product = convert_numpy_types(user_product)
    similar_products_data = convert_numpy_types(similar_products_data)
    
    return f"""
    Analyze the competitive landscape for this product:
    
    Target Product:
    {json.dumps(user_product, indent=2)}
    
    Competitor Products:
    {json.dumps(similar_products_data, indent=2)}
    
    Provide insights on:
    1. Competitive Position
    - Price positioning relative to competitors
    - Feature differentiation
    - Rating and review performance
    
    2. Market Opportunities
    - Underserved features or segments
    - Price optimization potential
    - Review growth patterns
    
    3. Competitive Advantages
    - Unique selling propositions
    - Price-feature balance
    - Market reception
    
    4. Strategic Recommendations
    - Immediate improvements
    - Long-term positioning
    - Feature optimization
    
    Format as clear sections with specific, actionable insights.
    """

if __name__ == "__main__":
    main()
