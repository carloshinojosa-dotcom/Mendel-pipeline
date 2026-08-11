# Mendel · Pipeline (Jorge, Iramar, Michell)

Dashboard estático que se actualiza solo, todos los días, con los deals de HubSpot
de tu equipo. Ya viene precargado con los `owner_id` de Jorge Cervera, Iramar Yeo
y Michell Munayer.

Esta guía asume que **nunca usaste GitHub**. Son ~15-20 minutos, una sola vez.

---

## Paso 1 — Crear cuenta de GitHub (si no tenés)

1. Andá a https://github.com/signup y creá una cuenta gratis.
2. Confirmá tu email.

## Paso 2 — Crear el repositorio

1. Ya adentro de GitHub, click en el botón verde **"New"** (o https://github.com/new).
2. Repository name: `mendel-pipeline` (o el nombre que quieras).
3. Dejalo en **Public** (necesario para que GitHub Pages sea gratis).
4. NO marques "Add a README" (ya tenés uno). Click **Create repository**.

## Paso 3 — Subir estos archivos al repo

La forma más fácil sin usar la terminal:

1. En la página de tu repo recién creado, click en **"uploading an existing file"**
   (o el link que dice eso en la pantalla de bienvenida).
2. Arrastrá **todos** los archivos y carpetas de esta carpeta que te compartí
   (`index.html`, `data/`, `scripts/`, `.github/`, `README.md`) manteniendo la
   misma estructura de carpetas.
   - Importante: GitHub arrastra carpetas completas si las soltás en el área
     de drop; si sube los archivos sueltos sin carpeta, tenés que crear las
     rutas manualmente (`data/quotas.json`, `.github/workflows/update-dashboard.yml`, etc.)
3. Click **Commit changes**.

(Alternativa si te sentís cómodo con la terminal: `git clone` tu repo vacío,
copiá los archivos adentro, `git add . && git commit -m "init" && git push`.)

## Paso 4 — Crear el token de HubSpot

1. En HubSpot: **Configuración (⚙️) → Integraciones → Apps privadas**.
2. Click **Crear una app privada**.
3. Nombre: "Dashboard pipeline" (o lo que quieras).
4. Pestaña **Scopes** → activá (mínimo):
   - `crm.objects.deals.read`
   - `crm.objects.contacts.read`
   - `crm.objects.owners.read`
5. Click **Crear app** → confirmá → te muestra un **token** (empieza con `pat-...`).
   **Copialo ahora**, no se vuelve a mostrar completo después.

## Paso 5 — Guardar el token como secreto en GitHub

1. En tu repo de GitHub: **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `HUBSPOT_TOKEN`
4. Value: pegá el token que copiaste en el Paso 4.
5. **Add secret**.

## Paso 6 — Activar GitHub Pages

1. En tu repo: **Settings → Pages**.
2. En "Build and deployment" → Source: **Deploy from a branch**.
3. Branch: `main` / carpeta `/ (root)` → **Save**.
4. GitHub te va a dar una URL tipo `https://tu-usuario.github.io/mendel-pipeline/`
   (tarda 1-2 min en activarse la primera vez).

## Paso 7 — Correr la actualización por primera vez

1. En tu repo: pestaña **Actions**.
2. Si es la primera vez, puede pedirte "I understand my workflows, enable them" → aceptá.
3. Click en el workflow **"Actualizar dashboard"** (columna izquierda).
4. Click **Run workflow** → **Run workflow** (botón verde).
5. Esperá ~1-2 min, refrescá — debería aparecer un ✅ verde.
6. Entrá a tu URL de Pages del Paso 6. Ya deberías ver deals reales.

A partir de acá, el workflow corre **solo todos los días a las 7am hora CDMX**
(lo podés cambiar editando el `cron` en `.github/workflows/update-dashboard.yml`
— usa hora UTC) y también podés forzarlo manualmente desde Actions cuando quieras.

---

## Ajustes que probablemente quieras hacer

- **Objetivos de venta (quotas):** editá `data/quotas.json` con el objetivo
  real en USD del trimestre para cada persona.
- **Agregar/sacar gente del equipo:** hay que tocar 3 archivos —
  `scripts/fetch_hubspot.py` (diccionario `OWNER_IDS`), `index.html`
  (`OWNER_COLORS` y `OWNER_INITIALS`), y `data/quotas.json`. Pedime el
  `owner_id` de HubSpot de la persona nueva y te armo el diff.
- **Pipeline / etapas distintas:** si tu equipo no usa "MX Sales" / "MX Viajes",
  revisá los IDs en HubSpot → Configuración → Objetos → Negocios → Pipelines,
  y actualizá `PIPELINES` y `STAGE_LABELS` en `scripts/fetch_hubspot.py`.

## Si algo falla

- Pestaña **Actions** de tu repo → click en la corrida fallida (❌) → te muestra
  el error línea por línea (típicamente: token mal copiado o scopes faltantes).
- Si la página dice "No se pudieron cargar los datos": corré el workflow
  manualmente (Paso 7) — puede que `data/deals.json` todavía no exista o esté vacío.
