import os
import pickle
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_500 = "https://image.tmdb.org/t/p/w500"

app = FastAPI(title="Movie Recommender API")

# --- CORS SETTINGS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows Streamlit Cloud to talk to this API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PICKLE LOADING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DF_PATH = os.path.join(BASE_DIR, "df.pkl")
INDICES_PATH = os.path.join(BASE_DIR, "indices.pkl")
TFIDF_MATRIX_PATH = os.path.join(BASE_DIR, "tfidf_matrix.pkl")

df = None
title_to_idx = {}
tfidf_matrix = None

@app.on_event("startup")
def load_data():
    global df, title_to_idx, tfidf_matrix
    try:
        with open(DF_PATH, "rb") as f: df = pickle.load(f)
        with open(INDICES_PATH, "rb") as f: 
            indices = pickle.load(f)
            title_to_idx = {str(k).lower(): v for k, v in indices.items()}
        with open(TFIDF_MATRIX_PATH, "rb") as f: tfidf_matrix = pickle.load(f)
        print("Backend data loaded successfully!")
    except Exception as e:
        print(f"Error loading pickle files: {e}")

# --- MODELS ---
class TMDBMovieCard(BaseModel):
    tmdb_id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[str] = None

class TMDBMovieDetails(BaseModel):
    tmdb_id: int
    title: str
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    genres: List[dict] = []
    release_date: Optional[str] = None

class TFIDFRecItem(BaseModel):
    title: str
    score: float
    tmdb: Optional[TMDBMovieCard] = None

class SearchBundleResponse(BaseModel):
    query: str
    movie_details: TMDBMovieDetails
    tfidf_recommendations: List[TFIDFRecItem]
    genre_recommendations: List[TMDBMovieCard]

# --- HELPERS ---
async def tmdb_get(path: str, params: dict):
    params["api_key"] = TMDB_API_KEY
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}

def make_card(m):
    return TMDBMovieCard(
        tmdb_id=m.get("id"),
        title=m.get("title", "Unknown"),
        poster_url=f"{TMDB_IMG_500}{m.get('poster_path')}" if m.get('poster_path') else None,
        release_date=m.get("release_date")
    )

# --- ROUTES ---
@app.get("/home", response_model=List[TMDBMovieCard])
async def get_home(category: str = "popular"):
    path = "/trending/movie/day" if category == "trending" else f"/movie/{category}"
    data = await tmdb_get(path, {"language": "en-US"})
    return [make_card(m) for m in data.get("results", [])[:24]]

@app.get("/tmdb/search")
async def search_tmdb(query: str):
    return await tmdb_get("/search/movie", {"query": query})

@app.get("/movie/id/{tmdb_id}", response_model=TMDBMovieDetails)
async def get_details(tmdb_id: int):
    m = await tmdb_get(f"/movie/{tmdb_id}", {"language": "en-US"})
    return TMDBMovieDetails(
        tmdb_id=m.get("id"),
        title=m.get("title", ""),
        overview=m.get("overview"),
        poster_url=f"{TMDB_IMG_500}{m.get('poster_path')}" if m.get('poster_path') else None,
        genres=m.get("genres", []),
        release_date=m.get("release_date")
    )

@app.get("/movie/search", response_model=SearchBundleResponse)
async def get_recommendations(query: str):
    search = await tmdb_get("/search/movie", {"query": query})
    if not search.get("results"): raise HTTPException(status_code=404)
    best = search["results"][0]
    details = await get_details(best["id"])

    # 1. Content-Based (TF-IDF)
    recs = []
    norm_title = details.title.lower()
    if tfidf_matrix is not None and norm_title in title_to_idx:
        idx = title_to_idx[norm_title]
        # Calculate cosine similarity using the sparse matrix
        qv = tfidf_matrix[idx]
        scores = (tfidf_matrix @ qv.T).toarray().ravel()
        order = np.argsort(-scores)[1:13]
        
        for i in order:
            t = df.iloc[i]["title"]
            s_res = await tmdb_get("/search/movie", {"query": t})
            card = make_card(s_res["results"][0]) if s_res.get("results") else None
            recs.append(TFIDFRecItem(title=t, score=float(scores[i]), tmdb=card))

    # 2. Genre-Based
    genre_recs = []
    if details.genres:
        g_id = details.genres[0]["id"]
        g_data = await tmdb_get("/discover/movie", {"with_genres": g_id, "sort_by": "popularity.desc"})
        genre_recs = [make_card(m) for m in g_data.get("results", [])[:12] if m.get("id") != details.tmdb_id]

    return SearchBundleResponse(
        query=query,
        movie_details=details,
        tfidf_recommendations=recs,
        genre_recommendations=genre_recs
    )