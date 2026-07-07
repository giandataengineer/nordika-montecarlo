"""Tres lecturas del mismo resultado, cada una con su propio modelo.

El caso base tenia una sola voz repartida en tres plantillas: los tres roles
justificaban siempre la misma decision, asi que la pantalla de "tres angulos"
era decorativa. Aqui cada rol:

- corre en un proveedor distinto, para que no compartan sesgos,
- ve la evidencia con el encuadre que le importa,
- **puede elegir una decision distinta**, que es lo unico que hace informativa
  la comparacion,
- pasa por el guardarrail de coherencia igual que el camino determinista.

Sin claves, cada rol cae al texto determinista y el agregador lo dice.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

# Las lecturas se guardan en disco con la huella del ranking que las produjo.
# Sin esto, cada reconstruccion del payload relanzaba tres llamadas y los
# tier gratuitos se agotan en minutos: el 429 no venia del proveedor, venia
# de consultar lo mismo una y otra vez.
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "lecturas_multirol.json"


def _huella(ranking: list[dict], uplift: list[dict]) -> str:
    crudo = json.dumps([ranking, uplift], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:16]


def _leer_cache(huella: str) -> dict[str, Any] | None:
    try:
        guardado = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if guardado.get("huella") != huella:
        return None
    # solo se reutiliza si al menos un rol llego a hablar con un modelo
    if not any(l.get("fuente") == "llm" for l in guardado.get("resultado", {}).get("lecturas", [])):
        return None
    resultado = guardado["resultado"]
    resultado["desde_cache"] = True
    return resultado


def _escribir_cache(huella: str, resultado: dict[str, Any]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"huella": huella, "resultado": resultado}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Proveedores. Los tres hablan el protocolo de OpenAI, asi que solo cambian
# la clave, la base_url y el modelo por defecto.
# ---------------------------------------------------------------------------
# Los modelos se eligen de FAMILIAS distintas a proposito: si los tres roles
# corrieran sobre el mismo modelo compartirian sesgos y coincidirian siempre,
# que es justo lo que hacia decorativa la pantalla de "tres angulos".
# Reparto comprobado contra las APIs reales en agosto de 2026:
#   Finanzas  -> Groq / Qwen 3.6         (Alibaba)
#   Operacion -> OpenRouter / Nemotron 3   (NVIDIA)
#   Riesgo    -> Gemini / 3.6 Flash        (Google)
# Un proveedor distinto por rol: con dos roles en el mismo se agotaba su limite
# por minuto y los dos caian a la vez. Cerebras queda configurado pero su free
# tier devuelve 402 sin facturacion activada.
PROVEEDORES: dict[str, dict[str, str]] = {
    "groq": {
        "env_key": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "modelo": "qwen/qwen3.6-27b",
        "env_modelo": "GROQ_MODEL",
    },
    "cerebras": {
        "env_key": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "modelo": "gpt-oss-120b",
        "env_modelo": "CEREBRAS_MODEL",
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "modelo": "z-ai/glm-5.2:free",
        "env_modelo": "OPENROUTER_MODEL",
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "modelo": "gemini-3.6-flash",
        "env_modelo": "GEMINI_MODEL",
    },
    # solo los Flash entran en el plan gratuito: el resto del catalogo responde
    # 1113 "insufficient balance" mientras no se recargue la cuenta
    "zai": {
        "env_key": "ZAI_API_KEY",
        "base_url": "https://api.z.ai/api/paas/v4",
        "modelo": "glm-4.5-flash",
        "env_modelo": "ZAI_MODEL",
    },
    "dashscope": {
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "modelo": "qwen-plus",
        "env_modelo": "DASHSCOPE_MODEL",
    },
    "minimax": {
        "env_key": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.io/v1",
        "modelo": "MiniMax-M3",
        "env_modelo": "MINIMAX_MODEL",
    },
    "nvidia": {
        "env_key": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "modelo": "deepseek-ai/deepseek-v3",
        "env_modelo": "NVIDIA_MODEL",
    },
    "moonshot": {
        "env_key": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.ai/v1",
        "modelo": "kimi-k2-turbo-preview",
        "env_modelo": "MOONSHOT_MODEL",
    },
    "mistral": {
        "env_key": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "modelo": "mistral-small-latest",
        "env_modelo": "MISTRAL_MODEL",
    },
    "sambanova": {
        "env_key": "SAMBANOVA_API_KEY",
        "base_url": "https://api.sambanova.ai/v1",
        "modelo": "Meta-Llama-3.3-70B-Instruct",
        "env_modelo": "SAMBANOVA_MODEL",
    },
    "huggingface": {
        "env_key": "HF_TOKEN",
        "base_url": "https://router.huggingface.co/v1",
        "modelo": "meta-llama/Llama-3.3-70B-Instruct",
        "env_modelo": "HF_MODEL",
    },
    "scaleway": {
        "env_key": "SCALEWAY_API_KEY",
        "base_url": "https://api.scaleway.ai/v1",
        "modelo": "llama-3.3-70b-instruct",
        "env_modelo": "SCALEWAY_MODEL",
    },
    # ultimo recurso: si solo hay una clave, los tres roles la comparten y el
    # agregador avisa de que el desacuerdo vale menos
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "",
        "modelo": "gpt-4o-mini",
        "env_modelo": "OPENAI_MODEL",
    },
}

# ---------------------------------------------------------------------------
# Catalogo de respaldo. Comprobado contra las APIs reales en agosto de 2026.
# El orden dentro de cada proveedor va de mas capaz a mas ligero: si el primero
# esta saturado se baja de escalon en vez de rendirse.
# ---------------------------------------------------------------------------
CATALOGO: dict[str, list[str]] = {
    "gemini": [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3-flash-preview",
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    ],
    "groq": [
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-20b",
        "groq/compound",
        "groq/compound-mini",
    ],
    # solo las variantes :free. El catalogo de pago de OpenRouter responde, pero
    # descuenta saldo real de la cuenta y este proyecto no gasta dinero.
    "openrouter": [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "z-ai/glm-5.2:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-nano-9b-v2:free",
        "openai/gpt-oss-20b:free",
        "dots-studio/dots-3-note-preview:free",
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-xs-2.1:free",
        "cohere/north-mini-code:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
    "cerebras": [
        "gpt-oss-120b",
        "gemma-4-31b",
    ],
    # un alias por familia. La API acepta ademas las versiones fechadas
    # (mistral-large-2512, mistral-medium-2604...), pero apuntan al mismo modelo
    # que su -latest: sumarlas inflaria la cuenta de "modelos independientes"
    # con lo que en realidad es una sola opinion repetida.
    "mistral": [
        "mistral-large-latest",
        "mistral-medium-latest",
        "magistral-medium-latest",
        "mistral-small-latest",
        "ministral-14b-latest",
        "magistral-small-latest",
        "ministral-8b-latest",
        "devstral-medium-latest",
        "ministral-3b-latest",
    ],
    "zai": [
        "glm-4.5-flash",
        "glm-4.7-flash",
    ],
    "nvidia": [
        "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia/nemotron-3-super-120b-a12b",
        "deepseek-ai/deepseek-v4-flash-0731",
        "meta/llama-3.1-70b-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "mistralai/mistral-nemotron",
        "stepfun-ai/step-3.7-flash",
        "thinkingmachines/inkling",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "nvidia/nemotron-3-nano-30b-a3b",
        "meta/muse-glimmer-30b",
        "openai/gpt-oss-20b",
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "nvidia/nemotron-mini-4b-instruct",
    ],
}

# Un modelo que acaba de devolver 429 se aparta un rato en vez de reintentarse
# en bucle. Vive en memoria del proceso: no merece persistirse.
_ENFRIANDO: dict[str, float] = {}
_ESPERA_TRAS_429 = 90.0


def _enfriar(clave: str) -> None:
    _ENFRIANDO[clave] = time.time() + _ESPERA_TRAS_429


def _esta_frio(clave: str) -> bool:
    hasta = _ENFRIANDO.get(clave)
    if hasta is None:
        return False
    if time.time() >= hasta:
        _ENFRIANDO.pop(clave, None)
        return False
    return True


def candidatos(rol: str, ya_usados: set[str]) -> list[tuple[str, str]]:
    """Todos los pares (proveedor, modelo) que este rol puede intentar, en orden.

    Cada rol arranca por un proveedor distinto y recorre el resto en rueda, de
    modo que tres roles simultaneos no compitan por la misma cuota. Se prefieren
    los modelos que ningun otro rol haya usado todavia, porque dos roles sobre
    el mismo modelo dejan de ser dos opiniones independientes.
    """
    cfg = ROLES[rol]
    orden = list(PROVEEDORES.keys())
    inicio = cfg["proveedor"]
    if inicio in orden:
        i = orden.index(inicio)
        orden = orden[i:] + orden[:i]

    preferidos: list[tuple[str, str]] = []
    resto: list[tuple[str, str]] = []
    repetidos: list[tuple[str, str]] = []

    for proveedor in orden:
        if not os.getenv(PROVEEDORES[proveedor]["env_key"]):
            continue
        modelos = CATALOGO.get(proveedor) or [PROVEEDORES[proveedor]["modelo"]]
        for modelo in modelos:
            clave = f"{proveedor}/{modelo}"
            if _esta_frio(clave):
                continue
            # un modelo que ya usó otro rol baja al final aunque sea el
            # preferido: dos roles sobre el mismo modelo no son dos opiniones
            if modelo in ya_usados:
                repetidos.append((proveedor, modelo))
            elif proveedor == inicio and modelo == cfg.get("modelo"):
                preferidos.append((proveedor, modelo))
            else:
                resto.append((proveedor, modelo))

    return preferidos + resto + repetidos


ROLES: dict[str, dict[str, Any]] = {
    "finanzas": {
        "etiqueta": "Finanzas",
        "proveedor": "groq",
        "modelo": "qwen/qwen3.6-27b",
        "prioriza": "retorno sobre el capital del activo, payback y defensa ante el comite",
        "sistema": (
            "Eres el director financiero del operador. La bateria es un activo de varios "
            "millones y tu respondes por su retorno. Te importa el margen neto sobre el capital "
            "comprometido, el plazo de recuperacion y poder defender la estrategia ante el comite "
            "de inversiones. Te molesta la dispersion sin justificacion y las apuestas que no "
            "puedes explicar con numeros. No eres el mas prudente ni el mas agresivo: eres el que "
            "tiene que responder por el resultado del anio."
        ),
    },
    "operacion": {
        "etiqueta": "Operacion",
        "proveedor": "openrouter",
        "modelo": "nvidia/nemotron-3-super-120b-a12b:free",
        "prioriza": "vida util del banco, ciclos consumidos y disponibilidad del activo",
        "sistema": (
            "Eres el responsable de operacion del activo. Tu unidad de medida no son los dolares "
            "del mes, son los ciclos equivalentes consumidos y la capacidad que le quedara al banco "
            "dentro de cinco anios. Sabes que el desgaste crece mas que proporcionalmente con la "
            "profundidad de descarga, asi que desconfias de cualquier estrategia que compre ingreso "
            "hoy pagandolo con vida util. Tambien sabes que un activo infrautilizado no amortiza. "
            "Estas dispuesto a discrepar de Finanzas si la opcion mas rentable sobre el papel "
            "compromete la salud del banco."
        ),
    },
    "riesgo": {
        "etiqueta": "Riesgo",
        "proveedor": "gemini",
        "modelo": "gemini-3.6-flash",
        "prioriza": "control del downside, suelo de la distribucion y compromiso con el operador de red",
        "sistema": (
            "Eres el director de riesgos. Tu trabajo no es maximizar el retorno esperado, es evitar "
            "que la compania se lleve un golpe del que no se recupere. Miras el percentil 10 antes "
            "que la media, y la probabilidad de perdida antes que el ROI. Una estrategia con mejor "
            "media pero cola izquierda peligrosa es peor para ti. Vigilas ademas los compromisos "
            "adquiridos con el operador de red: incumplir una reserva comprometida tiene "
            "consecuencias que no aparecen en la cuenta de resultados. Discrepa abiertamente si la "
            "opcion mejor situada en media no es la mas defendible."
        ),
    },
}
