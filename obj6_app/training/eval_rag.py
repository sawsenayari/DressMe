"""Évalue la récupération RAG : la bonne fiche est-elle dans le top-1 / top-3 ? python -m training.eval_rag (étiquettes subjectives)"""
from app.rag import retrieve

GOLD = [("فرح صاحبي هذا الويكاند", "Mariage"), ("je présente mon pfe devant le jury demain", "Soutenance et entretien"), ("henné de ma cousine samedi", "Henné et fiançailles"),
 ("le jour de l'aïd on rend visite à la famille", "Aïd"), ("نمشي للجامع نهار الجمعة", "Vendredi et mosquée"), ("ftour chez ma grand-mère", "Ramadan"),
 ("réunion client à 10h", "Travail et client"), ("enterrement d'un proche", "Condoléances"), ("canicule 40 degrés demain", "Chaleur d'été"),
 ("il va pleuvoir et il fait froid", "Hiver et pluie"), ("week-end à Djerba, plage", "Plage"), ("dîner au restaurant avec des amis", "Sortie et restaurant"),
 ("déjeuner chez la belle-famille", "Visite en famille"), ("match de foot avec les potes", "Sport"), ("cours à l'université toute la journée", "Université et stage")]

if __name__ == "__main__":
    h1 = h3 = 0
    for q, t in GOLD:
        r = [d["title"] for d in retrieve(q, k=3)]; h1 += r[:1] == [t]; h3 += t in r
        print(("OK " if t in r else "RATÉ"), q, "->", r)
    print({"hit@1": round(h1 / len(GOLD), 3), "hit@3": round(h3 / len(GOLD), 3), "n": len(GOLD)})
