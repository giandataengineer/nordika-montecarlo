from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

try:
    from .dashboard_agente_demo import MISSION_DASHBOARD_PATH, STAGES, _build_payload, generate_mission_dashboard
    from .simulacion_montecarlo import (
        DATASET_PATH,
        LIVE_DASHBOARD_PATH,
        LIVE_STATUS_PATH,
        LIVE_STATUS_SCRIPT_PATH,
        N_SIMULATIONS,
        PARAMS_PATH,
        REPORT_PATH,
        ROOT,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
        build_aov_model,
        build_conversion_model,
        estimate_historical_parameters,
        evaluate,
        generate_dataset,
        simulate_decisions,
        summarize,
        write_live_dashboard,
        write_report,
    )
except ImportError:
    from dashboard_agente_demo import MISSION_DASHBOARD_PATH, STAGES, _build_payload, generate_mission_dashboard
    from simulacion_montecarlo import (
        DATASET_PATH,
        LIVE_DASHBOARD_PATH,
        LIVE_STATUS_PATH,
        LIVE_STATUS_SCRIPT_PATH,
        N_SIMULATIONS,
        PARAMS_PATH,
        REPORT_PATH,
        ROOT,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
        build_aov_model,
        build_conversion_model,
        estimate_historical_parameters,
        evaluate,
        generate_dataset,
        simulate_decisions,
        summarize,
        write_live_dashboard,
        write_report,
    )


# Dentro de un contenedor 127.0.0.1 no es alcanzable desde fuera.
# Se deja local por defecto y se abre solo con MC_HOST.
HOST = os.getenv("MC_HOST", "127.0.0.1")
PORT = int(os.getenv("MC_PORT", "8765"))
PROJECT_ROOT = ROOT.parent
LIVE_DASHBOARD_RELATIVE_PATH = f"dashboards/{LIVE_DASHBOARD_PATH.name}"
DEBUG_LOG_PATH = PROJECT_ROOT / "datos" / "mission_control_debug.log"
DEBUG_LOG_LOCK = threading.Lock()


def _debug_log(event: str, **fields: Any) -> None:
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "mission_control_server",
            "event": event,
            **fields,
        }
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with DEBUG_LOG_LOCK:
            with DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:
        pass


@dataclass
class PreparationState:
    df: Any | None = None
    conversion_model: Any | None = None
    aov_model: Any | None = None
    params: Any | None = None
    auc: float | None = None
    ready: bool = False
    preparing: bool = False
    launch_requested: bool = False
    error: str | None = None
    thread: threading.Thread | None = None


@dataclass
class MissionRuntime:
    worker: threading.Thread | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    preparation: PreparationState = field(default_factory=PreparationState)
    completed: bool = False

    def _start_worker_locked(self) -> bool:
        if self.worker is not None and self.worker.is_alive():
            _debug_log("worker_start_skipped", reason="already_running")
            return False
        if not self.preparation.ready:
            _debug_log("worker_start_skipped", reason="preparation_not_ready")
            return False
        self.preparation.launch_requested = False
        _reset_live_status("Lanzando simulacion Monte Carlo.")
        self.worker = threading.Thread(target=self._run_montecarlo_worker, daemon=True)
        self.worker.start()
        _debug_log("worker_started", total_simulations=N_SIMULATIONS)
        return True

    def process_running(self) -> bool:
        with self.lock:
            if self.worker is None:
                return False
            if not self.worker.is_alive():
                self.worker = None
                return False
            return True

    def process_pid(self) -> int | None:
        return None

    def ensure_prepared_async(self) -> None:
        with self.lock:
            prep = self.preparation
            if prep.ready or prep.preparing:
                _debug_log(
                    "prepare_skipped",
                    ready=prep.ready,
                    preparing=prep.preparing,
                    launch_requested=prep.launch_requested,
                )
                return
            prep.preparing = True
            prep.error = None
            prep.thread = threading.Thread(target=self._prepare_assets, daemon=True)
            prep.thread.start()
            _debug_log("prepare_started")

    def _prepare_assets(self) -> None:
        should_launch = False
        started_at = time.perf_counter()
        try:
            df = generate_dataset()
            df.to_csv(DATASET_PATH, index=False, encoding="utf-8")

            conversion_model, auc = build_conversion_model(df)
            aov_model = build_aov_model(df)
            params = estimate_historical_parameters(df, conversion_model, aov_model)
            params.to_csv(PARAMS_PATH, index=False, encoding="utf-8")

            with self.lock:
                self.preparation.df = df
                self.preparation.conversion_model = conversion_model
                self.preparation.aov_model = aov_model
                self.preparation.params = params
                self.preparation.auc = auc
                self.preparation.ready = True
                self.preparation.preparing = False
                self.preparation.error = None
                should_launch = self.preparation.launch_requested and not (
                    self.worker is not None and self.worker.is_alive()
                )
            _debug_log(
                "prepare_completed",
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                rows=int(len(df)),
                launch_requested=should_launch,
                auc=round(float(auc), 4),
            )
        except Exception as exc:
            with self.lock:
                self.preparation.ready = False
                self.preparation.preparing = False
                self.preparation.launch_requested = False
                self.preparation.error = "No se pudo preparar el entorno de simulacion."
            _debug_log(
                "prepare_failed",
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error=str(exc),
            )

        if should_launch:
            with self.lock:
                self._start_worker_locked()

    def start_montecarlo(self) -> dict[str, Any]:
        with self.lock:
            if self.completed:
                _debug_log("montecarlo_launch", status="completed", already_running=False)
                return {"status": "completed", "already_running": False, "pid": None}

        self.ensure_prepared_async()
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                self.preparation.launch_requested = False
                _debug_log("montecarlo_launch", status="running", already_running=True)
                return {"status": "running", "already_running": True, "pid": None}
            if not self.preparation.ready:
                self.preparation.launch_requested = True
                _reset_live_status("Precalculando dataset y modelos para lanzar Monte Carlo.")
                _debug_log(
                    "montecarlo_launch",
                    status="preparing",
                    already_running=False,
                    preparation_error=self.preparation.error,
                )
                return {
                    "status": "preparing",
                    "already_running": False,
                    "pid": None,
                    "preparing": True,
                    "error": self.preparation.error,
                }

            self._start_worker_locked()
            _debug_log("montecarlo_launch", status="running", already_running=False)
            return {"status": "running", "already_running": False, "pid": None}

    def _run_montecarlo_worker(self) -> None:
        started_at = time.perf_counter()
        with self.lock:
            df = self.preparation.df
            conversion_model = self.preparation.conversion_model
            aov_model = self.preparation.aov_model
            params = self.preparation.params
            auc = float(self.preparation.auc or 0.0)

        if df is None or conversion_model is None or aov_model is None or params is None:
            _debug_log("worker_missing_assets")
            _write_preparing_status(
                current_simulation=0,
                total_simulations=N_SIMULATIONS,
                message="Preparacion incompleta. Reintentando precalculo.",
            )
            with self.lock:
                self.preparation.launch_requested = True
            self.ensure_prepared_async()
            return

        try:
            write_live_dashboard(0, N_SIMULATIONS, [], LIVE_DASHBOARD_PATH, LIVE_STATUS_PATH, LIVE_STATUS_SCRIPT_PATH)
            progress_callback = lambda current, total, results: write_live_dashboard(
                current,
                total,
                results,
                LIVE_DASHBOARD_PATH,
                LIVE_STATUS_PATH,
                LIVE_STATUS_SCRIPT_PATH,
            )

            simulations = simulate_decisions(
                df,
                conversion_model,
                aov_model,
                n_simulations=N_SIMULATIONS,
                progress_every=40,
                progress_callback=progress_callback,
                pacing_total_seconds=40.0,
            )
            simulations.to_csv(SIMULATIONS_PATH, index=False, encoding="utf-8")

            summary = summarize(simulations)
            summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8")

            passed, checks = evaluate(df, params, summary, auc)
            write_report(df, params, summary, auc, checks)
            write_live_dashboard(
                N_SIMULATIONS,
                N_SIMULATIONS,
                simulations.to_dict(orient="records"),
                LIVE_DASHBOARD_PATH,
                LIVE_STATUS_PATH,
                LIVE_STATUS_SCRIPT_PATH,
            )
            with self.lock:
                self.completed = True
            _invalidate_payload_cache()

            _debug_log(
                "worker_completed",
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                rows=int(len(simulations)),
                passed=passed,
            )
        except Exception as exc:
            _debug_log(
                "worker_failed",
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error=str(exc),
            )
            raise

    def reset_montecarlo(self) -> None:
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                # no se interrumpe una corrida en curso, solo se limpia el
                # resultado de la anterior para permitir relanzar despues.
                return
            self.worker = None
            self.completed = False
        _reset_live_status("Esperando lanzamiento.")
        _invalidate_payload_cache()
        _debug_log("montecarlo_reset")

    def preparation_info(self) -> dict[str, Any]:
        with self.lock:
            return {
                "ready": self.preparation.ready,
                "preparing": self.preparation.preparing,
                "error": self.preparation.error,
            }


RUNTIME = MissionRuntime()

# _build_payload() re-entrena ambos modelos de ML desde cero cada vez que se
# llama (reentrenar cuesta segundos, y antes se llamaba en cada cambio de
# fase). El payload solo cambia de verdad cuando termina una simulacion
# nueva, asi que se cachea aca y se invalida explicitamente en ese momento.
_payload_cache: dict[str, Any] | None = None
_payload_cache_lock = threading.Lock()


def _invalidate_payload_cache() -> None:
    global _payload_cache
    with _payload_cache_lock:
        _payload_cache = None


def _write_preparing_status(current_simulation: int, total_simulations: int, message: str) -> None:
    status = {
        "current_simulation": current_simulation,
        "total_simulations": total_simulations,
        "progress_pct": round(current_simulation / max(1, total_simulations) * 100, 2),
        "is_running": False,
        "leaderboard": [],
        "recent_runs": [],
        "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
        "phase": "preparing",
        "status_message": message,
    }
    LIVE_STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    LIVE_STATUS_SCRIPT_PATH.write_text(
        "window.__MONTECARLO_STATUS__ = " + json.dumps(status, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    _debug_log(
        "live_status_written",
        current_simulation=current_simulation,
        total_simulations=total_simulations,
        progress_pct=status["progress_pct"],
        phase=status["phase"],
        status_message=message,
    )


def _reset_live_status(message: str = "Esperando lanzamiento.") -> None:
    _write_preparing_status(0, N_SIMULATIONS, message)


def _read_live_status() -> dict[str, Any]:
    if LIVE_STATUS_PATH.exists():
        try:
            raw = LIVE_STATUS_PATH.read_text(encoding="utf-8").strip()
            if raw:
                return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {
        "current_simulation": 0,
        "total_simulations": N_SIMULATIONS,
        "progress_pct": 0.0,
        "is_running": False,
        "leaderboard": [],
        "recent_runs": [],
        "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
        "phase": "idle",
        "status_message": "Esperando lanzamiento.",
    }


def _safe_payload() -> dict[str, Any]:
    global _payload_cache

    with _payload_cache_lock:
        if _payload_cache is not None:
            return _payload_cache

    started_at = time.perf_counter()
    try:
        payload = _build_payload()
        _debug_log("payload_built", duration_ms=round((time.perf_counter() - started_at) * 1000, 2))
        with _payload_cache_lock:
            _payload_cache = payload
        return payload
    except FileNotFoundError:
        RUNTIME.ensure_prepared_async()
        prep = RUNTIME.preparation_info()
        _debug_log(
            "payload_missing_files",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            preparation_ready=prep["ready"],
            preparation_error=prep["error"],
        )
        if not prep["ready"]:
            raise
        payload = _build_payload()
        _debug_log("payload_built_after_prepare", duration_ms=round((time.perf_counter() - started_at) * 1000, 2))
        return payload
    except Exception as exc:
        _debug_log("payload_failed", duration_ms=round((time.perf_counter() - started_at) * 1000, 2), error=str(exc))
        raise


def _stage_definition(stage_key: str) -> dict[str, Any]:
    for stage in STAGES:
        if stage["key"] == stage_key:
            return stage
    raise KeyError(stage_key)


def _stage_response(stage_key: str) -> dict[str, Any]:
    stage = _stage_definition(stage_key)

    if stage_key == "briefing":
        payload = _safe_payload()
        return {
            "stage": stage_key,
            "status": "ok",
            "delay_ms": stage["duration_ms"],
            "payload": payload,
            "logs": [
                "> aplicacion inicializada correctamente",
                "> backend conectado y payload sincronizado",
                "> entorno listo para recorrer el analisis completo",
            ],
        }

    if stage_key == "ingesta":
        payload = _safe_payload()
        summary = payload["dataset"]["summary"]
        return {
            "stage": stage_key,
            "status": "ok",
            "delay_ms": stage["duration_ms"],
            "payload": payload,
            "logs": [
                "> cargando base historica del caso",
                f"> registros disponibles: {summary['rows']:,}",
                f"> periodo cubierto: {summary['period_start']} -> {summary['period_end']}",
                f"> conversion observada: {summary['conversion_rate']:.1%}",
            ],
        }

    if stage_key == "uplift":
        payload = _safe_payload()
        uplift = payload["uplift"]["main"]
        return {
            "stage": stage_key,
            "status": "ok",
            "delay_ms": stage["duration_ms"],
            "payload": payload,
            "logs": [
                "> ejecutando los modelos de evaluacion",
                *[
                    f"> {row['label']}: conversion esperada {row['scenario_conversion']:.1%}"
                    for row in uplift
                ],
            ],
        }

    if stage_key == "montecarlo":
        launch = RUNTIME.start_montecarlo()
        status = _read_live_status()
        prep = RUNTIME.preparation_info()
        logs = ["> activando simulacion Monte Carlo"]
        if launch["status"] == "preparing":
            logs.extend(
                [
                    "> precalculando dataset y modelos en memoria",
                    "> el panel live se activara en cuanto arranque la simulacion real",
                ]
            )
        elif launch["status"] == "completed":
            logs.extend(
                [
                    "> simulacion ya ejecutada en esta sesion",
                    "> mostrando los 10.000 escenarios calculados previamente",
                ]
            )
        else:
            logs.extend(
                [
                    "> simulacion lanzada correctamente",
                    "> objetivo: 10.000 escenarios en 40 segundos",
                ]
            )
        return {
            "stage": stage_key,
            "status": launch["status"],
            "delay_ms": 1,
            "payload": None,
            "logs": logs,
            "live_dashboard": f"dashboards/{LIVE_DASHBOARD_PATH.name}",
            "montecarlo": {
                "running": launch["status"] == "running",
                "preparing": launch["status"] == "preparing" or prep["preparing"],
                "pid": None,
                "progress_pct": status.get("progress_pct", 0.0),
                "current_simulation": status.get("current_simulation", 0),
                "total_simulations": status.get("total_simulations", N_SIMULATIONS),
            },
        }

    if stage_key == "reporte":
        payload = _safe_payload()
        recommendation = payload["recommendation"]
        return {
            "stage": stage_key,
            "status": "ok",
            "delay_ms": stage["duration_ms"],
            "payload": payload,
            "logs": [
                "> consolidando el ranking final",
                f"> mejor alternativa: {recommendation['decision']}",
                f"> beneficio esperado: {recommendation['expected_profit_usd']:,.0f} USD",
                "> recomendacion ejecutiva lista para presentacion",
            ],
        }

    payload = _safe_payload()
    return {"stage": stage_key, "status": "unknown", "delay_ms": 800, "payload": payload, "logs": []}


def _montecarlo_status_response() -> dict[str, Any]:
    live_status = _read_live_status()
    prep = RUNTIME.preparation_info()
    running = RUNTIME.process_running() or bool(live_status.get("is_running"))
    preparing = prep["preparing"] and not running
    payload = None
    leader = None

    if running or preparing:
        leaderboard = live_status.get("leaderboard") or []
        leader = leaderboard[0] if leaderboard else None
    else:
        current_simulation = int(live_status.get("current_simulation", 0) or 0)
        total_simulations = int(live_status.get("total_simulations", N_SIMULATIONS) or N_SIMULATIONS)
        if current_simulation >= total_simulations and total_simulations > 0:
            payload = _safe_payload()
            summary = payload["simulation"]["summary"]
            leader = summary[0] if summary else None
        else:
            leaderboard = live_status.get("leaderboard") or []
            leader = leaderboard[0] if leaderboard else None

    return {
        "running": running,
        "preparing": preparing,
        "preparation_ready": prep["ready"],
        "preparation_error": prep["error"],
        "pid": RUNTIME.process_pid(),
        "current_simulation": live_status.get("current_simulation", 0),
        "total_simulations": live_status.get("total_simulations", N_SIMULATIONS),
        "progress_pct": live_status.get("progress_pct", 0.0),
        "is_running": live_status.get("is_running", False),
        "phase": live_status.get("phase", "idle"),
        "status_message": live_status.get("status_message", ""),
        "leader": leader,
        # El leaderboard completo y las ultimas iteraciones son lo que permite
        # que las graficas del panel se muevan con datos reales durante la
        # simulacion, en vez de quedarse quietas hasta el final.
        "leaderboard": live_status.get("leaderboard") or [],
        "recent_runs": live_status.get("recent_runs") or [],
        "live_dashboard": f"dashboards/{LIVE_DASHBOARD_PATH.name}",
        "payload": payload,
        "completed": RUNTIME.completed,
    }


# Unico arbol que el servidor puede entregar. Todo lo demas (.env, scripts/,
# datos/, .venv/) queda fuera del alcance de una peticion HTTP.
# Sin esto, /api/stage lanza 10.000 simulaciones por peticion y encadenar
# reset+stage en bucle deja la maquina al 100 % de CPU indefinidamente, gratis
# para quien ataca. Ventana deslizante en memoria: suficiente para un solo
# proceso, que es como corre esto.
_LIMITE_LOCK = threading.Lock()
_LIMITE_PETICIONES: dict[str, list[float]] = {}
_LIMITE_VENTANA_S = 60.0
_LIMITE_MAX = 8
MAX_CUERPO_BYTES = 64 * 1024


def _supera_limite(ip: str) -> bool:
    # TODO: esto solo vale con un proceso. Con varios workers hay que sacarlo a redis.
    ahora = time.monotonic()
    with _LIMITE_LOCK:
        marcas = [t for t in _LIMITE_PETICIONES.get(ip, []) if ahora - t < _LIMITE_VENTANA_S]
        if len(marcas) >= _LIMITE_MAX:
            _LIMITE_PETICIONES[ip] = marcas
            return True
        marcas.append(ahora)
        _LIMITE_PETICIONES[ip] = marcas
        return False


RUTAS_PUBLICAS = ("/dashboards/", "/assets/")
ARCHIVOS_PUBLICOS = ("/index.html", "/favicon.ico")
EXTENSIONES_PUBLICAS = (".html", ".js", ".css", ".json", ".svg", ".png", ".woff2", ".ico")


def _ruta_publica(ruta: str) -> bool:
    """Decide si una ruta se puede servir como estatico.

    Lista de permitidos, no de bloqueados: una lista negra se queda corta en
    cuanto alguien anade un archivo nuevo a la raiz del proyecto.
    """
    if ".." in ruta or ruta.startswith("/."):
        return False
    if ruta in ARCHIVOS_PUBLICOS:
        return True
    if not ruta.startswith(RUTAS_PUBLICAS):
        return False
    return ruta.endswith(EXTENSIONES_PUBLICAS)


class MissionControlHandler(SimpleHTTPRequestHandler):
    # conexiones colgadas no deben retener un hilo para siempre
    timeout = 15

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def end_headers(self) -> None:
        # servidor local de desarrollo: nunca cachear, para que un refresh
        # normal (o el navegador reusando pestaña) siempre traiga lo ultimo.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        # cabeceras de seguridad: sin estas el navegador adivina tipos MIME y
        # la pagina se puede embeber en un iframe ajeno
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
        )
        super().end_headers()

    @staticmethod
    def _is_client_disconnect(exc: BaseException) -> bool:
        return isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except OSError as exc:
            if not self._is_client_disconnect(exc):
                raise

    def _serve_static(self) -> None:
        try:
            super().do_GET()
        except OSError as exc:
            if not self._is_client_disconnect(exc):
                raise

    def _read_request_json(self) -> dict[str, Any]:
        # Sin techo, un Content-Length enorme bloquea el hilo leyendo en memoria
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        if content_length > MAX_CUERPO_BYTES:
            raise ValueError("cuerpo demasiado grande")
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _log_http(self, method: str, path: str, started_at: float, **fields: Any) -> None:
        _debug_log(
            "http_request",
            method=method,
            path=path,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            **fields,
        )

    def do_GET(self) -> None:
        # self.path puede traer query string (?v=... para cache-busting,
        # ?ts=... del iframe live). Las rutas especiales se comparan sin ella
        # para que nunca se rompan por un parametro de mas.
        route_path = urlsplit(self.path).path

        if route_path in {"/", "/index.html"}:
            started_at = time.perf_counter()
            generate_mission_dashboard(MISSION_DASHBOARD_PATH)
            self.path = "/dashboards/agente_mission_control.html"
            self._serve_static()
            self._log_http("GET", "/", started_at, static_asset=self.path)
            return

        if route_path == "/api/payload":
            started_at = time.perf_counter()
            payload = _safe_payload()
            self._send_json({"status": "ok", "payload": payload})
            self._log_http("GET", self.path, started_at, payload_keys=list(payload.keys()))
            return

        if route_path == "/api/montecarlo-status":
            started_at = time.perf_counter()
            status = _montecarlo_status_response()
            self._send_json({"status": "ok", **status})
            self._log_http(
                "GET",
                self.path,
                started_at,
                running=status["running"],
                preparing=status["preparing"],
                progress_pct=status["progress_pct"],
                payload_present=status["payload"] is not None,
                leader=status["leader"]["decision"] if status["leader"] else None,
            )
            return

        started_at = time.perf_counter()
        path = self.path
        if not _ruta_publica(route_path):
            self.send_error(HTTPStatus.NOT_FOUND)
            self._log_http("GET", path, started_at, bloqueado=True)
            return
        self._serve_static()
        if path.endswith("dashboard_live_montecarlo.html") or path.endswith("estado_live_montecarlo.js") or path.endswith("agente_mission_control.html"):
            self._log_http("GET", path, started_at, static_asset=True)
        return

    def do_POST(self) -> None:
        # una sola puerta para los tres POST: limite de tasa y cuerpo valido
        if _supera_limite(self.client_address[0]):
            self._send_json(
                {"status": "error", "error": "Demasiadas solicitudes"},
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return
        try:
            cuerpo = self._read_request_json()
        except ValueError:
            self._send_json(
                {"status": "error", "error": "Cuerpo invalido o demasiado grande"},
                HTTPStatus.BAD_REQUEST,
            )
            return
        except Exception:
            self._send_json(
                {"status": "error", "error": "JSON invalido"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        if self.path == "/api/stage":
            started_at = time.perf_counter()
            data = cuerpo
            stage = data.get("stage", "briefing")
            try:
                response = _stage_response(stage)
                self._send_json(response)
                self._log_http(
                    "POST",
                    self.path,
                    started_at,
                    stage=stage,
                    stage_status=response.get("status"),
                    payload_present=response.get("payload") is not None,
                )
                return
            except KeyError:
                self._send_json({"status": "error", "error": f"Stage invalido: {stage}"}, HTTPStatus.BAD_REQUEST)
                self._log_http("POST", self.path, started_at, stage=stage, stage_status="invalid")
                return

        if self.path == "/api/montecarlo-reset":
            started_at = time.perf_counter()
            RUNTIME.reset_montecarlo()
            self._send_json({"status": "ok"})
            self._log_http("POST", self.path, started_at)
            return

        if self.path == "/api/debug-log":
            started_at = time.perf_counter()
            data = cuerpo
            if isinstance(data, dict):
                fields = dict(data)
                client_source = fields.pop("source", None)
                client_event = fields.pop("event", None)
                _debug_log("client_event", client_source=client_source, client_event=client_event, **fields)
            else:
                _debug_log("client_event", payload=data)
            self._send_json({"status": "ok"})
            self._log_http("POST", self.path, started_at)
            return

        self._send_json({"status": "error", "error": "Ruta no encontrada"}, HTTPStatus.NOT_FOUND)
        return

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(host: str = HOST, port: int = PORT) -> None:
    os.chdir(PROJECT_ROOT)
    generate_mission_dashboard(MISSION_DASHBOARD_PATH)
    _reset_live_status()
    RUNTIME.ensure_prepared_async()
    server = ThreadingHTTPServer((host, port), MissionControlHandler)
    print(f"Mission Control en http://{host}:{port}")
    print(f"Debug log en {DEBUG_LOG_PATH}")
    _debug_log("server_started", host=host, port=port, cwd=str(PROJECT_ROOT), python=os.sys.executable)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        _debug_log("server_stopped")


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
