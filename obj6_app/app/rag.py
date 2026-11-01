"""RAG léger : base de connaissances locale (usages vestimentaires tunisiens) + récupération TF-IDF (n-grammes de caractères,
robuste au français/arabe/fautes). Les extraits récupérés sont injectés dans le prompt de l'agent. À enrichir par l'équipe."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

KB = [
 dict(title="Mariage", keys="mariage wedding عرس فرح zaffa soirée de mariage cérémonie",
  text="Mariage : tenue élégante et soignée (formalité 3). Hommes : costume ou tenue traditionnelle (jebba). Femmes : robe élégante, kaftan ou tenue traditionnelle ; en général éviter le blanc, réservé à la mariée ; épaules et genoux couverts selon le milieu."),
 dict(title="Henné et fiançailles", keys="henné fiançailles khotba خطوبة حنة",
  text="Henné / fiançailles : tenue traditionnelle festive, couleurs vives acceptées, formalité 3."),
 dict(title="Aïd", keys="aïd aid eid عيد fitr kébir mouton",
  text="Aïd : tenue neuve ou très soignée, tenue traditionnelle appréciée (jebba, kaftan), visites familiales, formalité 2 à 3."),
 dict(title="Vendredi et mosquée", keys="jomaa vendredi mosquée prière صلاة جمعة جامع",
  text="Prière du vendredi / mosquée : tenue propre et couvrante, jebba ou tenue sobre appréciée, formalité 2, chaussures faciles à enlever."),
 dict(title="Ramadan", keys="ramadan ftour iftar tarawih shour رمضان فطور",
  text="Ramadan : en famille ou au ftour, tenue confortable mais soignée (formalité 2) ; pour les tarawih, tenue couvrante et confortable."),
 dict(title="Soutenance et entretien", keys="soutenance entretien interview jury pfe présentation defense recrutement",
  text="Soutenance / entretien d'embauche : tenue formelle (formalité 3), costume ou tailleur, chemise, chaussures de ville, sobriété."),
 dict(title="Travail et client", keys="réunion client meeting bureau travail professionnel rendez-vous direction اجتماع",
  text="Contexte professionnel : réunion client = formalité 3 ; réunion interne ou bureau = formalité 2 (smart casual)."),
 dict(title="Université et stage", keys="cours université faculté esprit stage cours tp amphi campus",
  text="Université / stage : casual soigné à smart casual (formalité 1 à 2), confortable pour la journée."),
 dict(title="Chaleur d'été", keys="chaud canicule été 35 40 degrés soleil sirocco",
  text="Forte chaleur (au-delà de 32 °C) : matières légères, claires et respirantes, éviter vestes et couleurs sombres au soleil, chaussures aérées."),
 dict(title="Hiver et pluie", keys="froid pluie hiver humide orage vent 10 degrés manteau",
  text="Froid et pluie (en dessous de 14 °C) : superposer les couches, veste imperméable, chaussures fermées ; l'humidité rend le froid plus pénétrant."),
 dict(title="Plage", keys="plage mer piscine hammamet djerba sousse vacances baignade",
  text="Plage / piscine / vacances : décontracté léger (formalité 0 à 1) ; se couvrir pour entrer en ville ou au restaurant."),
 dict(title="Sortie et restaurant", keys="soirée café restaurant sortie dîner rendez-vous amis cinéma anniversaire",
  text="Sortie, restaurant, anniversaire : smart casual soigné (formalité 2) ; premier rendez-vous : soigné mais à l'aise."),
 dict(title="Visite en famille", keys="belle-famille famille visite parents grands-parents invitation déjeuner",
  text="Visite en famille / belle-famille : tenue soignée et modeste (formalité 2), éviter le trop décontracté ou voyant."),
 dict(title="Condoléances", keys="condoléances décès enterrement funérailles عزاء جنازة",
  text="Condoléances / enterrement : tenue sobre, couleurs sombres ou neutres, couvrante, sans accessoires voyants (formalité 2 à 3)."),
 dict(title="Sport", keys="sport gym foot football running tennis jogging entraînement basket padel natation",
  text="Sport : tenue technique et confortable (formalité 0), chaussures de sport."),
]
_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
_M = _vec.fit_transform([d["keys"] + " " + d["text"] for d in KB])   # titre + mots-clés + texte
_K = _vec.transform([d["keys"] for d in KB])                           # mots-clés seuls (requêtes courtes)

def retrieve(query: str, k=3, min_sim=0.12):
    q = _vec.transform([query]); sims = np.maximum(linear_kernel(q, _M)[0], linear_kernel(q, _K)[0])
    return [dict(KB[i], sim=round(float(sims[i]), 3)) for i in sims.argsort()[::-1][:k] if sims[i] >= min_sim]
