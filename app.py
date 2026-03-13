import requests
import streamlit as st

# =============================
# CONFIG
# =============================
API_BASE = "https://movie-backend-wqs0.onrender.com"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"
FALLBACK_IMG = "https://images.unsplash.com/photo-1485846234645-a62644f84728?q=80&w=500&auto=format&fit=crop"

st.set_page_config(page_title="Cinema AI", page_icon="🍿", layout="wide")

# =============================
# CSS
# =============================
st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .block-container { padding-top: 1.5rem; max-width: 1400px; }

    .movie-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 8px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        margin-bottom: 4px;
    }
    .movie-card:hover {
        transform: scale(1.03);
        border-color: #ff4b4b;
        background: rgba(255, 255, 255, 0.07);
    }
    .movie-card img {
        width: 100%;
        border-radius: 8px;
        aspect-ratio: 2 / 3;
        object-fit: cover;
        display: block;
        background: #1a1d24;
    }
    .movie-title {
        font-weight: 600;
        font-size: 0.88rem;
        margin: 8px 0 6px 0;
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
    .detail-poster img {
        width: 100%;
        border-radius: 14px;
        aspect-ratio: 2 / 3;
        object-fit: cover;
        display: block;
        background: #1a1d24;
    }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# ROUTING & STATE
# =============================
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None

params = st.query_params
if params.get("view") == "details" and params.get("id"):
    st.session_state.view = "details"
    st.session_state.selected_id = int(params.get("id"))


def nav_to(view, movie_id=None):
    st.session_state.view = view
    st.session_state.selected_id = movie_id
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
        if r.status_code == 200:
            return r.json(), None
        return None, f"Error {r.status_code}"
    except Exception:
        return None, "Connection Error"


def validate_img(url) -> str:
    """Always returns a safe, non-None string URL."""
    if not isinstance(url, str):
        return FALLBACK_IMG
    url = url.strip()
    if not url or "None" in url or url == TMDB_IMG_BASE or not url.startswith("http"):
        return FALLBACK_IMG
    return url


def img_tag(url: str, extra_style: str = "") -> str:
    """
    Returns a safe <img> HTML tag.
    onerror swaps in FALLBACK_IMG client-side — survives any broken URL
    that slips past validate_img.
    """
    safe = validate_img(url)
    return (
        f'<img src="{safe}" '
        f'onerror="this.onerror=null;this.src=\'{FALLBACK_IMG}\';" '
        f'style="{extra_style}" />'
    )


# =============================
# GRID RENDERER
# =============================
def render_grid(movies, cols=5, key_p="grid"):
    if not isinstance(movies, list):
        st.error("Data format error: Expected a list of movies.")
        return
    if not movies:
        st.info("No movies found.")
        return

    for i in range(0, len(movies), cols):
        cols_obj = st.columns(cols)
        batch = movies[i : i + cols]

        for j, movie in enumerate(batch):
            with cols_obj[j]:
                m_id = movie.get("tmdb_id", f"unknown_{i}_{j}")
                title = movie.get("title", "Untitled")
                poster_html = img_tag(movie.get("poster_url"))

                # Single markdown block per card — no st.image(), no crash
                st.markdown(
                    f"""
                    <div class="movie-card">
                        {poster_html}
                        <div class="movie-title">{title}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                btn_key = f"btn_{key_p}_{m_id}_{i + j}"
                if st.button("Details", key=btn_key, use_container_width=True):
                    nav_to("details", m_id)


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.title("🎬 Cinema AI")
    if st.button("🏠 Home Catalog", use_container_width=True):
        nav_to("home")
    st.divider()
    cat = st.selectbox("Feed Category", ["popular", "trending", "top_rated", "upcoming"])
    grid_size = st.slider("View Density", 3, 7, 5)


# =============================
# VIEW: HOME
# =============================
if st.session_state.view == "home":
    st.title("Discover")
    query = st.text_input(
        "", placeholder="🔍 Search movies...", label_visibility="collapsed"
    )

    if query:
        data, err = safe_fetch("/tmdb/search", {"query": query})
        if data:
            results = data.get("results", [])
            st.subheader(f"Results for '{query}'")
            cards = [
                {
                    "tmdb_id": m["id"],
                    "title": m.get("title", ""),
                    # validate_img will catch the None poster_path case
                    "poster_url": f"{TMDB_IMG_BASE}{m.get('poster_path')}",
                }
                for m in results
            ]
            render_grid(cards, cols=grid_size, key_p="search")
        elif err:
            st.warning(f"Search failed: {err}")
    else:
        st.subheader(f"🔥 {cat.replace('_', ' ').title()}")
        home_data, err = safe_fetch("/home", {"category": cat})
        if home_data:
            render_grid(home_data, cols=grid_size, key_p="home")
        elif err:
            st.warning("Backend offline or still loading — try again in a moment.")


# =============================
# VIEW: DETAILS
# =============================
else:
    m_id = st.session_state.selected_id
    movie, err = safe_fetch(f"/movie/id/{m_id}")

    if movie:
        c1, c2 = st.columns([1, 2.2], gap="large")

        with c1:
            # Detail poster — larger, rounded via .detail-poster CSS class
            st.markdown(
                f'<div class="detail-poster">{img_tag(movie.get("poster_url"))}</div>',
                unsafe_allow_html=True,
            )

        with c2:
            st.title(movie["title"])

            genres_html = "".join(
                [
                    f'<span class="genre-tag">{g["name"]}</span>'
                    for g in movie.get("genres", [])
                ]
            )
            st.markdown(genres_html, unsafe_allow_html=True)
            st.write("")  # spacer after badges

            st.write(f"**Released:** {movie.get('release_date', 'N/A')}")
            st.markdown("### Overview")
            st.write(movie.get("overview") or "No description available.")

            if st.button("⬅️ Back to Browse", use_container_width=True):
                nav_to("home")

        st.divider()
        st.subheader("🎯 Smart Recommendations")

        with st.spinner("Calculating similarity..."):
            bundle, b_err = safe_fetch("/movie/search", {"query": movie["title"]})
            if bundle:
                t1, t2 = st.tabs(["AI Content Match", "Genre Explore"])
                with t1:
                    raw_recs = bundle.get("tfidf_recommendations", [])
                    tfidf_cards = [r["tmdb"] for r in raw_recs if r.get("tmdb")]
                    render_grid(tfidf_cards, cols=grid_size, key_p="tfidf")
                with t2:
                    render_grid(
                        bundle.get("genre_recommendations", []),
                        cols=grid_size,
                        key_p="genre",
                    )
            elif b_err:
                st.warning("Could not load recommendations.")
    else:
        st.error("Movie not found.")
        if st.button("Go Home"):
            nav_to("home")