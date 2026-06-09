# -*- coding: utf-8 -*-
"""NutriTrack Pro — Génération du rapport hebdomadaire HTML."""
import os
import tempfile
from datetime import date as _date

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, Arial, sans-serif; background: #f5f5f5; color: #1a1a1a; padding: 20px; }
.page { max-width: 920px; margin: 0 auto; background: white; border-radius: 12px;
        overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
header { background: #0d1117; color: white; padding: 20px 28px;
         display: flex; justify-content: space-between; align-items: center; }
header h1 { font-size: 20px; }
header p  { font-size: 12px; opacity: .7; margin-top: 4px; }
.btn-print { background: #22c55e; color: #000; border: none; padding: 8px 18px;
             border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
           padding: 20px 28px; background: #f8f9fa; }
.kpi { text-align: center; }
.kpi .val { font-size: 26px; font-weight: bold; color: #22c55e; }
.kpi .lbl { font-size: 11px; color: #666; margin-top: 3px; }
section { padding: 20px 28px; border-top: 1px solid #eee; }
section h2 { font-size: 15px; font-weight: bold; color: #333;
             border-left: 3px solid #22c55e; padding-left: 10px; margin-bottom: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #0d1117; color: white; padding: 8px 10px; text-align: right;
     font-weight: 500; font-size: 12px; }
th:first-child { text-align: left; }
td { padding: 7px 10px; text-align: right; border-bottom: 1px solid #f0f0f0; }
td:first-child { text-align: left; font-weight: 500; }
tr.ok  td { background: #f0fdf4; }
tr.nok td { background: #fff5f5; }
tr.empty td { color: #bbb; font-style: italic; }
.badge { display: inline-block; padding: 1px 7px; border-radius: 10px;
         font-size: 10px; font-weight: bold; margin-left: 6px; }
.badge-ok  { background: #dcfce7; color: #16a34a; }
.badge-nok { background: #fee2e2; color: #dc2626; }
.sport-item { display: flex; justify-content: space-between; padding: 6px 0;
              border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.sport-item:last-child { border-bottom: none; }
.progress-bar  { background: #eee; border-radius: 8px; height: 14px;
                 overflow: hidden; margin: 8px 0; }
.progress-fill { background: #22c55e; height: 100%; border-radius: 8px; }
footer { padding: 12px 28px; font-size: 11px; color: #aaa; text-align: center;
         border-top: 1px solid #eee; }
@media print {
  body { background: white; padding: 0; }
  .page { box-shadow: none; border-radius: 0; }
  .no-print { display: none !important; }
}
"""


def generer_rapport_html(data: dict) -> str:
    """Génère le HTML et retourne le chemin du fichier temporaire."""
    html = _build_html(data)
    fd, path = tempfile.mkstemp(suffix='.html', prefix='nutritrack_rapport_')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(html)
    return path


def _build_html(data: dict) -> str:
    user = data['user']
    nom  = f"{user.get('prenom','')} {user.get('nom','')}".strip() or "Utilisateur"

    moy   = data['moyennes']
    sport = data['sport']
    cible = data['cible']
    adh   = data['adherence']

    # ── KPI row ──────────────────────────────────────────────────
    eau_l   = round(moy.get('eau_ml', 0) / 1000, 1)
    kpis    = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="val">{int(moy['calories'])}</div><div class="lbl">Calories moy./jour</div></div>
      <div class="kpi"><div class="val">{int(moy['proteines'])} g</div><div class="lbl">Protéines moy./jour</div></div>
      <div class="kpi"><div class="val">{eau_l} L</div><div class="lbl">Eau moy./jour</div></div>
      <div class="kpi"><div class="val">{sport['nb_seances']}</div><div class="lbl">Séances sport</div></div>
    </div>"""

    # ── Tableau journalier ────────────────────────────────────────
    rows_html = ""
    for j in data['jours']:
        if not j['enregistre']:
            css, badge = 'empty', ''
            vals = '<td>—</td>' * 6
        elif j['a_objectif']:
            css   = 'ok'
            badge = '<span class="badge badge-ok">✓ Objectif</span>'
            vals  = (f'<td>{int(j["calories"])}</td><td>{int(j["proteines"])} g</td>'
                     f'<td>{int(j["glucides"])} g</td><td>{int(j["lipides"])} g</td>'
                     f'<td>{int(j["fibres"])} g</td><td>{int(j["eau_ml"])} ml</td>')
        else:
            css   = 'nok'
            badge = '<span class="badge badge-nok">✗</span>'
            vals  = (f'<td>{int(j["calories"])}</td><td>{int(j["proteines"])} g</td>'
                     f'<td>{int(j["glucides"])} g</td><td>{int(j["lipides"])} g</td>'
                     f'<td>{int(j["fibres"])} g</td><td>{int(j["eau_ml"])} ml</td>')
        rows_html += f'<tr class="{css}"><td>{j["label"]}{badge}</td>{vals}</tr>'

    table_html = f"""
    <section>
      <h2>📅 Détail journalier</h2>
      <table>
        <thead><tr>
          <th>Jour</th>
          <th>Calories<br><small>cible {cible['calories']} kcal</small></th>
          <th>Protéines</th><th>Glucides</th><th>Lipides</th><th>Fibres</th><th>Eau</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>"""

    # ── Sport ─────────────────────────────────────────────────────
    if sport['seances']:
        items = "".join(
            f'<div class="sport-item">'
            f'<span>{s["label"]}</span>'
            f'<span>{s["date"][8:]}/{s["date"][5:7]} · {s["duree_min"]} min · {int(s["calories_brulees"])} kcal</span>'
            f'</div>'
            for s in sport['seances'])
        sport_html = f"""
    <section>
      <h2>🏃 Sport</h2>
      {items}
      <p style="margin-top:10px;font-size:12px;color:#666;">
        Total : {sport['nb_seances']} séance(s) · {sport['total_min']} min · {int(sport['total_cal'])} kcal brûlées
      </p>
    </section>"""
    else:
        sport_html = """
    <section>
      <h2>🏃 Sport</h2>
      <p style="color:#bbb;font-size:13px;">Aucune séance enregistrée cette semaine.</p>
    </section>"""

    # ── Adhérence ─────────────────────────────────────────────────
    pct        = adh['pct']
    pct_color  = '#16a34a' if pct >= 70 else ('#f59e0b' if pct >= 40 else '#dc2626')
    adh_html   = f"""
    <section>
      <h2>🎯 Adhérence à l'objectif calorique (±10 %)</h2>
      <p style="font-size:13px;color:#555;">
        {adh['jours_ok']} / {adh['jours_enregistres']} jours enregistrés dans l'objectif
      </p>
      <div class="progress-bar">
        <div class="progress-fill" style="width:{pct}%"></div>
      </div>
      <p style="font-size:14px;font-weight:bold;color:{pct_color};">{pct} %</p>
    </section>"""

    today = _date.today().strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Bilan semaine — NutriTrack Pro</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <header>
    <div>
      <h1>🥗 NutriTrack Pro — Bilan nutritionnel hebdomadaire</h1>
      <p>{nom} · {user.get('objectif','—')} · {data['semaine_label']}</p>
    </div>
    <button class="btn-print no-print" onclick="window.print()">🖨️ Imprimer</button>
  </header>
  {kpis}
  {table_html}
  {sport_html}
  {adh_html}
  <footer>Généré le {today} par NutriTrack Pro</footer>
</div>
</body>
</html>"""
