"""Calcul des notes à partir des mesures.

Règle : une question rapporte ses points si exactement une case est cochée
et que c'est la bonne. Zéro sinon (blanc, mauvaise réponse ou réponses
multiples). Si les points négatifs sont activés sur le sujet, une mauvaise
réponse ou des réponses multiples retirent le malus ; un blanc reste à
zéro, et la note de la copie ne descend jamais sous 0.
"""

from . import config as C
from . import db


def cases_a_reviser(con, sujet_id):
    """Cases douteuses non tranchées, pour l'écran de révision manuelle."""
    return con.execute(
        "SELECT m.case_id, m.ratio, m.crop, co.numero, e.nom, e.prenom,"
        "       cq.ordre AS q_ordre, cr.ordre AS r_ordre "
        "FROM mesures m "
        "JOIN cases ca ON ca.id = m.case_id "
        "JOIN copies co ON co.id = ca.copie_id "
        "JOIN eleves e ON e.id = co.eleve_id "
        "JOIN copie_questions cq ON cq.copie_id = ca.copie_id "
        "  AND cq.question_id = ca.question_id "
        "JOIN copie_reponses cr ON cr.copie_id = ca.copie_id "
        "  AND cr.question_id = ca.question_id "
        "  AND cr.reponse_id = ca.reponse_id "
        "WHERE co.sujet_id=? AND m.etat='douteuse' AND m.decision IS NULL "
        "ORDER BY co.numero, cq.ordre, cr.ordre", (sujet_id,)).fetchall()


def trancher(con, case_id, decision):
    """decision : 'cochee' ou 'vide'."""
    con.execute("UPDATE mesures SET decision=? WHERE case_id=?",
                (decision, case_id))
    con.commit()


def _case_cochee(mesure, mode):
    """True/False/None (None = douteuse non tranchée en mode manuel)."""
    if mesure is None:
        return None
    if mesure["decision"]:
        return mesure["decision"] == "cochee"
    if mode == "auto":
        return mesure["ratio"] >= C.SEUIL_AUTO
    if mesure["etat"] == "douteuse":
        return None
    return mesure["etat"] == "cochee"


def corriger_sujet(con, sujet_id, mode="auto"):
    """Retourne la liste des résultats par copie."""
    sujet = con.execute("SELECT * FROM sujets WHERE id=?",
                        (sujet_id,)).fetchone()
    total = sum(
        (q["points"] if sujet["coef_actifs"] else sujet["points_defaut"])
        for q in db.questions_du_sujet(con, sujet_id))
    malus = sujet["malus"] if sujet["malus_actif"] else 0.0

    resultats = []
    for copie in db.copies_du_sujet(con, sujet_id):
        cid = copie["id"]
        pages_vues = {r["page"] for r in con.execute(
            "SELECT page FROM pages_scannees WHERE copie_id=?", (cid,))}
        manquantes = sorted(set(range(1, copie["nb_pages"] + 1)) - pages_vues)

        note = 0.0
        detail = []
        for cq in con.execute(
                "SELECT cq.question_id, cq.ordre, sq.points "
                "FROM copie_questions cq "
                "JOIN sujet_questions sq ON sq.sujet_id=? "
                "  AND sq.question_id = cq.question_id "
                "WHERE cq.copie_id=? ORDER BY cq.ordre",
                (sujet_id, cid)).fetchall():
            qid = cq["question_id"]
            pts = (cq["points"] if sujet["coef_actifs"]
                   else sujet["points_defaut"])
            rows = con.execute(
                "SELECT ca.id AS case_id, ca.reponse_id, r.correcte,"
                "       cr.ordre AS r_ordre, m.ratio, m.etat, m.decision "
                "FROM cases ca "
                "JOIN reponses r ON r.id = ca.reponse_id "
                "JOIN copie_reponses cr ON cr.copie_id = ca.copie_id "
                "  AND cr.question_id = ca.question_id "
                "  AND cr.reponse_id = ca.reponse_id "
                "LEFT JOIN mesures m ON m.case_id = ca.id "
                "WHERE ca.copie_id=? AND ca.question_id=? "
                "ORDER BY cr.ordre", (cid, qid)).fetchall()

            correcte_id = next((r["reponse_id"] for r in rows
                                if r["correcte"]), None)
            if any(r["ratio"] is None for r in rows):
                statut, cochees = "incomplet", []
            else:
                etats = {r["reponse_id"]: _case_cochee(r, mode) for r in rows}
                if any(v is None for v in etats.values()):
                    statut, cochees = "a_reviser", []
                else:
                    cochees = [rid for rid, v in etats.items() if v]
                    if not cochees:
                        statut = "blanc"
                    elif len(cochees) > 1:
                        statut = "multiple"
                        note -= malus
                    elif cochees[0] == correcte_id:
                        statut = "juste"
                        note += pts
                    else:
                        statut = "faux"
                        note -= malus
            lettres = {r["reponse_id"]: chr(65 + r["r_ordre"]) for r in rows}
            detail.append({
                "ordre": cq["ordre"] + 1, "question_id": qid,
                "points": pts, "statut": statut,
                "cochees": cochees, "correcte_id": correcte_id,
                "lettres": lettres,
            })
        note = max(note, 0.0)
        resultats.append({
            "copie_id": cid, "numero": copie["numero"],
            "eleve": f"{copie['nom']} {copie['prenom']}".strip(),
            "nom": copie["nom"], "prenom": copie["prenom"],
            "note": note, "total": total,
            "note20": round(note * 20 / total, 2) if total else 0.0,
            "pages_manquantes": manquantes,
            "questions": detail,
        })
    return resultats


def stats_questions(con, sujet_id, resultats):
    """Taux de réussite par question (dans l'ordre de la banque du sujet)."""
    stats = {}
    for res in resultats:
        for q in res["questions"]:
            s = stats.setdefault(q["question_id"],
                                 {"juste": 0, "faux": 0, "blanc": 0,
                                  "multiple": 0, "autres": 0})
            cle = q["statut"] if q["statut"] in s else "autres"
            s[cle] += 1
    lignes = []
    for i, q in enumerate(db.questions_du_sujet(con, sujet_id), start=1):
        s = stats.get(q["id"], {})
        n = sum(s.values()) or 1
        lignes.append({
            "num": i, "question_id": q["id"], "chapitre": q["chapitre"],
            "enonce": q["enonce"], "reussite": s.get("juste", 0) / n,
            **{k: s.get(k, 0) for k in
               ("juste", "faux", "blanc", "multiple", "autres")},
        })
    return lignes
