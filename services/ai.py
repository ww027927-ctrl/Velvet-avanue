import json
from config import OPENAI_API_KEY, OPENAI_MODEL
from services.shopping import parse_request

def ai_parse_request(text):
    if not OPENAI_API_KEY:
        return parse_request(text),"local"
    try:
        from openai import OpenAI
        client=OpenAI(api_key=OPENAI_API_KEY)
        response=client.responses.create(
            model=OPENAI_MODEL,
            input=f"""Return ONLY JSON with keys category, brand, size, max_price, min_rating, sort.
sort: best_match, cheapest, or highest_rating.
User: {text}"""
        )
        data=json.loads(response.output_text)
        local=parse_request(text)
        for k in ("category","brand","size","max_price","min_rating","sort"):
            if data.get(k) is not None:local[k]=data[k]
        return local,"openai"
    except Exception:
        return parse_request(text),"local-fallback"
