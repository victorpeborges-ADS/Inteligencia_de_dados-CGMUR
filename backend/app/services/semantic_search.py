import re
import math
from sqlalchemy.orm import Session
from app.models import CasoSucesso
from typing import List, Dict, Any

# Common Brazilian Portuguese Stopwords to filter out during indexing/search
PORTUGUESE_STOPWORDS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "sob", "sobre", "atras",
    "e", "ou", "mas", "porem", "todavia", "contudo", "entretanto", "que", "como", "se",
    "com", "para", "como", "em", "ao", "aos", "um", "uma", "me", "seu", "sua", "seus",
    "suas", "este", "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquelas"
}

def clean_and_tokenize(text: str) -> List[str]:
    """
    Cleans text by removing punctuation, converting to lower case, and filtering stopwords.
    """
    text = text.lower()
    # Replace common Portuguese accents
    replacements = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c'
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
        
    words = re.findall(r'\b[a-z]{3,}\b', text) # Only keep words with 3+ characters
    return [w for w in words if w not in PORTUGUESE_STOPWORDS]

def calculate_relevance(query_tokens: List[str], doc_text: str) -> float:
    """
    Computes a simple tf-idf-like relevance score for a document based on term matches.
    """
    if not query_tokens:
        return 0.0
        
    doc_tokens = clean_and_tokenize(doc_text)
    if not doc_tokens:
        return 0.0
        
    score = 0.0
    # Simple term frequency matches
    for qt in query_tokens:
        count = doc_tokens.count(qt)
        if count > 0:
            # Term Frequency scaling (tf)
            tf = 1 + math.log(count)
            score += tf
            
    # Normalize by document length to prevent long documents from dominating
    doc_len_factor = math.sqrt(len(doc_tokens))
    return score / doc_len_factor if doc_len_factor > 0 else 0.0

class SuccessCaseSearchService:
    @staticmethod
    def search(db: Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves success cases ranked by semantic relevance to the search query.
        """
        cases = db.query(CasoSucesso).all()
        query_tokens = clean_and_tokenize(query)
        
        if not query_tokens:
            return [
                {
                    "id": c.id,
                    "municipio": c.municipio_nome or c.municipio,
                    "uf": c.municipio_uf or c.uf,
                    "problema": c.problema_original or c.problema,
                    "solucao": c.solucao_implementada or c.solucao,
                    "resultado": c.resultado_mensuravel or c.resultado,
                    "relevance_score": 0.0,
                }
                for c in cases[:limit]
            ]

        ranked_cases = []
        for c in cases:
            muni_name = c.municipio_nome or c.municipio or ""
            combined_text = " ".join(
                filter(
                    None,
                    [
                        muni_name,
                        c.municipio_uf or c.uf,
                        c.titulo,
                        c.problema_original or c.problema,
                        c.solucao_implementada or c.solucao,
                        c.resultado_mensuravel or c.resultado,
                        c.tipo_intervencao,
                    ],
                )
            )
            score = calculate_relevance(query_tokens, combined_text)

            muni_tokens = clean_and_tokenize(muni_name)
            for mt in muni_tokens:
                if mt in query_tokens:
                    score += 1.5

            if score > 0.0:
                ranked_cases.append(
                    {
                        "id": c.id,
                        "municipio": muni_name,
                        "uf": c.municipio_uf or c.uf,
                        "problema": c.problema_original or c.problema,
                        "solucao": c.solucao_implementada or c.solucao,
                        "resultado": c.resultado_mensuravel or c.resultado,
                        "relevance_score": round(score, 3),
                    }
                )
                
        # Sort by score descending
        ranked_cases.sort(key=lambda x: x["relevance_score"], reverse=True)
        return ranked_cases[:limit]
