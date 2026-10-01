#!/usr/bin/env python3
"""Capa de riesgo del timelapse: ¿qué estaciones pueden vaciarse en ~30 min?

Corre en el portátil (venv con timesfm; el modelo no cabe en la e2-micro):
trae de la VM las últimas 96 h a 15 min, pasa TimesFM y sube risk.json al
bucket. La página lo pinta solo si es fresco (<25 min), así que si el portátil
está apagado la capa simplemente desaparece — fallo silencioso por diseño.

Regla validada en analysis/alarm_tuning.md: alarma si q10 <= 0.5 con la
estación no vacía ahora; precisión ~0.25, recall ~0.65; solo 7-20 h local
(de noche la precisión se hunde). El timer ya respeta el horario; aquí se
re-comprueba y fuera de horas se sube la lista vacía para limpiar la página.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

CTX, HSTEP = 384, 2            # 4 días de contexto, paso 2 = +30 min
BUCKET = "gs://cosas-con-datos-en-dbizi-viz/risk.json"
GC = ["gcloud"]
ENV = dict(os.environ, CLOUDSDK_ACTIVE_CONFIG_NAME="dbizi")

SQL = ("COPY (SELECT m.station_id, to_timestamp(floor(extract(epoch FROM m.ts)/900)*900) "
       "AT TIME ZONE 'UTC' AS ts, avg(m.bikes_available) AS bikes "
       "FROM dbizi_measurement m WHERE m.is_installed AND m.ts >= now() - interval '96 hours' "
       "GROUP BY 1,2 ORDER BY 1,2) TO STDOUT CSV HEADER;")


def publish(risk):
    body = json.dumps({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "h_min": 30, "risk": risk}).encode()
    with tempfile.NamedTemporaryFile("wb", suffix=".json") as f:
        f.write(body); f.flush()
        subprocess.run(GC + ["storage", "cp", "-q", "--cache-control=public, max-age=60",
                             f.name, BUCKET], env=ENV, check=True)


hour = datetime.now().astimezone().hour
if not 7 <= hour < 20:
    publish([]); print("fuera de horario: lista vacía"); sys.exit(0)

out = subprocess.run(GC + ["compute", "ssh", "dbizi-vm", "--zone=us-west1-a", "-q", "--",
                           f"sudo docker exec dbizi-postgres-1 psql -U dbizi -d dbizi -c \"{SQL}\""],
                     env=ENV, capture_output=True, text=True, check=True, timeout=240)
df = pd.read_csv(io.StringIO(out.stdout), parse_dates=["ts"])
wide = df.pivot(index="ts", columns="station_id", values="bikes")
wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq="15min")).interpolate(limit=4)
wide = wide.tail(CTX).ffill()
cur = wide.iloc[-1]
cols = [c for c in wide.columns if not wide[c].isna().any() and cur[c] > 0.5]

import torch, timesfm
torch.set_num_threads(4)
model = timesfm.TimesFM3Forecaster.from_pretrained("google/timesfm-3.0-pytorch", device="cpu")
outp = list(model.predict_batch([wide[c].to_numpy(dtype=np.float32) for c in cols],
                                horizon=HSTEP, return_quantiles=True, make_positive=True))
risk = [{"id": str(c), "q10": round(float(o.quantiles[HSTEP - 1, 0]), 1), "bikes": round(float(cur[c]), 1)}
        for c, o in zip(cols, outp) if o.quantiles[HSTEP - 1, 0] <= 0.5]
publish(risk)
print(f"{len(cols)} estaciones evaluadas, {len(risk)} en riesgo: {[r['id'] for r in risk]}")
