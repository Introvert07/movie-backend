import requests
import streamlit as st

# =============================
# CONFIG
# =============================
API_BASE =  "MOVIE_API_URL" or "http://127.0.0.1:8000" 
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"
# High-quality fallback image for missing posters
FALLBACK_IMG = "https://images.unsplash.com/photo-1485846234645-a62644f84728?q=80&w=500&auto=format&fit=crop"

st.set_page_config(page_title="Cinema AI", page_icon="🍿", layout="wide")

# =============================
# CSS: GLASSMORPHISM & PERFORMANCE
# =============================
st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .block-container { padding-top: 1.5rem; max-width: 1400px; }
    
    /* Movie Card Effect */
    .movie-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 8px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .movie-card:hover {
        transform: scale(1.03);
        border-color: #ff4b4b;
        background: rgba(255, 255, 255, 0.07);
    }
    
    .movie-title {
        font-weight: 600;
        font-size: 0.88rem;
        margin: 8px 0;
        height: 36px;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        line-height: 1.2;
    }
    
    .genre-tag {
        background: linear-gradient(90deg, #ff4b4b, #ff7e7e);
        color: white;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 500;
        margin-right: 6px;
    }

    /* Scrollbar for slow networks */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# LOGIC: ROUTING & STATE
# =============================
if "view" not in st.session_state: st.session_state.view = "home"
if "selected_id" not in st.session_state: st.session_state.selected_id = None

# Handle URL parameters for direct linking
params = st.query_params
if params.get("view") == "details" and params.get("id"):
    st.session_state.view = "details"
    st.session_state.selected_id = int(params.get("id"))

def nav_to(view, movie_id=None):
    st.session_state.view = view
    st.session_state.selected_id = movie_id
    
    # Safe way to update URL parameters in Streamlit
    st.query_params.clear()
    if view == "details" and movie_id:
        st.query_params["view"] = "details"
        st.query_params["id"] = str(movie_id)
        
    st.rerun()

# =============================
# API UTILS
# =============================
@st.cache_data(ttl=600, show_spinner=False)
def safe_fetch(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=8)
        if r.status_code == 200: return r.json(), None
        return None, f"Error {r.status_code}"
    except Exception as e:
        return None, "Connection Error"

def validate_img(url):
    """Prevents 'None' string errors in browser console"""
    if not url or "None" in str(url) or url == TMDB_IMG_BASE:
        return FALLBACK_IMG
    return url

def render_grid(movies, cols=5, key_p="grid"):
    if not movies:
        st.info("No movies found.")
        return
    
    for i in range(0, len(movies), cols):
        cols_obj = st.columns(cols)
        for j, movie in enumerate(movies[i : i + cols]):
            with cols_obj[j]:
                poster = validate_img(movie.get("poster_url"))
                
                st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                st.image(poster, use_container_width=True)
                st.markdown(f'<div class="movie-title">{movie["title"]}</div>', unsafe_allow_html=True)
                
                # Small, clean button
                if st.button("Details", key=f"btn_{key_p}_{movie['tmdb_id']}_{i+j}", use_container_width=True):
                    nav_to("details", movie['tmdb_id'])
                st.markdown('</div>', unsafe_allow_html=True)

# =============================
# UI: SIDEBAR
# =============================
with st.sidebar:
    st.title("🎬 Cinema AI")
    if st.button("🏠 Home Catalog", use_container_width=True): nav_to("home")
    st.divider()
    cat = st.selectbox("Feed Category", ["popular", "trending", "top_rated", "upcoming"])
    grid_size = st.slider("View Density", 3, 7, 5)

# =============================
# VIEW: HOME
# =============================
if st.session_state.view == "home":
    st.title("Discover")
    query = st.text_input("", placeholder="🔍 Search movies...", label_visibility="collapsed")

    if query:
        data, err = safe_fetch("/tmdb/search", {"query": query})
        if data:
            results = data.get("results", [])
            st.subheader(f"Results for '{query}'")
            # Convert TMDB format to Card format
            cards = [{"tmdb_id": m['id'], "title": m['title'], "poster_url": f"{TMDB_IMG_BASE}{m.get('poster_path')}"} for m in results]
            render_grid(cards, cols=grid_size, key_p="search")
    else:
        st.subheader(f"🔥 {cat.title()}")
        home_data, err = safe_fetch("/home", {"category": cat})
        if home_data:
            render_grid(home_data, cols=grid_size, key_p="home")
        elif err:
            st.warning("Backend offline or loading...")

# =============================
# VIEW: DETAILS
# =============================
else:
    m_id = st.session_state.selected_id
    movie, err = safe_fetch(f"/movie/id/{m_id}")
    
    if movie:
        c1, c2 = st.columns([1, 2.2], gap="large")
        with c1:
            st.image(validate_img(movie.get("poster_url")), use_container_width=True)
        with c2:
            st.title(movie['title'])
            # Render Genre Badges
            genres = "".join([f'<span class="genre-tag">{g["name"]}</span>' for g in movie.get("genres", [])])
            st.markdown(genres, unsafe_allow_html=True)
            
            st.write(f"**Released:** {movie.get('release_date')}")
            st.markdown("### Overview")
            st.write(movie.get("overview") or "No description available.")
            
            if st.button("⬅️ Back to Browse", use_container_width=True): nav_to("home")

        st.divider()
        st.subheader("🎯 Smart Recommendations")
        
        with st.spinner("Calculating similarity..."):
            bundle, b_err = safe_fetch("/movie/search", {"query": movie['title']})
            if bundle:
                t1, t2 = st.tabs(["AI Content Match", "Genre Explore"])
                with t1:
                    raw_recs = bundle.get("tfidf_recommendations", [])
                    # Flattening the nested TMDB dict from backend
                    tfidf_cards = [r['tmdb'] for r in raw_recs if r.get('tmdb')]
                    render_grid(tfidf_cards, cols=grid_size, key_p="tfidf")
                with t2:
                    render_grid(bundle.get("genre_recommendations", []), cols=grid_size, key_p="genre")
    else:
        st.error("Movie not found.")
        if st.button("Go Home"): nav_to("home")