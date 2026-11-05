"""Conservative relation-typed cohort after the general QuAC strata failed review."""
import re
from quac_teaching import stems, norm, NEG
from sampling import stratum

def cohort(r):
    if stratum(r)=="unanswerable": return None
    for q,a in zip(r["history"][::2],r["history"][1::2]):
        q=q["text"].rsplit("\n\n",1)[-1]
        a=a["text"]
        if not any(re.search(pattern,q,re.I) and re.search(pattern,a,re.I) for pattern in [
                r"\b(?:album|albums)\b",r"\b(?:release|released|releasing)\b",
                r"\b(?:single|singles)\b",r"\b(?:band|group)\b",r"\b(?:record|recorded|recording)\b",
                r"\b(?:won|win|winning)\b",r"\b(?:form|formed|formation)\b",r"\b(?:role|played)\b",
                r"\b(?:copies|copy)\b",r"\b(?:directed|director)\b",r"\b(?:award|awards)\b"]):
            return None
        keys=stems(q)
        if not keys or keys-stems(a):return None
        if not a.endswith((".","!","?",'"')) or len(a.split())>35:return None
        if re.search(r"\b(?:anything|interesting|how well|what happened|successful|influenc\w*)\b",q,re.I):return None
    return "relation-typed"
