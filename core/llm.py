import os
import logging

logger = logging.getLogger(__name__)


def generate_commercial_response(vendeur_context: dict, question: str) -> str | None:
    """Generate a commercial-style, analytical response using an LLM provider.

    Returns the assistant text or None if LLM is not available.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
    if not api_key:
        logger.info('No OPENAI_API_KEY set; skipping LLM call')
        return None

    try:
        import openai
    except Exception:
        logger.exception('OpenAI package not installed')
        return None

    openai.api_key = api_key

    system_prompt = (
        "Vous êtes un assistant commercial pour une plateforme e‑commerce destinée aux vendeurs. "
        "Répondez en français, ton commercial et orienté conversion, clair et concis. "
        "Structurez la réponse en 3 parties courtes: Résumé, Analyse, Recommandations actionnables. "
        "Expliquez brièvement la logique utilisée et proposez 2-4 actions prioritaires. "
        "Ne divulguez pas d'informations sensibles (tokens, clés)."
    )

    # Build context text
    ctx_lines = [f"Boutique: {vendeur_context.get('nom_boutique', 'N/A')}"]
    for k, v in vendeur_context.items():
        if k == 'nom_boutique':
            continue
        ctx_lines.append(f"{k}: {v}")

    user_prompt = (
        "Question: " + question + "\n\n" + "Contexte vendeur:\n" + "\n".join(ctx_lines)
    )

    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
            temperature=0.6,
        )
        text = resp['choices'][0]['message']['content'].strip()
        return text
    except Exception as e:
        logger.exception('LLM call failed: %s', e)
        return None
