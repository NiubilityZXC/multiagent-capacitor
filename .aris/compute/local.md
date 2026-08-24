# Local CPU Compute Ledger

### env: audit-cap@a99843f6

- how: Python venv at `/home/user/multiagent-capacitor/.venv-audit-cap`
- provider shape: direct local host, CPU-only
- tier: `{cpus: 4, mem_gib: 8, gpus: 0}`
- spec: `/home/user/multiagent-capacitor/.aris/compute/audit-cap-env-spec.json`
- requirements: `/home/user/multiagent-capacitor/requirements-audit-cap.txt`
- status: READY
- validated: 2026-08-20 (tier-1 imports + seeded CPU witness + fresh agent-follows-doc clean)
- weights: none
- gotcha: none recorded

## Build invocation

From `/home/user/multiagent-capacitor`:

```bash
python3 -m venv .venv-audit-cap
.venv-audit-cap/bin/python -m pip install --upgrade pip==24.2 setuptools==72.1.0 wheel==0.44.0
.venv-audit-cap/bin/python -m pip install -r requirements-audit-cap.txt
```

## Validation invocation

Run verbatim from `/home/user/multiagent-capacitor`:

```bash
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMEXPR_NUM_THREADS=4
export PYTHONHASHSEED=0
.venv-audit-cap/bin/python -c 'import numpy,scipy,pandas,h5py,sklearn,pytest; print("IMPORT_OK", numpy.__version__, scipy.__version__, pandas.__version__, h5py.__version__, sklearn.__version__, pytest.__version__)'
.venv-audit-cap/bin/python -c 'import numpy as np; from scipy.linalg import solve; from sklearn.linear_model import Ridge; np.random.seed(20260813); x=np.arange(12,dtype=float).reshape(-1,1); y=2*x.ravel()+1; m=Ridge(alpha=1e-4).fit(x,y); z=solve(np.eye(2),np.array([1.,2.])); print("WITNESS", np.round(m.predict([[12.]])[0],6), z.tolist(), np.__version__)'
```

Expected sentinels:

- `IMPORT_OK 1.26.4 1.11.4 2.2.2 3.11.0 1.5.1 8.3.2`
- witness matches `^WITNESS 24\.99999[0-9] \[1\.0, 2\.0\] 1\.26\.4$`
