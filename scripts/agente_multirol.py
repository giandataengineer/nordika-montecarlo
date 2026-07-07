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

ESQUEMA = """Devuelve exclusivamente JSON valido, sin markdown ni bloques de codigo:
{
  "decision_elegida": "el nombre exacto de una de las decisiones del ranking",
  "headline": "una frase con tu veredicto",
  "summary": "dos o tres frases justificando desde tu angulo",
  "reasons": ["tres razones"],
  "watchouts": ["tres cosas a vigilar"],
  "next_actions": ["tres siguientes pasos"],
  "switch_signals": ["tres senales que te harian cambiar de opinion"],
  "due_diligence": ["tres preguntas antes de ejecutar"]
}

Reglas duras:
- decision_elegida DEBE ser una de las del ranking, copiada literal.
- Puedes elegir una decision distinta a la primera del ranking si tu criterio lo justifica.
- No afirmes que el suelo es positivo si el P10 es negativo.
- No llames robusta a una opcion con probabilidad de perdida alta.
- Cita cifras concretas del ranking cuando sustenten tu argumento.
- Escribe en espanol ejecutivo, sin markdown."""


def _cliente(proveedor: str):
    """Devuelve (cliente, modelo) o None si ese proveedor no tiene clave."""
    cfg = PROVEEDORES[proveedor]
    api_key = os.getenv(cfg["env_key"])
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    modelo = os.getenv(cfg["env_modelo"]) or cfg["modelo"]
    if cfg["base_url"]:
        return OpenAI(api_key=api_key, base_url=cfg["base_url"]), modelo
    return OpenAI(api_key=api_key), modelo


def _proveedor_disponible(preferido: str) -> str | None:
    """El preferido si tiene clave; si no, cualquier otro que la tenga."""
    if os.getenv(PROVEEDORES[preferido]["env_key"]):
        return preferido
    for nombre, cfg in PROVEEDORES.items():
        if os.getenv(cfg["env_key"]):
            return nombre
    return None


def _contexto(ranking: list[dict], uplift: list[dict], avanzado: dict | None) -> str:
    partes = [
        "Ranking de decisiones tras simular los escenarios:",
        json.dumps(ranking, ensure_ascii=False, indent=1),
        "",
        "Uplift contrafactual estimado por los modelos:",
        json.dumps(uplift, ensure_ascii=False, indent=1),
    ]
    if avanzado:
        estab = avanzado.get("estabilidad", {})
        sens = avanzado.get("sensibilidad", {})
        evpi = avanzado.get("valor_informacion", {})
        partes += [
            "",
            "Evidencia adicional sobre la solidez de este ranking:",
            f"- Estabilidad: {estab.get('veredicto', 'no calculada')}",
            f"- Sensibilidad al ruido: {sens.get('veredicto', 'no calculada')}",
            f"- Valor de la informacion perfecta: {evpi.get('lectura', 'no calculado')}",
        ]
    return "\n".join(partes)


def _una_llamada(cliente, modelo: str, cfg: dict, prompt: str, timeout: float) -> dict[str, Any]:
    """Un intento contra un modelo concreto. Lanza si falla."""
    mensajes = [
        {"role": "system", "content": cfg["sistema"]},
        {"role": "user", "content": prompt},
    ]
    # El techo de tokens es lo que agotaba la cuota: Groq limita a 6.000 por
    # minuto y reservar justo 6.000 en una llamada consumia el minuto entero.
    kwargs = {"model": modelo, "messages": mensajes, "temperature": 0.4,
              "timeout": timeout, "max_tokens": 2600}
    try:
        respuesta = cliente.chat.completions.create(**kwargs, response_format={"type": "json_object"})
    except Exception:
        # no todos los proveedores admiten JSON forzado
        respuesta = cliente.chat.completions.create(**kwargs)
    return json.loads(_sin_vallas(respuesta.choices[0].message.content or ""))


def consultar_rol(
    rol: str,
    ranking: list[dict],
    uplift: list[dict],
    avanzado: dict | None = None,
    timeout: float = 45.0,
    ya_usados: set[str] | None = None,
) -> dict[str, Any]:
    """Recorre la cadena de respaldo hasta que un modelo responda.

    Antes bastaba un 429 del proveedor preferido para que el rol cayera al texto
    determinista. Ahora se baja de modelo y de proveedor: con cuatro proveedores
    y su catalogo, un rol tiene decenas de intentos antes de rendirse.
    """
    cfg = ROLES[rol]
    lista = candidatos(rol, ya_usados or set())
    if not lista:
        return {"rol": rol, "fuente": "determinista", "motivo": "sin proveedores disponibles"}

    prompt = (
        f"{_contexto(ranking, uplift, avanzado)}\n\n"
        f"Prioriza {cfg['prioriza']}.\n\n{ESQUEMA}"
    )
    validas = {str(d.get("decision")) for d in ranking}
    intentos: list[str] = []

    for proveedor, modelo in lista:
        par = _cliente(proveedor)
        if par is None:
            continue
        cliente, _ = par
        try:
            datos = _una_llamada(cliente, modelo, cfg, prompt, timeout)
        except Exception as exc:
            nombre = type(exc).__name__
            if "RateLimit" in nombre or "429" in str(exc):
                _enfriar(f"{proveedor}/{modelo}")
            intentos.append(f"{proveedor}/{modelo}: {nombre}")
            continue

        elegida = str(datos.get("decision_elegida", "")).strip()
        if elegida not in validas:
            intentos.append(f"{proveedor}/{modelo}: eligio {elegida!r}, que no esta en el ranking")
            continue

        datos.update({
            "rol": rol, "fuente": "llm", "proveedor": proveedor, "modelo": modelo,
            "intentos_previos": len(intentos),
        })
        return datos

    return {
        "rol": rol,
        "fuente": "determinista",
        "motivo": f"agotados {len(intentos)} modelos de respaldo",
        "intentos": intentos[:6],
    }


def _sin_vallas(texto: str) -> str:
    """Quita razonamiento y vallas de codigo antes de parsear.

    Los modelos con cadena de pensamiento visible (Qwen 3.6, Nemotron) emiten
    bloques <think>...</think> antes del JSON. Sin limpiarlos, json.loads falla
    y el rol cae al camino determinista sin que se sepa por que.
    """
    import re as _re

    # Un <think> sin cerrar significa que el modelo agoto su presupuesto pensando
    # y nunca llego a emitir el JSON. Rescatar el primer "{...}" de ahi dentro
    # produce basura, asi que se marca como truncado y el rol cae al determinista.
    if "<think>" in texto and "</think>" not in texto:
        raise ValueError("respuesta truncada: el modelo no cerro su bloque de razonamiento")
    limpio = _re.sub(r"<think>.*?</think>", "", texto, flags=_re.DOTALL).strip()
    if "```" in limpio:
        bloques = limpio.split("```")
        if len(bloques) > 1:
            limpio = bloques[1]
            if limpio.lstrip().startswith("json"):
                limpio = limpio.lstrip()[4:]
    limpio = limpio.strip()
    # ultimo recurso: quedarse con el primer objeto JSON que aparezca
    if not limpio.startswith("{"):
        i, j = limpio.find("{"), limpio.rfind("}")
        if i != -1 and j > i:
            limpio = limpio[i : j + 1]
    return limpio.strip()


def agregar_lecturas(lecturas: list[dict], ranking: list[dict]) -> dict[str, Any]:
    """Compara las tres decisiones y convierte el (des)acuerdo en informacion.

    El desacuerdo es el dato mas valioso de la pantalla: significa que la eleccion
    depende de que prioriza quien decide, no de los numeros. Coincidencia total
    significa que la conclusion aguanta los tres criterios.
    """
    con_llm = [l for l in lecturas if l.get("fuente") == "llm"]
    elecciones = {l["rol"]: l.get("decision_elegida") for l in con_llm}
    distintas = set(elecciones.values())

    # Lo que descorrelaciona es el MODELO, no el proveedor: dos modelos de
    # familias distintas sobre la misma infraestructura siguen siendo dos
    # opiniones independientes, mientras que el mismo modelo en dos proveedores
    # distintos daria practicamente la misma respuesta.
    modelos = {l.get("modelo") for l in con_llm}
    modelos_independientes = len(modelos) == len(con_llm) and len(con_llm) > 1

    if not con_llm:
        return {
            "modo": "determinista",
            "consenso": None,
            "veredicto": (
                "Sin claves de API configuradas: las tres lecturas salen de plantillas "
                "deterministas contrastadas contra las cifras. Coinciden por construccion, "
                "asi que su acuerdo no aporta informacion."
            ),
            "elecciones": {},
            "roles_con_llm": 0,
        }

    if len(distintas) == 1:
        unica = next(iter(distintas))
        veredicto = (
            f"Los {len(con_llm)} roles coinciden en {unica}. "
            + (
                "Al correr en modelos independientes, la coincidencia es una senal real de robustez."
                if modelos_independientes
                else "Varios roles comparten modelo, asi que la coincidencia vale menos de lo que parece."
            )
        )
        return {
            "modo": "llm",
            "consenso": True,
            "decision_consenso": unica,
            "veredicto": veredicto,
            "elecciones": elecciones,
            "roles_con_llm": len(con_llm),
            "modelos_independientes": modelos_independientes,
        }

    detalle = " · ".join(f"{ROLES[r]['etiqueta']} elige {d}" for r, d in elecciones.items())
    return {
        "modo": "llm",
        "consenso": False,
        "veredicto": (
            f"No hay consenso: {detalle}. La eleccion depende de que se prioriza, "
            "no de los numeros. Esta discrepancia es el hallazgo, no un fallo."
        ),
        "elecciones": elecciones,
        "roles_con_llm": len(con_llm),
        "modelos_independientes": modelos_independientes,
    }


def lecturas_multirol(
    ranking: list[dict],
    uplift: list[dict],
    avanzado: dict | None = None,
) -> dict[str, Any]:
    """Punto de entrada: consulta los tres roles y agrega el resultado."""
    from analitica_avanzada import coherencia_informe

    huella = _huella(ranking, uplift)
    guardado = _leer_cache(huella)
    if guardado is not None:
        return guardado

    lecturas = []
    usados: set[str] = set()
    for i, rol in enumerate(ROLES):
        if i:
            time.sleep(4)  # los free tier limitan por minuto, no solo por dia
        salida = consultar_rol(rol, ranking, uplift, avanzado, ya_usados=usados)
        if salida.get("modelo"):
            usados.add(salida["modelo"])
        if salida.get("fuente") == "llm":
            # el guardarrail se aplica tambien a lo que escribe el modelo
            revisado = coherencia_informe(salida, ranking)
            salida = revisado["informe"]
            salida["coherencia"] = {
                "frases_retiradas": revisado["frases_retiradas"],
                "incidencias": revisado["incidencias"],
            }
        lecturas.append(salida)

    resultado = {
        "lecturas": lecturas,
        "agregacion": agregar_lecturas(lecturas, ranking),
        "proveedores_configurados": [
            nombre for nombre, cfg in PROVEEDORES.items() if os.getenv(cfg["env_key"])
        ],
        "desde_cache": False,
    }
    _escribir_cache(huella, resultado)
    return resultado


def _autocomprobacion() -> None:
    ranking = [
        {"decision": "Ventana conservadora", "expected_profit_usd": 66132, "p10_usd": 56068, "probability_loss": 0.0},
        {"decision": "Arbitraje agresivo", "expected_profit_usd": 63446, "p10_usd": -33868, "probability_loss": 0.356},
    ]

    # sin claves: los tres roles caen al camino determinista y el agregador lo dice
    guardadas = {c["env_key"]: os.environ.pop(c["env_key"], None) for c in PROVEEDORES.values()}
    try:
        res = lecturas_multirol(ranking, [], None)
        assert len(res["lecturas"]) == 3
        assert all(l["fuente"] == "determinista" for l in res["lecturas"])
        assert res["agregacion"]["modo"] == "determinista"
        assert res["agregacion"]["consenso"] is None
        assert "no aporta informacion" in res["agregacion"]["veredicto"]
    finally:
        for k, v in guardadas.items():
            if v is not None:
                os.environ[k] = v

    # consenso con proveedores distintos vale mas que con el mismo
    # mismo modelo en los dos roles: la coincidencia no informa
    iguales = [
        {"rol": "finanzas", "fuente": "llm", "proveedor": "groq", "modelo": "qwen", "decision_elegida": "Ventana conservadora"},
        {"rol": "operacion", "fuente": "llm", "proveedor": "openrouter", "modelo": "qwen", "decision_elegida": "Ventana conservadora"},
    ]
    a = agregar_lecturas(iguales, ranking)
    assert a["consenso"] is True and a["modelos_independientes"] is False
    assert "vale menos" in a["veredicto"]

    # modelos distintos aunque compartan proveedor: la coincidencia si informa
    distintos = [
        {"rol": "finanzas", "fuente": "llm", "proveedor": "groq", "modelo": "qwen", "decision_elegida": "Ventana conservadora"},
        {"rol": "riesgo", "fuente": "llm", "proveedor": "groq", "modelo": "gpt-oss", "decision_elegida": "Ventana conservadora"},
    ]
    b = agregar_lecturas(distintos, ranking)
    assert b["consenso"] is True and b["modelos_independientes"] is True
    assert "senal real de robustez" in b["veredicto"]

    # desacuerdo: es hallazgo, no fallo
    discrepan = [
        {"rol": "finanzas", "fuente": "llm", "proveedor": "groq", "modelo": "qwen", "decision_elegida": "Arbitraje agresivo"},
        {"rol": "riesgo", "fuente": "llm", "proveedor": "groq", "modelo": "gpt-oss", "decision_elegida": "Ventana conservadora"},
    ]
    c = agregar_lecturas(discrepan, ranking)
    assert c["consenso"] is False
    assert "Finanzas elige Arbitraje agresivo" in c["veredicto"]
    assert "Riesgo elige Ventana conservadora" in c["veredicto"]

    print("agente_multirol: todas las comprobaciones pasan")


if __name__ == "__main__":
    _autocomprobacion()
