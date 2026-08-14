# Imagen del motor y la API. El frontend se construye aparte y se sirve
# estatico, asi que aqui solo va Python.
FROM python:3.13-slim

WORKDIR /app

# Las dependencias van primero para que Docker cachee esta capa: cambiar el
# codigo no obliga a reinstalar numpy y sklearn cada vez.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/
COPY datos/ ./datos/
COPY dashboards/ ./dashboards/

# No correr como root dentro del contenedor.
RUN useradd --create-home --uid 1000 fluenta && chown -R fluenta:fluenta /app
USER fluenta

EXPOSE 8765

# El servidor escucha en 127.0.0.1 por defecto, que dentro de un contenedor
# lo hace inalcanzable. Se sobrescribe por variable de entorno y se deja el
# proxy inverso por delante en produccion.
ENV MC_HOST=0.0.0.0

CMD ["python", "scripts/mission_control_server.py"]
