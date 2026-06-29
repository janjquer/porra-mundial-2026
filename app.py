import functools
import os
import shutil

from dotenv import load_dotenv
load_dotenv()
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from scoring import load_real, refresh, run, save, save_real

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "porra2026-secret")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Always sync partits.csv from project root to data/ so disk never has a stale version
_partits_src = os.path.join(os.path.dirname(__file__), "partits.csv")
_partits_dst = os.path.join(DATA_DIR, "partits.csv")
if os.path.exists(_partits_src):
    os.makedirs(DATA_DIR, exist_ok=True)
    shutil.copy2(_partits_src, _partits_dst)


def _load_gent() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "gent.csv"), parse_dates=["dia"])


def _load_partits() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "partits.csv"), parse_dates=["dia"])


def _game_day(dt: datetime) -> date:
    """A game day runs 19:00–18:59 CEST, so subtract 7h and take the date."""
    return (dt - timedelta(hours=7)).date()


def _last_played_game_day(df: pd.DataFrame) -> date:
    """Game day of the most recent match with a score."""
    scored = df.dropna(subset=["punts"])
    if scored.empty:
        return _game_day(datetime.now(timezone.utc).replace(tzinfo=None))
    return scored["dia"].apply(_game_day).max()


def _standings_up_to(df: pd.DataFrame, max_game_day: date) -> pd.DataFrame:
    scored = df.dropna(subset=["punts"]).copy()
    scored["game_day"] = scored["dia"].apply(_game_day)
    subset = scored[scored["game_day"] <= max_game_day]
    return (
        subset.groupby("nom")["punts"]
        .sum()
        .reset_index()
        .rename(columns={"punts": "puntuacio"})
        .sort_values(["puntuacio", "nom"], ascending=[False, True])
        .assign(posicio=lambda x: range(1, len(x) + 1))
    )


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/standings")
def api_standings():
    df = _load_gent()
    today = _last_played_game_day(df)
    yesterday = today - timedelta(days=1)

    current = _standings_up_to(df, today)
    old = _standings_up_to(df, yesterday)

    merged = current.merge(old[["nom", "posicio", "puntuacio"]], on="nom", suffixes=("", "_ahir"), how="left")
    merged["dif_pos"] = (merged["posicio_ahir"].fillna(merged["posicio"]) - merged["posicio"]).astype(int)
    merged["dif_punts"] = (merged["puntuacio"] - merged["puntuacio_ahir"].fillna(0)).astype(int)

    return jsonify(merged[["posicio", "nom", "puntuacio", "dif_pos", "dif_punts"]].to_dict(orient="records"))


@app.route("/api/daily")
def api_daily():
    df = _load_gent()
    today = _last_played_game_day(df)

    scored = df.dropna(subset=["punts"]).copy()
    scored["game_day"] = scored["dia"].apply(_game_day)
    recent = scored[scored["game_day"] == today]

    if recent.empty:
        return jsonify([])
    result = (
        recent.groupby("nom")["punts"]
        .sum()
        .reset_index()
        .rename(columns={"punts": "puntuacio"})
        .sort_values(["puntuacio", "nom"], ascending=[False, True])
        .assign(posicio=lambda x: range(1, len(x) + 1))
    )
    return jsonify(result.to_dict(orient="records"))


@app.route("/api/match/<int:n_partit>")
def api_match(n_partit):
    df = _load_gent()
    partits = _load_partits()
    match_row = partits[partits["n_partit"] == n_partit]
    if match_row.empty:
        return jsonify({"error": "Match not found"}), 404
    partit_name = match_row.iloc[0]["partit"]
    preds = df[df["partit"] == partit_name].copy()
    preds["local"] = preds["local"].astype(int)
    preds["visitant"] = preds["visitant"].astype(int)
    preds["resultat"] = preds["local"].astype(str) + "-" + preds["visitant"].astype(str)

    agg = (
        preds.groupby("resultat")
        .agg(n=("nom", "count"), punts=("punts", "first"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    agg["punts"] = agg["punts"].apply(lambda x: None if pd.isna(x) else int(x))
    return jsonify({
        "partit": partit_name,
        "predictions": agg.to_dict(orient="records"),
    })


@app.route("/api/matches")
def api_matches():
    partits = _load_partits()
    gent = _load_gent()
    real = load_real()

    rows = []
    for _, row in partits.iterrows():
        result = real.get(row["partit"])
        match_gent = gent[gent["partit"] == row["partit"]]
        clavats = int((match_gent["punts"] == 15).sum())
        grup_val = row["grup"] if pd.notna(row.get("grup")) else None
        fase_val = row["fase"] if ("fase" in row.index and pd.notna(row.get("fase"))) else None
        rows.append({
            "n_partit": int(row["n_partit"]),
            "dia": row["dia"].isoformat() if hasattr(row["dia"], "isoformat") else str(row["dia"]),
            "grup": grup_val,
            "fase": fase_val,
            "partit": row["partit"],
            "resultat": f"{result['home_score']}-{result['away_score']}" if result else None,
            "clavats": clavats,
        })
    return jsonify(rows)


@app.route("/api/clavats")
def api_clavats():
    df = _load_gent()
    clavats = (
        df[df["punts"] == 15]
        .groupby("nom")
        .agg(clavats=("punts", "count"), primer=("dia", "min"), ultim=("dia", "max"))
        .reset_index()
        .sort_values("clavats", ascending=False)
    )
    clavats["primer"] = clavats["primer"].astype(str)
    clavats["ultim"] = clavats["ultim"].astype(str)
    return jsonify(clavats.to_dict(orient="records"))


@app.route("/api/match-clavats")
def api_match_clavats():
    df = _load_gent()
    mc = (
        df[df["punts"] == 15]
        .groupby("partit")
        .agg(clavats=("punts", "count"), dia=("dia", "min"))
        .reset_index()
        .sort_values("clavats", ascending=False)
    )
    mc["dia"] = mc["dia"].astype(str)
    return jsonify(mc.to_dict(orient="records"))


JORNADA_RANGES = {1: (1, 24), 2: (25, 48), 3: (49, 72)}


@app.route("/api/ranking")
def api_ranking():
    fase = request.args.get("fase")
    grup = request.args.get("grup")
    jornada = request.args.get("jornada", type=int)
    seleccio = request.args.get("seleccio")

    df = _load_gent()
    partits = _load_partits()

    if fase and "fase" in partits.columns:
        valid_partits = partits[partits["fase"] == fase]["partit"].tolist()
        df = df[df["partit"].isin(valid_partits)]

    if grup:
        valid_partits = partits[partits["grup"] == grup]["partit"].tolist()
        df = df[df["partit"].isin(valid_partits)]

    if jornada and jornada in JORNADA_RANGES:
        lo, hi = JORNADA_RANGES[jornada]
        valid = partits[(partits["n_partit"] >= lo) & (partits["n_partit"] <= hi)]["partit"].tolist()
        df = df[df["partit"].isin(valid)]

    if seleccio:
        df = df[
            df["partit"].str.startswith(seleccio + " - ") |
            df["partit"].str.endswith(" - " + seleccio)
        ]

    scored = df.dropna(subset=["punts"])
    if scored.empty:
        return jsonify([])

    pts = scored.groupby("nom")["punts"].sum().rename("puntuacio")
    clavats = (scored[scored["punts"] == 15].groupby("nom")["punts"].count().rename("clavats"))
    result = (
        pts.to_frame()
        .join(clavats, how="left")
        .fillna({"clavats": 0})
        .astype({"clavats": int})
        .reset_index()
        .sort_values(["puntuacio", "nom"], ascending=[False, True])
        .assign(posicio=lambda x: range(1, len(x) + 1))
    )
    return jsonify(result.to_dict(orient="records"))


@app.route("/api/last-update")
def api_last_update():
    real = load_real()
    if not real:
        return jsonify({"text": None})
    partits = _load_partits()
    played = partits[partits["partit"].isin(real.keys())]
    if played.empty:
        return jsonify({"text": None})
    last = played.sort_values("dia").iloc[-1]
    r = real[last["partit"]]
    home, away = last["partit"].split(" - ", 1)
    hour = last["dia"].strftime("%H:%M")
    return jsonify({"text": f"{hour} {home} {r['home_score']} - {r['away_score']} {away}"})


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        error = "Contrasenya incorrecta"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin():
    partits = _load_partits()
    real = load_real()
    return render_template("admin.html",
                           partits=partits.to_dict(orient="records"),
                           real=real)


@app.route("/api/admin/result", methods=["POST"])
@login_required
def api_admin_result():
    data = request.json
    n_partit = int(data["n_partit"])
    home_score = int(data["home_score"])
    away_score = int(data["away_score"])

    partits = _load_partits()
    row = partits[partits["n_partit"] == n_partit]
    if row.empty:
        return jsonify({"error": "Match not found"}), 404

    partit_name = row.iloc[0]["partit"]
    real = load_real()
    real[partit_name] = {"home_score": home_score, "away_score": away_score}
    save_real(real)

    df = run(real)
    save(df)

    return jsonify({"ok": True, "partit": partit_name})


@app.route("/api/admin/result/<int:n_partit>", methods=["DELETE"])
@login_required
def api_admin_delete_result(n_partit):
    partits = _load_partits()
    row = partits[partits["n_partit"] == n_partit]
    if row.empty:
        return jsonify({"error": "Match not found"}), 404

    partit_name = row.iloc[0]["partit"]
    real = load_real()
    if partit_name in real:
        del real[partit_name]
        save_real(real)
        df = run(real)
        save(df)
    return jsonify({"ok": True})


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    partits = _load_partits()
    grups = sorted(partits["grup"].dropna().unique())
    fases = partits["fase"].dropna().unique().tolist() if "fase" in partits.columns else []
    teams = sorted({t for p in partits["partit"] for t in p.split(" - ")})
    return render_template("index.html", grups=grups, fases=fases, partits=partits.to_dict(orient="records"), teams=teams)


if __name__ == "__main__":
    app.run(debug=True)
